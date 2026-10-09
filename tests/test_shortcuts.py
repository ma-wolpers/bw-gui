from bw_gui.shortcuts import (
    compose_action_label,
    compose_hover_text,
    format_shortcut_label,
    humanize_shortcut,
)


def test_format_shortcut_label_compact_and_optional():
    assert format_shortcut_label("⟳", "Ctrl+R") == "⟳ [Ctrl+R]"
    assert format_shortcut_label("⟳", None) == "⟳"


def test_compose_hover_text_includes_shortcut_when_present():
    text = compose_hover_text("Vorschau neu laden", "Ctrl+R")
    assert "Vorschau neu laden" in text
    assert "Shortcut: Ctrl+R" in text


def test_compose_hover_text_without_description():
    assert compose_hover_text("", "Ctrl+S") == "Shortcut: Ctrl+S"


def test_humanize_shortcut_from_keyspec_and_notation():
    from bw_gui.contracts import Key, KeySpec, Mod

    assert humanize_shortcut(KeySpec.char("S", {Mod.CTRL})) == "Ctrl+Shift+S"
    assert humanize_shortcut("Ctrl+,") == "Ctrl+,"
    assert humanize_shortcut(KeySpec(Key.ESCAPE, (), {Mod.SHIFT})) == "Escape"


def test_humanize_shortcut_rejects_tk_syntax():
    import pytest

    with pytest.raises(ValueError):
        humanize_shortcut("<Control-s>")


def test_compose_action_label_icon_and_shortcut():
    label = compose_action_label("Save", icon="💾", shortcut="Ctrl+S")
    assert label == "💾 Save [Ctrl+S]"
