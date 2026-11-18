"""Contract tests for CheckList (staged multi-select, see widgets/check_list.py)."""

from __future__ import annotations

import pytest

from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import DEFAULT_THEME
from bw_gui.widgets import CheckList

GROUPS = [
    ("Konzentration", [("k.arbeiten", "konzentriert arbeiten"), ("k.zurueck", "zur Aufgabe zurückfinden")]),
    ("", [("motivation", "Motivation")]),
]


@pytest.fixture
def root(_shared_tk_root):
    """Themed shared root; children are destroyed after each test."""
    configure_ttk_theme(_shared_tk_root, DEFAULT_THEME)
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def test_one_checkbox_per_option_in_display_order(root) -> None:
    check_list = CheckList(root, groups=GROUPS)
    assert check_list.values == ("k.arbeiten", "k.zurueck", "motivation")
    assert [box.cget("text") for box in check_list.checkboxes.values()] == [
        "konzentriert arbeiten", "zur Aufgabe zurückfinden", "Motivation",
    ]


def test_titled_group_shows_a_heading_untitled_group_none(root) -> None:
    check_list = CheckList(root, groups=GROUPS)
    labels = [child for child in check_list.winfo_children() if child.winfo_class() == "TLabel"]
    assert [label.cget("text") for label in labels] == ["Konzentration"]


def test_initial_selection_ignores_unknown_values(root) -> None:
    check_list = CheckList(root, groups=GROUPS, selected=["motivation", "unbekannt"])
    assert check_list.selected_values() == ("motivation",)


def test_selection_is_reported_in_display_order_not_click_order(root) -> None:
    reported: list[tuple[str, ...]] = []
    check_list = CheckList(root, groups=GROUPS, on_select=reported.append)
    check_list.checkboxes["motivation"].invoke()
    check_list.checkboxes["k.arbeiten"].invoke()
    assert reported == [("motivation",), ("k.arbeiten", "motivation")]
    assert check_list.selected_values() == ("k.arbeiten", "motivation")


def test_set_selected_replaces_selection_without_callback(root) -> None:
    reported: list[tuple[str, ...]] = []
    check_list = CheckList(root, groups=GROUPS, selected=["k.arbeiten"], on_select=reported.append)
    check_list.set_selected(["k.zurueck"])
    assert check_list.selected_values() == ("k.zurueck",)
    assert reported == []


def test_raising_on_select_rolls_the_click_back(root, monkeypatch) -> None:
    reported: list[BaseException] = []
    monkeypatch.setattr(root, "report_callback_exception", lambda _type, exc, _tb: reported.append(exc))

    def reject(_selection: tuple[str, ...]) -> None:
        raise RuntimeError("abgelehnt")

    check_list = CheckList(root, groups=GROUPS, on_select=reject)
    check_list.checkboxes["motivation"].invoke()
    assert [type(exc) for exc in reported] == [RuntimeError]
    assert check_list.selected_values() == ()


@pytest.mark.parametrize(
    "groups",
    [[], [("A", [])], [("A", [("a", "A")]), ("B", [("a", "B")])], [("A", [("a", "  ")])]],
    ids=["no-groups", "only-empty-group", "duplicate-values", "empty-label"],
)
def test_invalid_groups_are_rejected(root, groups) -> None:
    with pytest.raises(ValueError):
        CheckList(root, groups=groups)
