"""ttk style registration for all bw-gui themes (private).

Split out of ``_theme_manager`` (file-size rule): ``configure_ttk_theme`` is the style
catalog of every themed ttk widget, ``configure_tinted_button_style`` its per-intent
button variant. ``_theme_manager`` re-exports both, so existing imports keep working.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ._color_math import _mix, contrast_text_color
from ._theme_manager import _set_current_theme, get_theme


def configure_tinted_button_style(
    root: tk.Misc,
    style_name: str,
    *,
    mix_color: str,
    degree: float = 0.15,
    theme_key: str | None = None,
) -> None:
    """Register a ttk button style with a custom tint color.

    Useful for domain-specific action buttons that need a distinct color separate
    from the standard accent palette — e.g. lesson-type buttons in a schedule
    app where each lesson type (regular, test, observation, cancelled) has its
    own hue, or resource-type toggles in a catalog.

    The background is computed as::

        bg = mix(theme["bg_surface"], mix_color, degree)

    so at degree=0.15 the tint is very subtle; at 0.40 it becomes prominent.
    Hover and pressed states step degree up by +0.12 and +0.25 respectively.
    Foreground is auto-selected for contrast via ``contrast_text_color()``.

    Call once per domain button type inside your ``apply_theme()`` override so
    colors update correctly when the user switches themes.

    Args:
        root:       Any Tk widget (used to retrieve the ttk.Style instance).
        style_name: The ttk style name to register, e.g. ``"Action.Lesson.TButton"``.
        mix_color:  The tint hex color, e.g. ``"#3E7A5D"``.
        degree:     Blend ratio in [0, 1].  Defaults to 0.15.
        theme_key:  Active theme; falls back to ``DEFAULT_THEME`` if None or unknown.
    """
    theme = get_theme(theme_key)
    bg = _mix(theme["bg_surface"], mix_color, degree)
    hover_bg = _mix(theme["bg_surface"], mix_color, min(1.0, degree + 0.12))
    active_bg = _mix(theme["bg_surface"], mix_color, min(1.0, degree + 0.25))
    fg = contrast_text_color(bg)
    hover_fg = contrast_text_color(hover_bg)
    style = ttk.Style(root)
    style.configure(
        style_name,
        background=bg,
        foreground=fg,
        bordercolor=theme["border"],
        lightcolor=bg,
        darkcolor=bg,
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        focuscolor=theme["focus_ring"],
    )
    style.map(
        style_name,
        background=[("disabled", theme["bg_panel"]), ("active", hover_bg), ("pressed", active_bg)],
        foreground=[("disabled", theme["fg_muted"]), ("active", hover_fg), ("pressed", hover_fg)],
    )


# ── TTK baseline (deliberate exception: long by necessity) ───────────────────

def configure_ttk_theme(root: tk.Misc, theme_key: str | None = None) -> None:
    """Configure the shared ttk style baseline for all Blattwerk-family programs.

    Call this **once per theme switch** from inside your ``apply_theme()``
    implementation (or from the constructor if you are not using ``BwBaseWindow``).
    It is idempotent: repeated calls simply overwrite the previous style configuration.

    Requires ``style.theme_use("clam")`` — the function sets this automatically;
    if the clam theme is unavailable (unusual), the call is silently skipped and
    styles are applied on top of whatever theme is active.

    Styles registered:

    *Frames*
        ``TFrame`` (bg_main), ``Surface.TFrame`` (bg_surface), ``Panel.TFrame``
        (panel_strong), ``Toolbar.TFrame`` (panel_strong), ``Settings.Panel.TFrame``
        (bg_surface), ``Settings.Sidebar.TFrame`` (panel_strong).

    *Control strip*
        ``ControlStrip.TFrame`` — accent-tinted toolbar strip.
        ``ControlStripLabel.TLabel`` — Segoe UI Semibold 9 on the strip background.
        ``ControlStrip.TSeparator`` — accent-tinted divider.

    *Segmented toggle buttons*
        ``Segmented.TButton`` — inactive toggle (accent-soft tint).
        ``SegmentedActive.TButton`` — active toggle (full accent bg, bold font).

    *Control strip notebook*
        ``ControlStrip.TNotebook`` / ``ControlStrip.TNotebook.Tab`` — accent-tinted
        tabs; selected tab uses a stronger accent mix.

    *Labels*
        ``TLabel`` (fg_primary), ``Muted.TLabel`` (fg_muted),
        ``SectionTitle.TLabel``, ``SettingsHint.TLabel``,
        ``Title.TLabel`` (18pt bold), ``Status.TLabel`` (10pt bold).

    *Buttons*
        ``TButton`` (secondary_soft bg), ``PrimaryAction.TButton`` (accent bg),
        ``SecondaryAction.TButton`` (secondary_soft bg),
        ``NavAction.TButton`` (accent_soft bg, accent fg — standard navigation),
        ``UtilityAction.TButton`` (secondary_soft bg, fg_primary — muted utility),
        ``Action.Primary/Secondary/Warn/Danger/Success.TButton``.

    *Entry and Combobox*
        ``TEntry``, ``TCombobox`` — bg_surface fieldbackground, themed borders.

    *Scrollbars*
        ``TScrollbar``, ``Horizontal.TScrollbar``, ``Vertical.TScrollbar`` — all
        configured identically using computed trough/thumb/active colors.

    *Treeview*
        ``Treeview`` — bg_surface rows, themed selection colors.
        ``Treeview.Heading`` — panel_strong background, flat relief.

    *Toggles*
        ``Checkbox.TCheckbutton`` / ``Switch.TCheckbutton`` — image indicators for
        ``bw_gui.widgets.Checkbox`` / ``Switch`` (see ``_toggle_styles`` and
        ``docs/TOGGLE_CONTRACT.md``).

    *Canvas default*
        ``option_add("*Canvas.Background", bg_surface)`` — sets the default
        background for any ``tk.Canvas`` created after this call, so bare canvases
        match the surface color without explicit configuration.

    Args:
        root:      Any Tk widget (used to create the ttk.Style instance and to
                   call ``option_add``).
        theme_key: Active theme key.  Falls back to ``DEFAULT_THEME`` if None or
                   unknown.
    """
    _set_current_theme(theme_key)
    theme = get_theme(theme_key)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    border = theme["border"]
    panel_bg = theme.get("panel_strong", theme["bg_panel"])

    root.option_add("*Canvas.Background", theme["bg_surface"])
    root.option_add("*Canvas.HighlightBackground", panel_bg)

    style.configure("TFrame", background=theme["bg_main"])
    style.configure("Surface.TFrame", background=theme["bg_surface"])
    style.configure("Panel.TFrame", background=panel_bg)
    style.configure("Toolbar.TFrame", background=panel_bg)
    style.configure("Settings.Panel.TFrame", background=theme["bg_surface"])
    style.configure("Settings.Sidebar.TFrame", background=panel_bg)

    strip_bg = _mix(theme["bg_surface"], theme["accent_soft"], 0.22)
    strip_border = _mix(border, theme["accent"], 0.18)
    style.configure("ControlStrip.TFrame", background=strip_bg)
    style.configure(
        "ControlStripLabel.TLabel",
        background=strip_bg,
        foreground=theme["fg_primary"],
        font=("Segoe UI Semibold", 9),
    )
    style.configure("ControlStrip.TSeparator", background=strip_border)

    segmented_bg = _mix(theme["bg_surface"], theme["accent_soft"], 0.35)
    style.configure(
        "Segmented.TButton",
        background=segmented_bg,
        foreground=theme["fg_primary"],
        bordercolor=strip_border,
        lightcolor=strip_border,
        darkcolor=strip_border,
        padding=(12, 5),
        relief="flat",
        font=("Segoe UI", 9),
    )
    style.map(
        "Segmented.TButton",
        background=[("active", _mix(theme["accent_soft"], theme["bg_surface"], 0.30)),
                    ("pressed", _mix(theme["accent_soft"], theme["bg_surface"], 0.30))],
        foreground=[("active", theme["fg_primary"]), ("pressed", theme["fg_primary"])],
    )
    style.configure(
        "SegmentedActive.TButton",
        background=theme["accent"],
        foreground=theme["fg_on_accent"],
        bordercolor=theme["accent"],
        lightcolor=theme["accent"],
        darkcolor=theme["accent"],
        padding=(12, 5),
        relief="flat",
        font=("Segoe UI Semibold", 9),
    )
    style.map(
        "SegmentedActive.TButton",
        background=[("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[("active", theme["fg_on_accent"]), ("pressed", theme["fg_on_accent"])],
    )

    tab_bg = _mix(theme["bg_surface"], theme["accent_soft"], 0.15)
    tab_selected_bg = _mix(theme["accent"], theme["bg_surface"], 0.12)
    tab_hover_bg = _mix(theme["accent_soft"], theme["bg_surface"], 0.30)
    style.configure(
        "ControlStrip.TNotebook",
        background=strip_bg,
        bordercolor=strip_border,
        lightcolor=strip_border,
        darkcolor=strip_border,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "ControlStrip.TNotebook.Tab",
        background=tab_bg,
        foreground=theme["fg_muted"],
        bordercolor=strip_border,
        lightcolor=strip_border,
        darkcolor=strip_border,
        padding=(12, 5),
        font=("Segoe UI", 9),
    )
    style.map(
        "ControlStrip.TNotebook.Tab",
        background=[("selected", tab_selected_bg), ("active", tab_hover_bg)],
        foreground=[("selected", theme["fg_primary"]), ("active", theme["fg_primary"])],
    )

    style.configure("TLabel", background=theme["bg_main"], foreground=theme["fg_primary"])
    style.configure("Muted.TLabel", background=theme["bg_main"], foreground=theme["fg_muted"])
    style.configure("SectionTitle.TLabel", background=theme["bg_main"], foreground=theme["fg_primary"])
    style.configure("SettingsHint.TLabel", background=theme["bg_main"], foreground=theme["fg_muted"])
    style.configure(
        "Title.TLabel",
        background=theme["bg_main"],
        foreground=theme["fg_primary"],
        font=("Segoe UI", 18, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=theme["bg_main"],
        foreground=theme["fg_primary"],
        font=("Segoe UI", 10, "bold"),
    )

    style.configure(
        "TButton",
        background=theme["secondary_soft"],
        foreground=theme["fg_primary"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        focuscolor=theme["focus_ring"],
        padding=(8, 4),
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", theme["accent_soft"]), ("pressed", theme["accent_soft"])],
        foreground=[("disabled", theme["fg_muted"])],
    )
    style.configure(
        "PrimaryAction.TButton",
        background=theme["accent"],
        foreground=theme["fg_on_accent"],
        bordercolor=theme["accent_hover"],
        lightcolor=theme["accent_hover"],
        darkcolor=theme["accent_hover"],
        padding=(12, 5),
    )
    style.map(
        "PrimaryAction.TButton",
        background=[("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[("disabled", theme["fg_muted"])],
    )
    style.configure("SecondaryAction.TButton", background=theme["secondary_soft"], foreground=theme["fg_primary"])
    style.map(
        "SecondaryAction.TButton",
        background=[("active", theme["accent_soft"]), ("pressed", theme["accent_soft"])],
    )
    style.configure(
        "NavAction.TButton",
        background=theme["accent_soft"],
        foreground=theme["accent"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=(8, 4),
    )
    style.map(
        "NavAction.TButton",
        background=[("active", _mix(theme["accent_soft"], theme["accent"], 0.12)),
                    ("pressed", _mix(theme["accent_soft"], theme["accent"], 0.12))],
        foreground=[("active", theme["accent"]), ("pressed", theme["accent"])],
    )
    style.configure(
        "UtilityAction.TButton",
        background=theme["secondary_soft"],
        foreground=theme["fg_primary"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=(8, 4),
    )
    style.map(
        "UtilityAction.TButton",
        background=[("active", theme["accent_soft"]), ("pressed", theme["accent_soft"])],
    )
    style.configure("Action.Primary.TButton", background=theme["accent"], foreground=theme["fg_on_accent"])
    style.map(
        "Action.Primary.TButton",
        background=[("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
    )
    style.configure("Action.Secondary.TButton", background=theme["secondary_soft"], foreground=theme["fg_primary"])
    style.map(
        "Action.Secondary.TButton",
        background=[("active", theme["accent_soft"]), ("pressed", theme["accent_soft"])],
    )
    style.configure("Action.Warn.TButton", background=theme["warning"], foreground=theme["fg_on_warning"])
    style.map(
        "Action.Warn.TButton",
        background=[("active", theme["warning_hover"]), ("pressed", theme["warning_hover"])],
    )
    style.configure("Action.Danger.TButton", background=theme["danger"], foreground=theme["fg_on_danger"])
    style.map(
        "Action.Danger.TButton",
        background=[("active", theme["danger_hover"]), ("pressed", theme["danger_hover"])],
    )
    style.configure("Action.Success.TButton", background=theme["success"], foreground=theme["fg_on_success"])
    style.map(
        "Action.Success.TButton",
        background=[("active", theme["success_hover"]), ("pressed", theme["success_hover"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=theme["bg_surface"],
        foreground=theme["fg_primary"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        insertcolor=theme["fg_primary"],
    )
    style.configure(
        "TCombobox",
        fieldbackground=theme["bg_surface"],
        foreground=theme["fg_primary"],
        background=theme["bg_surface"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        arrowcolor=theme["fg_primary"],
    )

    scroll_trough = _mix(theme["bg_surface"], panel_bg, 0.35)
    scroll_bg = _mix(theme["border"], theme["bg_surface"], 0.46)
    scroll_active = _mix(theme["accent_soft"], theme["bg_surface"], 0.66)
    for scroll_style in ("TScrollbar", "Horizontal.TScrollbar", "Vertical.TScrollbar"):
        style.configure(
            scroll_style,
            troughcolor=scroll_trough,
            background=scroll_bg,
            arrowcolor=theme["fg_primary"],
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            gripcount=0,
        )
        style.map(
            scroll_style,
            background=[("active", scroll_active), ("pressed", scroll_active)],
            arrowcolor=[
                ("active", theme["fg_primary"]),
                ("pressed", theme["fg_primary"]),
                ("disabled", theme["fg_muted"]),
            ],
        )

    style.configure(
        "Treeview",
        background=theme["bg_surface"],
        foreground=theme["fg_primary"],
        fieldbackground=theme["bg_surface"],
        bordercolor=border,
        lightcolor=theme["bg_surface"],
        darkcolor=theme["bg_surface"],
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", theme["selection_bg"])],
        foreground=[("selected", theme["selection_fg"])],
    )
    style.configure(
        "Treeview.Heading",
        background=panel_bg,
        foreground=theme["fg_primary"],
        bordercolor=border,
        lightcolor=panel_bg,
        darkcolor=panel_bg,
        relief="flat",
    )
    style.map(
        "Treeview.Heading",
        background=[("active", _mix(panel_bg, theme["accent"], 0.08))],
    )

    from ._toggle_styles import configure_toggle_styles  # late import avoids circular dependency
    configure_toggle_styles(root, style, theme)

    # Recolor all registered icon buttons for the new theme.
    from ._widget_utils import _reapply_icon_buttons  # late import avoids circular dependency
    _reapply_icon_buttons()
