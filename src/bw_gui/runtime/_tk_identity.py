"""Per-interpreter bw-gui runtime state, stored on the interpreter's ``tkinter.Tk`` root.

Decision 31: interpreter-wide registries (key router, scroll resolver, overlay
stack, subscription bookkeeping) live as a private attribute of the Python
``tkinter.Tk`` object, not in a global map keyed by ``root.tk`` (the
``_tkinter.tkapp`` object is not weak-referenceable). Every interpreter has exactly
one root ``.``; all widgets of an interpreter resolve to the same root object, so
"one router per interpreter" holds by construction. Several ``Tk()`` instances are
several interpreters with separate state. The state is dropped when the root is
destroyed.

:func:`interpreter_root` relies on tkinter internals (``Misc._root``); it is the
single place that does, verified by ``tests/test_tk_identity.py``.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

_ATTRIBUTE = "_bw_gui_runtime"


def interpreter_root(widget: Any) -> tk.Tk:
    """Return the ``tkinter.Tk`` root object of *widget*'s interpreter.

    Accepts any tkinter widget or an object delegating to one (``TkRootHost``,
    ``BwBaseWindow`` expose ``tk_root``).
    """
    root = getattr(widget, "tk_root", None)
    if isinstance(root, tk.Tk):
        return root
    if isinstance(widget, tk.Tk):
        return widget
    return widget._root()  # tkinter.Misc._root: follows .master up to the Tk instance


class InterpreterRuntime:
    """Container for the interpreter-wide registries of one Tk root."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._parts: dict[str, Any] = {}
        self._destroy_hooks: list[Callable[[], None]] = []

    def part(self, name: str, factory: Callable[["InterpreterRuntime"], Any]) -> Any:
        """Return the registry *name*, creating it once via *factory* (idempotent)."""
        if name not in self._parts:
            self._parts[name] = factory(self)
        return self._parts[name]

    def peek(self, name: str) -> Any:
        """Return the registry *name* if it exists, else ``None`` (never creates)."""
        return self._parts.get(name)

    def on_destroy(self, hook: Callable[[], None]) -> None:
        """Run *hook* when the root is destroyed (registries clean up there)."""
        self._destroy_hooks.append(hook)

    def _teardown(self) -> None:
        hooks, self._destroy_hooks = self._destroy_hooks, []
        for hook in reversed(hooks):
            try:
                hook()
            except Exception:  # teardown must not stop the remaining hooks
                pass
        self._parts.clear()


def runtime_for(widget: Any) -> InterpreterRuntime:
    """Return (creating once) the :class:`InterpreterRuntime` of *widget*'s interpreter."""
    root = interpreter_root(widget)
    state = root.__dict__.get(_ATTRIBUTE)
    if state is None:
        state = InterpreterRuntime(root)
        root.__dict__[_ATTRIBUTE] = state

        def _on_destroy(event: Any, *, _root: tk.Tk = root) -> None:
            if getattr(event, "widget", None) is not _root:
                return
            current = _root.__dict__.pop(_ATTRIBUTE, None)
            if current is not None:
                current._teardown()

        root.bind("<Destroy>", _on_destroy, add="+")
    return state


def existing_runtime(widget: Any) -> InterpreterRuntime | None:
    """Return the runtime of *widget*'s interpreter if one was created, else ``None``."""
    try:
        return interpreter_root(widget).__dict__.get(_ATTRIBUTE)
    except Exception:
        return None
