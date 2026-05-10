from bw_gui.theming import (
    DEFAULT_THEME,
    THEME_ORDER,
    THEMES,
    get_theme,
    normalize_theme_key,
    theme_contract_keys,
)


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


def test_blattwerk_and_kursplaner_theme_families_present():
    expected_theme_keys = {
        "mono_day",
        "mono_night",
        "porcelain",
        "charcoal",
        "slate_indigo",
        "forest_moss",
        "sand_terracotta",
        "midnight_cyan",
        "lavender_graphite",
        "obsidian_gold",
    }
    assert expected_theme_keys.issubset(set(THEMES))


def test_every_registered_theme_exposes_theme_contract_keys():
    contract = set(theme_contract_keys())
    for theme_key in THEME_ORDER:
        theme = get_theme(theme_key)
        missing = contract.difference(theme)
        assert not missing, f"theme '{theme_key}' missing keys: {sorted(missing)}"


def test_alias_and_domain_tokens_are_resolved_for_all_themes():
    for theme_key in THEME_ORDER:
        theme = get_theme(theme_key)
        assert theme["error"] == theme["danger"]
        assert theme["error_hover"] == theme["danger_hover"]
        assert theme["error_soft"] == theme["danger_soft"]
        assert theme["fg_on_error"] == theme["fg_on_danger"]
        assert theme["hospitation"]
        assert theme["hospitation_hover"]
        assert theme["hospitation_soft"]
        assert theme["fg_on_hospitation"]
