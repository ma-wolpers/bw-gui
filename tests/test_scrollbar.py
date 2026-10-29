"""Scrollbar primitive: options, takefocus, theme following (win32 dark mode / colours), lifetime."""

from __future__ import annotations

import gc
import tkinter as tk
from tkinter import ttk

import pytest

import bw_gui.runtime.scrollbar as scrollbar_module
from bw_gui.runtime import widgets
from bw_gui.theming import configure_ttk_theme
from bw_gui.widgets.scrollable_frame import ScrollableFrame


@pytest.fixture
def top(_shared_tk_root):
    window = tk.Toplevel(_shared_tk_root)
    window.geometry("220x160+20+20")
    window.update()
    yield window
    if window.winfo_exists():
        window.destroy()
    configure_ttk_theme(_shared_tk_root, "mono_day")


def test_is_a_native_tk_scrollbar_with_only_the_allowed_options(top):
    bar = widgets.Scrollbar(top, orient="horizontal", command=lambda *a: None)
    assert isinstance(bar, tk.Scrollbar) and not isinstance(bar, ttk.Scrollbar)
    assert str(bar.cget("orient")) == "horizontal"
    for bad in ({"style": "Vertical.TScrollbar"}, {"troughcolor": "#000"}, {"width": 12}):
        with pytest.raises(TypeError):
            widgets.Scrollbar(top, **bad)
        with pytest.raises(TypeError):
            bar.configure(**bad)
    with pytest.raises(TypeError):
        bar["style"] = "x"
    bar.configure(command=lambda *a: None)
    bar["orient"] = "vertical"
    assert str(bar.cget("orient")) == "vertical"
    bar.set(0.2, 0.6)
    assert tuple(round(v, 1) for v in bar.get()) == (0.2, 0.6)


def test_takefocus_none_keeps_the_former_tab_behaviour(top):
    entry_a, bar, entry_b = tk.Entry(top), widgets.Scrollbar(top), tk.Entry(top)
    forced = widgets.Scrollbar(top, takefocus=True)
    for w in (entry_a, bar, entry_b, forced):
        w.pack()
    top.update()
    assert entry_a.tk_focusNext() is entry_b  # skipped, like the former ttk scrollbars
    assert entry_b.tk_focusNext() is forced
    with pytest.raises(TypeError):
        widgets.Scrollbar(top, takefocus="yes")


def test_follows_theme_switches_with_native_dark_mode_on_win32(top, monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(scrollbar_module.sys, "platform", "win32")
    monkeypatch.setattr(scrollbar_module, "set_native_dark_mode", lambda widget, dark: calls.append(dark) or True)
    configure_ttk_theme(top, "mono_day")
    _bar = widgets.Scrollbar(top)  # kept referenced while the theme switches
    configure_ttk_theme(top, "mono_night")
    configure_ttk_theme(top, "porcelain")
    assert calls == [False, True, False]


def test_uses_theme_colours_elsewhere(top, monkeypatch):
    monkeypatch.setattr(scrollbar_module.sys, "platform", "linux")
    configure_ttk_theme(top, "mono_night")
    bar = widgets.Scrollbar(top)
    from bw_gui.theming._theme_manager import get_theme

    assert str(bar.cget("troughcolor")).lower() == get_theme("mono_night")["bg_surface"].lower()


def test_listener_ends_with_the_widget(top, monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(scrollbar_module.sys, "platform", "win32")
    monkeypatch.setattr(scrollbar_module, "set_native_dark_mode", lambda widget, dark: calls.append(dark) or True)
    bar = widgets.Scrollbar(top)
    calls.clear()
    bar.destroy()
    configure_ttk_theme(top, "charcoal")  # destroyed but referenced: listener removes itself
    del bar
    gc.collect()
    configure_ttk_theme(top, "mono_day")
    assert calls == []


def test_listener_is_removed_on_destroy_not_only_on_the_next_switch(top):
    """Regression: with the interpreter already gone, a later winfo_exists() raised TclError."""
    bar = widgets.Scrollbar(top)
    assert bar._theme_subscription.active
    bar.destroy()
    assert not bar._theme_subscription.active


def _scrolled_units(top, *deltas, over_bar):
    """Units a fresh 60-row ScrollableFrame scrolls for wheel *deltas* over its canvas or bar."""
    frame = ScrollableFrame(top)
    frame.pack(fill="both", expand=True)
    for i in range(60):
        tk.Label(frame.content, text=f"row {i}").pack()
    top.update()
    frame.canvas.configure(yscrollincrement=10)
    target = frame._scrollbar if over_bar else frame.canvas
    for delta in deltas:
        target.event_generate("<MouseWheel>", delta=delta)
    top.update()
    units = round(frame.canvas.canvasy(0) / 10)
    frame.destroy()
    return units


@pytest.mark.parametrize(("deltas", "notches"), [((-120,), 1), ((-120, -120), 2), ((-60, -60), 1), ((-60,), 0)])
def test_wheel_over_the_frame_scrollbar_scrolls_exactly_the_factor_times_the_content(top, deltas, notches):
    """Decision 2026-10-18: over the scrollbar faster by rule (formerly 4 + 1 units by accident).

    Touchpad fractions add up to whole notches like over the content; half a notch scrolls nothing.
    """
    from bw_gui.widgets.scrollable_frame import SCROLLBAR_WHEEL_FACTOR

    assert _scrolled_units(top, *deltas, over_bar=False) == notches
    assert _scrolled_units(top, *deltas, over_bar=True) == SCROLLBAR_WHEEL_FACTOR * notches


def test_wheel_up_over_the_scrollbar_at_the_top_scrolls_nothing(top):
    assert _scrolled_units(top, 120, over_bar=True) == 0
