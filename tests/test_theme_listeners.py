"""Theme listeners: order, isolation, owner lifetime, re-entrancy (deferral, cycle, safety limit)."""

from __future__ import annotations

import gc

import pytest

from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_data import THEME_ORDER
from bw_gui.theming._theme_listeners import MAX_FOLLOW_UPS, register_theme_listener
from bw_gui.theming._widget_utils import _icon_button_registry, icon_button
from bw_gui.runtime import ui


class _Owner:
    """Weak-referenceable owner for listener tests."""

    def __init__(self, log, name):
        self.log, self.name = log, name

    def on_theme(self, change):
        self.log.append((self.name, change.theme_key))


@pytest.fixture
def root(_shared_tk_root, monkeypatch):
    reported: list[BaseException] = []
    monkeypatch.setattr(_shared_tk_root, "report_callback_exception", lambda _t, exc, _tb: reported.append(exc))
    _shared_tk_root.reported = reported
    yield _shared_tk_root
    configure_ttk_theme(_shared_tk_root, "mono_day")


def test_listeners_run_after_styles_in_order_and_errors_are_isolated(root):
    log: list[tuple[str, str]] = []
    first, second = _Owner(log, "first"), _Owner(log, "second")

    def _broken(_change):
        raise ValueError("listener bug")

    register_theme_listener(first.on_theme, owner=first)
    register_theme_listener(_broken, owner=second)
    register_theme_listener(second.on_theme, owner=second)
    configure_ttk_theme(root, "mono_night")
    assert log == [("first", "mono_night"), ("second", "mono_night")]
    assert [type(e) for e in root.reported] == [ValueError]


def test_owner_rules_and_lifetime(root):
    with pytest.raises(TypeError):
        register_theme_listener(lambda c: None, owner=None)
    with pytest.raises(TypeError):
        register_theme_listener(lambda c: None, owner=42)
    log: list = []
    owner = _Owner(log, "x")
    register_theme_listener(owner.on_theme, owner=owner)  # bound method: WeakMethod
    free = _Owner(log, "y")
    register_theme_listener(lambda c, _log=log: _log.append(("free", c.theme_key)), owner=free)
    del owner, free
    gc.collect()
    configure_ttk_theme(root, "charcoal")
    assert log == []
    keep = _Owner(log, "z")
    subscription = register_theme_listener(keep.on_theme, owner=keep)
    subscription.remove()
    subscription.remove()  # idempotent
    configure_ttk_theme(root, "mono_day")
    assert log == []


def test_request_during_listener_phase_is_deferred_last_wins_once(root):
    log: list = []
    owner = _Owner(log, "o")

    def _switcher(change):
        log.append(change.theme_key)
        if change.theme_key == "mono_night":
            configure_ttk_theme(root, "porcelain")  # overwritten by the next request
            configure_ttk_theme(root, "charcoal")
            assert log[-1] == "mono_night"  # deferred, not applied inside the phase

    register_theme_listener(_switcher, owner=owner)
    configure_ttk_theme(root, "mono_night")
    assert log == ["mono_night", "charcoal"]
    assert root.reported == []


def test_request_equal_to_the_applied_state_is_dropped(root):
    log: list = []
    owner = _Owner(log, "o")

    def _same(change):
        log.append(change.theme_key)
        configure_ttk_theme(root, change.theme_key)

    register_theme_listener(_same, owner=owner)
    configure_ttk_theme(root, "graphite_core")
    assert log == ["graphite_core"]


def test_cycle_is_detected_before_the_safety_limit(root):
    log: list = []
    owner = _Owner(log, "o")
    flip = {"mono_night": "porcelain", "porcelain": "mono_night"}

    def _ping_pong(change):
        log.append(change.theme_key)
        configure_ttk_theme(root, flip[change.theme_key])

    register_theme_listener(_ping_pong, owner=owner)
    configure_ttk_theme(root, "mono_night")
    assert log == ["mono_night", "porcelain"]  # A -> B, the request back to A is the cycle
    assert len(root.reported) == 1 and "cycle" in str(root.reported[0])


def test_safety_limit_stops_endless_distinct_switches(root):
    log: list = []
    owner = _Owner(log, "o")
    order = list(THEME_ORDER)

    def _next(change):
        log.append(change.theme_key)
        configure_ttk_theme(root, order[(order.index(change.theme_key) + 1) % len(order)])

    register_theme_listener(_next, owner=owner)
    configure_ttk_theme(root, order[0])
    assert len(log) == 1 + MAX_FOLLOW_UPS
    assert len(root.reported) == 1 and str(MAX_FOLLOW_UPS) in str(root.reported[0])


def test_icon_buttons_follow_the_theme_and_are_held_weakly(root):
    photo = ui.PhotoImage(width=4, height=4)
    photo.put("#000000", to=(0, 0, 4, 4))
    button = icon_button(root, photo, command=lambda: None)
    before = str(button.cget("image"))
    configure_ttk_theme(root, "mono_night")
    assert str(button.cget("image")) != before  # recolored by its listener
    button.destroy()
    del button
    gc.collect()
    assert len([b for b in _icon_button_registry if not b.winfo_exists()]) == 0
