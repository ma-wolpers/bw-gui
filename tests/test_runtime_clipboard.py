"""Tests for the text clipboard protocol and its adapters (no real clipboard is touched)."""

from __future__ import annotations

import tkinter

from bw_gui.runtime import MemoryTextClipboard, TkTextClipboard


class _FakeTkWidget:
    """Stands in for a Tk widget so the test never overwrites the user's clipboard."""

    def __init__(self, content: str | None = None) -> None:
        self.content = content

    def clipboard_get(self) -> str:
        if self.content is None:
            raise tkinter.TclError("CLIPBOARD selection doesn't exist")
        return self.content

    def clipboard_clear(self) -> None:
        self.content = ""

    def clipboard_append(self, text: str) -> None:
        self.content = (self.content or "") + text


def test_tk_clipboard_round_trip():
    widget = _FakeTkWidget("alt")
    clipboard = TkTextClipboard(widget)
    clipboard.write_text("neu")
    assert widget.content == "neu"
    assert clipboard.read_text() == "neu"


def test_tk_clipboard_without_text_reads_none():
    assert TkTextClipboard(_FakeTkWidget(None)).read_text() is None


def test_tk_clipboard_normalizes_windows_line_endings():
    assert TkTextClipboard(_FakeTkWidget("a\r\nb\r\n")).read_text() == "a\nb\n"


def test_memory_clipboard_round_trip():
    clipboard = MemoryTextClipboard()
    assert clipboard.read_text() is None
    clipboard.write_text("x")
    assert clipboard.read_text() == "x"
