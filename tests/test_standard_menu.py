from bw_gui.menu import MenuItem
from bw_gui.menu.standard_menu import build_standard_menu_definitions, section_spec
import pytest


def _items():
    return (MenuItem(type="command", label="X"),)


def test_standard_menu_preserves_core_order_and_help_last():
    definitions = build_standard_menu_definitions(
        file_section=section_spec("file", _items),
        edit_section=section_spec("edit", _items),
        view_section=section_spec("view", _items),
        extra_sections=(section_spec("debug", _items, label="Debug", alt="d"),),
        help_section=section_spec("help", _items),
    )

    assert [entry.key for entry in definitions] == ["file", "edit", "view", "debug", "help"]
    assert [entry.label for entry in definitions] == ["Datei", "Bearbeiten", "Ansicht", "Debug", "Hilfe"]


def test_standard_menu_uses_fallback_metadata_for_unknown_key():
    definitions = build_standard_menu_definitions(
        extra_sections=(section_spec("runtime", _items),),
    )

    assert len(definitions) == 1
    assert definitions[0].key == "runtime"
    assert definitions[0].label == "Runtime"
    assert definitions[0].alt == "r"


def test_standard_menu_rejects_duplicate_keys():
    with pytest.raises(ValueError, match="Duplicate menu section key"):
        build_standard_menu_definitions(
            file_section=section_spec("file", _items),
            extra_sections=(section_spec("file", _items),),
        )
