"""Semantic keybinding conflict detection over the complete runtime applicability.

Two keybinding definitions *conflict* when they have the same
:func:`~bw_gui.contracts.key_sequence.binding_signature` (they match the same key
events) **and** there is at least one runtime context in which both would be
allowed to execute -- then the dispatcher could not decide unambiguously which one
the user meant.

"Runtime context" covers every criterion the dispatcher evaluates, not only
``modes``: base mode, offline flag, dialog flag, text-input flag and the modifier
state (exactly the declared modifiers, an additional undeclared shortcut modifier,
or an undecodable state). The derived active mode follows
:func:`~bw_gui.contracts.keybinding.derive_active_mode`, and each candidate context
is judged by :func:`~bw_gui.contracts.keybinding.evaluate_binding` -- the same
function the runtime uses -- so the conflict analysis cannot drift from the real
gating rules.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations, product
from typing import Iterable, Iterator

from .key_modifiers import UNKNOWN_MODIFIERS, KeyModifiers, TkBackend, UnknownModifiers, resolve_backend
from .key_sequence import binding_signature
from .keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRuntimeContext,
    derive_active_mode,
    evaluate_binding,
)

_OTHER_MODE = "<any-other-mode>"
_BUILTIN_MODES = (UI_MODE_GLOBAL, UI_MODE_EDITOR, UI_MODE_PREVIEW, UI_MODE_DIALOG, UI_MODE_OFFLINE)


def _modifier_variants(declared: KeyModifiers) -> tuple[KeyModifiers | UnknownModifiers, ...]:
    """Modifier states worth probing for a signature: exact, one extra shortcut modifier, unknown."""
    variants: list[KeyModifiers | UnknownModifiers] = [declared, UNKNOWN_MODIFIERS]
    for name in ("control", "alt", "command"):
        if not getattr(declared, name):
            variants.append(replace(declared, **{name: True}))
            break
    return tuple(variants)


def _candidate_contexts(
    first: KeyBindingDefinition,
    second: KeyBindingDefinition,
    declared: KeyModifiers,
    backend: TkBackend,
) -> Iterator[KeybindingRuntimeContext]:
    """Yield every runtime context the dispatcher can produce for this signature.

    Enumerates base mode (all built-in modes, both definitions' modes and one
    "other" mode) x offline x dialog x text-input x modifier variant, deriving the
    active mode exactly like the binder does (:func:`derive_active_mode`).
    """
    base_modes = set(_BUILTIN_MODES) | set(first.modes) | set(second.modes) | {_OTHER_MODE}
    for base_mode, offline, dialog_open, text_input, modifiers in product(
        sorted(base_modes), (False, True), (False, True), (False, True), _modifier_variants(declared)
    ):
        yield KeybindingRuntimeContext(
            active_mode=derive_active_mode(
                offline=offline, dialog_open=dialog_open, text_input_focused=text_input, base_mode=base_mode
            ),
            offline=offline,
            text_input_focused=text_input,
            dialog_open=dialog_open,
            modifiers=modifiers,
            backend=backend,
        )


def definitions_overlap(
    first: KeyBindingDefinition,
    second: KeyBindingDefinition,
    backend: TkBackend | None = None,
) -> bool:
    """True if both definitions match the same events and can both execute in one context.

    Raises:
        ValueError: If a sequence is outside the keyboard-shortcut contract.
    """
    resolved = resolve_backend(backend)
    signature = binding_signature(first.sequence, resolved)
    if signature != binding_signature(second.sequence, resolved):
        return False
    for context in _candidate_contexts(first, second, signature.modifiers, resolved):
        if evaluate_binding(first, context)[0] and evaluate_binding(second, context)[0]:
            return True
    return False


def find_conflicts(
    definitions: Iterable[KeyBindingDefinition],
    backend: TkBackend | None = None,
) -> list[tuple[str, str]]:
    """Return ``(binding_id, binding_id)`` pairs that conflict (see module docstring).

    Raises:
        ValueError: If a sequence is outside the keyboard-shortcut contract -- tooling
            must see such bindings instead of silently skipping them.
    """
    resolved = resolve_backend(backend)
    by_signature: dict[object, list[KeyBindingDefinition]] = {}
    for definition in definitions:
        by_signature.setdefault(binding_signature(definition.sequence, resolved), []).append(definition)
    conflicts: list[tuple[str, str]] = []
    for group in by_signature.values():
        for first, second in combinations(group, 2):
            if definitions_overlap(first, second, resolved):
                conflicts.append((first.binding_id, second.binding_id))
    return conflicts
