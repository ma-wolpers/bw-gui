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
single place that does, verified by ``tests/test_key_router.py``.

:func:`is_toplevel` is the one rule for "is this object the toplevel boundary" when
walking a ``.master`` chain: by Tk path, because wrappers (``ScrollablePopupWindow``,
``BwBaseWindow``) stand in such chains instead of the Tk objects they delegate to.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

_ATTRIBUTE = "_bw_gui_runtime"


def _host_root(obj: Any) -> tk.Tk | None:
    """Return *obj* itself if it is the ``tk.Tk``, or the ``tk_root`` it wraps, else ``None``."""
    if isinstance(obj, tk.Tk):
        return obj
    root = getattr(obj, "tk_root", None)
    return root if isinstance(root, tk.Tk) else None


def interpreter_root(widget: Any) -> tk.Tk:
    """Return the ``tkinter.Tk`` root object of *widget*'s interpreter.

    Accepts any tkinter widget or an object delegating to one (``TkRootHost``,
    ``BwBaseWindow`` expose ``tk_root``). The end of the ``.master`` chain is resolved
    the same way: a widget created with a wrapper as parent (``ui.Toplevel(app)``)
    keeps the *wrapper* as ``.master``, so ``widget._root()`` stops at the wrapper,
    not at the ``tk.Tk``. Without this second resolution such widgets got a separate
    runtime in the wrapper's ``__dict__`` (e.g. popups missing from the root's overlay
    stack, so Escape no longer closed them).
    """
    root = _host_root(widget)
    if root is not None:
        return root
    end = widget._root()  # tkinter.Misc._root: follows .master up to the top of the chain
    root = _host_root(end)
    return root if root is not None else end


def is_toplevel(widget: Any) -> bool:
    """Whether *widget* is its own toplevel window, compared by Tk path, not identity.

    Used to stop walks up a ``.master`` chain at the window boundary (scroll resolver,
    ``on_visibility``). An identity check (``current is widget.winfo_toplevel()``)
    misses wrappers: children of a ``ScrollablePopupWindow`` carry the wrapper as
    ``.master``, which is not the Tk ``Toplevel`` object but delegates ``str`` and
    ``winfo_toplevel`` to it, so the path comparison recognises it.

    Args:
        widget: A Tk widget or a wrapper delegating ``winfo_toplevel``/``str`` to one.

    Raises:
        tkinter.TclError: *widget* was destroyed (callers decide how to treat that).
    """
    return str(widget.winfo_toplevel()) == str(widget)


class InterpreterRuntime:
    """Container for the interpreter-wide registries of one Tk root."""

    def __init__(self, root: tk.Tk) -> None:
        """Start with no registries; :meth:`part` creates each on first use.

        Args:
            root: The interpreter's ``tkinter.Tk`` object this runtime belongs to.
        """
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
        """Run the destroy hooks in reverse registration order, then drop every registry.

        Reverse order mirrors construction (later registries may depend on earlier
        ones). A failing hook is swallowed so the remaining ones still run; the hook
        list is swapped out first, so a second teardown is a no-op.
        """
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
            """Tear the runtime down when the root itself is destroyed.

            ``<Destroy>`` on the root's path tag also fires for every descendant, so
            only the root's own event counts.
            """
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
