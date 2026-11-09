"""Which menu popups take keyboard focus (real Tk, monitor mocked, ``focus_set`` spied).

Regression 2026-11-09: a top-level popup whose rows were all disabled (Kartograph's
Extras menu with only a hint row) never took focus, so the click-away watchdog saw
focus outside the menu and closed it right after opening. Real focus is unreliable
under test (the test harness hands the foreground back), so the focus target is
recorded via a ``focus_set`` spy instead.
"""

from __future__ import annotations

import tkinter as tk

import pytest

import bw_gui.runtime.screen_placement as sp
from bw_gui.contracts.screen_geometry import MonitorInfo, MonitorSource, Rect
from bw_gui.menu.custom_menu_bar import CustomMenuBar
from bw_gui.menu.menu_types import MenuItem
from bw_gui.runtime import ui


@pytest.fixture
def bar(_shared_tk_root, monkeypatch):
    """A bar with a placed anchor and a spy that records every ``focus_set`` target."""
    work = Rect(0, 0, 800, 400)
    monkeypatch.setattr(
        sp, "get_monitor_info", lambda *_a, **_k: MonitorInfo(work, work, MonitorSource.WIN32, True)
    )
    focused: list[tk.Misc] = []
    real_focus_set = tk.Misc.focus_set
    monkeypatch.setattr(tk.Misc, "focus_set", lambda self: (focused.append(self), real_focus_set(self))[1])
    menu = CustomMenuBar(_shared_tk_root, (), theme_key="mono_day")
    anchor = ui.Frame(_shared_tk_root, width=40, height=20)
    anchor.place(x=10, y=10)
    _shared_tk_root.update_idletasks()
    yield menu, anchor, focused
    menu.close_popups_from_level(0)
    anchor.destroy()


def test_popup_with_only_disabled_rows_takes_focus(bar):
    menu, anchor, focused = bar
    with menu._focus_watchdog_suspended():
        menu.open_popup(anchor, (MenuItem(type="disabled", label="Nur ein Hinweis"),), 0, "extras")
        popup = menu._popup_stack[0]
        assert focused[-1] is popup
        assert menu._is_menu_managed(focused[-1])  # the watchdog would keep it open


def test_description_flyout_never_takes_focus(bar):
    menu, anchor, focused = bar
    with menu._focus_watchdog_suspended():
        menu.open_popup(anchor, (MenuItem(type="command", label="Eins", description="Erklärung"),), 0, "datei")
        top, flyout = menu._popup_stack
        assert getattr(flyout, "_bw_menu_description_flyout") is True
        assert getattr(top, "_bw_menu_description_flyout") is False
        assert flyout not in focused
        assert focused[-1] is top  # focus restored to the popup holding the hovered row
