"""Inline editor of the CardBoard: one WrappedTextField placed over a box of the body canvas.

At most one editor is open; opening another commits the open one first. Two modes:

- **Text** (the free text of a ``TEXT``/``CARDS_TEXT`` cell): Ctrl+Enter or losing
  focus commits, Escape cancels. The result is reported only when the text
  changed, so clicking through cells does not create no-op writes.
- **Card** (rename a card, or type a new card into a draft slot): a card text is
  one line -- Enter (or Ctrl+Enter) commits, Escape cancels. An optional
  validator's message appears in a `FieldErrorLabel` below the field and keeps
  the editor open. Losing focus commits a valid text and discards an invalid
  one, so no stale editor is ever left behind. An unchanged rename is not reported.

The board positions the editor (`open`/`move`); the editor knows no layout.
"""

from __future__ import annotations

from typing import Any, Callable

from ...contracts.events import EventResult
from ...contracts.key_spec import KeySpec
from ...runtime import widgets as tui
from ...runtime.widget_events import on_focus_change
from ...runtime.widget_keys import WidgetShortcutBinder
from ..field_error import FieldErrorLabel
from ..wrapped_text_field import WrappedTextField
from ._layout import CARD_PAD_Y, Box
from ._model import BoardSlot, EditTarget

TextDone = Callable[[str], object]
"""Receives the committed text."""

TextValidator = Callable[[str], "str | None"]
"""Error message for a card text, ``None`` to accept it."""

_TEXT_KEYS = (("Ctrl+Enter", "bw_gui.card_board.text_commit"),)
_CARD_KEYS = (("Enter", "bw_gui.card_board.card_commit"), ("Ctrl+Enter", "bw_gui.card_board.card_commit_ctrl"))


class InlineTextEditor:
    """At most one open inline editor on a canvas."""

    def __init__(self, canvas: Any, *, after_close: Callable[[EditTarget], object]) -> None:
        """Bind to the body canvas.

        Args:
            canvas: Canvas the editor is placed on (``create_window``).
            after_close: Called with the edited target after every close (commit or
                cancel), e.g. to drop a draft slot and refocus the board.
        """
        self._canvas = canvas
        self._after_close = after_close
        self._frame: Any = None
        self._field: WrappedTextField | None = None
        self._error: FieldErrorLabel | None = None
        self._window: int | None = None
        self._target: EditTarget | None = None
        self._card = False
        self._line_height = 1
        self._original = ""
        self._validate: TextValidator | None = None
        self._on_done: TextDone | None = None

    @property
    def target(self) -> EditTarget | None:
        """What is being edited, ``None`` when closed."""
        return self._target

    @property
    def error_message(self) -> str:
        """Validation message shown below the field (``""`` when none or closed)."""
        return self._error.message if self._error is not None else ""

    @property
    def field(self) -> WrappedTextField | None:
        """The open text field (tests), ``None`` when closed."""
        return self._field

    def open(
        self,
        target: EditTarget,
        box: Box,
        text: str,
        line_height: int,
        *,
        on_done: TextDone,
        card: bool = False,
        validate: TextValidator | None = None,
    ) -> None:
        """Open over *box* with *text*; an editor already open elsewhere is committed first.

        Args:
            target: What is edited (card key, text cell or draft slot).
            box: Canvas box to cover.
            text: Initial text.
            line_height: Font line height (sizes the field).
            on_done: Receives the committed text (only when it changed; always for a draft).
            card: Card mode (one line, Enter commits, *validate* applies).
            validate: Card mode only: error message for a text, ``None`` to accept.
        """
        self.commit()
        self._card, self._line_height = card, line_height
        x0, y0, x1, y1 = box
        frame = tui.Frame(self._canvas)
        lines = max(1, int((y1 - y0 - 2 * CARD_PAD_Y) // max(1, line_height))) if card else 3
        field = WrappedTextField(frame, height=lines)
        field.pack(fill="both", expand=True)
        field.load(text)
        self._error = FieldErrorLabel(frame, wraplength=int(x1 - x0 - 8), padx=4, pady=(2, 4))
        self._window = self._canvas.create_window(x0 + 2, y0 + 2, window=frame, anchor="nw", **self._geometry(box))
        keys = WidgetShortcutBinder(field.text)
        bindings = (*(_CARD_KEYS if card else _TEXT_KEYS), ("Escape", "bw_gui.card_board.text_cancel"))
        for notation, binding_id in bindings:
            action = self.cancel if notation == "Escape" else self.commit
            keys.bind(KeySpec.parse(notation), lambda _e, act=action: self._key(act), binding_id=binding_id,
                      intent=binding_id, allow_when_text_input=True)  # fmt: skip
        on_focus_change(field.text, on_lost=lambda _change: self.commit(from_focus=True))
        self._frame, self._field, self._target, self._original = frame, field, target, text
        self._validate, self._on_done = validate, on_done
        field.text.focus_set()
        field.text.mark_set("insert", "end")

    def _geometry(self, box: Box) -> dict[str, float]:
        """Window size over *box*: full width; text mode also a fixed height, card mode its natural one."""
        x0, y0, x1, y1 = box
        geometry: dict[str, float] = {"width": x1 - x0 - 4}
        if not self._card:
            geometry["height"] = max(y1 - y0 - 4, 3 * self._line_height + 8)
        return geometry

    def move(self, box: Box) -> None:
        """Follow a re-layout: place the open editor over *box* (no-op when closed)."""
        if self._window is None:
            return
        self._canvas.coords(self._window, box[0] + 2, box[1] + 2)
        self._canvas.itemconfigure(self._window, **self._geometry(box))

    @staticmethod
    def _key(action: Callable[[], None]) -> EventResult:
        action()
        return EventResult.HANDLED

    def commit(self, *, from_focus: bool = False) -> None:
        """Close and report the text (see the module docstring for the rules; no-op when closed).

        Args:
            from_focus: The editor lost the focus -- an invalid card text is
                discarded instead of being shown.
        """
        if self._field is None or self._target is None:
            return
        text = self._field.get()
        is_draft = isinstance(self._target, BoardSlot)
        changed = is_draft or text != self._original.strip()
        if self._card and changed and self._validate is not None:
            error = self._validate(text)
            if error:
                if from_focus:
                    self.cancel()
                elif self._error is not None:
                    self._error.show(error)
                return
        on_done = self._on_done
        self._close()
        if changed and on_done is not None:
            on_done(text)

    def cancel(self) -> None:
        """Close without reporting (no-op when closed)."""
        if self._field is not None:
            self._close()

    def _close(self) -> None:
        frame, window, target = self._frame, self._window, self._target
        self._frame, self._field, self._error, self._window, self._target = None, None, None, None, None
        self._validate, self._on_done = None, None
        if window is not None:
            self._canvas.delete(window)
        if frame is not None:
            frame.destroy()
        if target is not None:
            self._after_close(target)
