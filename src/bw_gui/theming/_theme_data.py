"""Static theme data: palette definitions, ordering, and key contracts.

This module is internal to bw_gui.theming. Consumer code should import from
bw_gui.theming (the public __init__) rather than from this module directly.
"""

from __future__ import annotations

THEME_CORE_KEYS: tuple[str, ...] = (
    "bg_main",
    "bg_surface",
    "fg_primary",
    "fg_muted",
    "accent",
    "accent_hover",
    "accent_soft",
    "danger",
    "border",
)

THEME_TOKEN_ALIASES: dict[str, str] = {
    "error": "danger",
    "error_hover": "danger_hover",
    "error_soft": "danger_soft",
    "fg_on_error": "fg_on_danger",
}

THEME_CONTRACT_KEYS: tuple[str, ...] = (
    "label",
    *THEME_CORE_KEYS,
    "bg_panel",
    "panel_strong",
    "secondary",
    "secondary_soft",
    "selection_bg",
    "selection_fg",
    "success",
    "success_hover",
    "success_soft",
    "warning",
    "warning_hover",
    "warning_soft",
    "danger_hover",
    "danger_soft",
    "focus_ring",
    "button_fg",
    "fg_on_accent",
    "fg_on_success",
    "fg_on_warning",
    "fg_on_danger",
    "error",
    "error_hover",
    "error_soft",
    "fg_on_error",
    "hospitation",
    "hospitation_hover",
    "hospitation_soft",
    "fg_on_hospitation",
)

