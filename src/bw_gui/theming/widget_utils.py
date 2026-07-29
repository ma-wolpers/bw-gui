"""Utilities for applying theme colors to raw tk widgets.

ttk widgets pick up colors from the ttk style system automatically after
``configure_ttk_theme()`` is called.  Raw tk widgets (``tk.Canvas``,
``tk.Text``, ``tk.Listbox``, ``tk.Scrollbar``) have no ttk equivalent and must
be configured directly.  These helpers apply the current theme to those widgets
consistently, so consumer code never hand-picks hex values.

Call each helper inside your ``apply_theme()`` override, passing the same
*theme_key* that was passed to you::

    def apply_theme(self, theme_key: str) -> None:
        super().apply_theme(theme_key)
        theme_canvas(self._map_canvas, theme_key)
        theme_text(self._notes_editor, theme_key)
"""

from __future__ import annotations

import tkinter as tk

from .theme_manager import get_theme


def theme_canvas(canvas: tk.Canvas, theme_key: str | None = None) -> None:
    """Apply theme background and border to a ``tk.Canvas`` widget.

    Sets ``bg=bg_surface``, ``highlightbackground=border``, and
    ``highlightthickness=1`` so the canvas blends into the themed surface and
    shows a subtle border consistent with other bordered widgets.

    Call inside ``apply_theme()`` for every ``tk.Canvas`` in the UI.

    Args:
        canvas:    The canvas widget to configure.
        theme_key: Active theme key.  Falls back to ``DEFAULT_THEME`` if None.
    """
    theme = get_theme(theme_key)
    canvas.configure(
        bg=theme["bg_surface"],
        highlightbackground=theme["border"],
        highlightthickness=1,
    )


def theme_text(text: tk.Text, theme_key: str | None = None) -> None:
    """Apply theme colors to a ``tk.Text`` widget.

    Configures background, foreground, insert cursor, text selection, border,
    and focus ring so the text area matches the active theme.  Sets
    ``highlightthickness=1`` so the focus ring is visible; the ring color
    changes to ``focus_ring`` when the widget receives keyboard focus.

    Call inside ``apply_theme()`` for every ``tk.Text`` in the UI (e.g. chat
    areas, document editors, notes fields).

    Args:
        text:      The text widget to configure.
        theme_key: Active theme key.  Falls back to ``DEFAULT_THEME`` if None.
    """
    theme = get_theme(theme_key)
    text.configure(
        bg=theme["bg_surface"],
        fg=theme["fg_primary"],
        insertbackground=theme["fg_primary"],
        selectbackground=theme["selection_bg"],
        selectforeground=theme["selection_fg"],
        highlightthickness=1,
        highlightbackground=theme["border"],
        highlightcolor=theme["focus_ring"],
    )


def theme_listbox(listbox: tk.Listbox, theme_key: str | None = None) -> None:
    """Apply theme colors to a ``tk.Listbox`` widget.

    Configures background, foreground, selection colors, and a themed border
    consistent with other widgets.  The listbox background uses ``bg_surface``
    (not ``bg_main``) so it stands out from surrounding panels.

    Args:
        listbox:   The listbox widget to configure.
        theme_key: Active theme key.  Falls back to ``DEFAULT_THEME`` if None.
    """
    theme = get_theme(theme_key)
    listbox.configure(
        bg=theme["bg_surface"],
        fg=theme["fg_primary"],
        selectbackground=theme["selection_bg"],
        selectforeground=theme["selection_fg"],
        highlightthickness=1,
        highlightbackground=theme["border"],
        highlightcolor=theme["focus_ring"],
    )


def theme_scrollbar(scrollbar: tk.Scrollbar, theme_key: str | None = None) -> None:
    """Apply theme colors to a raw ``tk.Scrollbar`` widget.

    Prefer ``ttk.Scrollbar`` (which is styled automatically by
    ``configure_ttk_theme()``) where possible.  Use this helper only for raw
    ``tk.Scrollbar`` instances that cannot be replaced by their ttk counterpart
    — typically those attached to a ``tk.Text`` or ``tk.Listbox`` that the
    ttk scrollbar geometry manager cannot parent correctly.

    Sets thumb (``bg``), trough (``troughcolor``), and active thumb
    (``activebackground``) colors; removes the border and highlight ring since
    scrollbars are not focusable.

    Args:
        scrollbar: The scrollbar widget to configure.
        theme_key: Active theme key.  Falls back to ``DEFAULT_THEME`` if None.
    """
    theme = get_theme(theme_key)
    scrollbar.configure(
        bg=theme["panel_strong"],
        troughcolor=theme["bg_surface"],
        activebackground=theme["accent_soft"],
        highlightthickness=0,
        borderwidth=0,
    )
