"""Theme manager: color utilities, intensity scaling, ttk style registration.

All theme data (THEMES dict, THEME_ORDER, constants) lives in _theme_data; this
module owns the runtime API — intensity state, color math, and style configuration.

``configure_ttk_theme`` sets the globally tracked current theme so all subsequent
utility calls resolve colors without a ``theme_key`` argument.  Consumer code
must never call ``get_theme()`` directly or construct color strings manually::

    from bw_gui.theming import configure_ttk_theme, theme_canvas, tinted_color

    class MyApp(BwBaseWindow):
        def apply_theme(self, theme_key: str) -> None:
            super().apply_theme(theme_key)
            configure_ttk_theme(self.tk_root, theme_key)  # sets global current theme
            theme_canvas(self._canvas)                    # no theme_key needed
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ._theme_data import (
    DEFAULT_THEME,
    DEFAULT_THEME_INTENSITY,
    THEME_CONTRACT_KEYS,
    THEME_CORE_KEYS,
    THEME_INTENSITY_LEVELS,
    THEME_ORDER,
    THEME_TOKEN_ALIASES,
    THEMES,
)

__all__ = [
    "DEFAULT_THEME",
    "DEFAULT_THEME_INTENSITY",
    "THEME_CONTRACT_KEYS",
    "THEME_CORE_KEYS",
    "THEME_INTENSITY_LEVELS",
    "THEME_ORDER",
    "THEME_TOKEN_ALIASES",
    "THEMES",
    "apply_window_theme",
    "configure_tinted_button_style",
    "configure_ttk_theme",
    "get_theme",
    "get_theme_intensity",
    "normalize_theme_key",
    "register_theme",
    "set_theme_intensity",
    "theme_contract_keys",
    "tinted_color",
    "tinted_foreground",
]

# ── Intensity state ──────────────────────────────────────────────────────────

_theme_intensity: str = DEFAULT_THEME_INTENSITY

# ── Current-theme state ──────────────────────────────────────────────────────

_current_theme_key: str = DEFAULT_THEME


def set_theme_intensity(level: str) -> None:
    """Set the global accent intensity level for the current process.

    Accepts ``"dezent"`` (0.5×), ``"mittel"`` (0.75×), or ``"kräftig"`` (1.0×,
    the default).  Any unknown value silently resets to the default.

    Intensity affects all subsequent ``get_theme()`` calls: ``"dezent"`` visually
    mutes accent, success, warning, and danger colors — useful when the UI is dense
    and full-strength color creates visual noise (e.g. a schedule grid with many
    color-coded lesson blocks).  ``"kräftig"`` is a no-op; it preserves the raw
    token values.

    Programs that want intensity control should call this from their settings
    dialog and then re-apply the current theme to all open windows.
    """
    global _theme_intensity
    _theme_intensity = level if level in THEME_INTENSITY_LEVELS else DEFAULT_THEME_INTENSITY


def get_theme_intensity() -> str:
    """Return the currently active intensity level string.

    One of ``"dezent"``, ``"mittel"``, or ``"kräftig"``.  Useful for initializing
    a settings widget to the current value on first open.
    """
    return _theme_intensity


# ── Private color helpers ────────────────────────────────────────────────────

def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse a ``"#RRGGBB"`` string into an (R, G, B) int tuple.

    Strips leading ``#`` and whitespace.  Returns ``(0, 0, 0)`` for any input
    that is not exactly 6 hex digits after stripping.
    """
    text = color.strip().lstrip("#")
    if len(text) != 6:
        return (0, 0, 0)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _mix(color_a: str, color_b: str, ratio: float) -> str:
    """Linearly interpolate between two ``"#RRGGBB"`` hex colors.

    ``ratio=0.0`` returns *color_a* unchanged; ``ratio=1.0`` returns *color_b*.
    Values outside [0, 1] are clamped.  Returns a ``"#RRGGBB"`` string.
    """
    ax, ay, az = _hex_to_rgb(color_a)
    bx, by, bz = _hex_to_rgb(color_b)
    w = max(0.0, min(1.0, ratio))
    return (
        f"#{round(ax + (bx - ax) * w):02X}"
        f"{round(ay + (by - ay) * w):02X}"
        f"{round(az + (bz - az) * w):02X}"
    )


