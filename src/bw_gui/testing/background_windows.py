"""pytest plugin: Tk test windows hand the OS foreground straight back to the user.

Problem: every Tk window a test maps is activated by Windows and takes the keyboard
focus. A developer typing in their editor while the suite runs loses keystrokes to
the test window (and the test may even receive them).

Solution: when the test session starts, remember the window that is in the
foreground (the developer's editor/terminal). Whenever a Tk toplevel is mapped
during the session, immediately give the foreground back to that window via
``SetForegroundWindow``. The test window stays alive and fully functional for
Tk-internal operations (layout, ``focus_set``, ``focus_lastfor``) -- it just no
longer owns the OS focus.

Tests that genuinely need the OS keyboard focus (real synthetic key routing) must be
opt-in via ``TK_FOCUS_TESTS=1``; this plugin is disabled in that case, so those runs
behave exactly as before.

Usage in a consumer repo's ``tests/conftest.py``::

    from bw_gui.testing.background_windows import pytest_configure, pytest_unconfigure  # noqa: F401

On non-Windows platforms the plugin is a no-op.
"""

from __future__ import annotations

import os
import sys
import tkinter

_state: dict[str, object] = {"hwnd": None, "originals": None}


def _user32():
    """Return ``ctypes.windll.user32`` on Windows, else ``None``."""
    if sys.platform != "win32":
        return None
    import ctypes

    return ctypes.windll.user32


def _return_foreground(event) -> None:
    """``<Map>`` handler: give the OS foreground back to the remembered window.

    Only reacts to toplevels (``event.widget`` is its own toplevel), because the
    toplevel's bindtag also receives ``<Map>`` for every child widget.
    """
    widget = event.widget
    try:
        if widget.winfo_toplevel() is not widget:
            return
    except (tkinter.TclError, AttributeError):
        return
    user32 = _user32()
    hwnd = _state["hwnd"]
    if user32 is None or not hwnd or not user32.IsWindow(hwnd):
        return
    user32.SetForegroundWindow(hwnd)


def _install_map_hook(window) -> None:
    """Attach the foreground-return hook to a freshly created toplevel."""
    try:
        window.bind("<Map>", _return_foreground, add="+")
    except tkinter.TclError:
        pass


def pytest_configure(config) -> None:
    """Remember the current foreground window and hook Tk/Toplevel creation."""
    user32 = _user32()
    if user32 is None or os.environ.get("TK_FOCUS_TESTS") == "1" or _state["originals"] is not None:
        return
    _state["hwnd"] = user32.GetForegroundWindow()
    tk_init, toplevel_init = tkinter.Tk.__init__, tkinter.Toplevel.__init__

    def tk_init_hooked(self, *args, **kwargs):
        """``tkinter.Tk.__init__`` plus the foreground-return hook."""
        tk_init(self, *args, **kwargs)
        _install_map_hook(self)

    def toplevel_init_hooked(self, *args, **kwargs):
        """``tkinter.Toplevel.__init__`` plus the foreground-return hook."""
        toplevel_init(self, *args, **kwargs)
        _install_map_hook(self)

    tkinter.Tk.__init__ = tk_init_hooked
    tkinter.Toplevel.__init__ = toplevel_init_hooked
    _state["originals"] = (tk_init, toplevel_init)


def pytest_unconfigure(config) -> None:
    """Restore the original ``Tk``/``Toplevel`` constructors."""
    originals = _state["originals"]
    if originals is None:
        return
    tkinter.Tk.__init__, tkinter.Toplevel.__init__ = originals
    _state["originals"] = None
