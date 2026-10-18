"""Opt-in live test: the native scrollbar really turns dark on win32 (SCROLLABILITY_CONTRACT).

Run with ``BW_GUI_LIVE_DISPLAY=1 pytest -m live_display tests/live``. It shows a small
topmost window and reads screen pixels of the scrollbar trough, so the window must not be
covered while the test runs. The spike measured (23, 23, 23) dark and (240, 240, 240)
light; the thresholds below leave room for other Windows builds.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

import pytest

from bw_gui.runtime import widgets
from bw_gui.theming import configure_ttk_theme

pytestmark = [
    pytest.mark.live_display,
    pytest.mark.skipif(sys.platform != "win32", reason="win32 only"),
    pytest.mark.skipif(os.environ.get("BW_GUI_LIVE_DISPLAY") != "1", reason="set BW_GUI_LIVE_DISPLAY=1"),
]


def _screen_brightness(x: int, y: int) -> int:
    """Mean of the RGB channels of the screen pixel at (*x*, *y*), read through GDI."""
    import ctypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    dc = user32.GetDC(0)
    try:
        colour = gdi32.GetPixel(dc, x, y)
    finally:
        user32.ReleaseDC(0, dc)
    red, green, blue = colour & 0xFF, (colour >> 8) & 0xFF, (colour >> 16) & 0xFF
    return (red + green + blue) // 3


def _trough_brightness(bar: tk.Scrollbar) -> int:
    """Brightness of a trough pixel below the thumb (the thumb sits at the top).

    Waits briefly before reading: right after mapping, the window manager may not have
    painted the new window yet, and the pixel would still show whatever lies behind it.
    """
    bar.update()
    bar.after(300)
    bar.update()
    return _screen_brightness(bar.winfo_rootx() + bar.winfo_width() // 2, bar.winfo_rooty() + bar.winfo_height() * 4 // 5)


def test_native_scrollbar_follows_dark_and_light_theme(_shared_tk_root):
    """Dark theme -> dark trough; back to a light theme -> light trough again."""
    window = tk.Toplevel(_shared_tk_root)
    window.geometry("120x300+60+60")
    window.attributes("-topmost", True)
    try:
        configure_ttk_theme(window, "mono_day")
        bar = widgets.Scrollbar(window, orient="vertical")
        bar.pack(side="right", fill="y")
        bar.set(0.0, 0.1)
        window.update()
        light_before = _trough_brightness(bar)
        configure_ttk_theme(window, "mono_night")
        dark = _trough_brightness(bar)
        configure_ttk_theme(window, "mono_day")
        light_after = _trough_brightness(bar)
    finally:
        window.destroy()
        configure_ttk_theme(_shared_tk_root, "mono_day")
    assert light_before > 180, light_before
    assert dark < 80, dark
    assert light_after > 180, light_after
