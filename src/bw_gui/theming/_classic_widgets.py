"""Theme colours for every classic Tk widget -- no widget keeps Tk's system colours.

ttk widgets follow the theme through styles. Classic Tk widgets (``tk.Frame``,
``tk.PanedWindow``, ``tk.Menu`` …, reachable as ``bw_gui.runtime.ui.*``) do not:
they start in the compiled-in system colours (on Windows literally
``SystemButtonFace``, ``SystemWindow`` …), which stand out in dark themes.

This module is the single source for their look (``docs/THEME_CONTRACT.md``,
"Classic Tk widgets"):

* :data:`CLASSIC_WIDGET_TOKENS` -- Tk class name -> option (Tk database name) ->
  theme token. :data:`CLASSIC_WIDGET_CONSTANTS` holds the theme-independent
  options of the same widgets (flat splitter handle).
* :func:`apply_classic_widget_theme` -- called by ``configure_ttk_theme`` before
  the listener phase. It writes the table into Tk's option database (every
  widget created afterwards starts themed) and walks the existing widget tree:
  an option that still holds Tk's compiled-in default or the value this table
  gave it for the previous theme takes the new value. Colours a consumer set
  explicitly stay untouched, and consumer theme listeners run afterwards.
* :func:`classic_widget_colors` -- the resolved colours of one class; the
  ``theme_canvas``/``theme_text``/``theme_listbox`` helpers build on it instead
  of repeating the token choice.

Limit (GRENZE): a classic widget created with a custom ``class_=`` is not matched
by its Tk class name; no program uses ``class_=`` (checked 2026-11-08).
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Mapping

from ._theme_manager import get_theme

__all__ = [
    "CLASSIC_WIDGET_CONSTANTS",
    "CLASSIC_WIDGET_TOKENS",
    "apply_classic_widget_theme",
    "classic_widget_colors",
]

# Shared option groups (Tk database names; the configure option is the lowercase form).
_CONTAINER = {"background": "bg_main", "highlightBackground": "bg_main", "highlightColor": "focus_ring"}
_TEXT_ON_MAIN = {**_CONTAINER, "foreground": "fg_primary", "disabledForeground": "fg_muted"}
_SELECTION = {"selectBackground": "selection_bg", "selectForeground": "selection_fg"}
_FIELD = {
    "background": "bg_surface", "foreground": "fg_primary", **_SELECTION,
    "highlightBackground": "border", "highlightColor": "focus_ring",
}
_ENTRY = {
    **_FIELD, "insertBackground": "fg_primary", "disabledForeground": "fg_muted",
    "disabledBackground": "bg_panel", "readonlyBackground": "bg_panel",
}
_BUTTON = {
    **_TEXT_ON_MAIN, "background": "secondary_soft",
    "activeBackground": "accent_soft", "activeForeground": "fg_primary",
}

CLASSIC_WIDGET_TOKENS: dict[str, dict[str, str]] = {
    "Toplevel": dict(_CONTAINER),  # the interpreter root is treated as a Toplevel
    "Frame": dict(_CONTAINER),
    "Labelframe": {**_CONTAINER, "foreground": "fg_primary"},
    # The splitter handle shows the PanedWindow background: a flat gap between
    # the panes' own borders, like the gaps between other panels.
    "Panedwindow": {"background": "bg_main"},  # Tk's class name, lowercase "w"
    "Label": {**_TEXT_ON_MAIN, "activeBackground": "bg_main", "activeForeground": "fg_primary"},
    "Message": {**_CONTAINER, "foreground": "fg_primary"},
    "Button": dict(_BUTTON),
    "Menubutton": dict(_BUTTON),
    "Checkbutton": {**_BUTTON, "background": "bg_main", "activeBackground": "bg_panel", "selectColor": "bg_surface"},
    "Radiobutton": {**_BUTTON, "background": "bg_main", "activeBackground": "bg_panel", "selectColor": "bg_surface"},
    "Entry": dict(_ENTRY),
    "Spinbox": {**_ENTRY, "buttonBackground": "secondary_soft", "activeBackground": "accent_soft"},
    "Text": {**_FIELD, "insertBackground": "fg_primary", "inactiveSelectBackground": "selection_bg"},
    "Listbox": {**_FIELD, "disabledForeground": "fg_muted"},
    "Canvas": {  # selection/insert colours apply to canvas text items
        "background": "bg_surface", **_SELECTION, "insertBackground": "fg_primary",
        "highlightBackground": "border", "highlightColor": "focus_ring",
    },
    "Menu": {
        "background": "bg_surface", "foreground": "fg_primary", "disabledForeground": "fg_muted",
        "activeBackground": "selection_bg", "activeForeground": "selection_fg", "selectColor": "fg_primary",
    },
    "Scale": {**_CONTAINER, "foreground": "fg_primary", "troughColor": "bg_panel", "activeBackground": "accent_soft"},
    # Off win32 the look of the bw-gui Scrollbar primitive (on win32 it uses the native dark mode).
    "Scrollbar": {**_CONTAINER, "background": "panel_strong", "troughColor": "bg_surface", "activeBackground": "accent_soft"},
}

CLASSIC_WIDGET_CONSTANTS: dict[str, dict[str, str]] = {
    "Panedwindow": {"sashRelief": "flat"},  # no 3D bevel on the splitter handle
}

# Values the table gave per (class, option) at the last switch: an option still
# holding one of them was set by this module, not by a consumer.
_applied: dict[tuple[str, str], str] = {}


def classic_widget_colors(tk_class: str, theme_key: str | None = None, **token_overrides: str) -> dict[str, str]:
    """Resolve the theme colours of Tk class *tk_class* as ``configure()`` keywords.

    Args:
        tk_class: Tk class name, a key of :data:`CLASSIC_WIDGET_TOKENS`.
        theme_key: Explicit theme; omit for the current theme.
        **token_overrides: Database option name -> other token (e.g.
            ``background="warning_soft"``) for helpers with a token parameter.

    Returns:
        Lowercase option name -> colour.
    """
    theme = get_theme(theme_key)
    tokens = {**CLASSIC_WIDGET_TOKENS[tk_class], **token_overrides}
    return {option.lower(): theme[token] for option, token in tokens.items()}


def _resolved_table(theme: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """Every class's options (database names) -> value for *theme*, constants included."""
    table = {cls: {option: theme[token] for option, token in options.items()} for cls, options in CLASSIC_WIDGET_TOKENS.items()}
    for cls, options in CLASSIC_WIDGET_CONSTANTS.items():
        table.setdefault(cls, {}).update(options)
    return table


