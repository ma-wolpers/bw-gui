"""Opt-in live test: verifies the win32 modifier masks against real key strokes.

Run with ``BW_GUI_LIVE_KEYBOARD=1 pytest -m live_keyboard tests/live``. It sends real
key strokes (only while its own window is in the foreground) and toggles NumLock,
restoring the original NumLock state afterwards.
"""

from __future__ import annotations

import os
import sys

import pytest

from bw_gui.contracts import KeyModifiers, TkBackend, modifiers_from_state

pytestmark = [
    pytest.mark.live_keyboard,
    pytest.mark.skipif(sys.platform != "win32", reason="win32 only"),
    pytest.mark.skipif(os.environ.get("BW_GUI_LIVE_KEYBOARD") != "1", reason="set BW_GUI_LIVE_KEYBOARD=1"),
]


@pytest.mark.parametrize("numlock", [False, True])
def test_real_key_strokes_decode_as_expected(numlock):
    from .keyboard_probe import VK_CONTROL, VK_MENU, VK_RMENU, VK_SHIFT, probe_states

    combos = {
        "plain": (),
        "shift": ((VK_SHIFT, False),),
        "ctrl": ((VK_CONTROL, False),),
        "alt": ((VK_MENU, False),),
        "altgr": ((VK_RMENU, True),),
    }
    observed = probe_states(combos, 0x51, numlock=numlock)  # 'Q' (AltGr+Q = '@' on German layout)
    decoded = {name: modifiers_from_state(states[0], TkBackend.WIN32) for name, states in observed.items()}
    assert decoded == {
        "plain": KeyModifiers(),
        "shift": KeyModifiers(shift=True),
        "ctrl": KeyModifiers(control=True),
        "alt": KeyModifiers(alt=True),
        # Tk strips Ctrl+Alt from characters produced via AltGr -> never gated.
        "altgr": KeyModifiers(),
    }
    if numlock:
        assert all(states[0] & 0x0008 for name, states in observed.items() if name != "altgr")
