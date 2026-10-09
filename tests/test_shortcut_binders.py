"""Binders on the semantic key dispatch (real Tk, dispatcher entry called directly).

Key presses are fed through the channel's Tcl entry (``_dispatch_from_tcl``) with
the raw Tk fields, so no OS keyboard focus is needed. Real key routing through Tk's
bindtags is covered opt-in by ``test_shortcut_binder_tk.py`` (``TK_FOCUS_TESTS=1``).
"""

from __future__ import annotations

import pytest

from bw_gui.contracts import UI_MODE_GLOBAL, UI_MODE_PREVIEW, EventResult, Key, KeySpec, Mod, TkBackend
from bw_gui.runtime import ApplicationShortcutBinder, WidgetShortcutBinder, WindowShortcutBinder, on_key, ui
from bw_gui.runtime._tk_identity import runtime_for
from bw_gui.runtime.key_router import router_for

NUMLOCK, CONTROL, SHIFT, ALT_WIN32 = 0x0008, 0x0004, 0x0001, 0x20000
CTRL_A = KeySpec.char("a", {Mod.CTRL})


@pytest.fixture
def top(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    canvas = ui.Canvas(window)
    entry = ui.Entry(window)
    canvas.pack()
    entry.pack()
    window.update_idletasks()
    yield window, canvas, entry
    window.destroy()


def _press(binder_or_tag_owner, widget, keysym, char="", state=0):
    """Feed one key press into the window channel of *widget*'s toplevel."""
    group = runtime_for(widget).peek("window_tags")[str(widget.winfo_toplevel())]
    return group.channel._dispatch_from_tcl(str(widget), keysym, char, str(state))


def _binder(window, **kwargs):
    return WindowShortcutBinder(window, backend=TkBackend.WIN32, **kwargs)


def test_exact_modifiers_numlock_and_unknown(top):
    window, canvas, _entry = top
    hits = []
    _binder(window).bind(KeySpec.char("a"), lambda e: (hits.append(e.modifiers), EventResult.HANDLED)[1], binding_id="a", intent="i")
    results = [_press(None, canvas, "a", "a", s) for s in (0, NUMLOCK, CONTROL, ALT_WIN32, NUMLOCK | CONTROL)]
    assert len(hits) == 2
    assert results == ["handled", "handled", "", "", ""]
    assert _press(None, canvas, "a", "a", "??") == ""


def test_ctrl_shift_does_not_fire_ctrl_binding(top):
    window, canvas, _entry = top
    hits = []
    _binder(window).bind(CTRL_A, lambda e: hits.append(1), binding_id="a", intent="i")
    _press(None, canvas, "A", "\x01", CONTROL | SHIFT)
    _press(None, canvas, "a", "\x01", CONTROL | ALT_WIN32)
    _press(None, canvas, "a", "\x01", CONTROL | NUMLOCK)
    assert hits == [1]


def test_shift_tolerance_via_second_spec(top):
    window, canvas, _entry = top
    hits = []
    _binder(window).bind(
        [KeySpec.char("z", {Mod.CTRL}), KeySpec.char("Z", {Mod.CTRL})], lambda e: hits.append(1), binding_id="z", intent="i"
    )
    _press(None, canvas, "z", "\x1a", CONTROL)
    _press(None, canvas, "Z", "\x1a", CONTROL | SHIFT)
    _press(None, canvas, "z", "\x1a", CONTROL | ALT_WIN32)
    assert hits == [1, 1]


def test_text_input_gating_uses_contract(top, _shared_tk_root):
    window, canvas, entry = top
    hits = []
    _binder(window).bind(KeySpec.char("a"), lambda e: hits.append(1), binding_id="a", intent="i")
    _press(None, entry, "a", "a")
    _press(None, canvas, "a", "a")
    entry.configure(state="readonly")
    _press(None, entry, "a", "a")
    assert hits == [1, 1]


def test_model_a_disjoint_modes_ok_predicate_only_rejected(top):
    window, _canvas, _entry = top
    binder = _binder(window, mode_provider=lambda: UI_MODE_PREVIEW)
    binder.bind(CTRL_A, lambda e: None, binding_id="global", intent="i", modes=("editor",))
    binder.bind(CTRL_A, lambda e: None, binding_id="preview", intent="i", modes=(UI_MODE_PREVIEW,))
    with pytest.raises(ValueError):
        binder.bind(CTRL_A, lambda e: None, binding_id="dup", intent="i", modes=(UI_MODE_PREVIEW,), applies_when=lambda e: False)


def test_conflict_spans_binders_on_same_toplevel(top):
    window, _canvas, _entry = top
    _binder(window).bind(CTRL_A, lambda e: None, binding_id="one", intent="i")
    with pytest.raises(ValueError):
        _binder(window).bind(KeySpec.char("a", {Mod.CTRL}, {Mod.ALT}), lambda e: None, binding_id="two", intent="i")


def test_applies_when_false_propagates_without_dispatch(top):
    window, canvas, _entry = top
    dispatched, hits = [], []
    binder = _binder(window, on_dispatch=lambda intent, success: dispatched.append(intent))
    binder.bind(CTRL_A, lambda e: hits.append(1), binding_id="a", intent="i", applies_when=lambda e: False)
    assert _press(None, canvas, "a", "\x01", CONTROL) == ""
    assert hits == [] and dispatched == []


def test_handler_must_not_return_tk_strings(top):
    window, canvas, _entry = top
    reported = []
    window.report_callback_exception = lambda *exc: reported.append(exc[0])
    root = window._root()
    original = root.report_callback_exception
    root.report_callback_exception = lambda *exc: reported.append(exc[0])
    try:
        _binder(window).bind(CTRL_A, lambda e: "break", binding_id="a", intent="i")
        _press(None, canvas, "a", "\x01", CONTROL)
    finally:
        root.report_callback_exception = original
    assert reported == [TypeError]


def test_destroy_disposes_binder_and_registrations(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    binder = _binder(window)
    registration = binder.bind(CTRL_A, lambda e: None, binding_id="a", intent="i")
    window.destroy()
    assert binder.disposed and not registration.active
    assert str(window) not in (runtime_for(_shared_tk_root).peek("window_tags") or {})


def test_foreign_key_binding_on_toplevel_rejected(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    try:
        window.bind("<Control-q>", lambda e: None)
        with pytest.raises(ValueError):
            _binder(window)
        window.unbind("<Control-q>")
        window.bind("<Configure>", lambda e: None)  # non-keyboard bindings may coexist
        _binder(window)
    finally:
        window.destroy()


def test_later_child_reaches_window_binder(top):
    window, _canvas, _entry = top
    hits = []
    _binder(window).bind(CTRL_A, lambda e: hits.append(1), binding_id="a", intent="i")
    late = ui.Label(window)
    assert str(window) in late.bindtags()
    _press(None, late, "a", "\x01", CONTROL)
    assert hits == [1]


def test_application_binder_conflicts_across_binders(_shared_tk_root):
    first = ApplicationShortcutBinder(_shared_tk_root, backend=TkBackend.WIN32)
    second = ApplicationShortcutBinder(_shared_tk_root, backend=TkBackend.WIN32)
    try:
        first.bind(KeySpec.char("y", {Mod.CTRL}), lambda e: None, binding_id="one", intent="i")
        with pytest.raises(ValueError):
            second.bind(KeySpec.char("y", {Mod.CTRL}), lambda e: None, binding_id="two", intent="i")
    finally:
        first.dispose()
        second.dispose()


def test_application_binder_fires_via_router(_shared_tk_root):
    hits = []
    binder = ApplicationShortcutBinder(_shared_tk_root, backend=TkBackend.WIN32)
    try:
        binder.bind(KeySpec.char("y", {Mod.CTRL}), lambda e: (hits.append(1), EventResult.HANDLED)[1], binding_id="y", intent="i")
        result = router_for(_shared_tk_root).channel._dispatch_from_tcl(".", "y", "\x19", str(CONTROL))
        assert result == "handled" and hits == [1]
    finally:
        binder.dispose()
    assert router_for(_shared_tk_root).channel._dispatch_from_tcl(".", "y", "\x19", str(CONTROL)) == ""


def test_backend_unsupported_modifier_rejected(top):
    window, _c, _e = top
    with pytest.raises(ValueError):
        _binder(window).bind(KeySpec.char("a", {Mod.CMD}), lambda e: None, binding_id="a", intent="i")


# -- widget binder and on_key ------------------------------------------------------


def _widget_press(widget, keysym, char="", state=0, after=False):
    hub = runtime_for(widget).peek("widget_keys")[str(widget)]
    channel = hub.after_channel if after else hub.before_channel
    return channel._dispatch_from_tcl(str(widget), keysym, char, str(state))


def test_widget_tags_are_inserted_in_contract_order(top):
    _window, canvas, _entry = top
    WidgetShortcutBinder(canvas, backend=TkBackend.WIN32)
    on_key(canvas, lambda e: None, phase="after")
    tags = list(canvas.bindtags())
    path = str(canvas)
    assert tags[:4] == [path, f"bwkeys:{path}", "Canvas", f"bwkeys-after:{path}"]


def test_executed_widget_shortcut_suppresses_on_key(top):
    _window, canvas, _entry = top
    seen = []
    WidgetShortcutBinder(canvas, backend=TkBackend.WIN32).bind(
        KeySpec(Key.UP), lambda e: seen.append("shortcut"), binding_id="up", intent="i"
    )
    on_key(canvas, lambda e: seen.append("on_key"))
    assert _widget_press(canvas, "Up") == ""  # shortcut ran, returned None -> propagates
    assert seen == ["shortcut"]
    _widget_press(canvas, "Down")
    assert seen == ["shortcut", "on_key"]


def test_on_key_order_and_handled(top):
    _window, _canvas, entry = top
    seen = []
    on_key(entry, lambda e: seen.append(("first", e.text)))
    on_key(entry, lambda e: (seen.append(("second", e.text)), EventResult.HANDLED)[1])
    on_key(entry, lambda e: seen.append(("third", e.text)))
    assert _widget_press(entry, "x", "x") == "handled"
    assert seen == [("first", "x"), ("second", "x")]


def test_on_key_subscription_lifecycle(top, _shared_tk_root):
    window, _canvas, _entry = top
    label = ui.Label(window)
    seen = []
    subscription = on_key(label, lambda e: seen.append(1))
    subscription.remove()
    subscription.remove()  # idempotent
    _widget_press(label, "x", "x")
    assert seen == [] and not subscription.active
    again = on_key(label, lambda e: seen.append(2))
    label.destroy()
    assert not again.active
