"""Win32 adapter for monitor geometry (the only module that calls these APIs).

Spike result (2026-10-09, Win11, Tk 8.6, two monitors, second monitor offset at
``x=1920``): Tk runs DPI-unaware (thread DPI awareness context 0). Win32 calls made
from the same thread return the same virtualised coordinates Tk uses
(``GetWindowRect`` of the root frame equals ``wm geometry``; negative positions
work). Therefore no coordinate conversion is needed; this module never changes the
thread's DPI awareness context. Should a future Tk become DPI-aware with differing
coordinates, the conversion belongs here and nowhere else (rounding inward via
``round_rect_inward``).
"""

from __future__ import annotations

import sys

from bw_gui.contracts.screen_geometry import MonitorInfo, MonitorSource, Rect


class Win32MonitorError(OSError):
    """Raised when a Win32 monitor query fails (callers fall back to the Tk screen)."""


def is_available() -> bool:
    """Return True on Windows, where the Win32 monitor APIs exist."""
    return sys.platform.startswith("win")


def enumerate_monitors() -> list[MonitorInfo]:
    """Return every monitor with its bounds and work area via ``EnumDisplayMonitors``.

    Raises:
        Win32MonitorError: If the APIs are unavailable or report no monitor.
    """
    if not is_available():
        raise Win32MonitorError("Win32 monitor APIs are only available on Windows")
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32

        class _MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        found: list[MonitorInfo] = []
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p
        )

        def _collect(handle, _hdc, _rect, _data) -> int:
            info = _MonitorInfo()
            info.cbSize = ctypes.sizeof(_MonitorInfo)
            if user32.GetMonitorInfoW(ctypes.c_void_p(handle), ctypes.byref(info)):
                mon, work = info.rcMonitor, info.rcWork
                found.append(
                    MonitorInfo(
                        bounds=Rect(int(mon.left), int(mon.top), int(mon.right), int(mon.bottom)),
                        work_area=Rect(int(work.left), int(work.top), int(work.right), int(work.bottom)),
                        source=MonitorSource.WIN32,
                        primary=bool(info.dwFlags & 1),
                    )
                )
            return 1

        if not user32.EnumDisplayMonitors(None, None, callback_type(_collect), 0):
            raise Win32MonitorError("EnumDisplayMonitors failed")
    except Win32MonitorError:
        raise
    except Exception as exc:  # ctypes/loader failures are environment errors
        raise Win32MonitorError(str(exc)) from exc
    if not found:
        raise Win32MonitorError("EnumDisplayMonitors reported no monitor")
    return found


def root_window_rect(window_id: int) -> Rect:
    """Return the outer frame rectangle of the native root window owning *window_id*.

    Args:
        window_id: The Tk ``winfo_id()`` of any widget in the toplevel.

    Raises:
        Win32MonitorError: If the window cannot be resolved.
    """
    if not is_available():
        raise Win32MonitorError("Win32 window APIs are only available on Windows")
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.c_void_p
        root = user32.GetAncestor(ctypes.c_void_p(window_id), 2) or window_id
        rect = wintypes.RECT()
        if not user32.GetWindowRect(ctypes.c_void_p(root), ctypes.byref(rect)):
            raise Win32MonitorError("GetWindowRect failed")
        return Rect(int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Win32MonitorError:
        raise
    except Exception as exc:
        raise Win32MonitorError(str(exc)) from exc
