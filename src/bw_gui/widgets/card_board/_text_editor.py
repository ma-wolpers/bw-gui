"""Inline editor for ``TEXT`` cells: a WrappedTextField placed over the cell.

Ctrl+Enter or losing focus commits, Escape cancels. The commit callback runs
only when the text actually changed, so clicking through cells does not create
no-op writes (one consumer write per real change, e.g. one undo step).
"""

from __future__ import annotations

from typing import Any, Callable

from ...contracts.events import EventResult
from ...contracts.key_spec import KeySpec
from ...runtime.widget_events import on_focus_change
from ...runtime.widget_keys import WidgetShortcutBinder
from ..wrapped_text_field import WrappedTextField
from ._layout import Box
from ._model import BoardCell

TextCommit = Callable[[BoardCell, str], object]


class InlineTextEditor:
    """At most one open text editor on a canvas."""

    def __init__(self, canvas: Any, *, on_commit: TextCommit | None, after_close: Callable[[], object]) -> None:
        """Bind to the body canvas.

        Args:
            canvas: Canvas the editor is placed on (``create_window``).
            on_commit: ``(cell, text)`` when a changed text is committed.
            after_close: Called after every close (commit or cancel), e.g. to refocus the board.
        """
        self._canvas = canvas
        self._on_commit = on_commit
        self._after_close = after_close
        self._field: WrappedTextField | None = None
        self._window: int | None = None
        self._cell: BoardCell | None = None
        self._original = ""

    @property
    def cell(self) -> BoardCell | None:
        """The cell being edited, ``None`` when closed."""
        return self._cell

    def open(self, cell: BoardCell, box: Box, text: str, line_height: int) -> None:
        """Open over *box* with *text*; an editor already open elsewhere is committed first."""
        self.commit()
        x0, y0, x1, y1 = box
        field = WrappedTextField(self._canvas, height=3)
        field.load(text)
        height = max(y1 - y0 - 4, 3 * line_height + 8)
        self._window = self._canvas.create_window(x0 + 2, y0 + 2, window=field, anchor="nw",
                                                  width=x1 - x0 - 4, height=height)  # fmt: skip
        keys = WidgetShortcutBinder(field.text)
        for notation, handler, binding_id in (
            ("Ctrl+Enter", lambda _e: self._key(self.commit), "bw_gui.card_board.text_commit"),
            ("Escape", lambda _e: self._key(self.cancel), "bw_gui.card_board.text_cancel"),
        ):
            keys.bind(KeySpec.parse(notation), handler, binding_id=binding_id, intent=binding_id, allow_when_text_input=True)
        on_focus_change(field.text, on_lost=lambda _change: self.commit())
        self._field, self._cell, self._original = field, cell, text
        field.text.focus_set()
        field.text.mark_set("insert", "end")

    @staticmethod
    def _key(action: Callable[[], None]) -> EventResult:
        action()
        return EventResult.HANDLED

    def commit(self) -> None:
        """Close and report the text if it changed (no-op when closed)."""
        if self._field is None or self._cell is None:
            return
        cell, text, changed = self._cell, self._field.get(), self._field.get() != self._original.strip()
        self._close()
        if changed and self._on_commit is not None:
            self._on_commit(cell, text)

    def cancel(self) -> None:
        """Close without reporting (no-op when closed)."""
        if self._field is not None:
            self._close()

    def _close(self) -> None:
        field, window = self._field, self._window
        self._field, self._window, self._cell = None, None, None
        if window is not None:
            self._canvas.delete(window)
        if field is not None:
            field.destroy()
        self._after_close()
