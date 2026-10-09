"""Menu popups follow the screen-placement contract (real Tk, monitor mocked)."""

from __future__ import annotations

import pytest

import bw_gui.runtime.screen_placement as sp
from bw_gui.contracts.screen_geometry import MonitorInfo, MonitorSource, Rect
from bw_gui.menu.custom_menu_bar import CustomMenuBar
from bw_gui.menu.menu_types import MenuItem
from bw_gui.runtime import ui


@pytest.fixture
def bar(_shared_tk_root, monkeypatch):
    work = Rect(0, 0, 800, 400)
    monkeypatch.setattr(
        sp, "get_monitor_info", lambda *_a, **_k: MonitorInfo(work, work, MonitorSource.WIN32, True)
    )
    menu = CustomMenuBar(_shared_tk_root, (), theme_key="mono_day")
    anchor = ui.Frame(_shared_tk_root, width=40, height=20)
    anchor.place(x=10, y=10)
    _shared_tk_root.update_idletasks()
    yield menu, anchor
    menu.close_popups_from_level(0)
    anchor.destroy()


def test_small_level0_popup_opens_below_anchor(bar):
    menu, anchor = bar
    with menu._focus_watchdog_suspended():  # test windows give focus back; keep the popup open
        menu.open_popup(anchor, (MenuItem(type="command", label="Eins"),), 0, "datei")
        popup = menu._popup_stack[0]
        popup.update()
        assert popup.geometry().endswith(f"+{anchor.winfo_rootx()}+{anchor.winfo_rooty() + anchor.winfo_height()}")


def test_tall_popup_is_capped_to_work_area_and_scrolls(bar):
    menu, anchor = bar
    items = tuple(MenuItem(type="command", label=f"Eintrag {i}") for i in range(60))
    with menu._focus_watchdog_suspended():
        menu.open_popup(anchor, items, 0, "datei")
        popup = menu._popup_stack[0]
        popup.update()
        assert popup.winfo_reqheight() <= 400
        top = int(popup.geometry().rsplit("+", 1)[1])
        assert 0 <= top and top + popup.winfo_reqheight() <= 400
        assert popup._bw_menu_scroll_host._overflows()
