"""Shared runtime primitives wrapping tkinter and ttk."""

from .app_shell import AppShellConfig, TkinterAppShell
from .primitives import fonts, ui, widgets
from .root_host import TkRootHost

__all__ = ["fonts", "ui", "widgets", "TkRootHost", "AppShellConfig", "TkinterAppShell"]
