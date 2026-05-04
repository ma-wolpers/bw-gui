from bw_gui.theming import DEFAULT_THEME, THEME_ORDER, get_theme, normalize_theme_key


def test_default_theme_is_valid_member():
    assert DEFAULT_THEME in THEME_ORDER


def test_normalize_theme_key_falls_back():
    assert normalize_theme_key("does-not-exist") == DEFAULT_THEME


def test_theme_has_required_runtime_keys():
    theme = get_theme(DEFAULT_THEME)
    required = [
        "bg_main",
        "bg_surface",
        "bg_panel",
        "fg_primary",
        "accent",
        "accent_hover",
        "accent_soft",
        "danger",
        "border",
        "focus_ring",
    ]
    for key in required:
        assert key in theme
