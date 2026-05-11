"""Shortcut resolution helpers used by LaufKern reachability checks."""

from __future__ import annotations

from bw_gui.contracts.keybinding import KeyBindingDefinition, KeybindingRuntimeContext, KeybindingRegistry


def registry_from_bindings(bindings: tuple[KeyBindingDefinition, ...]) -> KeybindingRegistry:
    """Build a temporary registry from manifest-provided keybindings."""

    registry = KeybindingRegistry()
    registry.register_many(bindings)
    return registry


def resolve_binding_runtime(
    definition: KeyBindingDefinition,
    *,
    context: KeybindingRuntimeContext,
) -> tuple[bool, str]:
    """Evaluate one binding against runtime context using the central registry rules."""

    registry = registry_from_bindings((definition,))
    return registry.evaluate_runtime(definition, context)
