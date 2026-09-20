from bw_gui.menu import MenuItem
from bw_gui.menu.custom_menu_bar import _is_description_slot_replaceable


class _FakeDescriptionFlyout:
    _bw_menu_description_flyout = True


class _FakeSubmenuPopup:
    _bw_menu_description_flyout = False


def test_menu_item_description_defaults_to_none():
    assert MenuItem(type="command", label="X").description is None


def test_menu_item_accepts_optional_description():
    item = MenuItem(type="command", label="Info", description="Erklärt den Block.")
    assert item.description == "Erklärt den Block."


def test_description_slot_replaceable_when_level_empty():
    assert _is_description_slot_replaceable([], target_level=1) is True


def test_description_slot_replaceable_when_occupied_by_earlier_description_flyout():
    stack = [object(), _FakeDescriptionFlyout()]
    assert _is_description_slot_replaceable(stack, target_level=1) is True


def test_description_slot_not_replaceable_when_occupied_by_real_submenu():
    stack = [object(), _FakeSubmenuPopup()]
    assert _is_description_slot_replaceable(stack, target_level=1) is False
