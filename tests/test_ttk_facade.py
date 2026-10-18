"""``bw_gui.runtime.widgets`` is the ttk namespace with the bw-gui scrollbar primitive."""

from __future__ import annotations

from tkinter import ttk

from bw_gui.runtime import widgets
from bw_gui.runtime.scrollbar import Scrollbar


def test_every_public_ttk_name_is_available():
    missing = [name for name in dir(ttk) if not name.startswith("_") and not hasattr(widgets, name)]
    assert missing == []


def test_only_the_scrollbar_is_replaced():
    assert widgets.Scrollbar is Scrollbar
    replaced = [name for name in ttk.__all__ if getattr(widgets, name) is not getattr(ttk, name)]
    assert replaced == ["Scrollbar"]
