"""Tests for the toggle indicator theming: state matrix, densities, contrast, lifecycle."""

from __future__ import annotations

import pytest

from bw_gui.runtime import widgets
from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import (
    DEFAULT_THEME,
    DEFAULT_THEME_INTENSITY,
    THEME_INTENSITY_LEVELS,
    THEME_ORDER,
    get_theme,
    relative_luminance,
    set_theme_intensity,
)
from bw_gui.theming._toggle_assets import DENSITIES, density_for_scaling, image_data, image_keys, role_colors
from bw_gui.theming._toggle_styles import (
    ELEMENT_NAMES,
    all_state_combinations,
    configure_toggle_styles,
    first_match,
    resolve,
    state_specs,
    toggle_image,
)

BASE_SCALING = 96 / 72


# --- state matrix -----------------------------------------------------------------

def test_matrix_covers_all_64_state_combinations() -> None:
    combos = all_state_combinations()
    assert len(combos) == 64
    specs = state_specs()
    for states in combos:
        assert first_match(specs, states) == resolve(states), sorted(states)


@pytest.mark.parametrize("states", all_state_combinations())
def test_pressed_renders_like_active(states: frozenset[str]) -> None:
    if "pressed" in states:
        swapped = (states - {"pressed"}) | {"active"}
        assert resolve(states) == resolve(swapped)


def test_matrix_priorities() -> None:
    assert resolve({"disabled", "alternate", "selected", "active", "focus"}) == "mixed-muted"
    assert resolve({"disabled", "selected", "focus"}) == "on-muted"
    assert resolve({"alternate", "selected", "focus"}) == "mixed-focus"
    assert resolve({"selected", "active", "focus"}) == "on-hover_focus"
    assert resolve({"pressed"}) == "off-hover"
    assert resolve(set()) == "off-rest"


def test_every_resolved_key_has_an_image() -> None:
    keys = set(image_keys())
    assert {resolve(states) for states in all_state_combinations()} == keys
    assert len(keys) == 15


# --- densities ----------------------------------------------------------------------

@pytest.mark.parametrize("factor, expected", [
    (1.0, 1.0), (1.25, 1.25), (1.5, 1.5), (2.0, 2.0),
    (1.125, 1.25), (1.375, 1.5), (1.1, 1.0), (0.8, 1.0), (2.6, 2.0),
])
def test_density_rounding(factor: float, expected: float) -> None:
    assert density_for_scaling(factor * BASE_SCALING) == expected


# --- colours ------------------------------------------------------------------------

def _contrast(a: str, b: str) -> float:
    high, low = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.fixture
def each_intensity():
    yield THEME_INTENSITY_LEVELS
    set_theme_intensity(DEFAULT_THEME_INTENSITY)


def test_state_bearing_parts_reach_3_to_1_in_every_theme_and_intensity(each_intensity) -> None:
    """Contrast guard: boundary vs. both backgrounds, mark/knob vs. its fill (not for disabled)."""
    failures = []
    for level in each_intensity:
        set_theme_intensity(level)
        for key in THEME_ORDER:
            theme = get_theme(key)
            for control in ("checkbox", "switch"):
                for image_key in image_keys():
                    if image_key.endswith("-muted"):
                        continue
                    colors = role_colors(theme, control, image_key)
                    for background in (theme["bg_main"], theme["bg_surface"]):
                        if _contrast(colors.outline, background) < 3:
                            failures.append((level, key, control, image_key, "boundary", background))
                    if colors.mark is not None and _contrast(colors.mark, colors.fill) < 3:
                        failures.append((level, key, control, image_key, "mark on fill"))
    assert failures == []


def test_contrast_guard_leaves_default_intensity_untouched() -> None:
    theme = get_theme(DEFAULT_THEME)
    assert role_colors(theme, "checkbox", "on-rest").fill == theme["accent"]
    assert role_colors(theme, "checkbox", "off-rest").outline == theme["fg_muted"]


def test_all_themes_and_intensities_build_all_images(each_intensity) -> None:
    for level in each_intensity:
        set_theme_intensity(level)
        for key in THEME_ORDER:
            theme = get_theme(key)
            for control in ("checkbox", "switch"):
                for image_key in image_keys():
                    assert image_data(theme, control, image_key, 1.0)


def test_all_densities_build_for_default_theme() -> None:
    theme = get_theme(DEFAULT_THEME)
    for density in DENSITIES:
        for control in ("checkbox", "switch"):
            assert image_data(theme, control, "on-hover_focus", density)


# --- lifecycle (real Tk) --------------------------------------------------------------

@pytest.fixture
def themed_root(_shared_tk_root):
    configure_ttk_theme(_shared_tk_root, DEFAULT_THEME)
    original_scaling = _shared_tk_root.tk.call("tk", "scaling")
    yield _shared_tk_root
    _shared_tk_root.tk.call("tk", "scaling", original_scaling)
    widgets.Style(_shared_tk_root).theme_use("clam")
    configure_ttk_theme(_shared_tk_root, DEFAULT_THEME)
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def test_theme_switch_keeps_image_objects_and_creates_no_elements(themed_root, monkeypatch) -> None:
    before = toggle_image(themed_root, "switch", "on-rest")
    style = widgets.Style(themed_root)
    calls = []
    monkeypatch.setattr(style.__class__, "element_create", lambda self, *a, **k: calls.append(a[0]))
    other_theme = next(key for key in THEME_ORDER if key != DEFAULT_THEME)
    configure_ttk_theme(themed_root, other_theme)
    assert calls == []
    assert toggle_image(themed_root, "switch", "on-rest") is before
    assert all(name in style.element_names() for name in ELEMENT_NAMES.values())


def test_elements_are_created_once_per_active_ttk_theme(themed_root) -> None:
    style = widgets.Style(themed_root)
    if "bwtoggle-test" not in style.theme_names():
        style.theme_create("bwtoggle-test", parent="clam")
    style.theme_use("bwtoggle-test")
    configure_toggle_styles(themed_root, style, get_theme(DEFAULT_THEME))
    assert all(name in style.element_names() for name in ELEMENT_NAMES.values())
    configure_toggle_styles(themed_root, style, get_theme(DEFAULT_THEME))  # no "Duplicate element" error


@pytest.mark.parametrize("factor, expected_width", [(1.0, 40), (1.25, 50), (1.5, 60), (2.0, 80)])
def test_scaling_reconfigures_same_objects(themed_root, factor: float, expected_width: int) -> None:
    photo = toggle_image(themed_root, "switch", "off-rest")
    themed_root.tk.call("tk", "scaling", factor * BASE_SCALING)
    configure_ttk_theme(themed_root, DEFAULT_THEME)
    assert toggle_image(themed_root, "switch", "off-rest") is photo
    assert photo.width() == expected_width


def test_density_change_relayouts_widget(themed_root) -> None:
    button = widgets.Checkbutton(themed_root, text="x", style="Switch.TCheckbutton")
    button.pack()
    themed_root.update_idletasks()
    small = button.winfo_reqheight()
    themed_root.tk.call("tk", "scaling", 2.0 * BASE_SCALING)
    configure_ttk_theme(themed_root, DEFAULT_THEME)
    themed_root.update_idletasks()
    assert button.winfo_reqheight() > small
