"""Windows-specific platform integration: title bar chrome theming and monitor geometry.

On Windows 10 (build 17763+) and Windows 11 the DWM API allows applications to
opt in to a dark or light title bar.  These functions set that attribute so the
window frame matches the active bw_gui theme.

This module also exposes ``get_monitor_bounds()`` and ``center_window_over_parent()``,
used to place tooltips and popup windows correctly on multi-monitor setups. Tk's own
``winfo_screenwidth``/``winfo_screenheight`` report only the *primary* monitor's size on
Windows, not the monitor the app is actually displayed on, so any code that clamps a
window position using those two calls silently drags popups back onto the primary
display whenever the app lives on a secondary monitor. ``get_monitor_bounds()`` asks
Win32 directly for the actual monitor rectangle instead.

On macOS and Linux all public functions in this module are no-ops (or fall back to
Tk's primary-screen-only behavior) — the module imports and runs cleanly on every
platform.
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


def get_monitor_bounds(widget: tk.Misc) -> tuple[int, int, int, int]:
    """Return ``(left, top, right, bottom)`` of the monitor showing *widget*.

    Coordinates are in the same virtual-desktop space as ``winfo_rootx()``/
    ``winfo_rooty()`` — i.e. a monitor to the right of the primary display has
    a positive ``left``, and one above/left of the primary display has a
    negative ``top``/``left``. This is the piece Tk itself doesn't give you:
    ``winfo_screenwidth()``/``winfo_screenheight()`` report only the *primary*
    monitor's size on Windows, anchored at ``(0, 0)``, regardless of which
    monitor the widget's window actually lives on.

    Resolves the widget's HWND up to its root window (via ``GetAncestor``)
    before asking Win32 ``MonitorFromWindow`` for the containing monitor, so
    it works for both regular windows and popups/tooltips whose own HWND may
    not exist yet.  Uses ``MONITOR_DEFAULTTONEAREST`` so a window that is
    slightly off every monitor (e.g. mid-drag) still resolves to the nearest
    one instead of failing.

    Falls back to ``(0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())``
    — the primary monitor's bounds anchored at the origin, i.e. Tk's own
    single-monitor assumption — on non-Windows platforms or if any Win32 call
    fails. Callers should treat that fallback as "best effort, single monitor"
    rather than a bug: it never crashes, it just can't be more precise than Tk
    itself is on that platform.

    Args:
        widget: Any Tk widget already realized enough to have an HWND (or
                whose toplevel does); typically the tooltip's owner widget or
                a dialog's parent window.
    """
    fallback = (
        0,
        0,
        max(1, int(widget.winfo_screenwidth())),
        max(1, int(widget.winfo_screenheight())),
    )
    if not sys.platform.startswith("win"):
        return fallback
    try:
        import ctypes

        widget.update_idletasks()
        hwnd = ctypes.c_void_p(widget.winfo_id())

        user32 = ctypes.windll.user32
        try:
            ga_root = 2
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.GetAncestor.restype = ctypes.c_void_p
            root_hwnd = user32.GetAncestor(hwnd, ga_root)
            if root_hwnd:
                hwnd = ctypes.c_void_p(root_hwnd)
        except Exception:
            pass

        class _Rect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class _MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", _Rect),
                ("rcWork", _Rect),
                ("dwFlags", ctypes.c_ulong),
            ]

        monitor_default_to_nearest = 2
        user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        monitor = user32.MonitorFromWindow(hwnd, monitor_default_to_nearest)
        if not monitor:
            return fallback

        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MonitorInfo)]
        user32.GetMonitorInfoW.restype = ctypes.c_int
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return fallback

        rect = info.rcMonitor
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        return fallback


def center_window_over_parent(window: tk.Misc, parent: tk.Misc) -> None:
    """Reposition (not resize) *window* to be centered over *parent*'s monitor.

    Reads *window*'s current size (set beforehand via ``window.geometry("WxH")``)
    and *parent*'s actual on-screen position via ``winfo_rootx()``/``winfo_rooty()``,
    then centers *window* over *parent* and clamps the result to the bounds of
    whichever monitor *parent* is actually displayed on (see
    ``get_monitor_bounds()``). Only the position (``+x+y``) is written back —
    *window*'s size is left untouched.

    This exists because an un-positioned ``tk.Toplevel`` (one created with only
    a ``"WxH"`` geometry, no ``+x+y``) is placed by Tk/Windows using its own
    default placement, which is biased toward the primary monitor and ignores
    where *parent* currently is. Popups and dialogs that skip this call will
    reliably reopen on the primary display when the app itself is on a second
    monitor.

    Args:
        window: The ``Toplevel`` to position. Must already have its target
                size applied (e.g. via ``window.geometry("980x700")``) so that
                ``winfo_width()``/``winfo_height()`` reflect it after
                ``update_idletasks()``.
        parent: The window to center over — typically the app's main window
                or whichever widget owns the popup.
    """
    window.update_idletasks()
    width = int(window.winfo_width())
    height = int(window.winfo_height())
    if width <= 1:
        width = int(window.winfo_reqwidth())
    if height <= 1:
        height = int(window.winfo_reqheight())
    width = max(1, width)
    height = max(1, height)

    parent.update_idletasks()
    parent_x = int(parent.winfo_rootx())
    parent_y = int(parent.winfo_rooty())
    parent_width = max(1, int(parent.winfo_width()))
    parent_height = max(1, int(parent.winfo_height()))

    x_pos = parent_x + (parent_width - width) // 2
    y_pos = parent_y + (parent_height - height) // 2

    left, top, right, bottom = get_monitor_bounds(parent)
    x_pos = max(left, min(x_pos, right - width))
    y_pos = max(top, min(y_pos, bottom - height))

    window.geometry(f"+{x_pos}+{y_pos}")
