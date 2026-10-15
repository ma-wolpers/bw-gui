"""Shared runtime primitives wrapping tkinter and ttk."""

from .app_shell import AppShellConfig, TkinterAppShell
from .base_window import BwBaseWindow
from .primitives import fonts, ui, widgets
from .overlay_stack import (
    OverlayCategory,
    blocking,
    modal_affecting_mode,
    overlay_state,
    register_overlay,
    topmost_window,
)
from .pointer import bind_click, bind_drag, bind_wheel, on_global_click
from .pointer_group import PointerGroup
from .pointer_hover import bind_canvas_item, bind_hover
from .root_host import TkRootHost, create_root
from .shortcuts import ApplicationShortcutBinder, ShortcutRegistration, WindowShortcutBinder, detect_backend
from .text_input import accepts_text_input, register_text_input
from .selection import (
    combobox_selection,
    listbox_selection,
    on_activate,
    on_combobox_select,
    on_listbox_select,
    on_treeview_select,
    treeview_selection,
)
from .widget_events import (
    on_destroy,
    on_focus_change,
    on_resize,
    on_tab_changed,
    on_text_modified,
    on_visibility,
    reset_text_modified,
)
from .widget_keys import WidgetShortcutBinder, on_key

__all__ = [
    "bind_canvas_item",
    "bind_hover",
    "combobox_selection",
    "listbox_selection",
    "on_activate",
    "on_combobox_select",
    "on_destroy",
    "on_focus_change",
    "on_listbox_select",
    "on_resize",
    "on_tab_changed",
    "on_text_modified",
    "on_treeview_select",
    "on_visibility",
    "reset_text_modified",
    "treeview_selection",
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
    "topmost_window",
    "bind_click",
    "bind_drag",
    "bind_wheel",
    "on_global_click",
    "PointerGroup",
    "create_root",
]
