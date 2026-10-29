"""DataGrid — a virtualised, canvas-based table with three regions and two splitters.

Replaces "several ttk.Treeviews kept in sync": one row model, one vertical
position (``top_row``) for all regions, so they cannot drift apart. Only
visible cells exist as canvas items; navigation moves a few persistent items
(selection band, cell cursor, active-column marker). All state changes only
mark a render dirty (:class:`IdleRenderScheduler`); the render itself is a
full visible pass whose unchanged parts cost nothing (:class:`CanvasItemPool`).

The grid binds no keys (principle E): consumers bind their shortcuts on
:attr:`DataGrid.key_widgets` through the keybinding contract.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from ...contracts.events import EventResult
from ...contracts.pointer import Axis, wheel_axis
from ...runtime import bind_click, bind_wheel, ui
from ...runtime import fonts
from ...runtime import widgets as tui
from ...runtime.idle_render import IdleRenderScheduler
from ...theming import ThemeChange, register_theme_listener
from ...theming._theme_manager import get_theme
from ._model import (
    GridColumn,
    GridRow,
    Region,
    RegionLayout,
    TextClipper,
    clamp_offset,
    fully_visible_row_count,
    visible_rows,
)
from ._region import RegionView, RenderState

CellCallback = Callable[[str, "str | None", Region], object]
_WHEEL_ROWS = 3
_WHEEL_PIXELS = 60
_RIGHT_MAX_SHARE = 0.45


class DataGrid:
    """Three-region table (LEFT | SCROLL | RIGHT) with splitters, shared rows and one cursor."""

    def __init__(self, parent: Any, *, on_cell_click: CellCallback | None = None,
                 on_cell_double_click: CellCallback | None = None,
                 on_header_click: Callable[[str], object] | None = None) -> None:
        """Build the grid inside *parent* (pack/grid :attr:`frame` yourself).

        Args:
            parent: Container widget.
            on_cell_click: ``(row_id, column_key | None, region)`` on a body click.
            on_cell_double_click: Same arguments, on a double click.
            on_header_click: ``(column_key)`` on a header click.
        """
        self.frame = tui.Frame(parent)
        self._font = fonts.nametofont("TkDefaultFont")
        line = int(self._font.metrics("linespace"))
        self._row_h, head_h = line + 8, line + 10
        clipper = TextClipper(self._font.measure, int(self._font.measure("W")))
        self._vbar = tui.Scrollbar(self.frame, orient="vertical", command=self._yview, takefocus=False)
        self._vbar.pack(side="right", fill="y")
        self._paned = ui.PanedWindow(self.frame, orient="horizontal", sashwidth=6, bd=0, sashrelief="raised")
        self._paned.pack(side="left", fill="both", expand=True)
        self._scheduler = IdleRenderScheduler(self.frame)
        self.regions: dict[Region, RegionView] = {}
        for region in Region:
            view = RegionView(self._paned, font=self._font, clipper=clipper, row_height=self._row_h,
                              header_height=head_h, on_viewport_change=self._mark_content)
            self._paned.add(view.frame, minsize=60, stretch="always" if region is Region.SCROLL else "never")
            self.regions[region] = view
            self._bind_pointer(region, view)
        self._callbacks = (on_cell_click, on_cell_double_click, on_header_click)
        self._columns: tuple[GridColumn, ...] = ()
        self._rows: tuple[GridRow, ...] = ()
        self._index_by_id: dict[str, int] = {}
        self._top_row = 0
        self._selected_id: str | None = None
        self._cursor_key: str | None = None
        self._sort: tuple[str | None, bool] = (None, True)
        self._scale = 1.0
        self._split_done = False
        self._pending_see: tuple[str, str | None] | None = None
        # Ends with the grid's frame even if a reference keeps the Python object alive.
        register_theme_listener(self._on_theme, owner=self, widget=self.frame)

    # -- data ------------------------------------------------------------------

    def set_columns(self, columns: Sequence[GridColumn]) -> None:
        """Replace the column set (keys must be unique across regions)."""
        self._columns = tuple(columns)
        self._relayout()

    def set_rows(self, rows: Sequence[GridRow]) -> None:
        """Replace rows (already in display order); unchanged visible cells cost nothing."""
        self._rows = tuple(rows)
        self._index_by_id = {row.row_id: index for index, row in enumerate(self._rows)}
        self._top_row = self._clamped_top(self._top_row)
        self._mark_content()

    def set_cursor(self, row_id: str | None, column_key: str | None) -> None:
        """Select row *row_id* (band in all regions) and put the cell cursor/marker on *column_key*."""
        self._selected_id, self._cursor_key = row_id, column_key
        self._mark_markers()

    def set_sort_indicator(self, column_key: str | None, ascending: bool) -> None:
        """Show ▲/▼ in the header of *column_key* (``None`` = no indicator)."""
        self._sort = (column_key, ascending)
        self._mark_content()

    def set_width_scale(self, scale: float) -> None:
        """Scale all column widths at once (global column-width zoom); an unchanged value is a no-op."""
        clamped = max(0.3, min(4.0, float(scale)))
        if clamped == self._scale:
            return
        self._scale = clamped
        self._relayout()

    # -- viewport --------------------------------------------------------------

    def see(self, row_id: str, column_key: str | None = None) -> None:
        """Scroll so that the row (and, if given, the column) is visible.

        Before the grid has its real size (viewport 1×1 right after creation),
        scrolling would be computed against a 1-pixel window; the target is
        then kept and applied on the first render with a real size.
        """
        if not self._has_real_size():
            self._pending_see = (row_id, column_key)
            self._mark_content()
            return
        before = (self._top_row, tuple(view.x_offset for view in self.regions.values()))
        self._apply_see(row_id, column_key)
        if (self._top_row, tuple(view.x_offset for view in self.regions.values())) != before:
            self._mark_content()

    def cell_bbox(self, row_id: str, column_key: str) -> tuple[Any, int, int, int, int] | None:
        """Make the cell visible and return ``(body_widget, x, y, width, height)``, or ``None``.

        Flushes pending renders first, so the returned geometry matches the screen.
        """
        self.see(row_id, column_key)
        self._scheduler.flush_now()
        offset = self._index_by_id.get(row_id, -1) - self._top_row
        for view in self.regions.values():
            box = view.cell_box(column_key, offset) if offset >= 0 else None
            if box is not None:
                return (view.body, *box)
        return None

    def focus(self, column_key: str | None = None) -> None:
        """Give keyboard focus to the body of the region showing *column_key* (default: SCROLL)."""
        self.regions[self.region_of_column(column_key) or Region.SCROLL].body.focus_set()

    def region_of_column(self, column_key: str | None) -> Region | None:
        """Region that contains *column_key*, or ``None``."""
        return next((c.region for c in self._columns if c.key == column_key), None)

    def region_of_widget(self, widget: Any) -> Region | None:
        """Region whose header or body is *widget*, or ``None``."""
        return next((r for r, v in self.regions.items() if widget in (v.body, v.header)), None)

    @property
    def key_widgets(self) -> tuple[Any, ...]:
        """Focusable body canvases; consumers bind keyboard shortcuts on these."""
        return tuple(view.body for view in self.regions.values())

    @property
    def row_ids(self) -> tuple[str, ...]:
        """Row ids in display order."""
        return tuple(row.row_id for row in self._rows)

    def flush_now(self) -> None:
        """Render pending changes immediately (for callers that read geometry right away)."""
        self._scheduler.flush_now()

    # -- internals --------------------------------------------------------------

    def _has_real_size(self) -> bool:
        """Whether every region has received its first real size from a resize event."""
        return all(view.viewport != (1, 1) for view in self.regions.values())

    def _apply_see(self, row_id: str, column_key: str | None) -> None:
        """Adjust ``top_row`` and the region x offsets so the target is visible (no render)."""
        index = self._index_by_id.get(row_id)
        if index is not None:
            fit = fully_visible_row_count(self._body_height(), self._row_h)
            if index < self._top_row:
                self._top_row = index
            elif index >= self._top_row + fit:
                self._top_row = self._clamped_top(index - fit + 1)
        if column_key is not None:
            for view in self.regions.values():
                view.ensure_column_visible(column_key)

    def _relayout(self) -> None:
        """Rebuild every region's layout from the columns and the width scale."""
        for region, view in self.regions.items():
            view.set_layout(RegionLayout([c for c in self._columns if c.region is region], self._scale))
        self._mark_content()

    def _mark_content(self) -> None:
        """Rows, columns, scrolling, zoom, sorting or theme changed: full visible pass next idle."""
        self._scheduler.mark("content", self._render_content)

    def _mark_markers(self) -> None:
        """Only selection/cursor changed: move band, cursor and marker next idle."""
        self._scheduler.mark("markers", self._render_markers)

    def _state(self) -> RenderState:
        """Snapshot of everything the regions draw."""
        height = self._body_height()
        selected = self._index_by_id.get(self._selected_id) if self._selected_id is not None else None
        return RenderState(self._rows, visible_rows(self._top_row, len(self._rows), height, self._row_h),
                           self._top_row, selected, self._cursor_key, self._cursor_key, *self._sort)

    def _render_content(self) -> None:
        """Full visible pass in all regions plus the vertical scrollbar."""
        self._initial_split()
        if self._pending_see is not None and self._has_real_size():
            pending, self._pending_see = self._pending_see, None
            self._apply_see(*pending)
        state, theme = self._state(), get_theme()
        for view in self.regions.values():
            view.render_content(state, theme)
        total = max(1, len(self._rows))
        self._vbar.set(self._top_row / total, min(1.0, (self._top_row + self._body_height() / self._row_h) / total))

    def _render_markers(self) -> None:
        """Move only band, cursor and active-column marker in all regions."""
        state, theme = self._state(), get_theme()
        for view in self.regions.values():
            view.render_markers(state, theme)

    def _initial_split(self) -> None:
        """Once the grid has a width: LEFT/RIGHT get their natural widths (RIGHT at most 45 %)."""
        width = int(self._paned.winfo_width()) if not self._split_done else 0
        if self._split_done or width <= 1 or not self._columns:
            return
        left = self.regions[Region.LEFT].layout.total_width + 4
        right = min(self.regions[Region.RIGHT].layout.total_width + 4, int(width * _RIGHT_MAX_SHARE))
        self._paned.sash_place(0, left, 0)
        self._paned.sash_place(1, max(left + 60, width - right), 0)
        self._split_done = True

    def _body_height(self) -> int:
        """Visible body height (the tallest region body; heights differ only by a scrollbar)."""
        return max(view.viewport[1] for view in self.regions.values())

    def _clamped_top(self, top: int) -> int:
        """Keep *top* so the last page is full."""
        return clamp_offset(top, len(self._rows), fully_visible_row_count(self._body_height(), self._row_h))

    def _yview(self, *args: str) -> None:
        """Vertical scrollbar protocol → ``top_row``."""
        if args and args[0] == "moveto":
            self._top_row = self._clamped_top(int(float(args[1]) * len(self._rows)))
        elif len(args) >= 3:
            page = fully_visible_row_count(self._body_height(), self._row_h)
            self._top_row = self._clamped_top(self._top_row + int(args[1]) * (page if args[2] == "pages" else 1))
        self._mark_content()

    def _bind_pointer(self, region: Region, view: RegionView) -> None:
        """Clicks, double clicks, header clicks and wheel for one region."""
        bind_click(view.body, lambda e, r=region: self._on_body_click(r, e, 0))
        bind_click(view.body, lambda e, r=region: self._on_body_click(r, e, 1), count=2)
        bind_click(view.header, lambda e, v=view: self._on_header_click(v, e))
        bind_wheel(view.body, lambda e, v=view: self._on_wheel(v, e))

    def _on_body_click(self, region: Region, event: Any, which: int) -> EventResult:
        """Translate a body click into ``(row_id, column_key, region)`` and focus the region."""
        view = self.regions[region]
        view.body.focus_set()
        index = self._top_row + int(event.y) // self._row_h
        callback = self._callbacks[which]
        if callback is not None and 0 <= index < len(self._rows):
            callback(self._rows[index].row_id, view.cell_at(event.x), region)
        return EventResult.HANDLED

    def _on_header_click(self, view: RegionView, event: Any) -> EventResult:
        """Report the clicked header's column key."""
        key, callback = view.cell_at(event.x), self._callbacks[2]
        if key is not None and callback is not None:
            callback(key)
        return EventResult.HANDLED

    def _on_wheel(self, view: RegionView, event: Any) -> EventResult:
        """Wheel scrolls rows; Shift+wheel scrolls the region horizontally.

        ``whole_steps`` is positive towards the content end (``wheel_steps``), so it
        is added: wheel down / swipe up shows later rows, like every other surface.
        """
        if wheel_axis(event) is Axis.HORIZONTAL:
            view.scroll_x(event.whole_steps * _WHEEL_PIXELS)
        else:
            self._top_row = self._clamped_top(self._top_row + event.whole_steps * _WHEEL_ROWS)
        self._mark_content()
        return EventResult.HANDLED

    def _on_theme(self, _change: ThemeChange) -> None:
        """Theme switched: re-theme canvas backgrounds; items get new colours on the next render."""
        for view in self.regions.values():
            view.retheme()
        self._mark_content()
