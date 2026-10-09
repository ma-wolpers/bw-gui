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