"""Text clipboard behind a protocol (the platform API stays isolated here).

Apps read and write the system clipboard only through ``TextClipboard``:

- ``TkTextClipboard(widget)``: the real clipboard via Tk
  (``clipboard_clear``/``clipboard_append``/``clipboard_get``). An empty or
  non-text clipboard yields ``None`` instead of a ``TclError``; Windows line
  endings become ``"\\n"``.
- ``MemoryTextClipboard``: an in-memory buffer for tests, so a test run never
  overwrites the clipboard of the person sitting at the computer.
"""

from __future__ import annotations

import tkinter
from typing import Protocol


class TextClipboard(Protocol):
    """Read and write plain text in a clipboard."""

    def read_text(self) -> str | None:
        """Current clipboard text, ``None`` when the clipboard holds no text."""
        ...

    def write_text(self, text: str) -> None:
        """Replace the clipboard content with *text*."""
        ...


class TkTextClipboard:
    """``TextClipboard`` over the Tk clipboard (= the system clipboard).

    Args:
        widget: Any Tk widget of the app; Tk ties the clipboard to its display
            (e.g. the main window).
    """

    def __init__(self, widget: tkinter.Misc) -> None:
        self._widget = widget

    def read_text(self) -> str | None:
        """System clipboard text with ``"\\n"`` line endings, or ``None``.

        Returns:
            The text, or ``None`` for an empty or non-text clipboard.
        """
        try:
            return str(self._widget.clipboard_get()).replace("\r\n", "\n")
        except tkinter.TclError:
            return None

    def write_text(self, text: str) -> None:
        """Put *text* into the system clipboard.

        Args:
            text: New content (may be empty).
        """
        self._widget.clipboard_clear()
        self._widget.clipboard_append(text)


class MemoryTextClipboard:
    """``TextClipboard`` kept in memory (tests, headless runs).

    Args:
        text: Initial content; ``None`` = clipboard without text.
    """

    def __init__(self, text: str | None = None) -> None:
        self.text = text

    def read_text(self) -> str | None:
        """Stored text or ``None``."""
        return self.text

    def write_text(self, text: str) -> None:
        """Store *text*.

        Args:
            text: New content.
        """
        self.text = text
