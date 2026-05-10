from __future__ import annotations

from bw_gui.runtime import ui, widgets


class WrappedTextField:
    """Multiline text input wrapper with compact get/set and word-delete shortcuts."""

    def __getattr__(self, name: str):
        """Delegate unknown widget attributes to the composed frame container."""
        return getattr(self._container, name)

    def __init__(self, master, *, initial: str = "", height: int = 3):
        self._container = widgets.Frame(master)
        self.text = ui.Text(self._container, wrap="word", height=height, undo=True)
        self.text.pack(fill="both", expand=True)
        self.text.bind("<Control-BackSpace>", self._on_ctrl_backspace, add="+")
        self.text.bind("<Control-Delete>", self._on_ctrl_delete, add="+")
        if initial:
            self.set(initial)

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

    def _on_ctrl_backspace(self, _event):
        """Delete the previous word using editor-like behavior."""
        before_cursor = self.text.get("1.0", "insert")
        delete_span = self._left_delete_span(before_cursor)
        if delete_span > 0:
            self.text.delete(f"insert-{delete_span}c", "insert")
        return "break"

    def _on_ctrl_delete(self, _event):
        """Delete the next word using editor-like behavior."""
        after_cursor = self.text.get("insert", "end-1c")
        delete_span = self._right_delete_span(after_cursor)
        if delete_span > 0:
            self.text.delete("insert", f"insert+{delete_span}c")
        return "break"

    def get(self) -> str:
        """Return normalized content without trailing newline artifacts."""
        return self.text.get("1.0", "end").strip()

    def set(self, value: str) -> None:
        """Replace current text content with ``value``."""
        self.text.delete("1.0", "end")
        if value:
            self.text.insert("1.0", value)

    def bind(self, sequence: str, func, add: str | None = None):  # type: ignore[override]
        """Forward event bindings to the internal text widget for convenience."""
        return self.text.bind(sequence, func, add=add)
