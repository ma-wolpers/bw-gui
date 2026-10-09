"""Common lifecycle handle for every bw-gui event registration (``SUBSCRIPTION_CONTRACT.md``).

Every hook (shortcut bindings, ``on_key``, pointer hooks, lifecycle hooks, selection
hooks, theme listeners) returns a :class:`Subscription`:

* ``remove()`` is idempotent;
* ``active`` tells whether it is still registered;
* the owner invalidates it automatically when the target widget is destroyed;
* after removal bw-gui keeps no strong reference to the handler or widget
  (the removal callback is dropped on first use).
"""

from __future__ import annotations

from typing import Callable


class Subscription:
    """Idempotent removal handle for one registration."""

    __slots__ = ("_remove", "_active", "__weakref__")

    def __init__(self, remove: Callable[[], None] | None) -> None:
        """Create a handle; *remove* performs the actual unregistration (called at most once)."""
        self._remove = remove
        self._active = remove is not None

    @property
    def active(self) -> bool:
        """True while the registration is in effect."""
        return self._active

    def remove(self) -> None:
        """Unregister (no-op when already removed or invalidated)."""
        if not self._active:
            return
        self._active = False
        remove, self._remove = self._remove, None
        if remove is not None:
            remove()

    def _invalidate(self) -> None:
        """Mark as removed without calling back (target already gone); drops references."""
        self._active = False
        self._remove = None


class CompositeSubscription(Subscription):
    """A subscription that removes several child subscriptions together."""

    __slots__ = ("_children",)

    def __init__(self, children: list[Subscription]) -> None:
        self._children = list(children)
        super().__init__(self._remove_children)

    def _remove_children(self) -> None:
        children, self._children = self._children, []
        for child in children:
            child.remove()
