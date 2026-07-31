"""Public theming API for all Blattwerk-family consumer programs.

Import everything from here rather than from the internal submodules::

    from bw_gui.theming import (
        configure_ttk_theme,
        configure_tinted_button_style,
        set_theme_intensity,
        theme_canvas,
        theme_text,
        tinted_color,
        tinted_foreground,
        icon_button,
        THEME_ORDER,
        DEFAULT_THEME,
    )
"""

from .theme_manager import (
    DEFAULT_THEME,
    DEFAULT_THEME_INTENSITY,
    THEME_CONTRACT_KEYS,
    THEME_CORE_KEYS,
    THEME_INTENSITY_LEVELS,
    THEME_TOKEN_ALIASES,
    THEME_ORDER,
    THEMES,
    apply_window_theme,
    configure_tinted_button_style,
    configure_ttk_theme,
    get_theme,
    get_theme_intensity,
    normalize_theme_key,
    register_theme,
    set_theme_intensity,
    theme_contract_keys,
    tinted_color,
    tinted_foreground,
)
from .widget_utils import (
    icon_button,
    theme_canvas,
    theme_listbox,
    theme_scrollbar,
    theme_text,
)

__all__ = [
    "DEFAULT_THEME",
    "DEFAULT_THEME_INTENSITY",
    "THEME_CONTRACT_KEYS",
    "THEME_CORE_KEYS",
    "THEME_INTENSITY_LEVELS",
    "THEME_TOKEN_ALIASES",
    "THEME_ORDER",
    "THEMES",
    "apply_window_theme",
    "configure_tinted_button_style",
    "configure_ttk_theme",
    "get_theme",
    "get_theme_intensity",
    "icon_button",
    "normalize_theme_key",
    "register_theme",
    "set_theme_intensity",
    "theme_canvas",
    "theme_contract_keys",
    "theme_listbox",
    "theme_scrollbar",
    "theme_text",
    "tinted_color",
    "tinted_foreground",
]
