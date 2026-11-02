"""Gemeinsame Fixtures und Helfer der Multi-Cursor-Tests (echter ``Text``).

Aus ``test_multicursor.py`` ausgelagert (300-Zeilen-Regel); Fixtures werden per Import geteilt."""

from __future__ import annotations

import pytest

from bw_gui.runtime import attach_multicursor, ui
from bw_gui.testing.keys import press_key

CTRL, SHIFT = 0x4, 0x1
BUTTON1 = 0x100


@pytest.fixture
def text(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    top.geometry("500x300+30+30")
    widget = ui.Text(top, undo=True, wrap="word", font=("Courier", 10), width=50, height=10)
    widget.pack(fill="both", expand=True)
    top.update()
    yield widget
    top.destroy()


@pytest.fixture
def mc(text):
    return attach_multicursor(text)


def _load(text, content):
    text.delete("1.0", "end")
    text.insert("1.0", content)
    text.edit_reset()
    text.update()


def _value(text):
    return text.get("1.0", "end-1c")


def _click(text, index, state=CTRL):
    text.see(index)
    x, y, _w, height = text.bbox(index)
    text.event_generate("<ButtonPress-1>", x=x + 1, y=y + height // 2, state=state)
    text.event_generate("<ButtonRelease-1>", x=x + 1, y=y + height // 2, state=state | BUTTON1)
    text.update()


def _drag(text, start, end, state=CTRL):
    x1, y1, _w, h1 = text.bbox(start)
    x2, y2, _w, h2 = text.bbox(end)
    text.event_generate("<ButtonPress-1>", x=x1 + 1, y=y1 + h1 // 2, state=state)
    text.event_generate("<B1-Motion>", x=x2 + 1, y=y2 + h2 // 2, state=state | BUTTON1)
    text.event_generate("<ButtonRelease-1>", x=x2 + 1, y=y2 + h2 // 2, state=state | BUTTON1)
    text.update()


def _type(text, chars):
    for char in chars:
        press_key(text, char, char=char)
    text.update()


def _heads(mc):
    return [region.head for region in mc.regions]


def _three_lines(text, mc):
    """Three carets at the start of the lines ``aaa``, ``bbb``, ``ccc``."""
    _load(text, "aaa\nbbb\nccc\n")
    text.mark_set("insert", "1.0")
    _click(text, "2.0")
    _click(text, "3.0")
