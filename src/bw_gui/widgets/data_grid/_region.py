"""One DataGrid region: header canvas, body canvas, optional horizontal scrollbar.

Two render kinds: ``render_content`` (a full "describe what is visible"
pass through :class:`CanvasItemPool`s, so unchanged cells cost no Tk calls)
and ``render_markers`` (only selection band, cell cursor and active-column
marker — one ``coords`` each), so moving the selection never walks the cells. Colours are read from the ambient theme on every pass
(principle A); a theme switch is just another render. The viewport size is
taken from resize events, never queried per render.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from ...runtime import on_resize, ui
from ...runtime import widgets as tui
from ...theming import theme_canvas
from ..canvas_item_pool import CanvasItemPool
from ._model import GridRow, RegionLayout, TextClipper, clamp_offset

_PAD_X = 6
_CURSOR_WIDTH = 2


@dataclass(frozen=True)
class RenderState:
    """What every region needs to draw one frame (shared by all three regions)."""

    rows: Sequence[GridRow]
    visible: range
    top_row: int
    selected_index: int | None
    cursor_key: str | None
    active_key: str | None
    sort_key: str | None
    sort_ascending: bool


class RegionView:
    """Draws the columns of one region and translates pointer positions back to cells."""

    def __init__(self, parent: Any, *, font: Any, clipper: TextClipper, row_height: int, header_height: int,
                 on_viewport_change: Callable[[], None]) -> None:
        """Build the region's widgets inside *parent*.

        Args:
            parent: Container (one pane of the grid's splitter).
            font: Tk font used for all text.
            clipper: Shared text clipper for that font.
            row_height: Body row height in pixels.
            header_height: Header height in pixels.
            on_viewport_change: Called when the visible size changes (grid re-renders).
        """
        self.frame = tui.Frame(parent)
        self.header = ui.Canvas(self.frame, height=header_height, highlightthickness=0, bd=0)
        self.header.pack(side="top", fill="x")
        self.hbar = tui.Scrollbar(self.frame, orient="horizontal", command=self._xview, takefocus=False)
        self.body = ui.Canvas(self.frame, highlightthickness=0, bd=0, takefocus=1)
        self.body.pack(side="top", fill="both", expand=True)
        self._font, self._clipper = font, clipper
        self._row_h, self._head_h = row_height, header_height
        self._on_viewport_change = on_viewport_change
        self.layout = RegionLayout((), 1.0)
        self.x_offset = 0
        self.viewport = (1, 1)
        self._hbar_shown = False
        self._head_bg = CanvasItemPool(self.header, "rectangle")
        self._marker = CanvasItemPool(self.header, "rectangle")
        self._head_text = CanvasItemPool(self.header, "text")
        self._head_line = CanvasItemPool(self.header, "line")
        self._band = CanvasItemPool(self.body, "rectangle")
        self._cells = CanvasItemPool(self.body, "text")
        self._cursor = CanvasItemPool(self.body, "rectangle")
        # Stacking order = creation order: create one hidden item per pool now, bottom to top,
        # so lazily created items later never end up above the wrong layer.
        for pool in (self._head_bg, self._marker, self._head_text, self._head_line, self._band, self._cells, self._cursor):
            _prewarm(pool)
        on_resize(self.body, self._on_resize)
        self.retheme()

    # -- geometry ---------------------------------------------------------------

    def set_layout(self, layout: RegionLayout) -> None:
        """Use *layout* (new columns or width scale) and keep the x offset in range."""
        self.layout = layout
        self.x_offset = clamp_offset(self.x_offset, layout.total_width, self.viewport[0])

    def scroll_x(self, pixels: int) -> bool:
        """Scroll horizontally by *pixels*; return whether the offset changed."""
        new = clamp_offset(self.x_offset + pixels, self.layout.total_width, self.viewport[0])
        changed, self.x_offset = new != self.x_offset, new
        return changed

    def ensure_column_visible(self, key: str) -> None:
        """Adjust the x offset so column *key* is fully visible (as far as it fits)."""
        index = self.layout.index_of(key)
        if index is None:
            return
        x0, x1 = self.layout.span(index)
        width = self.viewport[0]
        if x0 < self.x_offset:
            self.x_offset = x0
        elif x1 > self.x_offset + width:
            self.x_offset = clamp_offset(x1 - width, self.layout.total_width, width)

    def cell_at(self, x: float) -> str | None:
        """Column key under widget x *x* (header or body), or ``None``."""
        index = self.layout.index_at(x + self.x_offset)
        return None if index is None else self.layout.columns[index].key

    def cell_box(self, key: str, row_offset: int) -> tuple[int, int, int, int] | None:
        """Body-widget box ``(x, y, width, height)`` of the cell, or ``None`` if not in this region."""
        index = self.layout.index_of(key)
        if index is None:
            return None
        x0, x1 = self.layout.span(index)
        return x0 - self.x_offset, row_offset * self._row_h, x1 - x0, self._row_h

    # -- rendering --------------------------------------------------------------

    def retheme(self) -> None:
        """Apply the ambient theme to the canvas backgrounds (items follow on the next render)."""
        theme_canvas(self.header)
        theme_canvas(self.body)

    def render_content(self, state: RenderState, theme: Mapping[str, str]) -> None:
        """Full visible pass: header titles/lines and all cell texts (then the markers).

        Needed when rows, columns, scroll offsets, sorting or the theme change.
        *theme* is fetched once per grid render (resolving it is not free).
        """
        columns = self.layout.visible(self.x_offset, self.viewport[0])
        self._render_header(theme, columns, state)
        self._cells.begin()
        for row_index in state.visible:
            y = (row_index - state.top_row) * self._row_h + self._row_h / 2
            cells = state.rows[row_index].cells
            for index in columns:
                column = self.layout.columns[index]
                x0, x1 = (edge - self.x_offset for edge in self.layout.span(index))
                self._place_text(self._cells, column.anchor, x0, x1, y, cells.get(column.key, ""), theme["fg_primary"])
        self._cells.end()
        self._sync_hbar()
        self.render_markers(state, theme)

    def render_markers(self, state: RenderState, theme: Mapping[str, str]) -> None:
        """Only the moving parts: selection band, cell cursor, active-column marker (≤ 3 items).

        Text colours never depend on the selection (the band uses a soft accent
        under unchanged text), so moving the selection never touches cell texts.
        """
        width = self.viewport[0]
        self._band.begin()
        self._cursor.begin()
        self._marker.begin()
        selected = state.selected_index
        if selected is not None and selected in state.visible:
            y0 = (selected - state.top_row) * self._row_h
            self._band.place((0, y0, width, y0 + self._row_h), fill=theme["accent_soft"], outline="")
            box = self.cell_box(state.cursor_key, selected - state.top_row) if state.cursor_key else None
            if box is not None:
                x, y, w, h = box
                inset = _CURSOR_WIDTH / 2
                self._cursor.place((x + inset, y + inset, x + w - inset, y + h - inset),
                                   outline=theme["accent"], width=_CURSOR_WIDTH, fill="")
        index = self.layout.index_of(state.active_key) if state.active_key else None
        if index is not None:
            x0, x1 = (edge - self.x_offset for edge in self.layout.span(index))
            self._marker.place((x0, 0, x1, self._head_h), fill=theme["accent_soft"], outline="")
        for pool in (self._band, self._cursor, self._marker):
            pool.end()

    def _render_header(self, theme: Mapping[str, str], columns: range, state: RenderState) -> None:
        """Header background, titles (+ sort arrow) and separators (the marker is a moving part)."""
        width, height = self.viewport[0], self._head_h
        self._head_bg.begin()
        self._head_bg.place((0, 0, width, height), fill=theme["bg_panel"], outline="")
        self._head_bg.end()
        self._head_text.begin()
        self._head_line.begin()
        for index in columns:
            column = self.layout.columns[index]
            x0, x1 = (edge - self.x_offset for edge in self.layout.span(index))
            title = column.title
            if column.key == state.sort_key:
                title = f"{'▲' if state.sort_ascending else '▼'} {title}"
            self._place_text(self._head_text, column.anchor, x0, x1, height / 2, title, theme["fg_primary"])
            self._head_line.place((x1 - 1, 2, x1 - 1, height - 2), fill=theme["border"])
        self._head_line.place((0, height - 1, width, height - 1), fill=theme["border"])
        self._head_text.end()
        self._head_line.end()

    def _place_text(self, pool: CanvasItemPool, anchor: str, x0: float, x1: float, y: float, text: str, fill: str) -> None:
        """Place clipped *text* left-aligned or centred inside ``[x0, x1)``."""
        clipped = self._clipper.clip(text, int(x1 - x0) - 2 * _PAD_X)
        if anchor == "center":
            pool.place(((x0 + x1) / 2, y), text=clipped, anchor="center", fill=fill, font=self._font)
        else:
            pool.place((x0 + _PAD_X, y), text=clipped, anchor="w", fill=fill, font=self._font)

    def _sync_hbar(self) -> None:
        """Show the horizontal scrollbar only while the content is wider than the viewport."""
        total, width = self.layout.total_width, self.viewport[0]
        needed = total > width
        if needed != self._hbar_shown:
            if needed:
                self.hbar.pack(side="bottom", fill="x", before=self.body)
            else:
                self.hbar.pack_forget()
            self._hbar_shown = needed
        if needed:
            self.hbar.set(self.x_offset / total, (self.x_offset + width) / total)

    def _xview(self, *args: str) -> None:
        """Scrollbar protocol (``moveto f`` / ``scroll n units|pages``) → x offset."""
        if args and args[0] == "moveto":
            target = int(float(args[1]) * self.layout.total_width)
            self.x_offset = clamp_offset(target, self.layout.total_width, self.viewport[0])
        elif len(args) >= 3:
            step = self.viewport[0] if args[2] == "pages" else 40
            self.scroll_x(int(args[1]) * step)
        self._on_viewport_change()

    def _on_resize(self, event: Any) -> None:
        """Remember the new body size and let the grid re-render."""
        self.viewport = (max(1, int(event.width)), max(1, int(event.height)))
        self.x_offset = clamp_offset(self.x_offset, self.layout.total_width, self.viewport[0])
        self._on_viewport_change()


def _prewarm(pool: CanvasItemPool) -> None:
    """Create the pool's first item (hidden) so it fixes the pool's stacking position."""
    pool.begin()
    pool.place((0, 0) if pool.kind == "text" else (0, 0, 0, 0))
    pool.begin()
    pool.end()
