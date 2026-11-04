"""CardBoard — rows × lanes of ordered cards with drag & drop and an insertion line.

Layout, hit testing and navigation are pure (``_layout``/``_navigation``);
this module wires them to Tk: a fixed header canvas with the lane titles, a
scrolling body canvas, pointer gestures, theme changes and idle rendering.

The board binds no keys (principle E, like ``DataGrid``): consumers bind their
shortcuts on :attr:`CardBoard.key_widget` and drive the cursor with
:meth:`CardBoard.move_cursor`. All rules (which card may go where, what a row
means, uniqueness, undo) stay with the consumer -- the board reports gestures
through callbacks and only changes its own cursor.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from ...contracts.events import EventResult
from ...contracts.pointer import CancelReason, ClickEvent, DragEvent, WheelEvent
from ...runtime import bind_click, bind_drag, bind_wheel, fonts, ui
from ...runtime import widgets as tui
from ...runtime.idle_render import IdleRenderScheduler
from ...runtime.widget_events import on_resize
from ...theming import ThemeChange, register_theme_listener
from ...theming._theme_manager import get_theme
from ._layout import BoardLayout, HitKind, TextWrapper, compute_layout, cursor_box, hit_test, slot_at
from ._model import BoardCell, BoardLane, BoardRow, BoardSlot, Cursor, Direction, LaneKind
from ._navigation import neighbor
from ._render import BoardRenderer
from ._text_editor import InlineTextEditor, TextCommit

_EDGE_SCROLL = 18


class CardBoard:
    """Rows × lanes board; build it, pack :attr:`frame`, then feed lanes and rows."""

    def __init__(
        self,
        parent: Any,
        *,
        on_cursor_change: Callable[[Cursor], object] | None = None,
        on_card_activate: Callable[[str], object] | None = None,
        on_add: Callable[[BoardCell], object] | None = None,
        can_drop: Callable[[str, BoardSlot], bool] | None = None,
        on_drop: Callable[[str, BoardSlot], object] | None = None,
        on_text_commit: TextCommit | None = None,
    ) -> None:
        """Build header, body and scrollbar inside *parent*.

        Args:
            parent: Container widget.
            on_cursor_change: New cursor after a click (card key or cell).
            on_card_activate: Card key on a double click.
            on_add: Cell whose "+" box was clicked.
            can_drop: Whether a dragged card may land in a slot; without it every
                ``CARDS`` slot is allowed. No indicator line where it says ``False``.
            on_drop: ``(card_key, slot)`` when a drag is released over an allowed slot.
            on_text_commit: ``(cell, text)`` when an edited ``TEXT`` cell changed.
        """
        self.frame = tui.Frame(parent)
        self._font = fonts.nametofont("TkDefaultFont")
        self._line_h = int(self._font.metrics("linespace"))
        self._head_h = self._line_h + 10
        self._wrapper = TextWrapper(self._font.measure)
        self._header = ui.Canvas(self.frame, height=self._head_h, highlightthickness=0, takefocus=0)
        self._header.pack(side="top", fill="x")
        self._vbar = tui.Scrollbar(self.frame, orient="vertical", command=self._yview, takefocus=False)
        self._vbar.pack(side="right", fill="y")
        self._body = ui.Canvas(self.frame, highlightthickness=0, takefocus=1, yscrollcommand=self._vbar.set,
                               yscrollincrement=self._line_h)  # fmt: skip
        self._body.pack(side="left", fill="both", expand=True)
        self._renderer = BoardRenderer(self._body, self._header, self._font)
        self._editor = InlineTextEditor(self._body, on_commit=on_text_commit, after_close=self._body.focus_set)
        self._scheduler = IdleRenderScheduler(self.frame)
        self._on_cursor_change, self._on_card_activate, self._on_add = on_cursor_change, on_card_activate, on_add
        self._can_drop, self._on_drop = can_drop, on_drop
        self._lanes: tuple[BoardLane, ...] = ()
        self._rows: tuple[BoardRow, ...] = ()
        self._layout: BoardLayout | None = None
        self._cursor: Cursor = None
        self._drag_key: str | None = None
        self._drop: BoardSlot | None = None
        # Drag before click: the drag's press script passes the event on, the click's consumes it.
        bind_drag(self._body, on_start=self._drag_start, on_move=self._drag_move, on_end=self._drag_end,
                  on_cancel=self._drag_cancel, threshold=4, cancel_on_escape=True)  # fmt: skip
        bind_click(self._body, self._on_click)
        bind_click(self._body, self._on_double_click, count=2)
        bind_wheel(self._body, self._on_wheel)
        on_resize(self._body, lambda _event: self._mark_content())
        register_theme_listener(self._on_theme, owner=self, widget=self.frame)

    # -- data and cursor -------------------------------------------------------

    def set_lanes(self, lanes: Sequence[BoardLane]) -> None:
        """Replace the lanes (left to right)."""
        self._lanes = tuple(lanes)
        self._mark_content()

    def set_rows(self, rows: Sequence[BoardRow]) -> None:
        """Replace all rows (top to bottom); card keys must be unique across the board."""
        self._rows = tuple(rows)
        self._mark_content()

    @property
    def cursor(self) -> Cursor:
        """Current cursor (card key, cell or ``None``)."""
        return self._cursor

    def set_cursor(self, cursor: Cursor, *, see: bool = True) -> None:
        """Move the cursor (no callback); optionally scroll it into view."""
        self._cursor = cursor
        if see:
            self.see(cursor)
        self._mark_markers()

    def move_cursor(self, direction: Direction) -> Cursor:
        """Move the cursor one arrow step (stays put at the edge) and return it."""
        layout = self._current_layout()
        target = neighbor(layout, self._cursor, direction) if layout is not None else None
        if target is not None:
            self.set_cursor(target)
        return self._cursor

    def see(self, cursor: Cursor) -> None:
        """Scroll the body so *cursor* is fully visible (if it is on the board)."""
        layout = self._current_layout()
        box = cursor_box(layout, cursor) if layout is not None else None
        if box is None or layout.height <= 0:
            return
        top, view_h = self._body.canvasy(0), max(1, self._body.winfo_height())
        if box[1] < top:
            self._body.yview_moveto(box[1] / layout.height)
        elif box[3] > top + view_h:
            self._body.yview_moveto(max(0.0, box[3] - view_h) / layout.height)

    @property
    def key_widget(self) -> Any:
        """The focusable body canvas: bind the board's shortcuts here."""
        return self._body

    @property
    def editing_cell(self) -> BoardCell | None:
        """``TEXT`` cell whose inline editor is open, else ``None``."""
        return self._editor.cell

    def edit_text(self, cell: BoardCell) -> None:
        """Open the inline editor of a ``TEXT`` cell (no-op for other cells and locked rows)."""
        layout = self._current_layout()
        box = layout.cells.get(cell) if layout is not None else None
        if box is None or box.kind is not LaneKind.TEXT or box.locked:
            return
        row = next(r for r in self._rows if r.key == cell.row_key)
        self._editor.open(cell, box.box, row.texts.get(cell.lane_key, ""), self._line_h)

    def flush_now(self) -> None:
        """Run pending renders immediately (tests, before reading geometry)."""
        self._scheduler.flush_now()

    # -- rendering -------------------------------------------------------------

    def _current_layout(self) -> BoardLayout | None:
        if "content" in self._scheduler.pending or self._layout is None:
            self._scheduler.flush_now()
        return self._layout

    def _mark_content(self) -> None:
        self._scheduler.mark("content", self._render_content)

    def _mark_markers(self) -> None:
        self._scheduler.mark("markers", self._render_markers)

    def _render_content(self) -> None:
        width = self._body.winfo_width()
        width = width if width > 1 else int(self._body.winfo_reqwidth())
        self._layout = compute_layout(self._rows, self._lanes, width, line_height=self._line_h,
                                      wrapper=self._wrapper, badge_width=self._font.measure)  # fmt: skip
        theme = get_theme()
        self._body.configure(background=theme.get("bg_surface", theme["bg_main"]))
        self._renderer.render_content(self._layout, theme, self._head_h)
        self._body.configure(scrollregion=(0, 0, self._layout.width, self._layout.height))
        self._render_markers()

    def _render_markers(self) -> None:
        if self._layout is not None:
            self._renderer.render_markers(self._layout, get_theme(), self._cursor, self._drop)

    def _on_theme(self, _change: ThemeChange) -> None:
        self._mark_content()

    # -- pointer ---------------------------------------------------------------

    def _canvas_point(self, x: float, y: float) -> tuple[float, float]:
        return self._body.canvasx(x), self._body.canvasy(y)

    def _on_click(self, event: ClickEvent) -> EventResult:
        self._body.focus_set()
        layout = self._current_layout()
        if layout is None:
            return EventResult.HANDLED
        hit = hit_test(layout, *self._canvas_point(event.x, event.y))
        if hit.kind is HitKind.ADD and hit.cell is not None:
            self.set_cursor(hit.cell, see=False)
            if self._on_add is not None:
                self._on_add(hit.cell)
        elif hit.kind is HitKind.CARD:
            self._report_cursor(hit.card_key)
        elif hit.kind is HitKind.CELL and hit.cell is not None:
            cell_box = layout.cells[hit.cell]
            target: Cursor = hit.cell if not cell_box.card_keys else self._cursor
            self._report_cursor(target)
            if cell_box.kind is LaneKind.TEXT:
                self.edit_text(hit.cell)
        return EventResult.HANDLED

    def _report_cursor(self, cursor: Cursor) -> None:
        self.set_cursor(cursor, see=False)
        if self._on_cursor_change is not None:
            self._on_cursor_change(cursor)

    def _on_double_click(self, event: ClickEvent) -> EventResult:
        layout = self._current_layout()
        hit = hit_test(layout, *self._canvas_point(event.x, event.y)) if layout is not None else None
        if hit is not None and hit.kind is HitKind.CARD and self._on_card_activate is not None:
            self._on_card_activate(hit.card_key)
        return EventResult.HANDLED

    def _on_wheel(self, event: WheelEvent) -> EventResult:
        self._body.yview_scroll(event.whole_steps * 3, "units")
        return EventResult.HANDLED

    def _yview(self, *args: str) -> None:
        self._body.yview(*args)

    def _drag_start(self, event: DragEvent) -> None:
        layout = self._current_layout()
        if layout is None:
            return
        x = event.start_x_root - self._body.winfo_rootx()
        y = event.start_y_root - self._body.winfo_rooty()
        hit = hit_test(layout, *self._canvas_point(x, y))
        if hit.kind is HitKind.CARD:
            self._drag_key = hit.card_key
            self._report_cursor(hit.card_key)

    def _drag_move(self, event: DragEvent) -> None:
        layout = self._layout
        if self._drag_key is None or layout is None:
            return
        if event.y < _EDGE_SCROLL:
            self._body.yview_scroll(-1, "units")
        elif event.y > self._body.winfo_height() - _EDGE_SCROLL:
            self._body.yview_scroll(1, "units")
        slot = slot_at(layout, *self._canvas_point(event.x, event.y))
        allowed = slot is not None and (self._can_drop is None or self._can_drop(self._drag_key, slot))
        self._drop = slot if allowed else None
        self._mark_markers()

    def _drag_end(self, _event: DragEvent) -> None:
        key, slot = self._drag_key, self._drop
        self._drag_key, self._drop = None, None
        self._mark_markers()
        if key is not None and slot is not None and self._on_drop is not None:
            self._on_drop(key, slot)

    def _drag_cancel(self, _reason: CancelReason) -> None:
        self._drag_key, self._drop = None, None
        self._mark_markers()
