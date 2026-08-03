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

**Canvas drawing primitives** (``canvas_fill``, ``canvas_tinted_fill``,
``canvas_text_fill``, ``canvas_outline_color``) apply theme colors to individual
canvas *items* (rectangles, text, ovals …) after they have been created.
Consumer code passes a token name or tint seed; bw_gui resolves the actual color
internally so no hex value ever reaches the consumer::

    rect_id = canvas.create_rectangle(x1, y1, x2, y2)
    canvas_fill(canvas, rect_id, token="bg_panel")

    text_id = canvas.create_text(cx, cy, text="LZK")
    canvas_text_fill(canvas, text_id, token="fg_primary")

    canvas_tinted_fill(canvas, rect_id, color_tint="warning_soft", degree=0.72,
                       base_token="panel_strong")

``icon_button`` is a composite widget factory: it creates a ``ttk.Button``,
recolors its icon pixels to the appropriate foreground, and registers it for
automatic recoloring on every future theme switch.  Consumer code provides the
image, command, and optional color intent — bw_gui handles the rest forever.

``recolor_photo`` returns a recolored ``tk.PhotoImage`` for cases where the
consumer manages state-based icon switching manually (e.g. a button that shows
a different icon depending on app state).  The consumer provides the base photo
and a color-tint seed; bw_gui computes the foreground hex internally.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ._theme_manager import _is_dark, get_theme, tinted_color, tinted_foreground

__all__ = [
    "canvas_fill",
    "canvas_tinted_fill",
    "canvas_text_fill",
    "canvas_outline_color",
    "canvas_domain_fill",
    "canvas_domain_outline",
    "icon_button",
    "recolor_photo",
    "theme_canvas",
    "theme_text",
    "theme_text_tinted",
    "theme_label_token",
    "theme_label_tinted",
    "theme_widget_border",
    "theme_listbox",
    "theme_scrollbar",
]

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