THEMES: dict[str, dict[str, str]] = {
    # ── Neutral / kursplaner family ───────────────────────────────────────────
    "mono_day": {
        "label": "Mono Day",
        "bg_main": "#F2F3F5", "bg_panel": "#E9EBEF", "bg_surface": "#FFFFFF",
        "panel_strong": "#DDE1E7", "secondary": "#4A5568", "secondary_soft": "#E1E5EC",
        "fg_primary": "#111827", "fg_muted": "#4B5563",
        "accent": "#2563EB", "accent_hover": "#1E56CF", "accent_soft": "#D6E3FF",
        "selection_bg": "#1D4ED8", "selection_fg": "#FFFFFF",
        "success": "#16A34A", "success_hover": "#15803D", "success_soft": "#D8F0DF",
        "warning": "#D97706", "warning_hover": "#B95F04", "warning_soft": "#F5E6D2",
        "danger": "#DC2626", "danger_hover": "#BE2020", "danger_soft": "#F7D9D9",
        "focus_ring": "#2563EB", "border": "#B9C0CB",
    },
    "porcelain": {
        "label": "Porcelain",
        "bg_main": "#F8F9FA", "bg_panel": "#F0F2F5", "bg_surface": "#FFFFFF",
        "panel_strong": "#E3E7ED", "secondary": "#5E6470", "secondary_soft": "#E7EBF1",
        "fg_primary": "#111827", "fg_muted": "#5B6472",
        "accent": "#7C3AED", "accent_hover": "#6D32D2", "accent_soft": "#E4DAFA",
        "selection_bg": "#6D28D9", "selection_fg": "#FFFFFF",
        "success": "#16A34A", "success_hover": "#15803D", "success_soft": "#DCF0E2",
        "warning": "#D97706", "warning_hover": "#BF6A05", "warning_soft": "#F6E8D5",
        "danger": "#DB2777", "danger_hover": "#C0226A", "danger_soft": "#F7DCE9",
        "focus_ring": "#7C3AED", "border": "#C5CCD8",
    },
    "steel_morning": {
        "label": "Steel Morning",
        "bg_main": "#F4F4F5", "bg_panel": "#ECEDEF", "bg_surface": "#FFFFFF",
        "panel_strong": "#DEE1E5", "secondary": "#52525B", "secondary_soft": "#E4E6EA",
        "fg_primary": "#18181B", "fg_muted": "#52525B",
        "accent": "#0F766E", "accent_hover": "#0B645E", "accent_soft": "#CFECE8",
        "selection_bg": "#0F766E", "selection_fg": "#F8FFFE",
        "success": "#3F8F3F", "success_hover": "#377D37", "success_soft": "#DAE9DA",
        "warning": "#CA8A04", "warning_hover": "#AF7803", "warning_soft": "#F2EACF",
        "danger": "#BE123C", "danger_hover": "#A90F36", "danger_soft": "#F2D7DF",
        "focus_ring": "#0F766E", "border": "#BDC3CC",
    },
    "foglight": {
        "label": "Foglight",
        "bg_main": "#F5F6F8", "bg_panel": "#ECEFF3", "bg_surface": "#FFFFFF",
        "panel_strong": "#E1E5EB", "secondary": "#5B6472", "secondary_soft": "#E6EAF0",
        "fg_primary": "#111827", "fg_muted": "#5E6878",
        "accent": "#0284C7", "accent_hover": "#036FA8", "accent_soft": "#D7EAF6",
        "selection_bg": "#0369A1", "selection_fg": "#FFFFFF",
        "success": "#15803D", "success_hover": "#136C34", "success_soft": "#D9EADB",
        "warning": "#B45309", "warning_hover": "#9C4708", "warning_soft": "#F0E0D3",
        "danger": "#BE123C", "danger_hover": "#A60F35", "danger_soft": "#F0D8DF",
        "focus_ring": "#0284C7", "border": "#C0C7D2",
    },
    "mono_night": {
        "label": "Mono Night",
        "bg_main": "#0F1115", "bg_panel": "#151922", "bg_surface": "#1C2230",
        "panel_strong": "#252D3D", "secondary": "#64748B", "secondary_soft": "#222A39",
        "fg_primary": "#E5E7EB", "fg_muted": "#AAB0BD",
        "accent": "#3B82F6", "accent_hover": "#2F70DF", "accent_soft": "#213450",
        "selection_bg": "#2563EB", "selection_fg": "#F8FAFC",
        "success": "#22C55E", "success_hover": "#1FAE54", "success_soft": "#223D31",
        "warning": "#F59E0B", "warning_hover": "#D6880A", "warning_soft": "#463620",
        "danger": "#EF4444", "danger_hover": "#D73C3C", "danger_soft": "#4A272C",
        "focus_ring": "#60A5FA", "border": "#3A4354",
    },
    "charcoal": {
        "label": "Charcoal",
        "bg_main": "#101113", "bg_panel": "#171A1F", "bg_surface": "#1E232B",
        "panel_strong": "#282E38", "secondary": "#778092", "secondary_soft": "#242A34",
        "fg_primary": "#E8ECF3", "fg_muted": "#B0B8C6",
        "accent": "#3B82F6", "accent_hover": "#3170D9", "accent_soft": "#22364F",
        "selection_bg": "#2563EB", "selection_fg": "#F8FAFC",
        "success": "#22C55E", "success_hover": "#1FAE54", "success_soft": "#243B30",
        "warning": "#F59E0B", "warning_hover": "#D8890A", "warning_soft": "#473821",
        "danger": "#EF4444", "danger_hover": "#D33D3D", "danger_soft": "#4A292D",
        "focus_ring": "#60A5FA", "border": "#3A4250",
    },
    "graphite_core": {
        "label": "Graphite Core",
        "bg_main": "#121315", "bg_panel": "#191B1F", "bg_surface": "#21252B",
        "panel_strong": "#2A2F37", "secondary": "#707784", "secondary_soft": "#242932",
        "fg_primary": "#ECEFF4", "fg_muted": "#AEB5C0",
        "accent": "#06B6D4", "accent_hover": "#089AB3", "accent_soft": "#203842",
        "selection_bg": "#0891B2", "selection_fg": "#F3FCFF",
        "success": "#22C55E", "success_hover": "#1EAF53", "success_soft": "#243B30",
        "warning": "#F59E0B", "warning_hover": "#D8880A", "warning_soft": "#493A20",
        "danger": "#F43F5E", "danger_hover": "#DA3653", "danger_soft": "#4A2730",
        "focus_ring": "#22D3EE", "border": "#3A404A",
    },
    # ── Blattwerk family ──────────────────────────────────────────────────────
    "slate_indigo": {
        "label": "Slate and Indigo",
        "bg_main": "#EEF1F6", "bg_surface": "#FFFFFF",
        "fg_primary": "#1F2937", "fg_muted": "#5B6472",
        "accent": "#4F46E5", "accent_hover": "#4338CA", "accent_soft": "#DDE1FF",
        "danger": "#A73B3B", "border": "#C7CFDD", "button_fg": "#FFFFFF",
    },
    "forest_moss": {
        "label": "Forest and Moss",
        "bg_main": "#EEF3EF", "bg_surface": "#FAFCFA",
        "fg_primary": "#21322A", "fg_muted": "#587265",
        "accent": "#3E7A5D", "accent_hover": "#33664E", "accent_soft": "#D7E6DD",
        "danger": "#A14D45", "border": "#BDD1C5", "button_fg": "#FFFFFF",
    },
    "sand_terracotta": {
        "label": "Sand and Terracotta",
        "bg_main": "#F5EFE6", "bg_surface": "#FFF9F3",
        "fg_primary": "#3B3129", "fg_muted": "#7A6A5E",
        "accent": "#B8634F", "accent_hover": "#A45443", "accent_soft": "#EBD8CC",
        "danger": "#9B4A3B", "border": "#D9C7B8", "button_fg": "#FFFFFF",
    },
    "midnight_cyan": {
        "label": "Midnight and Cyan",
        "bg_main": "#1E252D", "bg_surface": "#26313C",
        "fg_primary": "#CCD6E0", "fg_muted": "#9DAAB8",
        "accent": "#18A7C9", "accent_hover": "#1286A2", "accent_soft": "#2F3E4A",
        "danger": "#E08A7E", "border": "#435564", "button_fg": "#FFFFFF",
    },
    "lavender_graphite": {
        "label": "Lavender and Graphite",
        "bg_main": "#F2F1F8", "bg_surface": "#FCFBFF",
        "fg_primary": "#302D39", "fg_muted": "#666174",
        "accent": "#6E5BC7", "accent_hover": "#5946B1", "accent_soft": "#E0DAF6",
        "danger": "#A84A66", "border": "#CBC4E7", "button_fg": "#FFFFFF",
    },
    "obsidian_gold": {
        "label": "Obsidian and Gold",
        "bg_main": "#1C1D1F", "bg_surface": "#242629",
        "fg_primary": "#D6CEBF", "fg_muted": "#AAA18F",
        "accent": "#C9A34A", "accent_hover": "#B28E3E", "accent_soft": "#34312A",
        "danger": "#D9886B", "border": "#4A4740", "button_fg": "#121212",
    },
}

THEME_ORDER: list[str] = [
    "mono_day", "porcelain", "steel_morning", "foglight",    # light neutrals
    "mono_night", "charcoal", "graphite_core",               # dark neutrals
    "slate_indigo", "forest_moss", "sand_terracotta",        # blattwerk warm
    "midnight_cyan", "lavender_graphite", "obsidian_gold",   # blattwerk cool
]

DEFAULT_THEME = "mono_day"

THEME_INTENSITY_LEVELS: dict[str, float] = {
    "dezent": 0.5,
    "mittel": 0.75,
    "kräftig": 1.0,
}
DEFAULT_THEME_INTENSITY = "kräftig"
