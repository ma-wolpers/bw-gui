"""Shared theme API for all consumer apps."""

from .theme_manager import (
    DEFAULT_THEME,
    THEME_ORDER,
    THEMES,
    apply_window_theme,
    configure_ttk_theme,
    get_theme,
    normalize_theme_key,
    register_theme,
)

__all__ = [
    "DEFAULT_THEME",
    "THEME_ORDER",
    "THEMES",
    "apply_window_theme",
    "configure_ttk_theme",
    "get_theme",
    "normalize_theme_key",
    "register_theme",
]
