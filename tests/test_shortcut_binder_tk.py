"""Real-Tk integration tests for WindowShortcutBinder (gating, multiplexing, propagation, scope).

Events are synthesised with ``event_generate(..., state=...)``; the win32 state values
used here were measured with real key strokes (see tests/live/). The live test
verifies the measurement itself; these tests verify the binder's behaviour on top.
"""

from __future__ import annotations

import pytest

from bw_gui.contracts import UI_MODE_GLOBAL, UI_MODE_PREVIEW, TkBackend
from bw_gui.runtime import WindowShortcutBinder, detect_backend, ui

NUMLOCK = 0x0008
CONTROL = 0x0004
ALT_WIN32 = 0x20000


@pytest.fixture
def window(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    top.geometry("200x120+20+20")
    canvas = ui.Canvas(top)
    entry = ui.Entry(top)
    canvas.pack()
    entry.pack()
    top.update()
    canvas.focus_force()
    top.update()
    yield top, canvas, entry
    top.destroy()


def _press(widget, key, state=0):
    widget.focus_force()
    widget.update()
    widget.event_generate(f"<KeyPress-{key}>", state=state, when="now")
    widget.update()


def _binder(top, **kwargs):
    return WindowShortcutBinder(top, backend=TkBackend.WIN32, **kwargs)


def test_detect_backend_reads_tk_windowing_system(_shared_tk_root):
    assert detect_backend(_shared_tk_root).value == _shared_tk_root.tk.call("tk", "windowingsystem")


def test_plain_letter_fires_with_numlock_and_is_blocked_by_ctrl_and_alt(window):
    top, canvas, _entry = window
    hits = []
    _binder(top).bind("a", lambda e: hits.append(e.state) or "break", binding_id="a", intent="i")
    for state in (0, NUMLOCK, CONTROL, ALT_WIN32, NUMLOCK | CONTROL):
        _press(canvas, "a", state)
    assert hits == [0, NUMLOCK]


def test_declared_control_binding_fires_with_numlock(window):
    top, canvas, _entry = window
    hits = []
    _binder(top).bind("<Control-f>", lambda e: hits.append(e.state), binding_id="f", intent="i")
    _press(canvas, "f", CONTROL | NUMLOCK)
    _press(canvas, "f", CONTROL | ALT_WIN32)
    assert hits == [CONTROL | NUMLOCK]


def test_blocked_shortcut_does_not_break_propagation_to_bind_all(window, _shared_tk_root):
    top, canvas, _entry = window
    global_hits = []
    funcid = _shared_tk_root.bind_all("<KeyPress-a>", lambda e: global_hits.append(e.state), add="+")
    try:
        _binder(top).bind("a", lambda e: "break", binding_id="a", intent="i")
        _press(canvas, "a", ALT_WIN32)  # blocked -> None -> "all" still runs
        _press(canvas, "a", 0)  # executed -> "break" stops "all"
    finally:
        _shared_tk_root.unbind_all("<KeyPress-a>")
        del funcid
    assert global_hits == [ALT_WIN32]


def test_text_input_is_gated(window):
    # Synthetic KeyPress events carry no character on win32, so text insertion itself
    # is not observable here; the gating (handler not run, no "break") is.
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


def test_multiplexing_dispatches_by_mode_instead_of_overwriting(window):
    top, canvas, _entry = window
    mode = {"value": UI_MODE_PREVIEW}
    binder = _binder(top, mode_provider=lambda: mode["value"])
    hits = []
    binder.bind("<Return>", lambda e: hits.append("preview"), binding_id="p", intent="i", modes=(UI_MODE_PREVIEW,))
    binder.bind("<KeyPress-Return>", lambda e: hits.append("global"), binding_id="g", intent="i", modes=("list",))
    _press(canvas, "Return")
    mode["value"] = "list"
    _press(canvas, "Return")
    assert hits == ["preview", "global"]


def test_overlapping_semantic_duplicate_is_rejected_at_bind_time(window):
    top, _canvas, _entry = window
    binder = _binder(top)
    binder.bind("<Control-comma>", lambda e: None, binding_id="one", intent="i", modes=(UI_MODE_GLOBAL,))
    with pytest.raises(ValueError, match="conflict"):
        binder.bind("<Control-,>", lambda e: None, binding_id="two", intent="i", modes=(UI_MODE_GLOBAL,))
    assert [d.binding_id for d in binder.registry.all()] == ["one"]


def test_sequence_outside_contract_is_rejected(window):
    top, _canvas, _entry = window
    with pytest.raises(ValueError):
        _binder(top).bind("<Command-a>", lambda e: None, binding_id="c", intent="i")


def test_on_dispatch_reports_executed_intent(window):
    top, canvas, _entry = window
    calls = []
    binder = _binder(top, on_dispatch=lambda intent, success: calls.append((intent, success)))
    binder.bind("a", lambda e: None, binding_id="a", intent="do.a")
    _press(canvas, "a", CONTROL)
    _press(canvas, "a")
    assert calls == [("do.a", True)]
