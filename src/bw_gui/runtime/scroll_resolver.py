"""Wheel responsibility for ``ScrollableFrame`` (``SCROLLABILITY_CONTRACT.md``, decision 13).

Exactly one router handler (``all`` tag, wheel sequences) resolves which frame a wheel
event scrolls. Frames register their outer frame, canvas and scrollbar in a
per-interpreter registry ``path -> frame``; the candidate is always the **nearest
registered ScrollableFrame along the widget hierarchy** -- registration order and the
number of frames play no role. Per event:

1. Walk from ``event.widget`` up via ``.master`` up to and including its own toplevel,
   never beyond (64-step cap): a popup whose master sits in a frame of the main window
   does not scroll the main window (bugfix 10).
2. A native scrollable widget on the way, before the first frame candidate, is
   responsible if it can scroll in the wheel direction (``Text``, ``Listbox``,
   ``ttk.Treeview``) or always consumes the wheel (scrollbars, combobox), and so is a
   widget with its own ``bind_wheel`` subscription: no frame scrolls in addition
   (bugfix 8: Tk's class bindings do not ``break``).
3. The nearest frame candidate that overflows on its axis scrolls by the accumulated
   whole notches; a non-overflowing candidate passes the event to the next outer one
   (deliberate change). There is no chaining at the content end.
4. An event on a frame's outer frame or own scrollbar resolves to that frame
   (bugfix 9).
5. No candidate: nothing happens.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from bw_gui.contracts.pointer import Axis, StepAccumulator, wheel_steps
from bw_gui.contracts.subscription import Subscription

from ._key_channel import detect_backend
from ._tk_identity import runtime_for
from .key_router import router_for

_ORDER_SCROLL = 30
_ALWAYS_CONSUME = (tk.Scrollbar, ttk.Scrollbar, ttk.Combobox)
_YVIEW_NATIVE = (tk.Text, tk.Listbox, ttk.Treeview)


class ScrollResolver:
    """Per-interpreter wheel resolver for registered scroll frames."""

    def __init__(self, root: Any) -> None:
        self.root = root
        self.backend = detect_backend(root)
        self.frames: dict[str, Any] = {}
        self._accumulators: dict[str, StepAccumulator] = {}
        router = router_for(root)
        router.register_event("<MouseWheel>", self._on_wheel, order=_ORDER_SCROLL)
        if self.backend.value == "x11":
            router.register_event("<Button-4>", self._on_wheel, order=_ORDER_SCROLL)
            router.register_event("<Button-5>", self._on_wheel, order=_ORDER_SCROLL)

    def register(self, frame: Any, parts: list[Any]) -> Subscription:
        """Register *frame* under the paths of *parts* (outer frame, canvas, scrollbar)."""
        paths = [str(p) for p in parts]
        for path in paths:
            self.frames[path] = frame
        self._accumulators[str(frame)] = StepAccumulator()

        def _remove() -> None:
            for path in paths:
                if self.frames.get(path) is frame:
                    del self.frames[path]
            self._accumulators.pop(str(frame), None)

        return Subscription(_remove)

    @staticmethod
    def _native_can_scroll(widget: Any, steps: float) -> bool:
        try:
            first, last = (float(v) for v in widget.yview())
        except Exception:
            return False
        return last < 1.0 if steps > 0 else first > 0.0

    def _on_wheel(self, event: Any) -> bool:
        from .pointer import wheel_subscribed

        steps = wheel_steps(backend=self.backend, delta=getattr(event, "delta", 0), num=getattr(event, "num", None))
        widget = getattr(event, "widget", None)
        if steps == 0.0 or not isinstance(widget, tk.Misc):
            return False
        try:
            toplevel = widget.winfo_toplevel()
        except tk.TclError:
            return False
        current = widget
        for _ in range(64):
            frame = self.frames.get(str(current))
            if frame is not None:
                if frame.overflows():
                    accumulator = self._accumulators.setdefault(str(frame), StepAccumulator())
                    whole = accumulator.add(Axis.HORIZONTAL if frame.is_horizontal else Axis.VERTICAL, steps)
                    if whole:
                        frame.scroll_units(whole)
                    return True
            elif isinstance(current, _ALWAYS_CONSUME) or wheel_subscribed(current):
                return True
            elif isinstance(current, _YVIEW_NATIVE) and self._native_can_scroll(current, steps):
                return True
            if current is toplevel:
                return False
            current = getattr(current, "master", None)
            if current is None:
                return False
        return False


def scroll_resolver_for(widget: Any) -> ScrollResolver:
    """Return the interpreter's scroll resolver (created once)."""
    return runtime_for(widget).part("scroll_resolver", lambda rt: ScrollResolver(rt.root))
