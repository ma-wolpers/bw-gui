"""Pointer contract, Tk side: ``bind_wheel``, ``bind_click``, ``bind_drag`` (``POINTER_CONTRACT.md``).

All hooks bind on the widget's own bw-gui tag ``bwkeys:<path>`` (directly after the
widget path, before the class tag) and return a :class:`Subscription` that is
invalidated when the widget is destroyed. Handlers return ``EventResult``;
``HANDLED`` stops the Tk event (bw-gui returns Tk's ``"break"``), which also keeps the
router's scroll resolver from scrolling an enclosing ``ScrollableFrame``.

Double clicks: ``count=2`` uses Tk's own multi-click recognition (system double-click
time and radius) on an internal raw ``<Double-ButtonPress-n>`` binding. Consumers see
no Tk syntax and no matching decision is delegated: per the dispatch-channel rule,
gesture recognition may use raw sequences. Semantics 1:1 to Tk: on a double click
``count=1`` fires for the first press and ``count=2`` for the second; without a
``count=2`` subscription the second press is an ordinary ``count=1`` press.
"""

from __future__ import annotations

from typing import Any, Callable

from bw_gui.contracts.events import EventResult, coerce_result
from bw_gui.contracts.key_modifiers import modifiers_from_event
from bw_gui.contracts.pointer import (
    Axis,
    Button,
    CancelReason,
    ClickEvent,
    DragEvent,
    StepAccumulator,
    WheelEvent,
    wheel_steps,
)
from bw_gui.contracts.subscription import CompositeSubscription, Subscription

from ._key_channel import detect_backend, gesture_slot
from ._tk_identity import interpreter_root, runtime_for
from .widget_keys import ensure_widget_tag

__all__ = ["bind_click", "bind_drag", "bind_wheel", "on_global_click", "wheel_subscribed"]


def _tk(result: object) -> str | None:
    return "break" if coerce_result(result) is EventResult.HANDLED else None


def _bind(widget: Any, sequence: str, func: Callable[[Any], object]) -> Subscription:
    """Bind *func* on the widget's bw-gui tag; removal unbinds exactly this script."""
    tag = ensure_widget_tag(widget)
    funcid = widget.bind_class(tag, sequence, func, add="+")

    def _remove() -> None:
        try:
            script = widget.tk.call("bind", tag, sequence)
            lines = [line for line in str(script).split("\n") if funcid not in line]
            widget.tk.call("bind", tag, sequence, "\n".join(lines))
        except Exception:
            pass
        # bind_class registers the command on the root's command list, so it must be
        # deleted through the root (otherwise root.destroy fails later).
        try:
            interpreter_root(widget).deletecommand(funcid)
        except Exception:
            pass

    return Subscription(_remove)


def _track(widget: Any, subscription: Subscription) -> Subscription:
    """Invalidate *subscription* when *widget* is destroyed."""

    def _on_destroy(event: Any) -> None:
        if event.widget is widget:
            subscription._invalidate()

    widget.bind("<Destroy>", _on_destroy, add="+")
    return subscription


def _wheel_registry(widget: Any) -> dict[str, int]:
    return runtime_for(widget).part("wheel_widgets", lambda _rt: {})


def wheel_subscribed(widget: Any) -> bool:
    """True if *widget* has an active ``bind_wheel`` subscription or is a member of a
    pointer group with a wheel handler (scroll resolver rule 2)."""
    runtime = runtime_for(widget)
    registry = runtime.peek("wheel_widgets")
    if registry and registry.get(str(widget)):
        return True
    group_tags = runtime.peek("wheel_group_tags")
    return bool(group_tags) and any(tag in group_tags for tag in widget.bindtags())


