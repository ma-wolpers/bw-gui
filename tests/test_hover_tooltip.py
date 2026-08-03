from bw_gui.widgets.hover_tooltip import HoverTooltip


class _FakeVar:
    def __init__(self, value: str):
        self._value = value

    def get(self) -> str:
        return self._value


class _FakeRoot:
    def __init__(self, theme_value: str | None = None):
        self.theme_var = _FakeVar(theme_value) if theme_value is not None else None


class _FakeWidget:
    def __init__(self, root):
        self._root = root

    def winfo_toplevel(self):
        return self._root


def test_clamp_to_monitor_keeps_bounds_on_primary_monitor():
    x_pos, y_pos = HoverTooltip._clamp_to_monitor(
        2000,
        1200,
        320,
        240,
        0,
        0,
        1920,
        1080,
    )
    assert x_pos <= 1920 - 320 - 8
    assert y_pos <= 1080 - 240 - 8


def test_clamp_to_monitor_applies_min_margin_on_primary_monitor():
    x_pos, y_pos = HoverTooltip._clamp_to_monitor(
        -40,
        -90,
        120,
        60,
        0,
        0,
        800,
        600,
    )
    assert x_pos == 8
    assert y_pos == 8


def test_clamp_to_monitor_keeps_tooltip_on_secondary_monitor_to_the_right():
    # Regression test: a monitor placed to the right of the primary display has a
    # non-zero left/right origin (e.g. primary is 0-1920, secondary is 1920-3840).
    # A naive clamp that assumes the monitor starts at x=0 would drag the tooltip
    # back onto the primary display instead of keeping it on the secondary one.
    x_pos, y_pos = HoverTooltip._clamp_to_monitor(
        3700,
        900,
        320,
        240,
        1920,
        0,
        3840,
        1080,
    )
    assert 1920 <= x_pos <= 3840 - 320
    assert x_pos <= 3840 - 320 - 8


def test_clamp_to_monitor_applies_min_margin_on_secondary_monitor():
    # Same non-origin scenario, but the proposed position undershoots the monitor's
    # own left edge (1920) — the clamp must pull it back to 1920 + margin, not to 8.
    x_pos, y_pos = HoverTooltip._clamp_to_monitor(
        1900,
        -20,
        120,
        60,
        1920,
        0,
        3840,
        1080,
    )
    assert x_pos == 1920 + 8
    assert y_pos == 0 + 8


def test_resolve_theme_key_prefers_explicit_value():
    tooltip = HoverTooltip.__new__(HoverTooltip)
    tooltip.theme_key = "charcoal"
    tooltip.widget = _FakeWidget(_FakeRoot("mono_day"))

    assert tooltip._resolve_theme_key() == "charcoal"


def test_resolve_theme_key_uses_toplevel_theme_var_when_available():
    tooltip = HoverTooltip.__new__(HoverTooltip)
    tooltip.theme_key = None
    tooltip.widget = _FakeWidget(_FakeRoot("slate_indigo"))

    assert tooltip._resolve_theme_key() == "slate_indigo"