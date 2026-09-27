"""Tests for the bw_gui.testing.background_windows pytest plugin."""

from __future__ import annotations

import os
import sys

import pytest

from bw_gui.runtime import ui
from bw_gui.testing import background_windows


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 foreground handling")
@pytest.mark.skipif(os.environ.get("TK_FOCUS_TESTS") == "1", reason="plugin disabled for focus tests")
def test_mapped_test_window_returns_the_foreground(_shared_tk_root):
    remembered = background_windows._state["hwnd"]
    if not remembered:
        pytest.skip("no foreground window was recorded at session start")
    user32 = background_windows._user32()
    top = ui.Toplevel(_shared_tk_root)
    try:
        top.geometry("120x80+30+30")
        top.update()
        current = user32.GetForegroundWindow()
        assert current == remembered, (hex(current), hex(remembered), hex(int(top.wm_frame(), 16)), hex(int(_shared_tk_root.wm_frame(), 16)))
    finally:
        top.destroy()


def test_plugin_is_a_noop_without_win32(monkeypatch):
    monkeypatch.setattr(background_windows.sys, "platform", "linux")
    assert background_windows._user32() is None
