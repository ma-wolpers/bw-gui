from bw_gui.contracts import (
    HsmIntentSpec,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
    PopupPolicy,
    PopupPolicyRegistry,
    TransitionRule,
)
from bw_gui.contracts.hsm import HsmContract


def test_keybinding_registry_duplicate_rejected():
    registry = KeybindingRegistry()
    registry.register(KeyBindingDefinition(binding_id="save", sequence="<Control-s>", intent="save"))

    try:
        registry.register(KeyBindingDefinition(binding_id="save", sequence="<Control-S>", intent="save_upper"))
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_keybinding_runtime_evaluation():
    definition = KeyBindingDefinition(
        binding_id="save",
        sequence="<Control-s>",
        intent="save",
        modes=("editor",),
        allow_when_text_input=False,
    )
    registry = KeybindingRegistry()
    registry.register(definition)

    ok, reason = registry.evaluate_runtime(
        definition,
        KeybindingRuntimeContext(active_mode="editor", text_input_focused=False),
    )
    assert ok is True
    assert reason == "active"

    ok, reason = registry.evaluate_runtime(
        definition,
        KeybindingRuntimeContext(active_mode="editor", text_input_focused=True),
    )
    assert ok is False
    assert reason == "text-input-focus"


def test_keybinding_shortcut_for_intent_resolution():
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

    assert registry.shortcut_for_intent("save", mode="editor") == "<Control-s>"
    assert registry.shortcut_for_intent("save", mode="preview") == "<Control-Shift-s>"
    assert registry.shortcut_for_intent("missing") is None


def test_popup_policy_registry_stack_behavior():
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="modal_default"))

    session = registry.open_popup("settings", "Settings", "modal_default")
    assert session.popup_id == "settings"
    assert registry.has_active_popup() is True
    assert registry.has_mode_blocking_popup() is True

    removed = registry.close_popup("settings")
    assert removed is True
    assert registry.has_active_popup() is False


def test_hsm_contract_validates_transitions_and_payload():
    contract = HsmContract(
        intent_specs=(HsmIntentSpec(intent="open", required_payload=("path",)),),
        transitions=(TransitionRule("global", "editor"),),
    )

    ok, reason = contract.validate_intent("open", {"path": "a.md"})
    assert ok is True
    assert reason == "ok"

    ok, reason = contract.validate_intent("open", {})
    assert ok is False
    assert reason == "missing-payload:path"

    ok, reason = contract.validate_transition("global", "editor")
    assert ok is True
    assert reason == "ok"

    ok, reason = contract.validate_transition("editor", "preview")
    assert ok is False
    assert reason == "transition-forbidden"
