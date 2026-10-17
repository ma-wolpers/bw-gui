"""Shared pointer and focus behaviour for many widgets on one bw-gui tag (``POINTER_CONTRACT.md``).

``bind_click``/``bind_wheel`` give each widget its own ``bwkeys:<path>`` tag, a key
channel and ``<Destroy>`` bookkeeping. That is right for single widgets, but a table
that rebuilds hundreds or thousands of cells (zoom, re-layout) pays for it on every
rebuild -- measured: ~45 µs extra per widget to bind and ~130 µs extra to destroy.

A :class:`PointerGroup` binds each gesture **once** on its own tag
``bwptr:<name>:<n>``; :meth:`PointerGroup.add` only inserts that tag into a member's
bindtags (directly after the widget path and its ``bwkeys`` tag, before the class
tag -- the same position as ``bind_click``). Handlers receive the usual
``ClickEvent``/``WheelEvent``/``FocusChange`` whose ``widget`` is the member that got the
event (focus: table cells that commit on focus loss pay the same per-widget cost).

Semantics equal ``bind_click``/``bind_wheel`` (``HANDLED`` stops the Tk event, Tk's own
multi-click recognition for ``count=2``, normalised wheel steps); differences, by
design: one wheel accumulator for the whole group, and no per-member lifecycle --
destroyed members simply disappear with their bindtags. The group lives until
:meth:`PointerGroup.dispose` or until the interpreter ends.
"""

from __future__ import annotations

import itertools
from typing import Any, Callable

from bw_gui.contracts.key_modifiers import modifiers_from_event
from bw_gui.contracts.pointer import Axis, Button, ClickEvent, StepAccumulator, WheelEvent, wheel_steps
from bw_gui.contracts.subscription import Subscription
from bw_gui.contracts.widget_events import FocusChange

from ._key_channel import detect_backend
from ._tk_identity import interpreter_root, runtime_for
from .pointer import _tk

__all__ = ["PointerGroup", "wheel_group_tags"]

_counter = itertools.count(1)


def wheel_group_tags(widget: Any) -> set[str]:
    """Tags of the interpreter's pointer groups that have a wheel handler (scroll resolver rule 2)."""
    return runtime_for(widget).part("wheel_group_tags", lambda _rt: set())


