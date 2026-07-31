"""Utilities for applying theme colors to raw tk widgets and creating composite widgets.

ttk widgets pick up colors from the ttk style system automatically after
``configure_ttk_theme()`` is called.  Raw tk widgets (``tk.Canvas``,
``tk.Text``, ``tk.Listbox``, ``tk.Scrollbar``) have no ttk equivalent and must
be configured directly.  These helpers apply the current theme to those widgets
consistently, so consumer code never hand-picks hex values.

The theme is ambient: after ``configure_ttk_theme(root, theme_key)`` is called,
all helpers resolve the active theme automatically — no ``theme_key`` argument
is needed in consumer ``apply_theme()`` overrides::

    def apply_theme(self, theme_key: str) -> None:
        super().apply_theme(theme_key)
        configure_ttk_theme(self.tk_root, theme_key)
        theme_canvas(self._map_canvas)
        theme_text(self._notes_editor)

``icon_button`` is a composite widget factory: it creates a ``ttk.Button``,
recolors its icon pixels to the appropriate foreground, and registers it for
automatic recoloring on every future theme switch.  Consumer code provides the
image, command, and optional color intent — bw_gui handles the rest forever.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .theme_manager import contrast_text_color, get_theme, tinted_color, tinted_foreground

# Registry of icon buttons for automatic recoloring on every theme switch.
_icon_button_registry: list[dict] = []


def theme_canvas(canvas: tk.Canvas, theme_key: str | None = None) -> None:
    """Apply theme background and border to a ``tk.Canvas`` widget.

    Sets ``bg=bg_surface``, ``highlightbackground=border``, and
    ``highlightthickness=1`` so the canvas blends into the themed surface and
    shows a subtle border consistent with other bordered widgets.

    Call inside ``apply_theme()`` for every ``tk.Canvas`` in the UI.  When
    ``theme_key`` is omitted or ``None``, the globally tracked current theme
    (set by the most recent ``configure_ttk_theme`` call) is used automatically.

    Args:
        canvas:    The canvas widget to configure.
        theme_key: Explicit theme override; omit to use the global current theme.
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
    areas, document editors, notes fields).  When ``theme_key`` is omitted or
    ``None``, the globally tracked current theme is used automatically.

    Args:
        text:      The text widget to configure.
        theme_key: Explicit theme override; omit to use the global current theme.
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
    (not ``bg_main``) so it stands out from surrounding panels.  When
    ``theme_key`` is omitted or ``None``, the globally tracked current theme is
    used automatically.

    Args:
        listbox:   The listbox widget to configure.
        theme_key: Explicit theme override; omit to use the global current theme.
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
    scrollbars are not focusable.  When ``theme_key`` is omitted or ``None``,
    the globally tracked current theme is used automatically.

    Args:
        scrollbar: The scrollbar widget to configure.
        theme_key: Explicit theme override; omit to use the global current theme.
    """
    theme = get_theme(theme_key)
    scrollbar.configure(
        bg=theme["panel_strong"],
        troughcolor=theme["bg_surface"],
        activebackground=theme["accent_soft"],
        highlightthickness=0,
        borderwidth=0,
    )


# ── Icon button composite widget ─────────────────────────────────────────────

def _recolor_photo(base: tk.PhotoImage, fg_hex: str) -> tk.PhotoImage:
    """Return a copy of *base* with all opaque pixels set to *fg_hex*.

    Creates a new ``tk.PhotoImage`` filled with *fg_hex*, then restores the
    original transparency mask pixel by pixel so icon shapes are preserved.
    Used internally by ``icon_button`` and ``_reapply_icon_buttons``; not part
    of the public API.

    Args:
        base:   Source ``tk.PhotoImage`` (typically a monochrome toolbar icon).
        fg_hex: ``"#RRGGBB"`` fill color applied to all non-transparent pixels.

    Returns:
        New ``tk.PhotoImage`` with the same dimensions and alpha mask as *base*
        but with all opaque pixels replaced by *fg_hex*.
    """
    width = int(base.width())
    height = int(base.height())
    recolored = tk.PhotoImage(width=width, height=height)
    recolored.put(fg_hex, to=(0, 0, width, height))
    if not (hasattr(base, "transparency_get") and hasattr(recolored, "transparency_set")):
        return recolored
    for y in range(height):
        for x in range(width):
            try:
                if bool(base.transparency_get(x, y)):
                    recolored.transparency_set(x, y, True)
            except tk.TclError:
                continue
    return recolored


def _reapply_icon_buttons() -> None:
    """Recolor all registered icon buttons to match the current active theme.

    Iterates ``_icon_button_registry``, recomputes the foreground color for
    each registered tint using the current global theme, creates a new
    ``PhotoImage`` with the updated color, and updates the button's ``image``
    option.  Called automatically by ``configure_ttk_theme`` after every theme
    switch.  Consumer code never calls this directly.
    """
    for entry in _icon_button_registry:
        color_tint = entry["color_tint"]
        if color_tint is None:
            continue
        fg = tinted_foreground(color_tint, degree=entry["degree"], base_token=entry["base_token"])
        new_photo = _recolor_photo(entry["base_photo"], fg)
        entry["current_photo"] = new_photo
        try:
            entry["button"].configure(image=new_photo)
        except tk.TclError:
            pass


def icon_button(
    parent: tk.Misc,
    photo_image: tk.PhotoImage,
    command: Callable,
    *,
    color_tint: str | None = None,
    degree: float = 0.35,
    base_token: str = "auto",
    **button_kwargs,
) -> ttk.Button:
    """Create a theme-aware icon button with automatic pixel recoloring.

    bw_gui computes the foreground color for *color_tint*, recolors
    *photo_image* pixels to match, and registers the button for automatic
    recoloring on every subsequent theme switch.  The consumer provides intent
    (image, command, optional color seed) — all color computation and icon
    recoloring stays in bw_gui permanently.

    On every ``configure_ttk_theme`` call, bw_gui iterates all registered icon
    buttons and updates their images to match the new theme.  No consumer code
    is needed for theme switching.

    Args:
        parent:       Parent widget.
        photo_image:  ``tk.PhotoImage`` to display as the button icon.  The
                      original is preserved in the registry; bw_gui creates a
                      recolored copy for each theme.
        command:      Callable invoked on button press.
        color_tint:   Optional ``"#RRGGBB"`` hex or bw_gui token name.  When
                      provided, icon pixels are colored to the foreground that
                      best contrasts the corresponding ``tinted_color``
                      background.  ``None`` leaves pixels unchanged.
        degree:       Tint strength used when computing the icon foreground;
                      passed to ``tinted_foreground`` internally.  Defaults to
                      0.35 so icon tints are visually distinct.
        base_token:   Base token for the foreground calculation; ``"auto"``
                      picks ``bg_panel`` (dark) or ``bg_surface`` (light).
        **button_kwargs: Forwarded to ``ttk.Button`` (e.g. ``style``,
                         ``padding``, ``cursor``).

    Returns:
        The created ``ttk.Button`` instance.
    """
    if color_tint is not None:
        fg = tinted_foreground(color_tint, degree=degree, base_token=base_token)
        colored = _recolor_photo(photo_image, fg)
    else:
        colored = photo_image

    btn = ttk.Button(parent, image=colored, command=command, **button_kwargs)
    _icon_button_registry.append({
        "button": btn,
        "base_photo": photo_image,
        "color_tint": color_tint,
        "degree": degree,
        "base_token": base_token,
        "current_photo": colored,
    })
    return btn
