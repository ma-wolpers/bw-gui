"""Pointer contract: wheel normalisation/accumulation, clicks, drag lifecycle (real Tk)."""

from __future__ import annotations

import pytest

from bw_gui.contracts.events import EventResult
from bw_gui.contracts.key_modifiers import TkBackend
from bw_gui.contracts.pointer import Axis, CancelReason, StepAccumulator, wheel_steps
from bw_gui.runtime import ui
from bw_gui.runtime.key_router import router_for
from bw_gui.runtime.pointer import bind_click, bind_drag, bind_wheel


@pytest.fixture
def canvas(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    top.geometry("200x120+30+30")
    widget = ui.Canvas(top, width=150, height=80)
    widget.pack()
    top.update()
    yield widget
    top.destroy()


@pytest.mark.parametrize(
    ("backend", "delta", "num", "expected"),
    [
        (TkBackend.WIN32, -120, None, 1.0),
        (TkBackend.WIN32, 240, None, -2.0),
        (TkBackend.WIN32, -30, None, 0.25),
        (TkBackend.X11, 0, 4, -1.0),
        (TkBackend.X11, 0, 5, 1.0),
        (TkBackend.AQUA, -3, None, 3.0),
        (TkBackend.WIN32, "??", None, 0.0),
    ],
)
def test_wheel_steps_normalisation(backend, delta, num, expected):
    assert wheel_steps(backend=backend, delta=delta, num=num) == expected


def test_accumulator_is_net_and_time_free():
    acc = StepAccumulator()
    assert [acc.add(Axis.VERTICAL, s) for s in (0.25, 0.25, 0.25, 0.25)] == [0, 0, 0, 1]
    assert acc.add(Axis.VERTICAL, 0.5) == 0
    assert acc.add(Axis.VERTICAL, -0.25) == 0  # counter-movement reduces the remainder
    assert acc.add(Axis.VERTICAL, 0.75) == 1
    assert [acc.add(Axis.VERTICAL, s) for s in (1.0, 1.0)] == [1, 1]  # whole notches stay exact


def test_bind_wheel_delivers_semantic_event_and_handled_stops(canvas):
    seen = []
    sub = bind_wheel(canvas, lambda e: (seen.append((e.steps, e.whole_steps, e.axis)), EventResult.HANDLED)[1])
    canvas.event_generate("<MouseWheel>", delta=-120)
    canvas.event_generate("<MouseWheel>", delta=-60)
    canvas.event_generate("<MouseWheel>", delta=-60)
    assert seen == [(1.0, 1, Axis.VERTICAL), (0.5, 0, Axis.VERTICAL), (0.5, 1, Axis.VERTICAL)]
    sub.remove()
    canvas.event_generate("<MouseWheel>", delta=-120)
    assert len(seen) == 3 and not sub.active


def test_bind_wheel_handled_blocks_router_scroll(canvas):
    observed = []
    router_sub = router_for(canvas).register_event("<MouseWheel>", lambda e: observed.append(1))
    try:
        bind_wheel(canvas, lambda e: EventResult.HANDLED)
        canvas.event_generate("<MouseWheel>", delta=-120)
        assert observed == []
    finally:
        router_sub.remove()


def test_bind_click_single_and_double(canvas):
    seen = []
    bind_click(canvas, lambda e: seen.append(e.count))
    bind_click(canvas, lambda e: seen.append(e.count), count=2)
    canvas.event_generate("<ButtonPress-1>", x=5, y=5)
    canvas.event_generate("<ButtonRelease-1>", x=5, y=5)
    canvas.event_generate("<ButtonPress-1>", x=5, y=5)
    assert seen == [1, 2]


def test_bind_click_rejects_invalid_count(canvas):
    with pytest.raises(ValueError):
        bind_click(canvas, lambda e: None, count=3)


def test_drag_lifecycle_release_outside_and_modifiers(canvas):
    events = []
    bind_drag(
        canvas,
        on_start=lambda e: events.append(("start", e.start_modifiers.alt)),
        on_move=lambda e: events.append(("move", e.modifiers.alt)),
        on_end=lambda e: events.append(("end", e.x_root, e.y_root)),
    )
    alt = 0x20000
    canvas.event_generate("<ButtonPress-1>", x=10, y=10, rootx=50, rooty=50, state=alt)
    canvas.event_generate("<B1-Motion>", x=20, y=20, rootx=60, rooty=60, state=0x100)
    canvas.event_generate("<ButtonRelease-1>", x=900, y=900, rootx=990, rooty=990)
    assert events == [("start", True), ("move", False), ("end", 990, 990)]


def test_drag_threshold_delays_start(canvas):
    events = []
    bind_drag(canvas, on_start=lambda e: events.append("start"), on_end=lambda e: events.append("end"), threshold=10)
    canvas.event_generate("<ButtonPress-1>", x=0, y=0, rootx=0, rooty=0)
    canvas.event_generate("<B1-Motion>", x=3, y=3, rootx=3, rooty=3, state=0x100)
    assert events == []
    canvas.event_generate("<B1-Motion>", x=15, y=0, rootx=15, rooty=0, state=0x100)
    canvas.event_generate("<ButtonRelease-1>", x=15, y=0, rootx=15, rooty=0)
    assert events == ["start", "end"]


def test_drag_escape_cancels_through_any_key_dispatcher(canvas):
    reasons = []
    bind_drag(canvas, on_cancel=reasons.append, on_end=lambda e: reasons.append("end"), cancel_on_escape=True)
    canvas.event_generate("<ButtonPress-1>", x=1, y=1, rootx=1, rooty=1)
    router = router_for(canvas)
    assert router.channel._dispatch_from_tcl(str(canvas), "Escape", "\x1b", "0") == "handled"
    assert reasons == [CancelReason.ESCAPE]
    canvas.event_generate("<ButtonRelease-1>", x=1, y=1, rootx=1, rooty=1)
    assert reasons == [CancelReason.ESCAPE]  # no end after cancel
    # the temporary gesture subscription is gone: Escape is an ordinary key again
    assert router.channel._dispatch_from_tcl(str(canvas), "Escape", "\x1b", "0") == ""


def test_drag_without_cancel_on_escape_ignores_escape(canvas):
    reasons = []
    bind_drag(canvas, on_cancel=reasons.append)
    canvas.event_generate("<ButtonPress-1>", x=1, y=1, rootx=1, rooty=1)
    assert router_for(canvas).channel._dispatch_from_tcl(str(canvas), "Escape", "\x1b", "0") == ""
    assert reasons == []


def test_drag_focus_loss_cancels(canvas):
    reasons = []
    bind_drag(canvas, on_cancel=reasons.append, cancel_on_escape=True)
    canvas.event_generate("<ButtonPress-1>", x=1, y=1, rootx=1, rooty=1)
    canvas.winfo_toplevel().event_generate("<FocusOut>")
    assert reasons == [CancelReason.FOCUS_LOST]
    assert router_for(canvas).channel._dispatch_from_tcl(str(canvas), "Escape", "\x1b", "0") == ""


def test_drag_exception_resets_and_stops_callbacks(canvas, _shared_tk_root):
    events = []
    reported = []
    original = _shared_tk_root.report_callback_exception
    _shared_tk_root.report_callback_exception = lambda *exc: reported.append(exc[0])
    try:
        bind_drag(canvas, on_start=lambda e: 1 / 0, on_end=lambda e: events.append("end"))
        canvas.event_generate("<ButtonPress-1>", x=1, y=1, rootx=1, rooty=1)
        canvas.event_generate("<ButtonRelease-1>", x=1, y=1, rootx=1, rooty=1)
    finally:
        _shared_tk_root.report_callback_exception = original
    assert reported == [ZeroDivisionError] and events == []


def test_pointer_subscriptions_invalidate_on_destroy(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    widget = ui.Canvas(top)
    subs = [bind_wheel(widget, lambda e: None), bind_click(widget, lambda e: None), bind_drag(widget)]
    top.destroy()
    assert not any(s.active for s in subs)


def test_on_global_click_observes_presses_in_every_toplevel(_shared_tk_root):
    from bw_gui.runtime import on_global_click

    top = ui.Toplevel(_shared_tk_root)
    canvas = ui.Canvas(top)
    canvas.pack()
    top.update()
    seen: list[object] = []
    subscription = on_global_click(_shared_tk_root, lambda event: seen.append(event.widget) or EventResult.HANDLED)
    try:
        canvas.event_generate("<ButtonPress-1>", x=3, y=3)
        top.update()
        assert seen == [canvas]
        subscription.remove()
        canvas.event_generate("<ButtonPress-1>", x=3, y=3)
        top.update()
        assert seen == [canvas]
    finally:
        top.destroy()


def test_on_global_click_owner_bounds_the_subscription(_shared_tk_root):
    """With ``owner`` the observer leaves the router when the owner is destroyed --
    a child's destroy (same toplevel tag) does not end it."""
    from bw_gui.runtime import on_global_click

    dialog = ui.Toplevel(_shared_tk_root)
    other = ui.Toplevel(_shared_tk_root)
    canvas = ui.Canvas(other)
    canvas.pack()
    child = ui.Frame(dialog)
    other.update()
    seen: list[object] = []
    subscription = on_global_click(_shared_tk_root, lambda event: seen.append(event.widget), owner=dialog)
    try:
        child.destroy()
        assert subscription.active
        canvas.event_generate("<ButtonPress-1>", x=3, y=3)
        other.update()
        assert seen == [canvas]
        dialog.destroy()
        assert not subscription.active
        canvas.event_generate("<ButtonPress-1>", x=3, y=3)
        other.update()
        assert seen == [canvas]
    finally:
        other.destroy()


def test_on_global_click_owner_may_be_a_delegating_wrapper(_shared_tk_root):
    """Popup wrappers delegate ``bind``/``str`` to their toplevel; the owner match is by path."""
    from bw_gui.runtime import on_global_click

    class _Wrapper:
        def __init__(self, toplevel):
            self._top = toplevel

        def __getattr__(self, name):
            return getattr(self._top, name)

        def __str__(self):
            return str(self._top)

    top = ui.Toplevel(_shared_tk_root)
    subscription = on_global_click(_shared_tk_root, lambda event: None, owner=_Wrapper(top))
    top.destroy()
    assert not subscription.active