def bind_wheel(widget: Any, handler: Callable[[WheelEvent], object]) -> Subscription:
    """Subscribe to wheel events over *widget* (all modifier variants; X11 buttons 4/5)."""
    backend = detect_backend(widget)
    accumulator = StepAccumulator()

    def _on_wheel(event: Any) -> str | None:
        steps = wheel_steps(backend=backend, delta=getattr(event, "delta", 0), num=getattr(event, "num", None))
        if steps == 0.0:
            return None
        wheel = WheelEvent(
            steps=steps,
            whole_steps=accumulator.add(Axis.VERTICAL, steps),
            axis=Axis.VERTICAL,
            modifiers=modifiers_from_event(event, backend),
            x=int(event.x),
            y=int(event.y),
            x_root=int(event.x_root),
            y_root=int(event.y_root),
            widget=widget,
        )
        return _tk(handler(wheel))

    parts = [_bind(widget, "<MouseWheel>", _on_wheel)]
    if backend.value == "x11":
        parts += [_bind(widget, "<Button-4>", _on_wheel), _bind(widget, "<Button-5>", _on_wheel)]
    registry = _wheel_registry(widget)
    path = str(widget)
    registry[path] = registry.get(path, 0) + 1

    def _unregister() -> None:
        registry[path] = max(0, registry.get(path, 1) - 1)

    parts.append(Subscription(_unregister))
    return _track(widget, CompositeSubscription(parts))


def _click_event(event: Any, button: Button, count: int, widget: Any, backend) -> ClickEvent:
    return ClickEvent(
        button=button,
        count=count,
        modifiers=modifiers_from_event(event, backend),
        x=int(event.x),
        y=int(event.y),
        x_root=int(event.x_root),
        y_root=int(event.y_root),
        widget=widget,
    )


def bind_click(
    widget: Any, handler: Callable[[ClickEvent], object], *, button: Button = Button.PRIMARY, count: int = 1
) -> Subscription:
    """Subscribe to presses of *button* on *widget* (``count`` 1 or 2, see module docstring)."""
    if count not in (1, 2):
        raise ValueError("count must be 1 or 2")
    backend = detect_backend(widget)
    sequence = f"<ButtonPress-{int(button)}>" if count == 1 else f"<Double-ButtonPress-{int(button)}>"
    subscription = _bind(widget, sequence, lambda e: _tk(handler(_click_event(e, button, count, widget, backend))))
    return _track(widget, subscription)


def on_global_click(
    anchor: Any,
    handler: Callable[[ClickEvent], object],
    *,
    button: Button = Button.PRIMARY,
    owner: Any | None = None,
) -> Subscription:
    """Observe every press of *button* anywhere in *anchor*'s interpreter (all toplevels).

    Runs on the ``all`` router as an **observer** (``POINTER_CONTRACT.md``): it sees the
    press after the widget, class and toplevel bindtags, only if none of them consumed
    it, and it can never consume the press itself -- the handler's result is ignored.
    Typical use: commit an inline edit when the user clicks somewhere else, or close a
    dialog's selection overlay on a click outside it. The ``ClickEvent.widget`` is the
    widget that received the press.

    Args:
        anchor: Any widget of the interpreter.
        handler: ``handler(ClickEvent)``.
        button: Mouse button to observe.
        owner: Optional widget (or a wrapper delegating ``bind``/``str`` to one, like
            ``ScrollablePopupWindow``) whose lifetime bounds the subscription: when it is
            destroyed, the observer is removed from the router (``remove()``, not just
            invalidated -- the router outlives the owner). Without an owner the
            subscription lives as long as the interpreter. The owner only bounds the
            lifetime; it does not filter presses (filter on ``ClickEvent.widget``).

    Returns:
        A subscription; ``remove()`` ends it earlier (idempotent).
    """
    from .key_router import router_for

    backend = detect_backend(anchor)

    def _observe(event: Any) -> None:
        handler(_click_event(event, button, 1, getattr(event, "widget", None), backend))

    subscription = router_for(anchor).register_event(f"<Button-{int(button)}>", _observe)
    if owner is not None:
        owner_path = str(owner)

        def _on_owner_destroy(event: Any) -> None:
            # A toplevel's own tag also sees its descendants' <Destroy>: filter on the
            # owner's Tk path (not identity -- the owner may be a wrapper that delegates
            # ``bind``/``str`` to its toplevel, e.g. ``ScrollablePopupWindow``).
            if str(event.widget) == owner_path:
                subscription.remove()

        owner.bind("<Destroy>", _on_owner_destroy, add="+")
    return subscription