def theme_text(
    text: tk.Text,
    theme_key: str | None = None,
    *,
    bg_token: str = "bg_surface",
    fg_token: str = "fg_primary",
) -> None:
    """Apply theme colors to a ``tk.Text`` widget.

    Configures background, foreground, insert cursor, text selection, border,
    and focus ring so the text area matches the active theme.  Sets
    ``highlightthickness=1`` so the focus ring is visible; the ring color
    changes to ``focus_ring`` when the widget receives keyboard focus.

    Call inside ``apply_theme()`` for every ``tk.Text`` in the UI (e.g. chat
    areas, document editors, notes fields).  When ``theme_key`` is omitted or
    ``None``, the globally tracked current theme is used automatically.

    The optional ``bg_token`` and ``fg_token`` parameters let callers override
    the background and foreground contract token without seeing hex values::

        theme_text(cell)                                 # bg_surface / fg_primary
        theme_text(cell, bg_token="bg_panel",
                         fg_token="fg_muted")            # disabled/read-only cell
        theme_text(cell, bg_token="warning_soft")        # unresolved-link cell

    Args:
        text:      The text widget to configure.
        theme_key: Explicit theme override; omit to use the global current theme.
        bg_token:  Contract token for the background color.  Defaults to
                   ``"bg_surface"``.
        fg_token:  Contract token for the foreground / cursor color.  Defaults to
                   ``"fg_primary"``.
    """
    theme = get_theme(theme_key)
    text.configure(
        bg=theme[bg_token],
        fg=theme[fg_token],
        insertbackground=theme[fg_token],
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


def theme_text_tinted(
    text: tk.Text,
    color_tint: str,
    *,
    degree: float = 0.5,
    base_token: str = "bg_panel",
    fg_token: str = "fg_primary",
) -> None:
    """Apply a tinted background to a ``tk.Text`` widget for domain-typed display states.

    Computes the background color internally via ``tinted_color``; no hex value
    is returned to the consumer.  The consumer expresses *what* the cell
    represents (tint seed + degree + base), bw_gui decides *what color* that
    produces for the active theme.

    Use for column-typed cells that need a tinted background different from the
    standard ``bg_surface`` — e.g. ausfall cells (``warning_soft`` tint),
    hospitation cells (domain-seed tint), LZK cells (``success_soft`` tint)::

        theme_text_tinted(cell, "warning_soft",   degree=0.72,
                          base_token="panel_strong", fg_token="fg_muted")
        theme_text_tinted(cell, HOSPITATION_SEED, degree=0.38,
                          base_token="panel_strong")

    Args:
        text:       The ``tk.Text`` widget to configure.
        color_tint: Tint seed — contract token name or ``"#RRGGBB"`` hex —
                    forwarded to ``tinted_color``.
        degree:     Tint strength [0, 1].
        base_token: Base contract token for the tinted_color blend.
        fg_token:   Contract token for the text foreground and cursor color.
    """
    theme = get_theme()
    bg = tinted_color(color_tint, degree=degree, base_token=base_token)
    fg = theme[fg_token]
    text.configure(
        bg=bg,
        fg=fg,
        insertbackground=fg,
        selectbackground=theme["selection_bg"],
        selectforeground=theme["selection_fg"],
    )


def theme_label_token(
    label: tk.Label,
    *,
    bg_token: str = "panel_strong",
    fg_token: str = "fg_primary",
) -> None:
    """Apply token-based background and foreground colors to a ``tk.Label`` widget.

    Use when the label's background should come from a standard contract token
    (e.g. ``"panel_strong"``, ``"bg_surface"``, ``"warning_soft"``,
    ``"selection_bg"``).  bw_gui resolves the hex value internally; no color
    string ever reaches the consumer::

        theme_label_token(corner_label)                           # panel_strong / fg_primary
        theme_label_token(label, bg_token="selection_bg",
                                 fg_token="selection_fg")         # selected header

    Args:
        label:    The ``tk.Label`` widget to configure.
        bg_token: Contract token for the label background.
        fg_token: Contract token for the label foreground.
    """
    theme = get_theme()
    label.configure(bg=theme[bg_token], fg=theme[fg_token])


def theme_label_tinted(
    label: tk.Label,
    color_tint: str,
    *,
    degree: float = 0.5,
    base_token: str = "bg_panel",
    fg_token: str = "fg_primary",
) -> None:
    """Apply a tinted background to a ``tk.Label`` for domain-typed column headers.

    Computes the background color internally via ``tinted_color``; the consumer
    expresses intent (tint seed + degree + base) while bw_gui resolves the hex.

    Use for column headers whose background reflects the column type — e.g. an
    ausfall header tinted toward ``"warning_soft"``, a hospitation header tinted
    toward the domain seed::

        theme_label_tinted(header, "warning_soft",   degree=0.72,
                           base_token="panel_strong", fg_token="fg_muted")
        theme_label_tinted(header, HOSPITATION_SEED, degree=0.38,
                           base_token="panel_strong")

    Args:
        label:      The ``tk.Label`` widget to configure.
        color_tint: Tint seed forwarded to ``tinted_color``.
        degree:     Tint strength [0, 1].
        base_token: Base contract token for the tinted_color blend.
        fg_token:   Contract token for the label foreground.
    """
    theme = get_theme()
    bg = tinted_color(color_tint, degree=degree, base_token=base_token)
    label.configure(bg=bg, fg=theme[fg_token])


def theme_widget_border(
    widget: tk.Misc,
    *,
    color_token: str = "border",
    thickness: int = 1,
) -> None:
    """Apply a themed highlight border to any ``tk`` widget.

    Sets ``highlightbackground`` and ``highlightcolor`` to the named contract
    token color.  Use for selection indicators, UB-column accent borders, or any
    widget border whose color should follow the active theme.  Supports
    ``tk.Text``, ``tk.Label``, ``tk.Canvas``, and any other widget that accepts
    the highlight options::

        theme_widget_border(cell, color_token="selection_bg", thickness=2)
        theme_widget_border(cell, color_token="accent",       thickness=2)
        theme_widget_border(cell)                              # border / 1px

    Args:
        widget:      Any Tk widget that accepts ``highlightbackground``.
        color_token: Contract token for the border color.
        thickness:   Highlight border thickness in pixels.
    """
    theme = get_theme()
    color = theme[color_token]
    widget.configure(highlightthickness=thickness, highlightbackground=color, highlightcolor=color)


# ── Canvas item drawing primitives ───────────────────────────────────────────

def canvas_fill(canvas: tk.Canvas, item_id: int, *, token: str = "bg_panel") -> None:
    """Set a canvas item's fill to the current value of a named contract token.

    Reads the globally tracked current theme — no ``theme_key`` argument.
    The token must be a guaranteed contract key (see ``theme_contract_keys()``).
    Typical tokens: ``"bg_panel"``, ``"bg_surface"``, ``"panel_strong"``,
    ``"selection_bg"``, ``"accent"``, ``"warning_soft"``.

    Call during canvas repaints / theme-switch redraws so colors stay consistent
    with the active theme without the consumer ever seeing a hex value.

    Args:
        canvas:  The canvas the item lives on.
        item_id: Integer item handle returned by ``canvas.create_*``.
        token:   Contract token name for the fill color.
    """
    canvas.itemconfig(item_id, fill=get_theme()[token])


def canvas_tinted_fill(
    canvas: tk.Canvas,
    item_id: int,
    *,
    color_tint: str,
    degree: float = 0.5,
    base_token: str = "bg_panel",
) -> None:
    """Set a canvas item's fill to a tinted color derived from *color_tint*.

    Identical semantics to ``tinted_color(color_tint, degree=degree,
    base_token=base_token)`` but applies the result directly to the canvas item.
    No color value is returned; the consumer never sees hex.

    Use for domain-typed cells whose background is a tinted shade, e.g. an
    Ausfall cell tinted toward ``"warning_soft"`` or a Hospitation cell tinted
    toward a domain seed::

        canvas_tinted_fill(canvas, rect, color_tint="warning_soft",
                           degree=0.72, base_token="panel_strong")
        canvas_tinted_fill(canvas, rect, color_tint=HOSPITATION_SEED,
                           degree=0.38, base_token="panel_strong")

    Args:
        canvas:     The canvas the item lives on.
        item_id:    Integer item handle returned by ``canvas.create_*``.
        color_tint: ``"#RRGGBB"`` hex literal or bw_gui token name used as the
                    tint seed (same as the first argument to ``tinted_color``).
        degree:     Tint strength [0, 1].
        base_token: Contract token used as the neutral base for blending.
    """
    canvas.itemconfig(item_id, fill=tinted_color(color_tint, degree=degree, base_token=base_token))


def canvas_text_fill(canvas: tk.Canvas, item_id: int, *, token: str = "fg_primary") -> None:
    """Set a canvas text item's fill to the current value of a named contract token.

    Reads the globally tracked current theme — no ``theme_key`` argument.
    Typical tokens: ``"fg_primary"``, ``"fg_muted"``, ``"selection_fg"``.

    Args:
        canvas:  The canvas the text item lives on.
        item_id: Integer item handle returned by ``canvas.create_text``.
        token:   Contract token name for the text fill color.
    """
    canvas.itemconfig(item_id, fill=get_theme()[token])


def canvas_outline_color(canvas: tk.Canvas, item_id: int, *, token: str = "border") -> None:
    """Set a canvas item's outline to the current value of a named contract token.

    Reads the globally tracked current theme — no ``theme_key`` argument.
    Typical tokens: ``"border"``, ``"accent"``, ``"focus_ring"``.

    Args:
        canvas:  The canvas the item lives on.
        item_id: Integer item handle returned by ``canvas.create_*``.
        token:   Contract token name for the outline color.
    """
    canvas.itemconfig(item_id, outline=get_theme()[token])


def canvas_domain_fill(
    canvas: tk.Canvas,
    item_id: int,
    *,
    light_color: str,
    dark_color: str,
) -> None:
    """Set a canvas item's fill to the appropriate domain color for the current theme.

    The consumer owns the domain color values and provides both light and dark
    variants; bw_gui picks the correct one based on whether the active theme is
    dark or light.  No color value is returned; the consumer never performs its
    own dark/light check.

    Use for canvas items whose color comes from domain-owned constants (e.g.
    lesson-type or achievement-category colors) rather than from the bw_gui
    contract token set::

        canvas_domain_fill(canvas, arc_id,
                           light_color=CATEGORY_COLORS_LIGHT[cat],
                           dark_color=CATEGORY_COLORS_DARK[cat])

    Args:
        canvas:      The canvas the item lives on.
        item_id:     Integer item handle returned by ``canvas.create_*``.
        light_color: ``"#RRGGBB"`` hex used when the active theme is light.
        dark_color:  ``"#RRGGBB"`` hex used when the active theme is dark.
    """
    theme = get_theme()
    canvas.itemconfig(item_id, fill=dark_color if _is_dark(theme["bg_main"]) else light_color)


def canvas_domain_outline(
    canvas: tk.Canvas,
    item_id: int,
    *,
    light_color: str,
    dark_color: str,
) -> None:
    """Set a canvas item's outline to the appropriate domain color for the current theme.

    The consumer owns the domain color values and provides both light and dark
    variants; bw_gui picks the correct one based on whether the active theme is
    dark or light.  No color value is returned; the consumer never performs its
    own dark/light check.

    Use for arc rings or outlined shapes whose stroke color is domain-owned (e.g.
    a progress arc colored per achievement category)::

        canvas_domain_outline(canvas, arc_id,
                              light_color=CATEGORY_COLORS_LIGHT[cat],
                              dark_color=CATEGORY_COLORS_DARK[cat])

    Args:
        canvas:      The canvas the item lives on.
        item_id:     Integer item handle returned by ``canvas.create_*``.
        light_color: ``"#RRGGBB"`` hex used when the active theme is light.
        dark_color:  ``"#RRGGBB"`` hex used when the active theme is dark.
    """
    theme = get_theme()
    canvas.itemconfig(item_id, outline=dark_color if _is_dark(theme["bg_main"]) else light_color)


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
            fg = get_theme()["fg_primary"]
        else:
            fg = tinted_foreground(color_tint, degree=entry["degree"], base_token=entry["base_token"])
        new_photo = _recolor_photo(entry["base_photo"], fg)
        entry["current_photo"] = new_photo
        try:
            entry["button"].configure(image=new_photo)
        except tk.TclError:
            pass


def recolor_photo(
    photo: tk.PhotoImage,
    color_tint: str,
    *,
    degree: float = 0.35,
    base_token: str = "auto",
) -> tk.PhotoImage:
    """Return a recolored copy of *photo* using the current theme's tinted foreground.

    Computes the appropriate foreground color for *color_tint* internally via
    ``tinted_foreground`` and recolors all opaque pixels of *photo* to that
    color.  No hex value is exposed to the consumer — only the resulting image
    is returned.

    Intended for cases where the consumer manages state-based icon switching
    manually (e.g. a toolbar button whose icon changes depending on app state).
    For static icon buttons, prefer ``icon_button`` which handles everything
    automatically.

    The returned image uses the colors of the currently active theme; call this
    again (and update the button's ``image`` option) after every theme switch.

    Args:
        photo:      Base ``tk.PhotoImage`` to recolor.
        color_tint: ``"#RRGGBB"`` hex or bw_gui token name used as the tint
                    seed — the same first argument as ``tinted_foreground``.
        degree:     Tint strength forwarded to ``tinted_foreground``.
        base_token: Base token forwarded to ``tinted_foreground``.

    Returns:
        New ``tk.PhotoImage`` with opaque pixels set to the computed foreground.
    """
    fg = tinted_foreground(color_tint, degree=degree, base_token=base_token)
    return _recolor_photo(photo, fg)


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
        color_tint:   Optional ``"#RRGGBB"`` hex or bw_gui token name used as
                      the tint seed.  Icon pixels are colored to the foreground
                      that best contrasts the corresponding ``tinted_color``
                      background.  ``None`` recolors to ``fg_primary`` so the
                      icon follows the active theme even for neutral actions.
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
    else:
        fg = get_theme()["fg_primary"]
    colored = _recolor_photo(photo_image, fg)

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
