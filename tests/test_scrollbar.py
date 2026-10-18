"""Scrollbar primitive: options, takefocus, theme following (win32 dark mode / colours), lifetime."""

from __future__ import annotations

import gc
import sys
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
    bar = widgets.Scrollbar(top)
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


def _wheel_distances(top, monkeypatch, scrollbar_class):
    """(over the canvas, over the frame's scrollbar) after one wheel notch."""
    import bw_gui.runtime._ttk_facade as facade

    monkeypatch.setattr(facade, "Scrollbar", scrollbar_class, raising=False)
    frame = ScrollableFrame(top)
    frame.pack(fill="both", expand=True)
    for i in range(60):
        tk.Label(frame.content, text=f"row {i}").pack()
    top.update()
    frame.canvas.event_generate("<MouseWheel>", delta=-120)
    top.update()
    over_canvas = frame.canvas.yview()[0]
    frame.canvas.yview_moveto(0.0)
    top.update()
    frame._scrollbar.event_generate("<MouseWheel>", delta=-120)
    top.update()
    over_bar = frame.canvas.yview()[0]
    frame.destroy()
    return round(over_canvas, 4), round(over_bar, 4)


def test_wheel_over_the_frame_scrollbar_behaves_like_the_former_ttk_scrollbar(top, monkeypatch):
    """1:1 with the former ttk scrollbar. Both class bindings scroll on their own, so over the
    scrollbar a notch moves further than over the content (pre-existing; open decision)."""
    from bw_gui.runtime.scrollbar import Scrollbar

    assert _wheel_distances(top, monkeypatch, Scrollbar) == _wheel_distances(top, monkeypatch, ttk.Scrollbar)