def _is_dark(color: str) -> bool:
    """Return True if *color* is perceptually dark using a fast luminance check.

    Uses weighted-average luminance (the W3C fast approximation) against a
    threshold of 0.45.  Not the full WCAG linearized calculation — use
    ``relative_luminance()`` when WCAG contrast ratios matter.
    """
    r, g, b = _hex_to_rgb(color)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return luminance < 0.45


# ── Public color utilities ───────────────────────────────────────────────────

def mix_hex(base: str, target: str, ratio: float) -> str:
    """Mix two ``"#RRGGBB"`` hex colors and return the result.

    Thin public alias for the internal ``_mix()`` helper.

    Args:
        base:   Starting color (``ratio=0`` returns this unchanged).
        target: Ending color (``ratio=1`` returns this unchanged).
        ratio:  Blend weight in [0, 1]; values outside that range are clamped.

    Returns:
        A ``"#RRGGBB"`` hex string for the blended color.

    Example — tint ``bg_surface`` with ``accent`` at 20%::

        tinted = mix_hex(theme["bg_surface"], theme["accent"], 0.20)
    """
    return _mix(base, target, ratio)


def relative_luminance(hex_color: str) -> float:
    """Compute the WCAG 2.1 relative luminance of a ``"#RRGGBB"`` hex color.

    Returns a value in [0.0, 1.0], where 0.0 is absolute black and 1.0 is
    absolute white.  Uses the full IEC 61966-2-1 sRGB linearization rather
    than the fast approximation used by ``_is_dark()``.

    Returns 0.0 for any unparseable input rather than raising.
    """
    color = hex_color.strip().lstrip("#")
    if len(color) != 6:
        return 0.0
    try:
        r = int(color[0:2], 16) / 255.0
        g = int(color[2:4], 16) / 255.0
        b = int(color[4:6], 16) / 255.0
    except ValueError:
        return 0.0

    def _srgb(c: float) -> float:
        """Linearise a single sRGB channel component to linear light."""
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast_text_color(bg_hex: str) -> str:
    """Return the highest-contrast text color (dark or white) for a given background.

    Uses ``relative_luminance()`` against a threshold of 0.38.  Returns
    ``"#111111"`` for light backgrounds and ``"#FFFFFF"`` for dark ones.

    Useful when computing foreground color for a dynamically-generated button
    background, e.g. inside ``configure_tinted_button_style()``.
    """
    return "#111111" if relative_luminance(bg_hex) >= 0.38 else "#FFFFFF"


def is_dark_color(color: str) -> bool:
    """Return True if *color* is perceptually dark.

    Public alias for ``_is_dark()``.  Use this to decide whether to apply a
    dark or light window chrome (title bar) via ``apply_window_chrome_theme()``.
    """
    return _is_dark(color)


def tinted_color(
    mix_color: str,
    *,
    degree: float = 0.15,
    base_token: str = "auto",
    theme_key: str | None = None,
) -> str:
    """Return a theme-adapted tinted color for any widget background property.

    Generalises ``configure_tinted_button_style`` to a pure color value usable
    as canvas fill, label ``bg``, cell background, or icon pixel color.  All
    dark/light adaptation is internal — callers never branch on theme darkness.
    When *theme_key* is ``None``, the globally tracked current theme (set by the
    most recent ``configure_ttk_theme`` call) is used automatically.

    Args:
        mix_color:  ``"#RRGGBB"`` hex literal OR a bw_gui token name (e.g.
                    ``"success_soft"``, ``"accent"``).  Token names resolve from
                    the active theme dict.
        degree:     Tint strength in [0, 1].  0 = pure base color; 1 = pure
                    *mix_color*.  ``base_token="auto"`` provides dark/light
                    adaptation by selecting a darker or lighter neutral base.
        base_token: Theme token used as the neutral mixing base.  ``"auto"``
                    picks ``bg_panel`` for dark themes and ``bg_surface`` for
                    light themes.  Override with any token name, e.g.
                    ``"panel_strong"``.
        theme_key:  Explicit theme override; ``None`` uses the globally tracked
                    current theme.

    Returns:
        ``"#RRGGBB"`` hex string for the tinted color.
    """
    theme = get_theme(theme_key)
    is_dark = _is_dark(theme["bg_main"])
    if base_token == "auto":
        base_hex = theme["bg_panel"] if is_dark else theme.get("bg_surface", theme["bg_main"])
    else:
        base_hex = theme.get(base_token, theme.get("bg_surface", theme["bg_main"]))
    resolved_mix = theme.get(mix_color, mix_color) if not mix_color.startswith("#") else mix_color
    return _mix(base_hex, resolved_mix, degree)


