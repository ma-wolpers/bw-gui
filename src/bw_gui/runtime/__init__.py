"""Shared runtime primitives wrapping tkinter and ttk."""

from .app_shell import AppShellConfig, TkinterAppShell
from .base_window import BwBaseWindow
from .primitives import fonts, ui, widgets
from .overlay_stack import OverlayCategory, blocking, modal_affecting_mode, overlay_state, register_overlay
from .pointer import bind_click, bind_drag, bind_wheel, on_global_click
from .root_host import TkRootHost, create_root
from .shortcuts import ApplicationShortcutBinder, ShortcutRegistration, WindowShortcutBinder, detect_backend
from .text_input import accepts_text_input, register_text_input
from .widget_keys import WidgetShortcutBinder, on_key

__all__ = [
    "BwBaseWindow",
    "fonts",
    "ui",
    "widgets",
    "TkRootHost",
    "AppShellConfig",
    "TkinterAppShell",
    "WindowShortcutBinder",
    "ApplicationShortcutBinder",
    "WidgetShortcutBinder",
    "ShortcutRegistration",
    "on_key",
    "accepts_text_input",
    "register_text_input",
    "detect_backend",
    "OverlayCategory",
    "blocking",
    "modal_affecting_mode",
    "overlay_state",
    "register_overlay",
    "bind_click",
    "bind_drag",
    "bind_wheel",
    "on_global_click",
    "create_root",
]
