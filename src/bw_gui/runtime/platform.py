"""Windows-specific platform integration: title bar chrome theming.

On Windows 10 (build 17763+) and Windows 11 the DWM API allows applications to
opt in to a dark or light title bar.  These functions set that attribute so the
window frame matches the active bw_gui theme.

On macOS and Linux all public functions in this module are no-ops — the module
imports cleanly on every platform.
"""

from __future__ import annotations

import sys
import tkinter as tk


def apply_window_chrome_theme(window: tk.Misc, prefer_dark: bool) -> None:
    """Set the Windows title bar and frame to dark or light mode.

    Uses the ``DwmSetWindowAttribute`` API (attributes 20 and 19, tried in that
    order for compatibility with different Windows builds) to toggle the title
    bar color scheme.  Also calls ``_apply_native_menu_theme()`` to synchronize
    the native menu bar color.

    Because Tk sometimes has not yet created the native HWND when this is called
    (e.g. immediately after ``__init__``), the function schedules a second pass
    120 ms later via ``window.after()``.  This is sufficient for all tested
    Windows 10/11 + Python 3.11/3.12 + Tk 8.6 combinations.

    All exceptions are silently swallowed so that non-Windows environments,
    missing DLL exports, or unusual Tk configurations never crash the app.

    Args:
        window:     Any Tk widget; the function walks up to the root HWND via
                    ``GetAncestor(GA_ROOT=2)`` before calling DWM.
        prefer_dark: True → dark title bar; False → light title bar.  Pass
                    ``is_dark_color(theme["bg_main"])`` to keep this in sync
                    with the active theme.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        _apply_native_menu_theme(prefer_dark)
        window.update_idletasks()

        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(window.winfo_id())

        try:
            ga_root = 2
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.GetAncestor.restype = ctypes.c_void_p
            root_hwnd = user32.GetAncestor(hwnd, ga_root)
            if root_hwnd:
                hwnd = ctypes.c_void_p(root_hwnd)
        except Exception:
            pass

        dark_value = ctypes.c_int(1 if prefer_dark else 0)
        attr_size = ctypes.sizeof(dark_value)
        dwmapi = ctypes.windll.dwmapi

        for attribute in (20, 19):
            try:
                dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    ctypes.c_uint(attribute),
                    ctypes.byref(dark_value),
                    ctypes.c_uint(attr_size),
                )
            except Exception:
                continue

        try:
            user32.DrawMenuBar.argtypes = [ctypes.c_void_p]
            user32.DrawMenuBar.restype = ctypes.c_int
            user32.DrawMenuBar(hwnd)
        except Exception:
            pass

        try:
            window.after(120, lambda: _apply_chrome_retry(window, prefer_dark))
        except Exception:
            pass

    except Exception:
        return


def _apply_chrome_retry(window: tk.Misc, prefer_dark: bool) -> None:
    """Second-pass chrome application scheduled 120 ms after the initial call.

    Some Windows 10 builds and certain Tk versions do not honor
    ``DwmSetWindowAttribute`` until the window has been fully realized.  The
    retry ensures the title bar color is correct even on those configurations.

    Args:
        window:     The same widget passed to ``apply_window_chrome_theme()``.
        prefer_dark: Dark/light flag, forwarded from the first pass.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        window.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(window.winfo_id())
        dark_value = ctypes.c_int(1 if prefer_dark else 0)
        attr_size = ctypes.sizeof(dark_value)
        dwmapi = ctypes.windll.dwmapi
        for attribute in (20, 19):
            try:
                dwmapi.DwmSetWindowAttribute(
                    hwnd, ctypes.c_uint(attribute), ctypes.byref(dark_value), ctypes.c_uint(attr_size),
                )
            except Exception:
                continue
    except Exception:
        return


def _apply_native_menu_theme(prefer_dark: bool) -> None:
    """Synchronize the native Win32 menu bar color with the app's light/dark mode.

    Calls ``uxtheme!SetPreferredAppMode`` (ordinal 135, available on Windows 10
    1903+) with mode 1 (dark) or 3 (light), then flushes the menu theme cache.
    This ensures that right-click context menus and the menu bar drawn by
    Windows itself use the correct color scheme.

    Silently no-ops if the uxtheme export is unavailable (older Windows builds)
    or on non-Windows platforms.

    Args:
        prefer_dark: True → dark menus (mode 1); False → light menus (mode 3).
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        uxtheme = ctypes.WinDLL("uxtheme")
        set_preferred_app_mode = getattr(uxtheme, "SetPreferredAppMode", None)
        flush_menu_themes = getattr(uxtheme, "FlushMenuThemes", None)

        if set_preferred_app_mode is not None:
            mode = 1 if prefer_dark else 3
            set_preferred_app_mode.argtypes = [ctypes.c_int]
            set_preferred_app_mode.restype = ctypes.c_int
            set_preferred_app_mode(mode)

        if flush_menu_themes is not None:
            flush_menu_themes.argtypes = []
            flush_menu_themes.restype = None
            flush_menu_themes()
    except Exception:
        return