class PointerGroup:
    """One shared bw-gui pointer tag for many widgets (see module docstring)."""

    def __init__(self, anchor: Any, name: str) -> None:
        """Create an empty group.

        Args:
            anchor: Any widget of the interpreter.
            name: Readable part of the tag (diagnostics only; uniqueness is added).
        """
        self._root = interpreter_root(anchor)
        self._backend = detect_backend(anchor)
        self.tag = f"bwptr:{name}:{next(_counter)}"
        self._accumulator = StepAccumulator()
        self._funcids: list[tuple[str, str]] = []
        self.disposed = False

    # -- membership --------------------------------------------------------------------

    def add(self, widget: Any) -> None:
        """Make *widget* a member (idempotent): insert the group tag before its class tag."""
        tags = list(widget.bindtags())
        if self.tag in tags:
            return
        path = str(widget)
        index = tags.index(path) + 1 if path in tags else 1
        if index < len(tags) and tags[index] == f"bwkeys:{path}":
            index += 1
        tags.insert(index, self.tag)
        widget.bindtags(tuple(tags))

    def discard(self, widget: Any) -> None:
        """Remove *widget* from the group (idempotent)."""
        tags = list(widget.bindtags())
        if self.tag in tags:
            tags.remove(self.tag)
            widget.bindtags(tuple(tags))

    # -- gestures ----------------------------------------------------------------------

    def _bind(self, sequence: str, func: Callable[[Any], object]) -> Subscription:
        funcid = self._root.bind_class(self.tag, sequence, func, add="+")
        self._funcids.append((sequence, funcid))

        def _remove() -> None:
            try:
                script = str(self._root.tk.call("bind", self.tag, sequence))
                kept = [line for line in script.split("\n") if funcid not in line]
                self._root.tk.call("bind", self.tag, sequence, "\n".join(kept))
                self._root.deletecommand(funcid)
            except Exception:
                pass

        return Subscription(_remove)

    def on_click(
        self, handler: Callable[[ClickEvent], object], *, button: Button = Button.PRIMARY, count: int = 1
    ) -> Subscription:
        """Subscribe to presses of *button* on any member (``count`` 1 or 2, like ``bind_click``)."""
        if count not in (1, 2):
            raise ValueError("count must be 1 or 2")
        sequence = f"<ButtonPress-{int(button)}>" if count == 1 else f"<Double-ButtonPress-{int(button)}>"

        def _on_press(event: Any) -> str | None:
            click = ClickEvent(
                button=button,
                count=count,
                modifiers=modifiers_from_event(event, self._backend),
                x=int(event.x),
                y=int(event.y),
                x_root=int(event.x_root),
                y_root=int(event.y_root),
                widget=event.widget,
            )
            return _tk(handler(click))

        return self._bind(sequence, _on_press)

    def on_wheel(self, handler: Callable[[WheelEvent], object]) -> Subscription:
        """Subscribe to wheel events over any member (one accumulator for the group)."""

        def _on_wheel(event: Any) -> str | None:
            steps = wheel_steps(backend=self._backend, delta=getattr(event, "delta", 0), num=getattr(event, "num", None))
            if steps == 0.0:
                return None
            wheel = WheelEvent(
                steps=steps,
                whole_steps=self._accumulator.add(Axis.VERTICAL, steps),
                axis=Axis.VERTICAL,
                modifiers=modifiers_from_event(event, self._backend),
                x=int(event.x),
                y=int(event.y),
                x_root=int(event.x_root),
                y_root=int(event.y_root),
                widget=event.widget,
            )
            return _tk(handler(wheel))

        parts = [self._bind("<MouseWheel>", _on_wheel)]
        if self._backend.value == "x11":
            parts += [self._bind("<Button-4>", _on_wheel), self._bind("<Button-5>", _on_wheel)]
        tags = wheel_group_tags(self._root)
        tags.add(self.tag)

        def _remove() -> None:
            for part in parts:
                part.remove()
            tags.discard(self.tag)

        return Subscription(_remove)

    def on_focus_change(
        self,
        *,
        on_gained: Callable[[FocusChange], object] | None = None,
        on_lost: Callable[[FocusChange], object] | None = None,
    ) -> Subscription:
        """Report keyboard focus gained/lost by any member (``FocusChange.widget`` = the member).

        Same semantics as ``on_focus_change`` of a single widget (every Tk focus event,
        whatever its notify detail; the result is ignored), but bound once for the whole
        group -- for tables whose cells commit on focus loss. Several callbacks of the
        same kind run in subscription order.
        """
        if on_gained is None and on_lost is None:
            raise ValueError("on_focus_change needs on_gained and/or on_lost")
        parts: list[Subscription] = []
        for sequence, callback, gained in (("<FocusIn>", on_gained, True), ("<FocusOut>", on_lost, False)):
            if callback is None:
                continue

            def _on_focus(event: Any, *, _callback=callback, _gained=gained) -> None:
                _callback(FocusChange(_gained, event.widget))

            parts.append(self._bind(sequence, _on_focus))

        def _remove() -> None:
            for part in parts:
                part.remove()

        return Subscription(_remove)

    def dispose(self) -> None:
        """Remove every gesture binding of the group (idempotent); members keep a dead tag."""
        if self.disposed:
            return
        self.disposed = True
        wheel_group_tags(self._root).discard(self.tag)
        for sequence, funcid in self._funcids:
            try:
                self._root.tk.call("bind", self.tag, sequence, "")
                self._root.deletecommand(funcid)
            except Exception:
                pass
        self._funcids.clear()
