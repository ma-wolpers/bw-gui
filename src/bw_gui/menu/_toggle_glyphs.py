"""Glyphs and click resolution for binary menu items (private).

Keeps the toggle knowledge out of ``custom_menu_bar.py``: which items are binary, which
indicator image they show (the same shared ``PhotoImage``s as the ``Checkbox``/``Switch``
widgets, recoloured in place on every theme switch) and which callable a click runs.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from bw_gui.theming._toggle_styles import toggle_image

from .menu_types import MenuItem

BINARY_TYPES = ("checkbox", "switch")
_FALLBACK_PREFIX = {
    ("checkbox", "on"): "☑ ", ("checkbox", "off"): "☐ ", ("checkbox", "mixed"): "⊟ ",
    ("switch", "on"): "◉ ", ("switch", "off"): "○ ", ("switch", "mixed"): "◐ ",
}


def is_binary(item: MenuItem) -> bool:
    """True for ``checkbox`` and ``switch`` items."""
    return item.type in BINARY_TYPES


def shape_of(checked: bool, mixed: bool) -> str:
    """Indicator shape for a value and mixed flag: ``"mixed"``, ``"on"`` or ``"off"``."""
    return "mixed" if mixed else "on" if checked else "off"


def glyph_image(widget: tk.Misc, control: str, checked: bool, mixed: bool) -> tk.PhotoImage | None:
    """Shared indicator image for a menu row, or ``None`` before the theme is configured."""
    try:
        return toggle_image(widget, control, f"{shape_of(checked, mixed)}-rest")
    except KeyError:
        return None


def text_prefix(control: str, checked: bool, mixed: bool) -> str:
    """Plain-text indicator used only when no themed image is available yet."""
    return _FALLBACK_PREFIX[(control, shape_of(checked, mixed))]


def menu_item_command(item: MenuItem) -> Callable[[], None] | None:
    """The callable a click (or Enter) on *item* runs.

    Binary items with ``on_toggle`` get a closure delivering the requested bool
    (contract "Click sequence"); everything else - including legacy ``checkbox`` items
    with only ``command`` - returns ``item.command`` unchanged.
    """
    if not is_binary(item) or item.on_toggle is None:
        return item.command
    target = item.mixed_click_target if item.mixed_click_target is not None else item.type == "checkbox"
    requested = target if item.mixed else not item.checked
    on_toggle = item.on_toggle
    return lambda: on_toggle(requested)
