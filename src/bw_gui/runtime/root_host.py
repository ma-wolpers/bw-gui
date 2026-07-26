"""TkRootHost — a thin composition wrapper around the Tk root window.

Rather than subclassing ``tk.Tk`` directly, bw-gui composes the root window
as an internal attribute. This keeps the Tk class hierarchy flat and avoids
multiple-inheritance complications when combining Tk with Python mixins.

The host exposes the raw ``tk_root`` property for code that needs direct Tk
access, and delegates all unknown attribute lookups to it so callers can use
the host object wherever a Tk root is expected (e.g. as a parent for widgets).

Typical usage::

    class MyApp(TkRootHost):
        def __init__(self):
            super().__init__()
            # self.title("…") works via __getattr__ delegation
            # self.tk_root is the raw tk.Tk instance
"""

from __future__ import annotations

from .primitives import ui


class TkRootHost:
    """Compose and expose a ``tk.Tk`` root while delegating standard widget API calls.

    Low-level API — not exported from ``bw_gui`` top-level. Use ``BwBaseWindow`` instead.

    The host owns the Tk root but does not inherit from it. This separation lets
    subclasses add Python-level state and methods without polluting the Tk widget
    namespace, and avoids the Tk multiple-inheritance issues that arise when mixing
    ``tk.Tk`` with other Python base classes.

    Unknown attribute lookups are forwarded to the composed root, so code such as
    ``host.title("…")``, ``host.protocol(…)``, ``host.after(…)`` works transparently.

    The ``__str__`` method returns the Tk widget path, which is required by Tk APIs
    that accept a parent widget as a string (e.g. ``winfo_parent()``).

    Attributes:
        _tk_root: The composed ``tk.Tk`` instance. Prefer using ``tk_root`` property.
    """

    def __init__(self, root: ui.Tk | None = None):
        """Create or adopt a Tk root window.

        Args:
            root: An existing ``tk.Tk`` instance to wrap. If None, a new one is created.
                Passing an existing root is useful in tests or when embedding into a
                larger application.
        """
        self._tk_root = root or ui.Tk()

    @property
    def tk_root(self) -> ui.Tk:
        """Return the composed ``tk.Tk`` root instance.

        Use this when you need to call Tk methods not available via delegation,
        or when you need to pass the Tk instance explicitly (e.g. to ``mainloop()``).

        Returns:
            The ``tk.Tk`` root window.
        """
        return self._tk_root

    def __getattr__(self, name: str):
        """Delegate unknown attribute lookups to the composed Tk root instance.

        This makes the host transparent for standard Tk window operations like
        ``.title()``, ``.geometry()``, ``.protocol()``, ``.after()``, etc.

        Args:
            name: The attribute name to look up on the Tk root.

        Returns:
            The attribute from the Tk root.

        Raises:
            AttributeError: If the attribute does not exist on the Tk root either.
        """
        return getattr(self._tk_root, name)

    def __str__(self) -> str:
        """Expose the Tk widget path string for APIs that stringify widget masters.

        Tk widget creation functions accept either a widget object or its string
        path. Returning ``str(self._tk_root)`` ensures this host object can be
        passed as a ``master`` argument anywhere a Tk root is expected.

        Returns:
            The Tk widget path of the root window (e.g. ``"."``) .
        """
        return str(self._tk_root)
