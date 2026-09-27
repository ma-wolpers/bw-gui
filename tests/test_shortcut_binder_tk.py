"""Opt-in real-Tk integration tests for WindowShortcutBinder (key routing, bindtags, scope).

Real synthetic key events only reach a widget while the test window has the OS
keyboard focus, so these tests must take the focus (``focus_force``) -- which would
steal keystrokes from a user typing in another window. They are therefore skipped
by default and only run with ``TK_FOCUS_TESTS=1`` (an intentional, undisturbed run).
Gating, multiplexing and return values are covered headlessly in
``test_shortcut_binder_headless.py``.

The win32 state values used here were measured with real key strokes (tests/live/).
"""

from __future__ import annotations

import os

import pytest

from bw_gui.contracts import TkBackend
from bw_gui.runtime import WindowShortcutBinder, detect_backend, ui

pytestmark = pytest.mark.skipif(
    os.environ.get("TK_FOCUS_TESTS") != "1",
    reason="opens windows and takes the keyboard focus; run with TK_FOCUS_TESTS=1",
)

NUMLOCK = 0x0008
CONTROL = 0x0004
ALT_WIN32 = 0x20000


@pytest.fixture
def window(_shared_tk_root):
    """A fresh toplevel with a canvas and an entry, destroyed after the test."""
    top = ui.Toplevel(_shared_tk_root)
    top.geometry("200x120+20+20")
    canvas = ui.Canvas(top)
    entry = ui.Entry(top)
    canvas.pack()
    entry.pack()
    top.update()
    yield top, canvas, entry
    top.destroy()


def _press(widget, key, state=0):
    """Take the keyboard focus for *widget* and send one synthetic KeyPress."""
    widget.focus_force()
    widget.update()
    widget.event_generate(f"<KeyPress-{key}>", state=state, when="now")
    widget.update()


def _binder(top, **kwargs):
    return WindowShortcutBinder(top, backend=TkBackend.WIN32, **kwargs)


def test_detect_backend_reads_tk_windowing_system(_shared_tk_root):
    assert detect_backend(_shared_tk_root).value == _shared_tk_root.tk.call("tk", "windowingsystem")


def test_real_key_routing_numlock_passes_ctrl_alt_block(window):
    top, canvas, _entry = window
    hits = []
    _binder(top).bind("a", lambda e: hits.append(e.state) or "break", binding_id="a", intent="i")
    for state in (0, NUMLOCK, CONTROL, ALT_WIN32):
        _press(canvas, "a", state)
    assert hits == [0, NUMLOCK]


def test_blocked_shortcut_does_not_break_propagation_to_bind_all(window, _shared_tk_root):
    top, canvas, _entry = window
    global_hits = []
    _shared_tk_root.bind_all("<KeyPress-a>", lambda e: global_hits.append(e.state), add="+")
    try:
        _binder(top).bind("a", lambda e: "break", binding_id="a", intent="i")
        _press(canvas, "a", ALT_WIN32)  # blocked -> None -> "all" still runs
        _press(canvas, "a", 0)  # executed -> "break" stops "all"
    finally:
        _shared_tk_root.unbind_all("<KeyPress-a>")
    assert global_hits == [ALT_WIN32]


def test_text_input_is_gated(window):
    # Synthetic KeyPress events carry no character on win32, so text insertion itself
    # is not observable here; the gating (handler not run) is.
    top, _canvas, entry = window
    hits = []
    _binder(top).bind("a", lambda e: hits.append(1) or "break", binding_id="a", intent="i")
    _press(entry, "a")
    assert hits == []


def test_scope_is_one_toplevel(window, _shared_tk_root):
    top, _canvas, _entry = window
    other = ui.Toplevel(_shared_tk_root)
    other_canvas = ui.Canvas(other)
    other_canvas.pack()
    try:
        hits = []
        _binder(top).bind("a", lambda e: hits.append(1), binding_id="a", intent="i")
        _press(other_canvas, "a")
        assert hits == []
    finally:
        other.destroy()
