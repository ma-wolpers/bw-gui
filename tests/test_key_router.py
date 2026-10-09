"""AllTagRouter: TK_DEFAULT wrapping (Tcl-safe), single dispatch, role order, verify, registry."""

from __future__ import annotations

import gc
import weakref

import pytest

from bw_gui.contracts.events import EventResult
from bw_gui.contracts.key_spec import Key, KeySpec, Mod, matches
from bw_gui.runtime import ui
from bw_gui.runtime._tk_identity import existing_runtime, interpreter_root, runtime_for
from bw_gui.runtime.key_router import ROLE_APP_SHORTCUT, ROLE_MENU_MNEMONIC, ROLE_OBSERVER, router_for

# A deliberately nasty fake "Tk default": quotes, backslashes, braces, brackets,
# several commands (newline and ';'), %-substitutions and a '+'-appended part.
# It is bound on a virtual event: virtual events on `all` are wrapped like key
# defaults, and unlike key presses they reach a widget without OS keyboard focus
# (the test plugin hands the foreground back), so the Tcl-level wrapping can be
# verified headlessly. Real key routing is covered by the TK_FOCUS_TESTS tests below.
FAKE = "<<BwTestDefault>>"
NASTY = 'set ::bwtest(log) [list "%K" {a\\b} [string length "q\\"x"] %s]; incr ::bwtest(n)\nlappend ::bwtest(log) {[x]} "y z"'
NASTY_PLUS = "lappend ::bwtest(log) plus-%K"


@pytest.fixture(scope="module")
def _module_root():
    """One extra interpreter for this module (repeated Tk() creation races, see conftest)."""
    root = ui.Tk()
    root.geometry("200x80+0+0")  # must be mapped: a withdrawn root gets no Tk focus
    entry = ui.Entry(root)
    entry.pack()
    root.update()
    yield root, entry
    if root.winfo_exists():
        root.destroy()


def _reset_runtime(root):
    runtime = existing_runtime(root)
    if runtime is not None:
        runtime._teardown()
        root.__dict__.pop("_bw_gui_runtime", None)


@pytest.fixture
def fresh_root(_module_root):
    """The module interpreter with no bw-gui runtime and a fake Tk default on <Key-F9>."""
    root, entry = _module_root
    _reset_runtime(root)
    for seq in root.tk.splitlist(root.tk.call("bind", "all")):
        if str(seq) in (FAKE, "<Control-Key-q>"):
            root.tk.call("bind", "all", seq, "")
    root.tk.call("bind", "all", FAKE, NASTY)
    root.tk.call("bind", "all", FAKE, "+" + NASTY_PLUS)
    root.report_callback_exception = ui.Tk.report_callback_exception.__get__(root)
    entry.focus_set()
    root.update()
    yield root, entry
    _reset_runtime(root)


def _run(root, entry):
    root.tk.call("array", "unset", "::bwtest")
    root.tk.call("set", "::bwtest(n)", "0")
    entry.event_generate(FAKE)
    root.update()
    log = root.tk.call("array", "get", "::bwtest")
    pairs = [str(x) for x in root.tk.splitlist(log)]
    return dict(zip(pairs[::2], pairs[1::2]))


def test_wrapping_preserves_original_behaviour_verbatim(fresh_root):
    root, entry = fresh_root
    original = str(root.tk.call("bind", "all", FAKE))
    assert NASTY_PLUS in original  # the '+'-appended part is part of the opaque original
    before = _run(root, entry)
    router = router_for(root)
    assert router.originals[FAKE] == original
    wrapped = str(root.tk.call("bind", "all", FAKE))
    assert wrapped == router.channel.prefix + "\n" + original
    after = _run(root, entry)
    assert after == before and before["n"] == "1" and "plus-??" in before["log"]
    router.uninstall()
    assert str(root.tk.call("bind", "all", FAKE)) == original


def test_handled_suppresses_original_and_dispatch_runs_once(fresh_root):
    root, entry = fresh_root
    router = router_for(root)
    calls = []
    router.register(ROLE_APP_SHORTCUT, lambda d: (calls.append(d.event.key), EventResult.HANDLED)[1])
    result = _run(root, entry)
    assert calls == [Key.OTHER]  # virtual event without key information: dispatched exactly once
    assert result.get("n") == "0"  # original did not run


