"""IdleRenderScheduler: one run per idle cycle, first-marked order, flush_now, destroy cancels."""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.runtime.idle_render import IdleRenderScheduler


@pytest.fixture
def frame(_shared_tk_root):
    widget = ui.Frame(_shared_tk_root)
    yield widget
    if widget.winfo_exists():
        widget.destroy()
    _shared_tk_root.update()


def test_marks_coalesce_into_one_run_in_first_marked_order(frame, _shared_tk_root):
    calls: list[str] = []
    scheduler = IdleRenderScheduler(frame)
    scheduler.mark("a", lambda: calls.append("a1"))
    scheduler.mark("b", lambda: calls.append("b"))
    scheduler.mark("a", lambda: calls.append("a2"))  # last callable wins, position kept
    assert scheduler.pending == ("a", "b")
    _shared_tk_root.update()
    assert calls == ["a2", "b"]
    _shared_tk_root.update()
    assert calls == ["a2", "b"]


def test_flush_now_runs_synchronously_and_cancels_idle(frame, _shared_tk_root):
    calls: list[str] = []
    scheduler = IdleRenderScheduler(frame)
    scheduler.mark("a", lambda: calls.append("a"))
    scheduler.flush_now()
    assert calls == ["a"]
    _shared_tk_root.update()
    assert calls == ["a"]


def test_marking_during_a_render_runs_in_the_next_cycle(frame, _shared_tk_root):
    calls: list[str] = []
    scheduler = IdleRenderScheduler(frame)

    def first() -> None:
        calls.append("first")
        scheduler.mark("second", lambda: calls.append("second"))

    scheduler.mark("first", first)
    scheduler.flush_now()
    assert calls == ["first"]
    _shared_tk_root.update()
    assert calls == ["first", "second"]


def test_destroying_the_owner_cancels_pending_work(frame, _shared_tk_root):
    calls: list[str] = []
    scheduler = IdleRenderScheduler(frame)
    scheduler.mark("a", lambda: calls.append("a"))
    frame.destroy()
    _shared_tk_root.update()
    scheduler.mark("b", lambda: calls.append("b"))
    _shared_tk_root.update()
    assert calls == []