def tinted_foreground(
    mix_color: str,
    *,
    degree: float = 0.15,
    base_token: str = "auto",
    theme_key: str | None = None,
) -> str:
    """Return the highest-contrast text color for a ``tinted_color`` background.

    Computes ``tinted_color(mix_color, degree=degree, base_token=base_token,
    theme_key=theme_key)`` internally and returns ``"#111111"`` or ``"#FFFFFF"``
    based on the resulting background luminance.  All arguments are identical to
    ``tinted_color``.

    Use this to determine icon pixel colors, label foreground colors, and any
    other text or symbol rendered on top of a ``tinted_color`` background.

    Args:
        mix_color:  Same as ``tinted_color``.
        degree:     Same as ``tinted_color``.
        base_token: Same as ``tinted_color``.
        theme_key:  Same as ``tinted_color``; ``None`` uses the global current theme.

    Returns:
        ``"#111111"`` for light tinted backgrounds; ``"#FFFFFF"`` for dark ones.
    """
    bg = tinted_color(mix_color, degree=degree, base_token=base_token, theme_key=theme_key)
    return contrast_text_color(bg)


# ── Semantic defaults ────────────────────────────────────────────────────────

def _ensure_semantic_defaults(theme: dict[str, str]) -> dict[str, str]:
    """Fill in any missing semantic tokens from a partial theme dict.

    Blattwerk-family themes (slate_indigo, forest_moss, …) ship only their core
    palette; the neutral family ships the full set.  This function derives every
    token listed in ``THEME_CONTRACT_KEYS`` from the available values so that
    callers can always access any token without ``get()``/``setdefault`` guards.

    Derivation rules (applied only when a key is absent):
    - ``bg_panel``:       35% mix of bg_main→bg_surface
    - ``panel_strong``:   25% mix of bg_panel→border
    - ``secondary``:      35% mix of bg_panel→fg_primary
    - ``secondary_soft``: 45% mix of bg_panel toward bg_surface
    - ``accent_hover``:   15% mix of accent toward black
    - ``selection_bg``:   accent value
    - ``selection_fg``:   white for dark selection, near-black for light
    - ``success``:        #16A34A (green)
    - ``*_hover``:        15% toward black for dark colors, 5% for light colors
    - ``*_soft``:         25% mix of bg_panel with the semantic color
    - ``danger_soft``:    22% mix (slightly stronger)
    - ``focus_ring``:     accent value
    - ``button_fg`` / ``fg_on_*``:  contrast_text_color of the matching bg
    - ``hospitation``:    42% blend of accent and warning
    - alias keys (``error`` → ``danger``, etc.)

    Returns a new dict; the original is not mutated.
    """
    out = dict(theme)
    out.setdefault("bg_panel", _mix(out.get("bg_main", "#FFFFFF"), out.get("bg_surface", "#FFFFFF"), 0.35))
    out.setdefault("panel_strong", _mix(out["bg_panel"], out.get("border", out["bg_panel"]), 0.25))
    out.setdefault("secondary", _mix(out["bg_panel"], out.get("fg_primary", "#111111"), 0.35))
    out.setdefault("secondary_soft", _mix(out["bg_panel"], out.get("bg_surface", out["bg_panel"]), 0.45))
    out.setdefault("accent_hover", _mix(out.get("accent", "#2563EB"), "#000000", 0.15))
    out.setdefault("selection_bg", out.get("accent", "#2563EB"))
    out.setdefault("selection_fg", "#FFFFFF" if _is_dark(out["selection_bg"]) else "#111827")
    out.setdefault("success", "#16A34A")
    out.setdefault("success_hover", _mix(out["success"], "#000000", 0.15 if _is_dark(out["success"]) else 0.05))
    out.setdefault("success_soft", _mix(out["bg_panel"], out["success"], 0.25))
    out.setdefault("warning", "#D97706")
    out.setdefault("warning_hover", _mix(out["warning"], "#000000", 0.15 if _is_dark(out["warning"]) else 0.05))
    out.setdefault("warning_soft", _mix(out["bg_panel"], out["warning"], 0.25))
    out.setdefault("danger_hover", _mix(out.get("danger", "#DC2626"), "#000000", 0.15))
    out.setdefault("danger_soft", _mix(out["bg_panel"], out.get("danger", "#DC2626"), 0.22))
    out.setdefault("focus_ring", out.get("accent", "#2563EB"))
    out.setdefault("button_fg", "#FFFFFF" if _is_dark(out.get("accent", "#2563EB")) else "#111827")
    out.setdefault("fg_on_accent", "#FFFFFF" if _is_dark(out.get("accent", "#2563EB")) else "#111827")
    out.setdefault("fg_on_success", "#FFFFFF" if _is_dark(out["success"]) else "#111827")
    out.setdefault("fg_on_warning", "#FFFFFF" if _is_dark(out["warning"]) else "#111827")
    out.setdefault("fg_on_danger", "#FFFFFF" if _is_dark(out.get("danger", "#DC2626")) else "#111827")
    out.setdefault("hospitation", _mix(out.get("accent", "#2563EB"), out.get("warning", "#D97706"), 0.42))
    out.setdefault(
        "hospitation_hover",
        _mix(out["hospitation"], "#000000", 0.15 if _is_dark(out["hospitation"]) else 0.05),
    )
    out.setdefault("hospitation_soft", _mix(out["bg_panel"], out["hospitation"], 0.24))
    out.setdefault("fg_on_hospitation", "#FFFFFF" if _is_dark(out["hospitation"]) else "#111827")
    for alias_key, canonical_key in THEME_TOKEN_ALIASES.items():
        out.setdefault(alias_key, out.get(canonical_key, ""))
    return out


