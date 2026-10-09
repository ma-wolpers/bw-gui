"""Tk side of the screen-placement contract (real Tk root, monitor queries mocked)."""

from __future__ import annotations

import logging

import pytest

import bw_gui.runtime._win_monitors as win_monitors
import bw_gui.runtime.screen_placement as sp
from bw_gui.contracts.screen_geometry import MonitorInfo, MonitorSource, Point, Rect, Side, Size
from bw_gui.runtime import ui


@pytest.fixture
def toplevel(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    window.withdraw()
    yield window
    if window.winfo_exists():
        window.destroy()


def test_non_windows_backend_uses_tk_screen(monkeypatch, _shared_tk_root):
    monkeypatch.setattr(win_monitors.sys, "platform", "linux")
    info = sp.get_monitor_info(Point(5, 5), tk_context=_shared_tk_root)
    assert info.source is MonitorSource.TK_SCREEN
    assert info.work_area == info.bounds == Rect(0, 0, _shared_tk_root.winfo_screenwidth(), _shared_tk_root.winfo_screenheight())


def test_win32_failure_falls_back_with_single_warning(monkeypatch, caplog, _shared_tk_root):
    monkeypatch.setattr(win_monitors.sys, "platform", "win32")
    monkeypatch.setattr(sp, "_fallback_warned", False)

    def _boom():
        raise win_monitors.Win32MonitorError("boom")

    monkeypatch.setattr(win_monitors, "enumerate_monitors", _boom)
    with caplog.at_level(logging.WARNING, logger=sp.__name__):
        first = sp.get_monitor_info(Point(1, 1), tk_context=_shared_tk_root)
        second = sp.get_monitor_info(Point(1, 1), tk_context=_shared_tk_root)
    assert first.source is second.source is MonitorSource.FALLBACK
    assert first.work_area == first.bounds
    assert len([r for r in caplog.records if "fallback" in r.getMessage()]) == 1


def test_win32_selects_monitor_of_point(monkeypatch, _shared_tk_root):
    monitors = [
        MonitorInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040), MonitorSource.WIN32, True),
        MonitorInfo(Rect(1920, 0, 3600, 1050), Rect(1920, 0, 3600, 1010), MonitorSource.WIN32),
    ]
    monkeypatch.setattr(win_monitors.sys, "platform", "win32")
    monkeypatch.setattr(win_monitors, "enumerate_monitors", lambda: monitors)
    assert sp.get_monitor_info(Point(2500, 10), tk_context=_shared_tk_root) is monitors[1]


def test_unmapped_widget_target_is_a_programming_error(toplevel):
    with pytest.raises(ValueError):
        sp.get_monitor_info(toplevel, tk_context=toplevel)


def test_dead_interpreter_raises_monitor_query_error(monkeypatch):
    class _Dead:
        def winfo_screenwidth(self):
            raise ui.TclError("application has been destroyed")

        winfo_screenheight = winfo_screenwidth

    monkeypatch.setattr(win_monitors.sys, "platform", "linux")
    with pytest.raises(sp.MonitorQueryError):
        sp.get_monitor_info(Point(0, 0), tk_context=_Dead())


def test_apply_window_position_sets_only_position(toplevel):
    toplevel.geometry("120x80+0+0")
    toplevel.update_idletasks()
    sp.apply_window_position(toplevel, Point(-37, 44))
    toplevel.update_idletasks()
    assert toplevel.geometry().endswith("-37+44") or toplevel.geometry().endswith("+-37+44")
    assert toplevel.geometry().startswith("120x80")


def test_apply_window_position_on_destroyed_window_raises(toplevel):
    toplevel.destroy()
    with pytest.raises(ValueError):
        sp.apply_window_position(toplevel, Point(0, 0))


def _fixed_monitor(monkeypatch, info):
    monkeypatch.setattr(sp, "get_monitor_info", lambda *_a, **_k: info)


def test_place_overlay_now_order_and_result(monkeypatch, toplevel):
    info = MonitorInfo(Rect(0, 0, 800, 600), Rect(0, 0, 800, 600), MonitorSource.WIN32, True)
    _fixed_monitor(monkeypatch, info)
    calls: list[str] = []
    real_measure, real_apply = sp.measure_overlay, sp.apply_window_position
    monkeypatch.setattr(sp, "measure_overlay", lambda w: (calls.append("measure"), real_measure(w))[1])
    monkeypatch.setattr(sp, "apply_window_position", lambda w, p: (calls.append("apply"), real_apply(w, p))[1])
    ui.Frame(toplevel, width=100, height=50).pack()
    result = sp.place_overlay_now(toplevel, anchor=Rect(10, 10, 60, 30), placement=(Side.BELOW,))
    assert calls[0] == "measure" and calls[-1] == "apply"
    assert result.position == Point(10, 30) and result.fits


def test_place_overlay_now_recomputes_after_max_size_policy(monkeypatch, toplevel):
    info = MonitorInfo(Rect(0, 0, 800, 300), Rect(0, 0, 800, 300), MonitorSource.WIN32, True)
    _fixed_monitor(monkeypatch, info)
    body = ui.Frame(toplevel, width=100, height=900)
    body.pack()
    seen: list[Size] = []

    def _limit(max_size: Size) -> None:
        seen.append(max_size)
        body.configure(height=max_size.height)

    result = sp.place_overlay_now(toplevel, anchor=Rect(10, 10, 60, 30), placement=(Side.BELOW,), margin=8, max_size_policy=_limit)
    assert seen == [Size(800 - 16, 300 - 16)]
    assert result.size.height == 300 - 16
    assert result.position.y == 8  # recomputed for the final size: top-left inside the work area


def test_place_overlay_now_detects_stale_placement(monkeypatch, toplevel):
    info = MonitorInfo(Rect(0, 0, 800, 600), Rect(0, 0, 800, 600), MonitorSource.WIN32, True)
    _fixed_monitor(monkeypatch, info)
    sizes = iter([Size(100, 50), Size(120, 50)])
    monkeypatch.setattr(sp, "measure_overlay", lambda _w: next(sizes))
    with pytest.raises(RuntimeError):
        sp.place_overlay_now(toplevel, anchor=Rect(10, 10, 60, 30), placement=(Side.BELOW,))
