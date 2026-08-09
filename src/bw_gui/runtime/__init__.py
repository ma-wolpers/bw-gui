"""Shared runtime primitives wrapping tkinter and ttk."""

from .app_shell import AppShellConfig, TkinterAppShell
from .base_window import BwBaseWindow
from .primitives import fonts, ui, widgets
from .root_host import TkRootHost
from .shortcuts import WindowShortcutBinder

__all__ = [
    "BwBaseWindow",
    "fonts",
    "ui",
    "widgets",
    "TkRootHost",
    "AppShellConfig",
    "TkinterAppShell",
    "WindowShortcutBinder",
]
