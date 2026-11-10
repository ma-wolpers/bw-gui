from bw_gui.shortcuts import (
    compose_action_label,
    compose_hover_text,
    format_shortcut_label,
    humanize_shortcut,
)


def test_format_shortcut_label_compact_and_optional():
    assert format_shortcut_label("⟳", "Ctrl+R") == "⟳ [Strg+R]"
    assert format_shortcut_label("⟳", None) == "⟳"


def test_compose_hover_text_includes_shortcut_when_present():
    text = compose_hover_text("Vorschau neu laden", "Ctrl+R")
    assert "Vorschau neu laden" in text
    assert "Shortcut: Strg+R" in text


def test_compose_hover_text_without_description():
    assert compose_hover_text("", "Ctrl+S") == "Shortcut: Strg+S"


def test_alternative_shortcuts_join_with_oder_and_skip_unbound():
    from bw_gui.contracts import KeySpec
    from bw_gui.contracts.keybinding import KeyBindingDefinition, KeybindingRegistry
    from bw_gui.shortcuts import compose_hover_text_for_intent, compose_menu_label

    keys = (KeySpec.parse("Ctrl+Delete"), None, KeySpec.parse("Ctrl+Backspace"))
    assert compose_hover_text("Löschen", keys) == "Löschen\nShortcut: Strg+Entf oder Strg+Rücktaste"
    assert compose_menu_label("Löschen", (None,)) == "Löschen"

    registry = KeybindingRegistry()
    for binding_id, key, intent in (("a", "Ctrl+Delete", "clear"), ("b", "Ctrl+Backspace", "clear.back")):
        registry.register(KeyBindingDefinition(binding_id=binding_id, keys=(KeySpec.parse(key),), intent=intent))
    text = compose_hover_text_for_intent("Löschen", intent=("clear", "clear.back", "unbound"), shortcuts=registry)
    assert text.endswith("Strg+Entf oder Strg+Rücktaste")


def test_humanize_shortcut_from_keyspec_and_notation():
    from bw_gui.contracts import Key, KeySpec, Mod

    assert humanize_shortcut(KeySpec.char("S", {Mod.CTRL})) == "Strg+Shift+S"
    assert humanize_shortcut("Ctrl+,") == "Strg+,"
    assert humanize_shortcut(KeySpec(Key.ESCAPE, (), {Mod.SHIFT})) == "Esc"


def test_humanize_shortcut_rejects_tk_syntax():
    import pytest

    with pytest.raises(ValueError):
        humanize_shortcut("<Control-s>")


def test_compose_action_label_icon_and_shortcut():
    label = compose_action_label("Save", icon="💾", shortcut="Ctrl+S")
    assert label == "💾 Save [Strg+S]"


def test_humanize_shortcut_passes_localized_display_text():
    assert humanize_shortcut("Entf") == "Entf"
    assert humanize_shortcut("strg+t") == "Strg+T"
    assert humanize_shortcut("Leertaste") == "Leertaste"
    assert compose_hover_text("Löschen", "Entf") == "Löschen\nShortcut: Entf"


def test_display_is_german_while_notation_stays_english():
    from bw_gui.contracts import KeySpec

    spec = KeySpec.parse("Ctrl+Shift+L")
    assert str(spec) == "Ctrl+Shift+L"
    assert spec.notation_parts() == ("Ctrl", "Shift", "L")
    assert KeySpec.parse("Ctrl++").notation_parts() == ("Ctrl", "+")
    assert humanize_shortcut(spec) == "Strg+Shift+L"
    for notation, shown in (
        ("Ctrl+Delete", "Strg+Entf"),
        ("Ctrl+Left", "Strg+Links"),
        ("Ctrl+Down", "Strg+Runter"),
        ("Home", "Pos1"),
        ("Alt+F2", "Alt+F2"),
    ):
        assert humanize_shortcut(KeySpec.parse(notation)) == shown
        assert humanize_shortcut(notation) == shown


def test_compose_menu_label_appends_shortcut_in_parentheses():
    from bw_gui.shortcuts import compose_menu_label

    assert compose_menu_label("Rückgängig", "Ctrl+Z") == "Rückgängig (Strg+Z)"
    assert compose_menu_label("Ohne Taste", None) == "Ohne Taste"
