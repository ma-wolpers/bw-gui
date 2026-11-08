from bw_gui.theming import (
    DEFAULT_THEME,
    THEME_ORDER,
    normalize_theme_key,
    recolor_photo_domain,
    theme_contract_keys,
)
from bw_gui.theming._theme_manager import THEMES, get_theme
import bw_gui.theming._widget_utils as widget_utils


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


def test_recolor_photo_domain_picks_light_or_dark_color_for_active_theme(monkeypatch):
    """`recolor_photo_domain` must route to the domain color pair based on the
    ambient theme's brightness (same decision `canvas_domain_fill`/
    `canvas_domain_outline` make), and reuse `_recolor_photo` -- no separate
    pixel-recoloring path. Stubs `_recolor_photo` instead of using a real
    `tk.PhotoImage`, matching this test suite's convention of not creating
    live Tk widgets."""
    from bw_gui.theming._theme_manager import _set_current_theme

    captured: list[tuple[object, str]] = []

    def _fake_recolor_photo(photo, fg_hex):
        captured.append((photo, fg_hex))
        return "recolored"

    monkeypatch.setattr(widget_utils, "_recolor_photo", _fake_recolor_photo)

    sentinel_photo = object()
    try:
        _set_current_theme("mono_day")
        result_light = recolor_photo_domain(sentinel_photo, light_color="#111111", dark_color="#EEEEEE")
        _set_current_theme("mono_night")
        result_dark = recolor_photo_domain(sentinel_photo, light_color="#111111", dark_color="#EEEEEE")
    finally:
        _set_current_theme(DEFAULT_THEME)

    assert result_light == "recolored"
    assert result_dark == "recolored"
    assert captured == [
        (sentinel_photo, "#111111"),
        (sentinel_photo, "#EEEEEE"),
    ]


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


def test_info_family_exists_in_every_theme_and_is_light_on_light_themes():
    from bw_gui.theming._color_math import _is_dark

    for theme_key in THEME_ORDER:
        theme = get_theme(theme_key)
        for key in ("info", "info_hover", "info_soft", "fg_on_info"):
            assert theme[key].startswith("#"), (theme_key, key)
        if not _is_dark(theme["bg_main"]):
            assert not _is_dark(theme["info_soft"]), theme_key


def test_tinted_color_rejects_unknown_tokens_instead_of_blending_grey():
    import pytest

    from bw_gui.theming import tinted_color

    assert tinted_color("info_soft", degree=0.5, base_token="panel_strong", theme_key=DEFAULT_THEME).startswith("#")
    assert tinted_color("#7C3AED", degree=0.4, base_token="auto", theme_key=DEFAULT_THEME).startswith("#")
    with pytest.raises(ValueError, match="does_not_exist"):
        tinted_color("does_not_exist", theme_key=DEFAULT_THEME)
    with pytest.raises(ValueError, match="no_such_base"):
        tinted_color("accent", base_token="no_such_base", theme_key=DEFAULT_THEME)
