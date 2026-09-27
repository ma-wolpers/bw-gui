"""Contract tests for modifier gating in evaluate_runtime and semantic conflict detection."""

from __future__ import annotations

import pytest

from bw_gui.contracts import (
    UI_MODE_DIALOG,
    UI_MODE_GLOBAL,
    UI_MODE_PREVIEW,
    UNKNOWN_MODIFIERS,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
    KeyModifiers,
    TkBackend,
    find_conflicts,
    modifiers_from_state,
)


def _definition(sequence, binding_id="b", **kwargs):
    return KeyBindingDefinition(binding_id=binding_id, sequence=sequence, intent="i", **kwargs)


def _evaluate(sequence, modifiers, backend=TkBackend.WIN32, **kwargs):
    context = KeybindingRuntimeContext(active_mode=UI_MODE_GLOBAL, modifiers=modifiers, backend=backend)
    return KeybindingRegistry().evaluate_runtime(_definition(sequence, **kwargs), context)


# Truth table from docs/KEYBINDING_CONTRACT.md (allow_modifiers=False).
@pytest.mark.parametrize(
    ("held", "sequence", "backend", "allowed"),
    [
        (KeyModifiers(), "a", TkBackend.WIN32, True),
        (KeyModifiers(shift=True), "a", TkBackend.WIN32, True),
        (KeyModifiers(control=True), "a", TkBackend.WIN32, False),
        (KeyModifiers(alt=True), "a", TkBackend.WIN32, False),
        (KeyModifiers(command=True), "a", TkBackend.AQUA, False),
        (KeyModifiers(control=True, shift=True), "a", TkBackend.WIN32, False),
        (KeyModifiers(control=True), "<Control-a>", TkBackend.WIN32, True),
        (KeyModifiers(alt=True), "<Alt-a>", TkBackend.WIN32, True),
        (KeyModifiers(control=True, alt=True), "<Control-a>", TkBackend.WIN32, False),
        (modifiers_from_state(0x0008, TkBackend.WIN32), "a", TkBackend.WIN32, True),  # NumLock
        (modifiers_from_state(0x000C, TkBackend.WIN32), "<Control-f>", TkBackend.WIN32, True),
    ],
)
def test_modifier_truth_table(held, sequence, backend, allowed):
    assert _evaluate(sequence, held, backend)[0] is allowed


def test_blocked_reason_names():
    assert _evaluate("a", KeyModifiers(control=True)) == (False, "modifier-held")
    assert _evaluate("a", UNKNOWN_MODIFIERS) == (False, "modifier-unknown")


def test_unknown_modifiers_fail_closed_even_for_declared_modifiers():
    # Tk also matches <Control-a> while additional modifiers are held.
    assert _evaluate("<Control-a>", UNKNOWN_MODIFIERS) == (False, "modifier-unknown")


def test_allow_modifiers_permits_undeclared_and_unknown_modifiers():
    assert _evaluate("a", KeyModifiers(control=True), allow_modifiers=True)[0]
    assert _evaluate("a", UNKNOWN_MODIFIERS, allow_modifiers=True)[0]


def test_context_without_modifier_information_keeps_legacy_behaviour():
    # modifiers=None: no gating, and not even the sequence is parsed.
    assert _evaluate("<Alt-KeyPress>", None) == (True, "active")


def test_semantic_duplicates_with_overlapping_scope_conflict():
    definitions = [
        _definition("<Control-comma>", "settings", modes=(UI_MODE_GLOBAL,)),
        _definition("<Control-,>", "settings.alt", modes=(UI_MODE_GLOBAL,)),
    ]
    assert find_conflicts(definitions, TkBackend.WIN32) == [("settings", "settings.alt")]


def test_disjoint_modes_do_not_conflict():
    definitions = [
        _definition("<Return>", "preview", modes=(UI_MODE_PREVIEW,)),
        _definition("<Return>", "dialog", modes=(UI_MODE_DIALOG,)),
    ]
    assert find_conflicts(definitions, TkBackend.WIN32) == []


def test_different_text_input_flags_still_overlap_outside_text_inputs():
    # Both apply outside text inputs -> overlap, although only one allows text input.
    definitions = [
        _definition("a", "one", modes=(UI_MODE_PREVIEW,), allow_when_text_input=True),
        _definition("a", "two", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False),
    ]
    assert find_conflicts(definitions, TkBackend.WIN32) == [("one", "two")]


def test_text_input_only_vs_preview_only_is_disjoint():
    # "editor" mode is only active with text focus; "preview" excludes text focus.
    from bw_gui.contracts import UI_MODE_EDITOR

    definitions = [
        _definition("a", "editor", modes=(UI_MODE_EDITOR,), allow_when_text_input=True),
        _definition("a", "preview", modes=(UI_MODE_PREVIEW,)),
    ]
    assert find_conflicts(definitions, TkBackend.WIN32) == []


def test_registry_find_conflicts_delegates():
    registry = KeybindingRegistry()
    registry.register(_definition("a", "one"))
    registry.register(_definition("<KeyPress-a>", "two"))
    assert registry.find_conflicts(TkBackend.WIN32) == [("one", "two")]
