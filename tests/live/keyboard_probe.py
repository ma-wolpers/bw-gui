"""Win32 live keyboard probe: sends real key strokes via ``keybd_event`` to a Tk window.

Used by ``test_live_keyboard.py`` (opt-in, ``BW_GUI_LIVE_KEYBOARD=1``) to verify the
low-level assumptions of :mod:`bw_gui.contracts.key_modifiers` against what Tk really
reports -- instead of only re-stating those assumptions in unit tests.

Safety: key strokes are only sent while the probe window is the foreground window;
otherwise the probe aborts, so no keys ever land in another application. The NumLock
state is restored at the end.
"""

from __future__ import annotations

import ctypes
import time
import tkinter as tk

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
VK_SHIFT, VK_CONTROL, VK_MENU, VK_RMENU, VK_NUMLOCK = 0x10, 0x11, 0x12, 0xA5, 0x90


class ForegroundLost(RuntimeError):
    """Raised when the probe window is no longer the foreground window."""


def _key(vk: int, up: bool = False, extended: bool = False) -> None:
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    _user32.keybd_event(vk, 0, flags, 0)


def numlock_on() -> bool:
    """Return True if NumLock is currently toggled on."""
    return bool(_user32.GetKeyState(VK_NUMLOCK) & 1)


def probe_states(combos: dict[str, tuple[tuple[int, bool], ...]], key_vk: int, *, numlock: bool) -> dict[str, list[int]]:
    """Press each modifier combo + *key_vk* in a Tk window and return the observed ``event.state`` values.

    Args:
        combos: name -> tuple of (virtual key, extended flag) held while tapping *key_vk*.
        key_vk: Virtual key code of the main key.
        numlock: Desired NumLock state during the probe (restored afterwards).
    """
    original_numlock = numlock_on()
    root = tk.Tk()
    root.geometry("240x80+80+80")
    root.title("bw-gui live keyboard probe")
    seen: list[int] = []
    root.bind("<KeyPress>", lambda e: seen.append(int(e.state)) if e.keysym not in {
        "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Num_Lock"} else None)
    results: dict[str, list[int]] = {}
    try:
        root.update()
        root.lift(); root.focus_force(); root.update()
        hwnd = int(root.wm_frame(), 16)
        _user32.SetForegroundWindow(hwnd)
        time.sleep(0.3); root.update()

        def guard() -> None:
            if _user32.GetForegroundWindow() != hwnd:
                raise ForegroundLost("probe window lost foreground; aborting before sending keys")

        if numlock_on() != numlock:
            guard(); _key(VK_NUMLOCK); _key(VK_NUMLOCK, up=True); time.sleep(0.1); root.update()
        for name, held in combos.items():
            seen.clear()
            guard()
            for vk, ext in held:
                _key(vk, extended=ext)
            _key(key_vk); _key(key_vk, up=True)
            for vk, ext in reversed(held):
                _key(vk, up=True, extended=ext)
            time.sleep(0.1); root.update()
            results[name] = list(seen)
    finally:
        if numlock_on() != original_numlock:
            _key(VK_NUMLOCK); _key(VK_NUMLOCK, up=True)
        root.destroy()
    return results
