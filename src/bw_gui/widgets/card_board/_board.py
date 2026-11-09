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
from ._layout import BoardLayout, Box, HitKind, TextWrapper, compute_layout, cursor_box, hit_test, slot_at
from ._model import BoardCell, BoardLane, BoardRow, BoardSlot, Cursor, Direction, EditTarget, lane_holds_cards
from ._navigation import neighbor
from ._render import BoardRenderer
from ._text_editor import InlineTextEditor, TextDone, TextValidator

TextCommit = Callable[[BoardCell, str], object]
"""``(cell, text)`` when an edited text cell changed."""

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
        on_row_action: Callable[[str], object] | None = None,
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
            on_row_action: Row key whose action button (``BoardRow.action``) was clicked.
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
        self._editor = InlineTextEditor(self._body, after_close=self._editor_closed)
        self._scheduler = IdleRenderScheduler(self.frame)
        self._on_cursor_change, self._on_card_activate, self._on_add = on_cursor_change, on_card_activate, on_add
        self._can_drop, self._on_drop, self._on_row_action = can_drop, on_drop, on_row_action
        self._on_text_commit = on_text_commit
        self._lanes: tuple[BoardLane, ...] = ()
        self._rows: tuple[BoardRow, ...] = ()
        self._layout: BoardLayout | None = None
        self._cursor: Cursor = None
        self._drag_key: str | None = None
        self._drop: BoardSlot | None = None
        self._draft: BoardSlot | None = None
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
        self._see_box(cursor_box(layout, cursor) if layout is not None else None)

    def _see_box(self, box: Box | None) -> None:
        layout = self._layout
        if box is None or layout is None or layout.height <= 0:
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
    def editing(self) -> EditTarget | None:
        """What the inline editor edits (card key, text cell or draft slot), ``None`` when closed."""
        return self._editor.target

    @property
    def editing_cell(self) -> BoardCell | None:
        """Text cell whose inline editor is open, else ``None``."""
        target = self._editor.target
        return target if isinstance(target, BoardCell) else None

    @property
    def editor(self) -> InlineTextEditor:
        """The inline editor (tests: field, error message, commit/cancel)."""
        return self._editor

    def edit_text(self, cell: BoardCell) -> None:
        """Open the inline editor of a text cell (no-op for other cells and locked rows)."""
        layout = self._current_layout()
        box = layout.cells.get(cell) if layout is not None else None
        if box is None or box.text_box is None or box.locked:
            return
        row = next(r for r in self._rows if r.key == cell.row_key)
        commit = self._on_text_commit
        self._editor.open(cell, box.text_box, row.texts.get(cell.lane_key, ""), self._line_h,
                          on_done=lambda text: commit(cell, text) if commit is not None else None)  # fmt: skip

    def edit_card(
        self, key: str, *, on_done: TextDone, initial: str | None = None, validate: TextValidator | None = None
    ) -> bool:
        """Rename a card in place: an editor over the card (Enter commits, Escape cancels).

        Args:
            key: Card to edit.
            on_done: Receives the new text (only when it differs from *initial*).
            initial: Text to start with (default: the card's text).
            validate: Error message for a text (shown below the field, editor stays open) or ``None``.

        Returns:
            ``False`` when the card is not on the board (nothing opens).
        """
        layout = self._current_layout()
        card = layout.cards.get(key) if layout is not None else None
        if card is None:
            return False
        text = initial if initial is not None else self._card_text(key)
        self._see_box(card.box)
        self._editor.open(key, card.box, text, self._line_h, on_done=on_done, card=True, validate=validate)
        return True

    def draft_card(
        self, slot: BoardSlot, *, on_done: TextDone, initial: str = "", validate: TextValidator | None = None
    ) -> bool:
        """Type a new card at *slot*: space opens there and an editor sits in it (Enter commits).

        The board never adds the card itself -- *on_done* receives the text and the
        consumer updates its rows. Escape or an invalid text on focus loss drops the draft.

        Returns:
            ``False`` for a slot outside a card-holding, unlocked cell (nothing opens).
        """
        layout = self._current_layout()
        cell = layout.cells.get(slot.cell) if layout is not None else None
        if cell is None or not lane_holds_cards(cell.kind) or cell.locked:
            return False
        self._editor.commit()
        self._draft = slot
        self._mark_content()
        layout = self._current_layout()
        if layout is None or layout.draft_box is None:
            self._draft = None
            return False
        self._see_box(layout.draft_box)
        self._editor.open(slot, layout.draft_box, initial, self._line_h, on_done=on_done, card=True, validate=validate)
        return True

    def _card_text(self, key: str) -> str:
        for row in self._rows:
            for cards in row.cards.values():
                for card in cards:
                    if card.key == key:
                        return card.text
        return ""

    def _editor_closed(self, target: EditTarget) -> None:
        if isinstance(target, BoardSlot):
            self._draft = None
            self._mark_content()
        self._body.focus_set()

    def _edit_box(self, layout: BoardLayout, target: EditTarget) -> Box | None:
        """Where the editor of *target* belongs in *layout* (``None``: the target is gone)."""
        if isinstance(target, BoardSlot):
            return layout.draft_box
        if isinstance(target, BoardCell):
            cell = layout.cells.get(target)
            return cell.text_box if cell is not None and not cell.locked else None
        card = layout.cards.get(target)
        return card.box if card is not None else None

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
                                      wrapper=self._wrapper, badge_width=self._font.measure,
                                      draft=self._draft)  # fmt: skip
        theme = get_theme()
        self._body.configure(background=theme.get("bg_surface", theme["bg_main"]))
        self._renderer.render_content(self._layout, theme, self._head_h)
        target = self._editor.target
        if target is not None:  # new rows or width: the open editor follows its target, or closes with it
            box = self._edit_box(self._layout, target)
            if box is None:
                self._editor.cancel()
            else:
                self._editor.move(box)
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
        if hit.kind is HitKind.ROW_ACTION and hit.row_key is not None:
            if self._on_row_action is not None:
                self._on_row_action(hit.row_key)
        elif hit.kind is HitKind.ADD and hit.cell is not None:
            self.set_cursor(hit.cell, see=False)
            if self._on_add is not None:
                self._on_add(hit.cell)
        elif hit.kind is HitKind.CARD:
            self._report_cursor(hit.card_key)
        elif hit.kind is HitKind.TEXT and hit.cell is not None:
            self._report_cursor(hit.cell)
            self.edit_text(hit.cell)
        elif hit.kind is HitKind.CELL and hit.cell is not None:
            cell_box = layout.cells[hit.cell]
            self._report_cursor(hit.cell if not cell_box.card_keys else self._cursor)
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