def _apply_intensity(theme: dict[str, str]) -> dict[str, str]:
    """Scale accent and semantic colors by the current global intensity level.

    When the level is ``"kräftig"`` (1.0, the default) this is a pure no-op and
    returns the input dict unchanged.  For ``"mittel"`` (0.75) and ``"dezent"``
    (0.5) it mutes colors by mixing them toward the panel background:

    - Accent family (accent, accent_hover, accent_soft, selection_bg, focus_ring):
      blended at ``strength`` (0.5 or 0.75).
    - Semantic full colors (success, warning, danger and their hovers):
      blended at ``clamp(0.7 + 0.3 * strength, 1.0)`` — attenuated less aggressively
      so red/green/amber remain recognizable even at "dezent".
    - Soft backgrounds (success_soft, warning_soft, danger_soft):
      blended at ``clamp(0.5 + 0.4 * strength, 1.0)``.

    Returns a new dict; the input is not mutated.
    """
    strength = THEME_INTENSITY_LEVELS.get(_theme_intensity, 1.0)
    if strength >= 1.0:
        return theme
    neutral = theme.get("bg_panel", theme.get("bg_main", "#FFFFFF"))
    adjusted = dict(theme)
    for key in ("accent", "accent_hover", "accent_soft", "selection_bg", "focus_ring"):
        if key in adjusted:
            adjusted[key] = _mix(neutral, adjusted[key], strength)
    semantic_strength = min(1.0, 0.7 + 0.3 * strength)
    for key in ("success", "success_hover", "warning", "warning_hover", "danger", "danger_hover"):
        if key in adjusted:
            adjusted[key] = _mix(neutral, adjusted[key], semantic_strength)
    soft_strength = min(1.0, 0.5 + 0.4 * strength)
    for key in ("success_soft", "warning_soft", "danger_soft"):
        if key in adjusted:
            adjusted[key] = _mix(neutral, adjusted[key], soft_strength)
    return adjusted


