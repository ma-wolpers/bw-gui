"""Pointer contract, Tk side: hover over widgets and pointer hooks on canvas items.

``bind_hover`` replaces consumer ``<Enter>``/``<Leave>``/``<Motion>`` bindings;
``bind_canvas_item`` replaces ``canvas.tag_bind(tag, "<Button-1>" | "<Double-Button-1>" |
"<Enter>" | "<Leave>", ...)`` (``docs/POINTER_CONTRACT.md``). Handlers get
:class:`HoverEvent`/:class:`ClickEvent`; their result is ignored -- hover is never
consumed, and Tk runs canvas item bindings independently of the widget's bindtags, so
an item hook cannot stop widget-level pointer hooks either (1:1 to ``tag_bind``).
"""

from __future__ import annotations

from typing import Any, Callable

from bw_gui.contracts.pointer import Button, ClickEvent
from bw_gui.contracts.subscription import CompositeSubscription, Subscription
from bw_gui.contracts.widget_events import HoverEvent

from ._key_channel import detect_backend
from ._tk_identity import runtime_for
from .pointer import _bind, _click_event, _track

__all__ = ["bind_canvas_item", "bind_hover"]


def _hover_event(event: Any, widget: Any) -> HoverEvent:
    return HoverEvent(int(event.x), int(event.y), int(event.x_root), int(event.y_root), widget)


def bind_hover(
    widget: Any,
    *,
    on_enter: Callable[[HoverEvent], object] | None = None,
    on_leave: Callable[[HoverEvent], object] | None = None,
    on_motion: Callable[[HoverEvent], object] | None = None,
) -> Subscription:
    """Report the pointer entering, moving over and leaving *widget* (its own events only)."""
    path = str(widget)
    subs: list[Subscription] = []
    for sequence, callback in (("<Enter>", on_enter), ("<Leave>", on_leave), ("<Motion>", on_motion)):
        if callback is None:
            continue

        def _on_event(event: Any, *, _callback=callback) -> None:
            if str(event.widget) == path:
                _callback(_hover_event(event, event.widget))

        subs.append(_bind(widget, sequence, _on_event))
    if not subs:
        raise ValueError("bind_hover needs at least one of on_enter, on_leave, on_motion")
    return _track(widget, CompositeSubscription(subs))


def bind_canvas_item(
    canvas: Any,
    tag: str | int,
    *,
    on_click: Callable[[ClickEvent], object] | None = None,
    on_double_click: Callable[[ClickEvent], object] | None = None,
    on_enter: Callable[[HoverEvent], object] | None = None,
    on_leave: Callable[[HoverEvent], object] | None = None,
) -> Subscription:
    """Pointer hooks on the canvas items with *tag* (or item id), primary button.

    Like ``tag_bind`` without ``add``, a new hook for the same tag and kind **replaces**
    the previous one (re-rendering a graph rebinds its tags); the replaced callback is
    released. A double click reports ``on_click`` for the first press and
    ``on_double_click`` for the second (Tk multi-click recognition, like ``bind_click``).
    The hook lives until ``remove()`` or the canvas is destroyed.
    """
    backend = detect_backend(canvas)
    registry: dict[tuple[str, str, str], str] = runtime_for(canvas).part("canvas_item_hooks", lambda _rt: {})
    hooks = (
        ("<ButtonPress-1>", on_click, lambda e: _click_event(e, Button.PRIMARY, 1, canvas, backend)),
        ("<Double-ButtonPress-1>", on_double_click, lambda e: _click_event(e, Button.PRIMARY, 2, canvas, backend)),
        ("<Enter>", on_enter, lambda e: _hover_event(e, canvas)),
        ("<Leave>", on_leave, lambda e: _hover_event(e, canvas)),
    )
    subs: list[Subscription] = []
    for sequence, callback, make in hooks:
        if callback is None:
            continue
        key = (str(canvas), str(tag), sequence)
        previous = registry.pop(key, None)
        if previous is not None:
            _release(canvas, previous)

        def _on_event(event: Any, *, _callback=callback, _make=make) -> None:
            _callback(_make(event))

        funcid = canvas.tag_bind(tag, sequence, _on_event)
        registry[key] = funcid

        def _remove(*, _key=key, _funcid=funcid, _sequence=sequence) -> None:
            if registry.get(_key) != _funcid:
                return  # already replaced by a newer hook
            del registry[_key]
            try:
                canvas.tag_unbind(tag, _sequence, _funcid)
            except Exception:
                pass

        subs.append(Subscription(_remove))
    if not subs:
        raise ValueError("bind_canvas_item needs at least one hook")
    return _track(canvas, CompositeSubscription(subs))


def _release(canvas: Any, funcid: str) -> None:
    try:
        canvas.deletecommand(funcid)
    except Exception:
        pass
