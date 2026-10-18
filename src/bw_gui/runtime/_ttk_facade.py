"""``bw_gui.runtime.widgets``: the ttk namespace with bw-gui primitives in place of ttk ones.

Every public name of ``tkinter.ttk`` stays available under the same name (a coverage
test enforces it); only ``Scrollbar`` is the bw-gui scrollbar primitive
(``bw_gui.runtime.scrollbar.Scrollbar``, a native themed scrollbar) instead of
``ttk.Scrollbar``. The primitive is resolved lazily on first access because it imports
the theming package, which itself imports this namespace.
"""

from __future__ import annotations

from tkinter import ttk as _ttk

# Re-export the public ttk namespace explicitly (no star import: the facade only provides
# names, it creates no widgets). ``Scrollbar`` is left out and resolved to the primitive.
globals().update({name: getattr(_ttk, name) for name in _ttk.__all__ if name != "Scrollbar"})
__all__ = list(_ttk.__all__)


def __getattr__(name: str):
    """Resolve ``Scrollbar`` to the bw-gui primitive and any other name to ``tkinter.ttk``."""
    if name == "Scrollbar":
        from .scrollbar import Scrollbar

        globals()["Scrollbar"] = Scrollbar
        return Scrollbar
    return getattr(_ttk, name)