# ── Public theme API ─────────────────────────────────────────────────────────

def register_theme(theme_key: str, values: dict[str, str], *, append_order: bool = True) -> None:
    """Register a custom theme in the shared registry at runtime.

    Useful for programs that ship an app-specific theme (e.g. a branded color
    scheme) alongside the built-in bw_gui themes.  After registration the theme
    appears in ``THEMES``, and — by default — at the end of ``THEME_ORDER`` so
    it shows up in the View menu.

    Args:
        theme_key:    Unique snake_case identifier (e.g. ``"my_brand"``).
        values:       Partial or full token dict.  Missing tokens are filled by
                      ``_ensure_semantic_defaults()`` each time ``get_theme()`` is
                      called, so only the core palette is required.
        append_order: If True (default) and the key is not already in
                      ``THEME_ORDER``, append it so the View menu includes it.
    """
    THEMES[theme_key] = dict(values)
    if append_order and theme_key not in THEME_ORDER:
        THEME_ORDER.append(theme_key)


def normalize_theme_key(theme_key: str | None = None) -> str:
    """Return *theme_key* if it exists in ``THEMES``, otherwise ``DEFAULT_THEME``.

    Lets callers pass ``None`` or an unknown string without crashing — the result
    is always a valid dict key.
    """
    return theme_key if theme_key in THEMES else DEFAULT_THEME


def _set_current_theme(key: str | None) -> None:
    """Record *key* as the globally active theme.

    Called by ``configure_ttk_theme`` on every theme switch so that all
    subsequent utility calls (``tinted_color``, ``theme_canvas``,
    ``get_theme()`` with no argument, etc.) automatically resolve the correct
    active theme without callers forwarding ``theme_key``.
    """
    global _current_theme_key
    _current_theme_key = normalize_theme_key(key)


def get_theme(theme_key: str | None = None) -> dict[str, str]:
    """Return the fully-resolved theme dict for the given key.

    This is the primary API for reading theme tokens.  It:
    1. Normalises the key via ``normalize_theme_key()`` (falls back to
       ``DEFAULT_THEME`` for unknown keys or ``None``).
    2. Expands the raw palette with ``_ensure_semantic_defaults()`` so every key
       listed in ``THEME_CONTRACT_KEYS`` is present.
    3. Applies the current global intensity scaling via ``_apply_intensity()``.

    Returns a new dict; the original palette in ``THEMES`` is never mutated.

    When *theme_key* is ``None``, returns the globally tracked current theme
    (set by the most recent ``configure_ttk_theme`` call) rather than the static
    default.  Consumer code should not need to call this directly — use
    ``tinted_color`` or the widget utility helpers instead.
    """
    key = _current_theme_key if theme_key is None else theme_key
    base = _ensure_semantic_defaults(THEMES[normalize_theme_key(key)])
    return _apply_intensity(base)


def theme_contract_keys() -> tuple[str, ...]:
    """Return the tuple of token names guaranteed by ``get_theme()`` for all themes.

    Consumers that iterate over token sets (e.g. to validate a custom theme or
    build a theme preview widget) should call this rather than hardcoding the list.
    """
    return THEME_CONTRACT_KEYS


def apply_window_theme(window: tk.Misc, theme_key: str | None = None) -> None:
    """Set the Tk root background to the theme's ``bg_main`` color.

    Primarily for raw ``tk.Tk`` roots that sit outside a ``BwBaseWindow``
    (e.g. splash screens, secondary top-levels).  The ``BwBaseWindow`` class
    handles this automatically through ``TkinterAppShell``.
    """
    theme = get_theme(theme_key)
    window.configure(bg=theme["bg_main"])


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

    # Recolor all registered icon buttons for the new theme.
    from .widget_utils import _reapply_icon_buttons  # late import avoids circular dependency
    _reapply_icon_buttons()
