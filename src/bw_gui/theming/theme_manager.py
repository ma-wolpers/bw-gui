"""Unified theme manager for Kursplaner and Blattwerk design families."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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
    # Kursplaner baseline family
    "mono_day": {
        "label": "Mono Day",
        "bg_main": "#F2F3F5",
        "bg_panel": "#E9EBEF",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#DDE1E7",
        "secondary": "#4A5568",
        "secondary_soft": "#E1E5EC",
        "fg_primary": "#111827",
        "fg_muted": "#4B5563",
        "accent": "#2563EB",
        "accent_hover": "#1E56CF",
        "accent_soft": "#D6E3FF",
        "selection_bg": "#1D4ED8",
        "selection_fg": "#FFFFFF",
        "success": "#16A34A",
        "success_hover": "#15803D",
        "success_soft": "#D8F0DF",
        "warning": "#D97706",
        "warning_hover": "#B95F04",
        "warning_soft": "#F5E6D2",
        "danger": "#DC2626",
        "danger_hover": "#BE2020",
        "danger_soft": "#F7D9D9",
        "focus_ring": "#2563EB",
        "border": "#B9C0CB",
    },
    "mono_night": {
        "label": "Mono Night",
        "bg_main": "#0F1115",
        "bg_panel": "#151922",
        "bg_surface": "#1C2230",
        "panel_strong": "#252D3D",
        "secondary": "#64748B",
        "secondary_soft": "#222A39",
        "fg_primary": "#E5E7EB",
        "fg_muted": "#AAB0BD",
        "accent": "#3B82F6",
        "accent_hover": "#2F70DF",
        "accent_soft": "#213450",
        "selection_bg": "#2563EB",
        "selection_fg": "#F8FAFC",
        "success": "#22C55E",
        "success_hover": "#1FAE54",
        "success_soft": "#223D31",
        "warning": "#F59E0B",
        "warning_hover": "#D6880A",
        "warning_soft": "#463620",
        "danger": "#EF4444",
        "danger_hover": "#D73C3C",
        "danger_soft": "#4A272C",
        "focus_ring": "#60A5FA",
        "border": "#3A4354",
    },
    "porcelain": {
        "label": "Porcelain",
        "bg_main": "#F8F9FA",
        "bg_panel": "#F0F2F5",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#E3E7ED",
        "secondary": "#5E6470",
        "secondary_soft": "#E7EBF1",
        "fg_primary": "#111827",
        "fg_muted": "#5B6472",
        "accent": "#7C3AED",
        "accent_hover": "#6D32D2",
        "accent_soft": "#E4DAFA",
        "selection_bg": "#6D28D9",
        "selection_fg": "#FFFFFF",
        "success": "#16A34A",
        "success_hover": "#15803D",
        "success_soft": "#DCF0E2",
        "warning": "#D97706",
        "warning_hover": "#BF6A05",
        "warning_soft": "#F6E8D5",
        "danger": "#DB2777",
        "danger_hover": "#C0226A",
        "danger_soft": "#F7DCE9",
        "focus_ring": "#7C3AED",
        "border": "#C5CCD8",
    },
    "charcoal": {
        "label": "Charcoal",
        "bg_main": "#101113",
        "bg_panel": "#171A1F",
        "bg_surface": "#1E232B",
        "panel_strong": "#282E38",
        "secondary": "#778092",
        "secondary_soft": "#242A34",
        "fg_primary": "#E8ECF3",
        "fg_muted": "#B0B8C6",
        "accent": "#3B82F6",
        "accent_hover": "#3170D9",
        "accent_soft": "#22364F",
        "selection_bg": "#2563EB",
        "selection_fg": "#F8FAFC",
        "success": "#22C55E",
        "success_hover": "#1FAE54",
        "success_soft": "#243B30",
        "warning": "#F59E0B",
        "warning_hover": "#D8890A",
        "warning_soft": "#473821",
        "danger": "#EF4444",
        "danger_hover": "#D33D3D",
        "danger_soft": "#4A292D",
        "focus_ring": "#60A5FA",
        "border": "#3A4250",
    },
    # Blattwerk family
    "slate_indigo": {
        "label": "Slate and Indigo",
        "bg_main": "#EEF1F6",
        "bg_surface": "#FFFFFF",
        "fg_primary": "#1F2937",
        "fg_muted": "#5B6472",
        "accent": "#4F46E5",
        "accent_hover": "#4338CA",
        "accent_soft": "#DDE1FF",
        "danger": "#A73B3B",
        "border": "#C7CFDD",
        "button_fg": "#FFFFFF",
    },
    "forest_moss": {
        "label": "Forest and Moss",
        "bg_main": "#EEF3EF",
        "bg_surface": "#FAFCFA",
        "fg_primary": "#21322A",
        "fg_muted": "#587265",
        "accent": "#3E7A5D",
        "accent_hover": "#33664E",
        "accent_soft": "#D7E6DD",
        "danger": "#A14D45",
        "border": "#BDD1C5",
        "button_fg": "#FFFFFF",
    },
    "sand_terracotta": {
        "label": "Sand and Terracotta",
        "bg_main": "#F5EFE6",
        "bg_surface": "#FFF9F3",
        "fg_primary": "#3B3129",
        "fg_muted": "#7A6A5E",
        "accent": "#B8634F",
        "accent_hover": "#A45443",
        "accent_soft": "#EBD8CC",
        "danger": "#9B4A3B",
        "border": "#D9C7B8",
        "button_fg": "#FFFFFF",
    },
    "midnight_cyan": {
        "label": "Midnight and Cyan",
        "bg_main": "#1E252D",
        "bg_surface": "#26313C",
        "fg_primary": "#CCD6E0",
        "fg_muted": "#9DAAB8",
        "accent": "#18A7C9",
        "accent_hover": "#1286A2",
        "accent_soft": "#2F3E4A",
        "danger": "#E08A7E",
        "border": "#435564",
        "button_fg": "#FFFFFF",
    },
    "lavender_graphite": {
        "label": "Lavender and Graphite",
        "bg_main": "#F2F1F8",
        "bg_surface": "#FCFBFF",
        "fg_primary": "#302D39",
        "fg_muted": "#666174",
        "accent": "#6E5BC7",
        "accent_hover": "#5946B1",
        "accent_soft": "#E0DAF6",
        "danger": "#A84A66",
        "border": "#CBC4E7",
        "button_fg": "#FFFFFF",
    },
    "obsidian_gold": {
        "label": "Obsidian and Gold",
        "bg_main": "#1C1D1F",
        "bg_surface": "#242629",
        "fg_primary": "#D6CEBF",
        "fg_muted": "#AAA18F",
        "accent": "#C9A34A",
        "accent_hover": "#B28E3E",
        "accent_soft": "#34312A",
        "danger": "#D9886B",
        "border": "#4A4740",
        "button_fg": "#121212",
    },
}

THEME_ORDER = [
    "mono_day",
    "porcelain",
    "mono_night",
    "charcoal",
    "slate_indigo",
    "forest_moss",
    "sand_terracotta",
    "midnight_cyan",
    "lavender_graphite",
    "obsidian_gold",
]

DEFAULT_THEME = "mono_day"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    text = color.strip().lstrip("#")
    if len(text) != 6:
        return (0, 0, 0)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _mix(color_a: str, color_b: str, ratio: float) -> str:
    ax, ay, az = _hex_to_rgb(color_a)
    bx, by, bz = _hex_to_rgb(color_b)
    weight = max(0.0, min(1.0, ratio))
    return f"#{round(ax + (bx - ax) * weight):02X}{round(ay + (by - ay) * weight):02X}{round(az + (bz - az) * weight):02X}"


def _is_dark(color: str) -> bool:
    red, green, blue = _hex_to_rgb(color)
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0
    return luminance < 0.45


def _ensure_semantic_defaults(theme: dict[str, str]) -> dict[str, str]:
    out = dict(theme)
    out.setdefault("bg_panel", _mix(out.get("bg_main", "#FFFFFF"), out.get("bg_surface", "#FFFFFF"), 0.35))
    out.setdefault("panel_strong", _mix(out["bg_panel"], out.get("border", out["bg_panel"]), 0.25))
    out.setdefault("secondary", _mix(out["bg_panel"], out.get("fg_primary", "#111111"), 0.35))
    out.setdefault("secondary_soft", _mix(out["bg_panel"], out.get("bg_surface", out["bg_panel"]), 0.45))
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
        _mix(
            out["hospitation"],
            "#000000",
            0.15 if _is_dark(out["hospitation"]) else 0.05,
        ),
    )
    out.setdefault("hospitation_soft", _mix(out["bg_panel"], out["hospitation"], 0.24))
    out.setdefault("fg_on_hospitation", "#FFFFFF" if _is_dark(out["hospitation"]) else "#111827")
    for alias_key, canonical_key in THEME_TOKEN_ALIASES.items():
        out.setdefault(alias_key, out.get(canonical_key, ""))
    return out


def register_theme(theme_key: str, values: dict[str, str], *, append_order: bool = True) -> None:
    """Register one theme in the shared registry."""
    THEMES[theme_key] = dict(values)
    if append_order and theme_key not in THEME_ORDER:
        THEME_ORDER.append(theme_key)


def normalize_theme_key(theme_key: str | None = None) -> str:
    return theme_key if theme_key in THEMES else DEFAULT_THEME


def get_theme(theme_key: str | None = None) -> dict[str, str]:
    return _ensure_semantic_defaults(THEMES[normalize_theme_key(theme_key)])


def theme_contract_keys() -> tuple[str, ...]:
    """Return the key set guaranteed by ``get_theme`` for every registered theme."""
    return THEME_CONTRACT_KEYS


def apply_window_theme(window: tk.Misc, theme_key: str | None = None) -> None:
    theme = get_theme(theme_key)
    window.configure(bg=theme["bg_main"])


def configure_ttk_theme(root: tk.Misc, theme_key: str | None = None) -> None:
    """Configure a shared ttk style baseline across all apps."""
    theme = get_theme(theme_key)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    border = theme["border"]
    panel_bg = theme.get("panel_strong", theme["bg_panel"])

    style.configure("TFrame", background=theme["bg_main"])
    style.configure("Panel.TFrame", background=panel_bg)
    style.configure("Toolbar.TFrame", background=panel_bg)
    style.configure("TLabel", background=theme["bg_main"], foreground=theme["fg_primary"])
    style.configure("Muted.TLabel", background=theme["bg_main"], foreground=theme["fg_muted"])

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

    style.configure("NavAction.TButton", background=_mix(theme["border"], theme["success"], 0.2), foreground=theme["fg_primary"])
    style.map("NavAction.TButton", background=[("active", _mix(theme["accent_soft"], theme["success"], 0.2))])

    style.configure("UtilityAction.TButton", background=_mix(theme["border"], theme["accent"], 0.14), foreground=theme["fg_primary"])
    style.map("UtilityAction.TButton", background=[("active", _mix(theme["accent_soft"], theme["accent"], 0.18))])

    style.configure("Action.Primary.TButton", background=theme["accent"], foreground=theme["fg_on_accent"])
    style.configure("Action.Secondary.TButton", background=theme["secondary_soft"], foreground=theme["fg_primary"])
    style.configure("Action.Warn.TButton", background=theme["warning"], foreground=theme["fg_on_warning"])
    style.configure("Action.Danger.TButton", background=theme["danger"], foreground=theme["fg_on_danger"])

    style.configure(
        "TEntry",
        fieldbackground=theme["bg_surface"],
        foreground=theme["fg_primary"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
    )

    scroll_bg = _mix(theme["border"], theme["bg_surface"], 0.35)
    scroll_active = _mix(theme["accent_soft"], theme["bg_surface"], 0.52)
    style.configure(
        "TScrollbar",
        troughcolor=theme["bg_surface"],
        background=scroll_bg,
        arrowcolor=theme["fg_primary"],
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        gripcount=0,
    )
    style.map("TScrollbar", background=[("active", scroll_active), ("pressed", scroll_active)])
    style.configure("Horizontal.TScrollbar", troughcolor=theme["bg_surface"], background=scroll_bg)
    style.configure("Vertical.TScrollbar", troughcolor=theme["bg_surface"], background=scroll_bg)
