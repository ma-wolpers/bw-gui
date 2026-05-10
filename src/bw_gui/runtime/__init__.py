"""Shared runtime primitives wrapping tkinter and ttk."""

from .primitives import fonts, ui, widgets
from .root_host import TkRootHost

__all__ = ["fonts", "ui", "widgets", "TkRootHost"]
