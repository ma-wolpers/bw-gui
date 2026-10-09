"""One bw-gui-owned keyboard entry on a bindtag (``KEYBINDING_CONTRACT.md``, decisions 25/32).

A :class:`KeyChannel` binds exactly **one** ``<KeyPress>`` catch-all script on its
bindtag. The script is a constant Tcl prefix calling a registered dispatcher
command; when the dispatcher returns ``"handled"`` the script ``break``s, otherwise
Tk continues with the next bindtag. Tk's sequence matcher therefore never decides
which shortcut applies: every matching decision is made by
``bw_gui.contracts.key_spec.matches`` in Python.

Handlers are ordered by ``(phase, registration order)``. Observer phases always run
and cannot consume; for all other phases the first ``HANDLED`` ends processing.
Before any phase, an active gesture (e.g. a drag with ``cancel_on_escape``) gets the
chance to consume an exact Escape (drag contract).
"""

from __future__ import annotations

import itertools
import re
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable

from bw_gui.contracts.events import EventResult, coerce_result
from bw_gui.contracts.key_event import KeyEvent, RawKey, classify_key
from bw_gui.contracts.key_modifiers import TkBackend
from bw_gui.contracts.key_spec import Key, KeyIdentity, KeySpec, matches
from bw_gui.contracts.subscription import Subscription

from ._tk_identity import runtime_for

_ESCAPE = KeySpec(Key.ESCAPE)
_counter = itertools.count(1)
_KEYBOARD_SEQUENCE = re.compile(r"^<(?:[A-Za-z0-9]+-)*(?:Key|KeyPress)(?:-[^>]+)?>$")


def is_keyboard_press_sequence(sequence: str) -> bool:
    """True for a Tk key-press sequence as reported by ``bind <tag>`` (not KeyRelease).

    Tk reports printable single-key bindings in their bare form (``bind t a`` is
    listed as ``"a"``), so one-character sequences count as key presses too.
    """
    if len(sequence) == 1:
        return True
    return bool(_KEYBOARD_SEQUENCE.match(sequence)) and "KeyRelease" not in sequence


def detect_backend(widget: tk.Misc) -> TkBackend:
    """Return the Tk backend of *widget*'s interpreter (``tk windowingsystem``)."""
    from bw_gui.contracts.key_modifiers import backend_for_platform, backend_for_windowing_system

    try:
        return backend_for_windowing_system(widget.tk.call("tk", "windowingsystem"))
    except Exception:
        return backend_for_platform()


@dataclass(frozen=True)
class KeyDispatch:
    """What a channel handler receives for one key press."""

    event: KeyEvent
    identity: KeyIdentity
    widget: Any
    tag: str


Handler = Callable[[KeyDispatch], object]
PHASE_OBSERVER = 0


class _GestureSlot:
    """Interpreter-wide stack of active gestures that consume an exact Escape."""

    def __init__(self) -> None:
        self.cancelers: list[Callable[[], None]] = []

    def push(self, cancel: Callable[[], None]) -> Subscription:
        self.cancelers.append(cancel)

        def _remove() -> None:
            if cancel in self.cancelers:
                self.cancelers.remove(cancel)

        return Subscription(_remove)


def gesture_slot(widget: Any) -> _GestureSlot:
    """Return the interpreter's gesture slot (used by ``bind_drag``)."""
    return runtime_for(widget).part("gestures", lambda _rt: _GestureSlot())


class KeyChannel:
    """The single keyboard catch-all of one bindtag, dispatching to ordered handlers."""

    def __init__(self, root: tk.Misc, tag: str, *, allow_foreign: Callable[[str], bool] | None = None) -> None:
        """Install the channel on *tag*.

        Raises:
            ValueError: If *tag* already carries a foreign keyboard binding (the
                channel would otherwise be masked or mask it silently); *allow_foreign*
                may whitelist sequences (the router uses it for Tk defaults).
        """
        self.root = root
        self.tag = tag
        self.backend = detect_backend(root)
        self._handlers: list[tuple[int, int, Handler]] = []
        self._seq = itertools.count()
        self.command = f"::bwgui::kd_{next(_counter)}"
        for sequence in self._bound_sequences():
            if is_keyboard_press_sequence(sequence) and not (allow_foreign and allow_foreign(sequence)):
                raise ValueError(f"Bindtag {tag!r} already has a foreign keyboard binding {sequence!r}")
        root.tk.createcommand(self.command, self._dispatch_from_tcl)
        self.prefix = f'if {{[{self.command} %W %K %A %s] eq "handled"}} break'
        root.tk.call("bind", tag, "<KeyPress>", self.prefix)
        self._installed = True

    def _bound_sequences(self) -> tuple[str, ...]:
        return tuple(str(s) for s in self.root.tk.splitlist(self.root.tk.call("bind", self.tag)))

    def add(self, phase: int, handler: Handler) -> Subscription:
        """Register *handler* in *phase* (lower phases run first)."""
        entry = (phase, next(self._seq), handler)
        self._handlers.append(entry)
        self._handlers.sort(key=lambda item: (item[0], item[1]))

        def _remove() -> None:
            if entry in self._handlers:
                self._handlers.remove(entry)

        return Subscription(_remove)

    @property
    def is_empty(self) -> bool:
        """True when no handler is registered."""
        return not self._handlers

    def uninstall(self) -> None:
        """Remove the Tk binding and Tcl command (idempotent)."""
        if not self._installed:
            return
        self._installed = False
        try:
            if self.root.tk.call("bind", self.tag, "<KeyPress>") == self.prefix:
                self.root.tk.call("bind", self.tag, "<KeyPress>", "")
            self.root.tk.deletecommand(self.command)
        except tk.TclError:
            pass
        self._handlers.clear()

    def _widget(self, path: str) -> Any:
        try:
            return self.root.nametowidget(path)
        except (KeyError, tk.TclError):
            return None

    def _dispatch_from_tcl(self, path: str, keysym: str, char: str, state: str) -> str:
        """Tcl entry point; returns ``"handled"`` to stop propagation."""
        try:
            numeric_state: object = int(state)
        except (TypeError, ValueError):
            numeric_state = state
        widget = self._widget(path)
        event, identity = classify_key(RawKey(keysym, char, numeric_state), self.backend, widget)
        return "handled" if self.dispatch(KeyDispatch(event, identity, widget, self.tag)) is EventResult.HANDLED else ""

    def dispatch(self, item: KeyDispatch) -> EventResult:
        """Run gestures, observers and handlers for one key press (snapshot of handlers)."""
        slot = runtime_for(self.root).peek("gestures")
        if slot is not None and slot.cancelers and matches(_ESCAPE, item.identity):
            slot.cancelers[-1]()
            return EventResult.HANDLED
        for phase, _order, handler in list(self._handlers):
            try:
                result = handler(item)
                outcome = EventResult.NOT_HANDLED if phase == PHASE_OBSERVER else coerce_result(result)
            except Exception:
                # Reported, and the event's processing ends (no double actions), except
                # for observers, which never end the observer phase.
                self.root.report_callback_exception(*_exc_info())
                if phase == PHASE_OBSERVER:
                    continue
                return EventResult.HANDLED
            if outcome is EventResult.HANDLED:
                return EventResult.HANDLED
        return EventResult.NOT_HANDLED


def _exc_info():
    import sys

    return sys.exc_info()
