"""The single owner of the ``all`` bindtag (``KEYBINDING_CONTRACT.md``, decisions 25/31/32).

One :class:`AllTagRouter` per Tk interpreter, stored on the interpreter's root
(decision 31) and installed by ``TkRootHost`` directly after ``Tk()`` (step 2-0), before
any consumer code runs. It is the only code that writes bindings on ``all``.

Keyboard
    * A ``KeyChannel`` binds the ``<KeyPress>`` catch-all with the dispatcher prefix.
    * **TK_DEFAULT wrapping (decision 32):** every keyboard-press sequence and every
      virtual event present on ``all`` at installation time is by definition a Tk
      default. Each gets the script ``prefix + "\\n" + original``: the constant
      dispatcher line followed by the *verbatim* original (read as one opaque Tcl
      string via ``bind all S``, including ``+``-appended parts; never parsed,
      escaped or formatted in Python). Tk's own matcher keeps choosing which binding
      runs; the dispatcher runs exactly once per key press, and only on
      ``NOT_HANDLED`` does the original of exactly that binding follow. bw-gui never
      re-implements Tk's matcher. Key-release defaults are left untouched (no bw-gui
      role handles releases).
    * Roles in fixed order: ``OBSERVER`` (all run, result ignored) ->
      ``APP_SHORTCUT`` -> ``MENU_MNEMONIC``; then the wrapped Tk default.
      ``APP_SHORTCUT`` before ``MENU_MNEMONIC`` reproduces today's outcome (a
      concrete ``bind_all("<Alt-z>")`` beat the generic menu ``<Alt-KeyPress>`` by Tk
      specificity) but is now guaranteed instead of depending on Tk.
    * :meth:`AllTagRouter.verify` re-reads ``bind all`` and reports every keyboard or
      virtual sequence that does not carry the wrapper prefix.

Other event types on ``all``
    Pointer-press and focus observers (menu watchdog) and the wheel scroll resolver
    use one Python ``bind_all`` fan-out per sequence, also owned here.
"""

from __future__ import annotations

import itertools
import tkinter as tk
from typing import Any, Callable

from bw_gui.contracts.subscription import Subscription

from ._key_channel import PHASE_OBSERVER, KeyChannel, KeyDispatch, is_keyboard_press_sequence
from ._tk_identity import interpreter_root, runtime_for

ROLE_OBSERVER = PHASE_OBSERVER
ROLE_APP_SHORTCUT = 10
ROLE_MENU_MNEMONIC = 20


def _is_wrappable(sequence: str) -> bool:
    return sequence.startswith("<<") or is_keyboard_press_sequence(sequence)


class _Fanout:
    """One Python ``bind_all`` for a non-keyboard sequence with ordered handlers."""

    def __init__(self, root: tk.Misc, sequence: str) -> None:
        self.root = root
        self.sequence = sequence
        self.handlers: list[tuple[int, int, Callable[[Any], object]]] = []
        self._seq = itertools.count()
        self._funcid = root.bind_all(sequence, self._dispatch, add="+")

    def add(self, order: int, handler: Callable[[Any], object]) -> Subscription:
        entry = (order, next(self._seq), handler)
        self.handlers.append(entry)
        self.handlers.sort(key=lambda item: (item[0], item[1]))

        def _remove() -> None:
            if entry in self.handlers:
                self.handlers.remove(entry)

        return Subscription(_remove)

    def _dispatch(self, event: Any) -> None:
        for order, _n, handler in list(self.handlers):
            try:
                result = handler(event)
            except Exception:
                self.root.report_callback_exception(*__import__("sys").exc_info())
                continue
            if order != ROLE_OBSERVER and result:
                return None
        return None

    def uninstall(self) -> None:
        try:
            self.root.unbind_all(self.sequence)
        except tk.TclError:
            pass
        self.handlers.clear()


class AllTagRouter:
    """Owner of every binding on the ``all`` tag of one interpreter."""

    def __init__(self, root: tk.Tk) -> None:
        """Wrap the Tk defaults found on ``all`` and install the keyboard catch-all."""
        self.root = root
        tk_app = root.tk
        sequences = [str(s) for s in tk_app.splitlist(tk_app.call("bind", "all"))]
        self.originals: dict[str, str] = {
            seq: str(tk_app.call("bind", "all", seq)) for seq in sequences if _is_wrappable(seq)
        }
        self.channel = KeyChannel(root, "all", allow_foreign=lambda seq: seq in self.originals)
        for sequence, original in self.originals.items():
            tk_app.call("bind", "all", sequence, self.channel.prefix + "\n" + original)
        self._fanouts: dict[str, _Fanout] = {}
        self._owners: dict[int, list[Subscription]] = {}

    # -- keyboard roles ------------------------------------------------------------

    def register(self, role: int, handler: Callable[[KeyDispatch], object], *, owner: object = None) -> Subscription:
        """Register a keyboard handler in *role* (``ROLE_*``); returns its subscription."""
        subscription = self.channel.add(role, handler)
        if owner is not None:
            self._owners.setdefault(id(owner), []).append(subscription)
        return subscription

    def remove_owner(self, owner: object) -> None:
        """Remove every registration made with *owner*."""
        for subscription in self._owners.pop(id(owner), []):
            subscription.remove()

    # -- other event types ---------------------------------------------------------

    def register_event(self, sequence: str, handler: Callable[[Any], object], *, order: int = ROLE_OBSERVER) -> Subscription:
        """Register a handler for a non-keyboard ``all`` sequence (observer by default).

        Non-observer handlers stop the fan-out by returning a truthy value.
        """
        if _is_wrappable(sequence):
            raise ValueError(f"{sequence!r} is a keyboard sequence; use register() with a role")
        fanout = self._fanouts.get(sequence)
        if fanout is None:
            fanout = self._fanouts[sequence] = _Fanout(self.root, sequence)
        return fanout.add(order, handler)

    # -- diagnostics / lifecycle -----------------------------------------------------

    def verify(self) -> list[str]:
        """Return keyboard/virtual sequences on ``all`` that do not start with the wrapper prefix."""
        tk_app = self.root.tk
        findings = []
        for seq in (str(s) for s in tk_app.splitlist(tk_app.call("bind", "all"))):
            if not (_is_wrappable(seq) or seq == "<KeyPress>"):
                continue
            first_line = str(tk_app.call("bind", "all", seq)).split("\n", 1)[0]
            if first_line != self.channel.prefix:
                findings.append(seq)
        return findings

    def uninstall(self) -> None:
        """Restore every original Tk default verbatim and drop all handlers (idempotent)."""
        tk_app = self.root.tk
        for sequence, original in self.originals.items():
            try:
                tk_app.call("bind", "all", sequence, original)
            except tk.TclError:
                pass
        self.channel.uninstall()
        for fanout in self._fanouts.values():
            fanout.uninstall()
        self._fanouts.clear()
        self._owners.clear()


def router_for(widget: Any) -> AllTagRouter:
    """Return the interpreter's router, installing it once (idempotent)."""

    def _create(runtime: Any) -> AllTagRouter:
        router = AllTagRouter(runtime.root)
        runtime.on_destroy(router.uninstall)
        return router

    return runtime_for(widget).part("router", _create)


def install_router(root: tk.Tk) -> AllTagRouter:
    """Install the router on a fresh root (called by ``TkRootHost`` right after ``Tk()``)."""
    return router_for(interpreter_root(root))