class _DragSession:
    """State of one press-drag-release on a widget (see ``bind_drag``)."""

    def __init__(self, widget: Any, event: Any, backend) -> None:
        self.widget = widget
        self.backend = backend
        self.start = (int(event.x_root), int(event.y_root))
        self.start_modifiers = modifiers_from_event(event, backend)
        self.started = False
        self.escape: Subscription | None = None

    def make(self, event: Any) -> DragEvent:
        return DragEvent(
            x=int(event.x),
            y=int(event.y),
            x_root=int(event.x_root),
            y_root=int(event.y_root),
            start_x_root=self.start[0],
            start_y_root=self.start[1],
            start_modifiers=self.start_modifiers,
            modifiers=modifiers_from_event(event, self.backend),
            widget=self.widget,
        )


def bind_drag(
    widget: Any,
    *,
    on_start: Callable[[DragEvent], object] | None = None,
    on_move: Callable[[DragEvent], object] | None = None,
    on_end: Callable[[DragEvent], object] | None = None,
    on_cancel: Callable[[CancelReason], object] | None = None,
    button: Button = Button.PRIMARY,
    threshold: int = 0,
    cancel_on_escape: bool = False,
) -> Subscription:
    """Press-drag-release lifecycle on *widget* (``POINTER_CONTRACT.md``).

    * Press creates a candidate; ``on_start`` fires at press (``threshold=0``) or on
      first exceeding *threshold* pixels.
    * Tk's implicit grab delivers motion/release to the pressed widget across widget
      and window borders; bw-gui never calls ``grab_set``.
    * Release (also outside the widget) -> ``on_end`` with valid root coordinates.
    * Focus loss of the toplevel -> ``on_cancel(FOCUS_LOST)``; Escape only with
      ``cancel_on_escape`` (temporary gesture subscription checked first by every bw-gui
      key dispatcher, so it works wherever focus is in the toplevel).
    * Widget destroyed -> state silently discarded. An exception in a callback resets
      the drag (reported by Tk) and no further callback of this drag runs.
    """
    backend = detect_backend(widget)
    state: dict[str, _DragSession | None] = {"session": None}

    def _finish() -> None:
        session = state["session"]
        state["session"] = None
        if session is not None and session.escape is not None:
            session.escape.remove()

    def _call(callback: Callable[..., object] | None, *args: Any) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:
            _finish()
            raise

    def _cancel(reason: CancelReason) -> None:
        if state["session"] is None:
            return
        _finish()
        _call(on_cancel, reason)

    def _begin(session: _DragSession, event: Any) -> None:
        session.started = True
        if cancel_on_escape:
            session.escape = gesture_slot(widget).push(lambda: _cancel(CancelReason.ESCAPE))
        _call(on_start, session.make(event))

    def _press(event: Any) -> None:
        session = state["session"] = _DragSession(widget, event, backend)
        if threshold <= 0:
            _begin(session, event)

    def _motion(event: Any) -> None:
        session = state["session"]
        if session is None:
            return
        if not session.started:
            dx, dy = int(event.x_root) - session.start[0], int(event.y_root) - session.start[1]
            if max(abs(dx), abs(dy)) < threshold:
                return
            _begin(session, event)
            return
        _call(on_move, session.make(event))

    def _release(event: Any) -> None:
        session = state["session"]
        if session is None:
            return
        started = session.started
        drag_event = session.make(event)
        _finish()
        if started:
            _call(on_end, drag_event)

    def _focus_out(event: Any) -> None:
        if state["session"] is not None and event.widget is widget.winfo_toplevel():
            _cancel(CancelReason.FOCUS_LOST)

    number = int(button)
    parts = [
        _bind(widget, f"<ButtonPress-{number}>", _press),
        _bind(widget, f"<B{number}-Motion>", _motion),
        _bind(widget, f"<ButtonRelease-{number}>", _release),
    ]
    toplevel = widget.winfo_toplevel()
    focus_id = toplevel.bind("<FocusOut>", _focus_out, add="+")

    def _unbind_focus() -> None:
        try:
            script = str(toplevel.tk.call("bind", str(toplevel), "<FocusOut>"))
            toplevel.tk.call("bind", str(toplevel), "<FocusOut>", "\n".join(l for l in script.split("\n") if focus_id not in l))
        except Exception:
            pass

    def _on_destroy(event: Any) -> None:
        if event.widget is widget:
            session = state["session"]
            state["session"] = None
            if session is not None and session.escape is not None:
                session.escape.remove()

    widget.bind("<Destroy>", _on_destroy, add="+")
    parts.append(Subscription(_unbind_focus))
    return _track(widget, CompositeSubscription(parts))
