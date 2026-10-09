"""Text-input context: does a widget accept text input *right now*? (``KEYBINDING_CONTRACT.md``).

Semantics: a widget accepts text input when a key without shortcut modifier would
insert or delete text in it. The built-in table is closed, because Tk has no other
text-capable classes:

* ``Entry``/``ttk.Entry``/``Spinbox``/``ttk.Spinbox`` unless ``disabled``/``readonly``
* ``ttk.Combobox`` unless ``readonly``
* ``Text`` when its state is ``normal``

Custom widgets take part only via the protocol (a ``bw_accepts_text_input()``
method) or :func:`register_text_input`; any other widget is never text input. The
event widget is checked (falling back to the focus widget); there is no ancestor walk.
Deliberate change against the former class-only heuristic: a read-only combobox and a
disabled entry no longer count as text input.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from bw_gui.contracts.subscription import Subscription

from ._tk_identity import runtime_for

_ENTRY_LIKE = (tk.Entry, ttk.Entry, tk.Spinbox, ttk.Spinbox)


def _state_of(widget: Any) -> str:
    try:
        return str(widget.cget("state"))
    except (tk.TclError, AttributeError):
        return "normal"


def _registry(widget: Any) -> dict[str, Callable[[], bool]]:
    return runtime_for(widget).part("text_input", lambda _rt: {})


def register_text_input(widget: Any, predicate: Callable[[], bool] | None = None) -> Subscription:
    """Declare *widget* (a custom editor) as text input, optionally conditionally.

    Returns a subscription; it is removed automatically when the widget is destroyed.
    """
    registry = _registry(widget)
    path = str(widget)
    registry[path] = predicate or (lambda: True)

    def _remove() -> None:
        registry.pop(path, None)

    subscription = Subscription(_remove)
    widget.bind("<Destroy>", lambda e: subscription.remove() if e.widget is widget else None, add="+")
    return subscription


def accepts_text_input(widget: Any) -> bool:
    """Return True if *widget* currently accepts text input (see module docstring)."""
    if widget is None:
        return False
    method = getattr(widget, "bw_accepts_text_input", None)
    if callable(method):
        return bool(method())
    if isinstance(widget, tk.Misc):
        try:
            registry = runtime_for(widget).peek("text_input")
        except Exception:
            registry = None
        if registry and str(widget) in registry:
            return bool(registry[str(widget)]())
    if isinstance(widget, ttk.Combobox):
        return _state_of(widget) not in ("disabled", "readonly")
    if isinstance(widget, _ENTRY_LIKE):
        state = _state_of(widget)
        if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox):
            try:
                if widget.instate(["disabled"]) or widget.instate(["readonly"]):
                    return False
            except tk.TclError:
                pass
        return state not in ("disabled", "readonly")
    if isinstance(widget, tk.Text):
        return _state_of(widget) == "normal"
    return False
