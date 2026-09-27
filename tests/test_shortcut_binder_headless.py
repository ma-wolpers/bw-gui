"""Headless tests for WindowShortcutBinder: gating, multiplexing, return values.

Uses a window test double instead of a real Tk window, so running the default suite
never opens windows or steals the user's keyboard focus. Tk key routing and
bindtag propagation are covered by the opt-in ``test_shortcut_binder_tk.py``
(``TK_FOCUS_TESTS=1``).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bw_gui.contracts import UI_MODE_GLOBAL, UI_MODE_PREVIEW, TkBackend
from bw_gui.runtime import WindowShortcutBinder

NUMLOCK, CONTROL, ALT_WIN32 = 0x0008, 0x0004, 0x20000


class _FakeWindow:
    """Records ``bind`` calls like a Tk window (one script per sequence, last wins)."""

    def __init__(self) -> None:
        self.scripts: dict[str, object] = {}
        self.bind_calls: list[str] = []

    def bind(self, sequence, func):
        """Store *func* for *sequence*, replacing any previous script (Tk semantics)."""
        self.bind_calls.append(sequence)
        self.scripts[sequence] = func

    def focus_get(self):
        """No focused widget (not a text input)."""
        return None

    def fire(self, sequence, state=0, widget=None):
        """Invoke the script bound to *sequence* with a synthetic event."""
        return self.scripts[sequence](SimpleNamespace(state=state, widget=widget))


def _binder(window, **kwargs):
    return WindowShortcutBinder(window, backend=TkBackend.WIN32, **kwargs)


def test_numlock_passes_ctrl_and_alt_block_a_plain_letter():
    window = _FakeWindow()
    hits = []
    _binder(window).bind("a", lambda e: hits.append(e.state) or "break", binding_id="a", intent="i")
    results = [window.fire("a", state) for state in (0, NUMLOCK, CONTROL, ALT_WIN32, NUMLOCK | CONTROL)]
    assert hits == [0, NUMLOCK]
    # Executed -> handler result ("break"); blocked -> None so later bindtags still run.
    assert results == ["break", "break", None, None, None]


def test_declared_control_fires_with_numlock_but_not_with_extra_alt():
    window = _FakeWindow()
    hits = []
    _binder(window).bind("<Control-f>", lambda e: hits.append(e.state), binding_id="f", intent="i")
    window.fire("<Control-f>", CONTROL | NUMLOCK)
    window.fire("<Control-f>", CONTROL | ALT_WIN32)
    assert hits == [CONTROL | NUMLOCK]


def test_undecodable_state_is_fail_closed():
    window = _FakeWindow()
    hits = []
    _binder(window).bind("a", lambda e: hits.append(1), binding_id="a", intent="i")
    window.fire("a", state="??")
    assert hits == []


def test_text_input_widget_is_gated():
    window = _FakeWindow()
    hits = []
    _binder(window, is_text_input=lambda w: w == "entry").bind("a", lambda e: hits.append(1), binding_id="a", intent="i")
    window.fire("a", widget="entry")
    window.fire("a", widget="canvas")
    assert hits == [1]


def test_semantic_duplicates_are_multiplexed_by_mode_and_bound_once():
    window = _FakeWindow()
    mode = {"value": UI_MODE_PREVIEW}
    binder = _binder(window, mode_provider=lambda: mode["value"])
    hits = []
    binder.bind("<Return>", lambda e: hits.append("preview"), binding_id="p", intent="i", modes=(UI_MODE_PREVIEW,))
    binder.bind("<KeyPress-Return>", lambda e: hits.append("list"), binding_id="l", intent="i", modes=("list",))
    assert window.bind_calls == ["<Return>"]  # one Tk binding per signature, no silent overwrite
    window.fire("<Return>")
    mode["value"] = "list"
    window.fire("<Return>")
    assert hits == ["preview", "list"]


def test_overlapping_duplicate_is_rejected_at_bind_time():
    window = _FakeWindow()
    binder = _binder(window)
    binder.bind("<Control-comma>", lambda e: None, binding_id="one", intent="i", modes=(UI_MODE_GLOBAL,))
    with pytest.raises(ValueError, match="conflict"):
        binder.bind("<Control-,>", lambda e: None, binding_id="two", intent="i", modes=(UI_MODE_GLOBAL,))
    assert [d.binding_id for d in binder.registry.all()] == ["one"]


def test_sequence_outside_contract_is_rejected():
    with pytest.raises(ValueError):
        _binder(_FakeWindow()).bind("<Command-a>", lambda e: None, binding_id="c", intent="i")


def test_on_dispatch_reports_only_executed_intents():
    window = _FakeWindow()
    calls = []
    binder = _binder(window, on_dispatch=lambda intent, success: calls.append((intent, success)))
    binder.bind("a", lambda e: None, binding_id="a", intent="do.a")
    window.fire("a", CONTROL)
    window.fire("a")
    assert calls == [("do.a", True)]


def test_backend_falls_back_to_platform_for_windowless_doubles():
    binder = WindowShortcutBinder(_FakeWindow())
    assert isinstance(binder.backend, TkBackend)
