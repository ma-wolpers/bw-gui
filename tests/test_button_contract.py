from __future__ import annotations

import pytest

from bw_gui.contracts import ButtonDefinition, ButtonRegistry, KeyBindingDefinition, KeybindingRegistry


def _shortcuts() -> KeybindingRegistry:
    registry = KeybindingRegistry()
    registry.register(
        KeyBindingDefinition(
            binding_id="save.editor",
            sequence="<Control-s>",
            intent="save",
            modes=("editor",),
        )
    )
    registry.register(
        KeyBindingDefinition(
            binding_id="save.global",
            sequence="<Control-Shift-s>",
            intent="save",
            modes=("global",),
        )
    )
    return registry


def test_button_registry_rejects_duplicate_button_ids():
    registry = ButtonRegistry()
    registry.register(ButtonDefinition(button_id="save", intent="save", label="Save", description="Save current file"))

    with pytest.raises(ValueError):
        registry.register(ButtonDefinition(button_id="save", intent="save_as", label="Save as", description="Save with new name"))


def test_button_registry_renders_label_and_hover_from_intent_shortcut():
    buttons = ButtonRegistry()
    buttons.register(
        ButtonDefinition(
            button_id="save",
            intent="save",
            label="Save",
            icon="💾",
            description="Save current file",
        )
    )

    shortcuts = _shortcuts()
    label = buttons.render_label("save", shortcuts=shortcuts, mode="editor")
    hover = buttons.render_hover_text("save", shortcuts=shortcuts, mode="editor")

    assert label == "💾 Save [Ctrl+S]"
    assert hover == "Save current file\nShortcut: Ctrl+S"


def test_button_registry_can_skip_shortcut_in_hover_text():
    buttons = ButtonRegistry()
    buttons.register(
        ButtonDefinition(
            button_id="toggle",
            intent="toggle_preview",
            label="Preview",
            description="Toggle preview",
            include_shortcut_in_hover=False,
        )
    )
    shortcuts = _shortcuts()

    hover = buttons.render_hover_text("toggle", shortcuts=shortcuts, mode="editor")
    assert hover == "Toggle preview"
