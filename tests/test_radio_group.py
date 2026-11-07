"""Contract tests for RadioGroup (exclusive staged choice, see widgets/radio_group.py)."""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import DEFAULT_THEME
from bw_gui.widgets import RadioGroup

OPTIONS = [("schriftlich", "Schriftlich"), ("sonstig", "Sonstig")]


@pytest.fixture
def root(_shared_tk_root):
    """Themed shared root; children are destroyed after each test."""
    configure_ttk_theme(_shared_tk_root, DEFAULT_THEME)
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def test_one_button_per_option_in_order(root) -> None:
    group = RadioGroup(root, options=OPTIONS, variable=ui.StringVar(master=root))
    assert [button.cget("text") for button in group.buttons] == ["Schriftlich", "Sonstig"]
    assert [str(button.cget("value")) for button in group.buttons] == ["schriftlich", "sonstig"]
    assert group.first_button is group.buttons[0]


def test_title_is_shown_above_the_options(root) -> None:
    group = RadioGroup(root, title="Kategorie", options=OPTIONS, variable=ui.StringVar(master=root))
    first_child = group.winfo_children()[0]
    assert first_child.winfo_class() == "TLabel"
    assert first_child.cget("text") == "Kategorie"


def test_invoke_writes_the_value_and_selects_exclusively(root) -> None:
    variable = ui.StringVar(master=root, value="schriftlich")
    group = RadioGroup(root, options=OPTIONS, variable=variable)
    group.buttons[1].invoke()
    assert variable.get() == "sonstig"
    assert group.buttons[1].instate(["selected"])
    assert not group.buttons[0].instate(["selected"])


def test_programmatic_set_selects_the_matching_button(root) -> None:
    variable = ui.StringVar(master=root, value="schriftlich")
    group = RadioGroup(root, options=OPTIONS, variable=variable)
    variable.set("sonstig")
    assert group.buttons[1].instate(["selected"])


def test_modified_space_is_no_activation(root) -> None:
    RadioGroup(root, options=OPTIONS, variable=ui.StringVar(master=root))
    assert str(root.tk.call("bind", "TRadiobutton", "<Control-Key-space>"))
    assert str(root.tk.call("bind", "TRadiobutton", "<Alt-Key-space>"))


def test_variable_must_be_stringvar(root) -> None:
    with pytest.raises(TypeError):
        RadioGroup(root, options=OPTIONS, variable=ui.BooleanVar(master=root))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "options",
    [[], [("a", "A"), ("a", "B")], [("a", "  ")]],
    ids=["empty", "duplicate-values", "empty-label"],
)
def test_invalid_options_are_rejected(root, options) -> None:
    with pytest.raises(ValueError):
        RadioGroup(root, options=options, variable=ui.StringVar(master=root))
