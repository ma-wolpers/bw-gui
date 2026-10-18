"""Win32 adapter: dark mode for native controls (the only module with this platform knowledge).

Spike (2026-10-18, Windows 11, Tk 8.6/9 via Python 3.14): a ``tk.Scrollbar`` is a native
``ScrollBar`` window and ``winfo_id()`` is its HWND (no child windows). After
``SetWindowTheme(hwnd, "DarkMode_Explorer", NULL)`` the trough measured (23, 23, 23)
instead of (240, 240, 240) right after the next ``update()`` -- no extra redraw call was
needed. Resetting the theme brings the light rendering back. The HWND exists right after
the widget was created (before it is mapped), so the theme can be set at creation.

On other platforms, or when the call fails (old Windows without the dark theme class,
no ``uxtheme``), the functions do nothing and return ``False``; a failure is reported once
per process as a warning.
"""

from __future__ import annotations

import sys
import warnings
from typing import Any

__all__ = ["set_native_dark_mode"]

_DARK_THEME = "DarkMode_Explorer"
_state = {"warned": False, "set_window_theme": None}


def _set_window_theme():
    """Return a configured ``uxtheme.SetWindowTheme`` (cached), or ``None`` if unavailable."""
    if _state["set_window_theme"] is None:
        import ctypes
        from ctypes import wintypes

        function = ctypes.windll.uxtheme.SetWindowTheme
        function.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
        function.restype = ctypes.c_long  # HRESULT
        _state["set_window_theme"] = function
    return _state["set_window_theme"]


def set_native_dark_mode(widget: Any, dark: bool) -> bool:
    """Render the native control behind *widget* dark (``True``) or with the default theme.

    Returns ``True`` when the theme was applied. Light restores the default theme
    (``SetWindowTheme(hwnd, NULL, NULL)``), i.e. exactly the rendering before bw-gui
    touched the control.
    """
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(widget.winfo_id())
        result = _set_window_theme()(hwnd, _DARK_THEME if dark else None, None)
    except Exception as exc:  # noqa: BLE001 - a missing theme API must never break the GUI
        if not _state["warned"]:
            _state["warned"] = True
            warnings.warn(f"bw-gui: native dark mode unavailable ({exc!r})", RuntimeWarning, stacklevel=2)
        return False
    return result == 0
