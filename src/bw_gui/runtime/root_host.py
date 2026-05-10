from __future__ import annotations

from .primitives import ui


class TkRootHost:
    """Compose and expose a Tk root while delegating standard widget API calls.

    Consumers can hold app state on the host object and keep raw Tk access
    available through ``tk_root`` when needed by low-level integrations.
    """

    def __init__(self, root: ui.Tk | None = None):
        self._tk_root = root or ui.Tk()

    @property
    def tk_root(self) -> ui.Tk:
        """Return the composed root Tk instance."""
        return self._tk_root

    def __getattr__(self, name: str):
        """Delegate unknown attributes to the composed Tk root instance."""
        return getattr(self._tk_root, name)
