"""Public theming API for all Blattwerk-family consumer programs.

Import from here, never from the internal submodules directly::

    from bw_gui.theming import (
        configure_ttk_theme,
        configure_tinted_button_style,
        set_theme_intensity,
        theme_canvas,
        theme_text,
        tinted_color,
        tinted_foreground,
        icon_button,
        recolor_photo,
        canvas_fill,
        canvas_tinted_fill,
        canvas_text_fill,
        canvas_outline_color,
        THEME_ORDER,
        DEFAULT_THEME,
    )

Canvas drawing primitives apply theme colors to individual canvas *items*
without returning hex values to the consumer.  Pass a contract token name or
tint seed; bw_gui resolves the actual color internally::

    rect_id = canvas.create_rectangle(x1, y1, x2, y2)
    canvas_fill(canvas, rect_id, token="bg_panel")
    canvas_tinted_fill(canvas, rect_id, color_tint=SEED, degree=0.38,
                       base_token="panel_strong")
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
    canvas_fill,
    canvas_outline_color,
    canvas_text_fill,
    canvas_tinted_fill,
    icon_button,
    recolor_photo,
    theme_canvas,
    theme_listbox,
    theme_scrollbar,
    theme_text,
)

__all__ = [
    # Theme configuration
    "configure_ttk_theme",
    "configure_tinted_button_style",
    "apply_window_theme",
    "register_theme",
    "normalize_theme_key",
    "set_theme_intensity",
    "get_theme_intensity",
    "theme_contract_keys",
    # Color intent utilities (for theming-configuration code)
    "tinted_color",
    "tinted_foreground",
    # Raw tk widget theming
    "theme_canvas",
    "theme_text",
    "theme_listbox",
    "theme_scrollbar",
    # Canvas item drawing primitives
    "canvas_fill",
    "canvas_tinted_fill",
    "canvas_text_fill",
    "canvas_outline_color",
    # Composite widgets
    "icon_button",
    "recolor_photo",
    # Constants
    "DEFAULT_THEME",
    "DEFAULT_THEME_INTENSITY",
    "THEME_ORDER",
]
