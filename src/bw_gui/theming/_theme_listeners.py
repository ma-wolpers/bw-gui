"""Theme listeners (``docs/THEME_CONTRACT.md``): widgets that follow a theme switch.

``configure_ttk_theme`` applies the ttk styles and then calls :func:`notify_theme_changed`
exactly once. Listeners registered with :func:`register_theme_listener` run after the
styles, in registration order, over a snapshot (a listener added during the phase runs
from the next switch on). A listener that raises does not stop the others; the error is
reported through the root's ``report_callback_exception``.

**Lifetime.** ``owner`` is mandatory and must be weak-referenceable. A bound method is
held as ``WeakMethod``; any other callable is held strongly and removed when ``owner`` is
finalized -- so it must not capture ``owner`` strongly (documented limit). ``remove()``
ends a registration earlier.

**Re-entrancy (decision 24).** A theme request (a ``configure_ttk_theme`` call) during
the listener phase is deferred; the last one wins and runs once, completely (styles +
listeners), after the phase. A deferred request equal to the state just applied (theme
key + intensity) is dropped. Within one sequence of follow-up switches bw-gui remembers
the applied states: a request that repeats one of them is a cycle -- the sequence stops
with a reported ``RuntimeError`` and the last applied state stays. Independently, at most
:data:`MAX_FOLLOW_UPS` follow-up switches run (a pure safety limit against endless
sequences of *different* states, e.g. a continuously changing intensity; normal use never
reaches it).
"""

from __future__ import annotations

import inspect
import sys
import weakref
from dataclasses import dataclass
from typing import Any, Callable

from bw_gui.contracts.subscription import Subscription

from ._color_math import is_dark_color
from ._theme_manager import get_theme, get_theme_intensity, normalize_theme_key

__all__ = ["MAX_FOLLOW_UPS", "ThemeChange", "defer_theme_request", "notify_theme_changed", "register_theme_listener"]

MAX_FOLLOW_UPS = 8


@dataclass(frozen=True)
class ThemeChange:
    """What a listener learns about the applied theme."""

    theme_key: str
    intensity: str
    is_dark: bool


class _Entry:
    __slots__ = ("resolve", "active")

    def __init__(self, resolve: Callable[[], Callable[[ThemeChange], object] | None]) -> None:
        self.resolve = resolve
        self.active = True


_entries: list[_Entry] = []
_phase = {"dispatching": False, "pending": None}


def register_theme_listener(callback: Callable[[ThemeChange], object], *, owner: object) -> Subscription:
    """Call ``callback(ThemeChange)`` after every theme switch while *owner* lives.

    Raises:
        TypeError: *owner* is ``None`` or not weak-referenceable.
    """
    if owner is None:
        raise TypeError("register_theme_listener needs an owner")
    try:
        weakref.ref(owner)
    except TypeError as exc:
        raise TypeError(f"theme listener owner must be weak-referenceable, got {type(owner).__name__}") from exc
    if inspect.ismethod(callback):
        method = weakref.WeakMethod(callback)
        entry = _Entry(method)
    else:
        entry = _Entry(lambda: callback)

    def _remove() -> None:
        entry.active = False
        if entry in _entries:
            _entries.remove(entry)

    _entries.append(entry)
    subscription = Subscription(_remove)
    weakref.finalize(owner, subscription.remove)
    return subscription


def _state(theme_key: str | None, intensity: str) -> tuple[str, str]:
    return (normalize_theme_key(theme_key), intensity)


def _report(root: Any, exc: BaseException) -> None:
    reporter = getattr(root, "report_callback_exception", None)
    if callable(reporter):
        reporter(type(exc), exc, exc.__traceback__)
    else:  # pragma: no cover - roots always have it; keep errors visible regardless
        print(f"bw-gui theme listener error: {exc!r}", file=sys.stderr)


def _dispatch(root: Any, state: tuple[str, str]) -> None:
    change = ThemeChange(state[0], state[1], is_dark_color(get_theme(state[0])["bg_main"]))
    _phase["dispatching"] = True
    try:
        for entry in list(_entries):
            callback = entry.resolve() if entry.active else None
            if callback is None:
                if entry in _entries and entry.active:
                    _entries.remove(entry)  # dead WeakMethod
                continue
            try:
                callback(change)
            except Exception as exc:  # noqa: BLE001 - listener errors are isolated by contract
                _report(root, exc)
    finally:
        _phase["dispatching"] = False


def defer_theme_request(root: Any, theme_key: str | None) -> bool:
    """Called first by ``configure_ttk_theme``: during the listener phase, defer the request.

    Returns ``True`` when the request was deferred (the caller must not apply it now).
    """
    if not _phase["dispatching"]:
        return False
    _phase["pending"] = (root, theme_key, get_theme_intensity())
    return True


def notify_theme_changed(root: Any, theme_key: str | None, *, apply: Callable[[Any, str | None], None]) -> None:
    """Run the listener phase for the applied theme, then any deferred follow-up switches.

    Args:
        root: Widget the switch was applied to (error reporting, follow-ups).
        theme_key: The theme just applied by ``apply``.
        apply: The style part of ``configure_ttk_theme`` (used for follow-up switches).
    """
    applied = [_state(theme_key, get_theme_intensity())]
    _dispatch(root, applied[-1])
    follow_ups = 0
    while _phase["pending"] is not None:
        pending_root, pending_key, intensity = _phase["pending"]
        _phase["pending"] = None
        state = _state(pending_key, intensity)
        if state == applied[-1]:
            continue
        if state in applied:
            _report(pending_root, RuntimeError(f"theme switch cycle detected: {applied + [state]}"))
            return
        follow_ups += 1
        if follow_ups > MAX_FOLLOW_UPS:
            _report(pending_root, RuntimeError(f"more than {MAX_FOLLOW_UPS} follow-up theme switches; stopped"))
            return
        apply(pending_root, pending_key)
        applied.append(state)
        _dispatch(pending_root, state)