def _widgets(root: tk.Misc):
    """Yield *root* and all its descendants (Toplevels included)."""
    stack: list[Any] = [root]
    while stack:
        widget = stack.pop()
        yield widget
        stack.extend(widget.winfo_children())


def _retheme_widget(widget: Any, tk_class: str, options: Mapping[str, str]) -> None:
    """Give *widget* the new values wherever it still shows a default (see module docstring).

    Talks to Tk through ``tk.Misc`` directly: wrapper classes may restrict their own
    ``configure``/``cget`` (the bw-gui ``Scrollbar`` accepts only three options).
    """
    for option, value in options.items():
        name = option.lower()
        try:
            current = str(tk.Misc.cget(widget, name))
            if current != value and current in (str(tk.Misc.configure(widget, name)[3]), _applied.get((tk_class, option))):
                tk.Misc.configure(widget, {name: value})
        except tk.TclError:  # option unknown on this platform/Tk version, or widget just destroyed
            continue


def apply_classic_widget_theme(widget: tk.Misc, theme_key: str | None = None) -> None:
    """Theme every classic Tk widget of *widget*'s interpreter, now and for later creations.

    Args:
        widget: Any widget of the interpreter (the walk starts at its root).
        theme_key: Theme just configured; omit for the current theme.
    """
    from ..runtime._tk_identity import interpreter_root  # late: runtime imports theming

    root = interpreter_root(widget)
    table = _resolved_table(get_theme(theme_key))
    for cls, options in table.items():
        for option, value in options.items():
            root.option_add(f"*{cls}.{option}", value)
    for item in _widgets(root):
        try:
            tk_class = "Toplevel" if item is root else item.winfo_class()
        except tk.TclError:
            continue
        if tk_class in table:
            _retheme_widget(item, tk_class, table[tk_class])
    _applied.clear()
    _applied.update({(cls, option): value for cls, options in table.items() for option, value in options.items()})
