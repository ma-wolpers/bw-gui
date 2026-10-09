"""Widget-scoped shortcuts and the ``on_key`` stream (``WIDGET_EVENTS_CONTRACT.md``).

Bindtag order of a widget (decision 15/36)::

    widget -> bwkeys:<path> -> Class -> bwkeys-after:<path> -> toplevel -> all

* ``bwkeys:<path>`` (inserted directly after the widget's own path tag): first the
  widget's shortcut definitions; if one *executed*, ``on_key`` is not called for this
  event and the shortcut's result decides propagation. Otherwise the ``before``
  handlers run in registration order; the first ``HANDLED`` stops everything.
* Class tag: native Tk bindings (e.g. text insertion).
* ``bwkeys-after:<path>`` (inserted directly after the class tag, only when an
  ``after`` handler exists): ``phase="after"`` means *after successful propagation
  through all preceding bindtags* -- if anything before consumed the event (a
  shortcut or ``before`` handler returning ``HANDLED``, or a native class binding
  breaking), Tk never reaches this tag. When it is reached, the class bindings'
  effects (inserted character, native navigation) have happened.
"""

from __future__ import annotations

import itertools
from typing import Any, Callable

from bw_gui.contracts.events import EventResult, coerce_result
from bw_gui.contracts.key_event import KeyEvent
from bw_gui.contracts.subscription import Subscription

from ._key_channel import KeyChannel, KeyDispatch
from ._tk_identity import interpreter_root, runtime_for
from .shortcuts import PHASE_SHORTCUT, _ShortcutScope

__all__ = ["WidgetShortcutBinder", "on_key"]


class _WidgetKeyHub:
    """The two bw-gui tags of one widget with their shortcut scopes and ``on_key`` handlers."""

    def __init__(self, widget: Any) -> None:
        self.widget = widget
        self.path = str(widget)
        self.before_tag = f"bwkeys:{self.path}"
        self.after_tag = f"bwkeys-after:{self.path}"
        self.scopes: list[_ShortcutScope] = []
        self.before: list[tuple[int, Callable[[KeyEvent], object]]] = []
        self.after: list[tuple[int, Callable[[KeyEvent], object]]] = []
        self._seq = itertools.count()
        self._subscriptions: list[Subscription] = []
        root = interpreter_root(widget)
        self._insert_tag(self.before_tag, after=self.path)
        self.before_channel = KeyChannel(root, self.before_tag)
        self.before_channel.add(PHASE_SHORTCUT, self._dispatch_before)
        self.after_channel: KeyChannel | None = None

    def _insert_tag(self, tag: str, *, after: str) -> None:
        tags = list(self.widget.bindtags())
        if tag in tags:
            return
        index = tags.index(after) + 1 if after in tags else 1
        tags.insert(index, tag)
        self.widget.bindtags(tuple(tags))

    def ensure_after(self) -> None:
        if self.after_channel is not None:
            return
        self._insert_tag(self.after_tag, after=self.widget.winfo_class())
        self.after_channel = KeyChannel(interpreter_root(self.widget), self.after_tag)
        self.after_channel.add(PHASE_SHORTCUT, self._dispatch_after)

    @staticmethod
    def _run(handlers: list[tuple[int, Callable[[KeyEvent], object]]], event: KeyEvent) -> EventResult:
        for _n, handler in list(handlers):
            if coerce_result(handler(event)) is EventResult.HANDLED:
                return EventResult.HANDLED
        return EventResult.NOT_HANDLED

    def _dispatch_before(self, item: KeyDispatch) -> EventResult:
        for scope in list(self.scopes):
            result = scope.handle(item)
            if result is not None:
                return result
        return self._run(self.before, item.event)

    def _dispatch_after(self, item: KeyDispatch) -> EventResult:
        return self._run(self.after, item.event)

    def add_handler(self, phase: str, handler: Callable[[KeyEvent], object]) -> Subscription:
        if phase not in ("before", "after"):
            raise ValueError(f"phase must be 'before' or 'after', got {phase!r}")
        if phase == "after":
            self.ensure_after()
        bucket = self.before if phase == "before" else self.after
        entry = (next(self._seq), handler)
        bucket.append(entry)

        def _remove() -> None:
            if entry in bucket:
                bucket.remove(entry)

        subscription = Subscription(_remove)
        self._subscriptions.append(subscription)
        return subscription

    def teardown(self) -> None:
        for subscription in self._subscriptions:
            subscription._invalidate()
        self._subscriptions.clear()
        for scope in list(self.scopes):
            scope.dispose()
        self.before.clear()
        self.after.clear()
        self.before_channel.uninstall()
        if self.after_channel is not None:
            self.after_channel.uninstall()


def _hub_for(widget: Any) -> _WidgetKeyHub:
    runtime = runtime_for(widget)
    hubs: dict[str, _WidgetKeyHub] = runtime.part("widget_keys", lambda _rt: {})
    path = str(widget)
    hub = hubs.get(path)
    if hub is None or hub.widget is not widget:
        hub = hubs[path] = _WidgetKeyHub(widget)

        def _on_destroy(event: Any, *, _widget: Any = widget, _path: str = path) -> None:
            if event.widget is not _widget:
                return
            removed = hubs.pop(_path, None)
            if removed is not None:
                removed.teardown()

        widget.bind("<Destroy>", _on_destroy, add="+")
    return hub


class WidgetShortcutBinder(_ShortcutScope):
    """Shortcuts that apply only while key events are delivered to one widget.

    Same API and gating as ``WindowShortcutBinder``; the gating context uses the
    widget itself. Typical use: arrow keys on a canvas, Return/Escape in an entry,
    completion keys in a text editor (``allow_when_text_input=True``).
    """

    def __init__(self, widget: Any, **kwargs: Any) -> None:
        super().__init__(widget, **kwargs)
        self.widget = widget
        self._hub = _hub_for(widget)
        self._hub.scopes.append(self)

    def _peer_definitions(self):
        return [entry[0] for scope in self._hub.scopes for entry in scope._entries]

    def dispose(self) -> None:
        if self in self._hub.scopes:
            self._hub.scopes.remove(self)
        super().dispose()


def on_key(widget: Any, handler: Callable[[KeyEvent], object], *, phase: str = "before") -> Subscription:
    """Subscribe to every key press delivered to *widget* (see module docstring for routing).

    Args:
        handler: ``handler(KeyEvent) -> EventResult | None``; ``HANDLED`` stops the event.
        phase: ``"before"`` (ahead of native class bindings) or ``"after"``.
    """
    return _hub_for(widget).add_handler(phase, handler)
