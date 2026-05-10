from bw_gui.shortcuts import (
    compose_action_label,
    compose_hover_text,
    format_shortcut_label,
    humanize_shortcut_sequence,
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


def test_humanize_shortcut_sequence_from_tk_sequence():
    assert humanize_shortcut_sequence("<Control-Shift-s>") == "Ctrl+Shift+S"
    assert humanize_shortcut_sequence("<Control-comma>") == "Ctrl+,"


def test_compose_action_label_icon_and_shortcut():
    label = compose_action_label("Save", icon="💾", shortcut="<Control-s>")
    assert label == "💾 Save [Ctrl+S]"
