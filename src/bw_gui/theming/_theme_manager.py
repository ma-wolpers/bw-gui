"""Theme manager: theme registry, intensity scaling, current theme, tinting.

Color math lives in ``_color_math`` and ttk style registration in ``_ttk_theme``;
both are re-exported here so ``from ._theme_manager import ...`` stays stable.

All theme data (THEMES dict, THEME_ORDER, constants) lives in _theme_data; this
module owns the runtime API — intensity state, the current theme and tinting.

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
from ._color_math import (  # noqa: F401 - re-exported, used by sibling modules
    _hex_to_rgb,
    _is_dark,
    _mix,
    contrast_text_color,
    is_dark_color,
    mix_hex,
    relative_luminance,
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


# Re-export (at the end: _ttk_theme imports get_theme/_set_current_theme from here;
# the theming package __init__ always imports this module first).
from ._ttk_theme import configure_tinted_button_style, configure_ttk_theme  # noqa: E402,F401