def test_role_order_is_fixed_and_independent_of_registration(fresh_root):
    root, entry = fresh_root
    router = router_for(root)
    order = []
    router.register(ROLE_MENU_MNEMONIC, lambda d: order.append("mnemonic"))
    router.register(ROLE_APP_SHORTCUT, lambda d: order.append("app"))
    router.register(ROLE_OBSERVER, lambda d: (order.append("observer"), EventResult.HANDLED)[1])
    router.channel._dispatch_from_tcl(str(entry), "a", "a", "0")
    assert order == ["observer", "app", "mnemonic"]


def test_app_shortcut_beats_mnemonic_and_not_handled_falls_through(fresh_root):
    root, entry = fresh_root
    router = router_for(root)
    seen = []
    alt_z = KeySpec.char("z", {Mod.ALT})

    def app(d):
        if matches(alt_z, d.identity):
            seen.append("app")
            return app.result
        return None

    def mnemonic(d):
        if d.identity.character == "z" and Mod.ALT in d.identity.modifiers:
            seen.append("mnemonic")
            assert d.event.text is None
            return EventResult.HANDLED
        return None

    router.register(ROLE_APP_SHORTCUT, app)
    router.register(ROLE_MENU_MNEMONIC, mnemonic)
    alt_win32 = str(0x20000)
    app.result = EventResult.HANDLED
    assert router.channel._dispatch_from_tcl(str(entry), "z", "z", alt_win32) == "handled"
    assert seen == ["app"]
    seen.clear()
    app.result = EventResult.NOT_HANDLED
    router.channel._dispatch_from_tcl(str(entry), "z", "z", alt_win32)
    assert seen == ["app", "mnemonic"]


def test_handler_error_is_reported_and_ends_processing(fresh_root):
    root, entry = fresh_root
    router = router_for(root)
    reported, later = [], []
    root.report_callback_exception = lambda *exc: reported.append(exc[0])
    router.register(ROLE_APP_SHORTCUT, lambda d: 1 / 0)
    router.register(ROLE_MENU_MNEMONIC, lambda d: later.append(1))
    result = _run(root, entry)
    assert reported == [ZeroDivisionError] and later == [] and result.get("n") == "0"


def test_verify_finds_unwrapped_all_binding(fresh_root):
    root, _entry = fresh_root
    router = router_for(root)
    assert router.verify() == []
    root.bind_all("<Control-Key-q>", lambda e: None)
    assert router.verify() == ["<Control-Key-q>"]


def test_foreign_binding_on_owned_tag_is_rejected(fresh_root):
    from bw_gui.runtime._key_channel import KeyChannel

    root, _entry = fresh_root
    root.tk.call("bind", "mytag", "<Key-a>", "set x 1")
    with pytest.raises(ValueError):
        KeyChannel(root, "mytag")


def test_one_router_per_interpreter_and_cleanup(fresh_root):
    root, _entry = fresh_root
    top_a, top_b = ui.Toplevel(root), ui.Toplevel(root)
    child = ui.Frame(top_b)
    try:
        assert interpreter_root(child) is root
        assert router_for(top_a) is router_for(child) is router_for(root)
    finally:
        top_a.destroy()
        top_b.destroy()
    other = ui.Tk()  # the only second interpreter of this module
    other.withdraw()
    assert router_for(other) is not router_for(root)
    router_ref = weakref.ref(router_for(other))
    other.destroy()
    gc.collect()
    assert router_ref() is None
    assert "_bw_gui_runtime" not in other.__dict__


def test_existing_runtime_does_not_create(fresh_root):
    root, _entry = fresh_root
    assert existing_runtime(root) is None
    runtime_for(root)
    assert existing_runtime(root) is not None


def test_register_event_rejects_keyboard_sequences(fresh_root):
    root, _entry = fresh_root
    with pytest.raises(ValueError):
        router_for(root).register_event("<Key-a>", lambda e: None)
