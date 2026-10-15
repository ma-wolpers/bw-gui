from __future__ import annotations

from bw_gui.contracts.events import EventResult
from bw_gui.contracts.key_spec import KeySpec
from bw_gui.runtime import ui, widgets
from bw_gui.runtime.widget_keys import WidgetShortcutBinder


class WrappedTextField:
    """Multiline text input wrapper with compact get/set and word-delete shortcuts.

    Content methods and their roles:

    * ``load(value)``: set the *initial* content of an editing session. The undo and
      redo stacks are cleared, so Ctrl+Z can never revert to an empty field.
    * ``set(value)``: replace the content mid-session. The replacement stays undoable.
    * ``get()``: normalized content (surrounding whitespace stripped).
    * ``get_raw()``: the exact content, without any normalization.

    Round trip: for every string ``s``, ``get_raw()`` returns ``s`` after ``load(s)``
    or ``set(s)``. This covers ``\\r``, ``\\r\\n``, NUL, U+2028, emoji, combining
    characters and surrounding whitespace.
    """

    def __getattr__(self, name: str):
        """Delegate unknown widget attributes to the composed frame container."""
        return getattr(self._container, name)

    def __str__(self) -> str:
        """Expose the container Tk widget path when callers stringify masters."""
        return str(self._container)

    def __init__(self, master, *, initial: str = "", height: int = 3):
        self._container = widgets.Frame(master)
        self.text = ui.Text(self._container, wrap="word", height=height, undo=True)
        self.text.pack(fill="both", expand=True)
        # Word delete through the keyboard contract (Shift tolerated like the former Tk
        # <Control-BackSpace>/<Control-Delete>, which also fired with Shift held).
        keys = WidgetShortcutBinder(self.text)
        for notation, handler, binding_id in (
            ("Ctrl+Backspace (tolerate: Shift)", self._on_ctrl_backspace, "bw_gui.wrapped_text.delete_word_left"),
            ("Ctrl+Delete (tolerate: Shift)", self._on_ctrl_delete, "bw_gui.wrapped_text.delete_word_right"),
        ):
            keys.bind(KeySpec.parse(notation), handler, binding_id=binding_id, intent=binding_id, allow_when_text_input=True)
        if initial:
            self.load(initial)

    @staticmethod
    def _left_delete_span(before_cursor: str) -> int:
        """Return chars to delete left of the cursor for Ctrl+Backspace behavior."""
        count = 0
        index = len(before_cursor)
        while index > 0 and before_cursor[index - 1].isspace():
            index -= 1
            count += 1
        while index > 0 and not before_cursor[index - 1].isspace():
            index -= 1
            count += 1
        return count

    @staticmethod
    def _right_delete_span(after_cursor: str) -> int:
        """Return chars to delete right of the cursor for Ctrl+Delete behavior."""
        count = 0
        index = 0
        length = len(after_cursor)
        while index < length and after_cursor[index].isspace():
            index += 1
            count += 1
        while index < length and not after_cursor[index].isspace():
            index += 1
            count += 1
        return count

    def _on_ctrl_backspace(self, _event) -> EventResult:
        """Delete the previous word using editor-like behavior (consumes the key)."""
        before_cursor = self.text.get("1.0", "insert")
        delete_span = self._left_delete_span(before_cursor)
        if delete_span > 0:
            self.text.delete(f"insert-{delete_span}c", "insert")
        return EventResult.HANDLED

    def _on_ctrl_delete(self, _event) -> EventResult:
        """Delete the next word using editor-like behavior (consumes the key)."""
        after_cursor = self.text.get("insert", "end-1c")
        delete_span = self._right_delete_span(after_cursor)
        if delete_span > 0:
            self.text.delete("insert", f"insert+{delete_span}c")
        return EventResult.HANDLED

    def get(self) -> str:
        """Return the normalized content: surrounding whitespace is stripped.

        Use ``get_raw()`` when the text must come back exactly as typed.

        Returns:
            The content with leading and trailing whitespace removed.
        """
        return self.text.get("1.0", "end").strip()

    def get_raw(self) -> str:
        """Return the exact content without any normalization.

        Tk keeps one newline after the last character internally. This method
        excludes exactly that newline (``"end-1c"``) and nothing else: no
        stripping, no line-ending conversion (``\\r``, ``\\r\\n`` and ``\\n`` come
        back as stored) and no Unicode normalization. Emits no events.

        Returns:
            The buffer content. For every ``s`` it equals ``s`` after ``load(s)``
            or ``set(s)``.

        Raises:
            tkinter.TclError: if the widget has been destroyed.
        """
        return self.text.get("1.0", "end-1c")

    def set(self, value: str) -> None:
        """Replace the current content with ``value``; the replacement stays undoable.

        Meant for changes during an editing session (e.g. applying a suggestion).
        The undo/redo stacks and the modified flag are left untouched, so the
        user can take the replacement back with Ctrl+Z. To start an editing
        session use ``load()`` instead.

        Args:
            value: The new content (inserted verbatim).
        """
        self.text.delete("1.0", "end")
        if value:
            self.text.insert("1.0", value)

    def load(self, value: str) -> None:
        """Load the initial content of an editing session; this cannot be undone.

        Replaces the content with ``value``, then clears the undo and redo
        stacks (``edit_reset``), resets the modified flag (``edit_modified(False)``)
        and puts the cursor at the start and scrolls there. Afterwards Ctrl+Z does
        nothing until the user types. Resetting the modified flag can fire Tk's
        ``<<Modified>>`` event, but only if the flag was ``True`` before.

        Args:
            value: The initial content (inserted verbatim).

        Raises:
            tkinter.TclError: if the widget has been destroyed.
        """
        self.set(value)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")

    def bind(self, sequence: str, func, add: str | None = None):  # type: ignore[override]
        """Forward event bindings to the internal text widget for convenience."""
        return self.text.bind(sequence, func, add=add)
