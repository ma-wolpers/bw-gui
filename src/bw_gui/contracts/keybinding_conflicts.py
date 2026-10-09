"""Keybinding conflict detection, model A (``KEYBINDING_CONTRACT.md``, decision 21).

Two definitions *conflict* when some key event matches a key of each
(:func:`~bw_gui.contracts.key_spec.overlaps`, the same exact matching the runtime
uses) **and** there is at least one runtime context in which both would pass gating.
Runtime contexts cover every gating criterion: base mode, offline flag, dialog flag
and text-input flag; the derived active mode follows
:func:`~bw_gui.contracts.keybinding.derive_active_mode` and each context is judged by
:func:`~bw_gui.contracts.keybinding.evaluate_binding` itself, so the analysis cannot
drift from the runtime.

Model A: for every runtime context at most one definition per key is applicable.
``applies_when`` predicates are opaque and never make two definitions disjoint;
definitions that differ only by their predicate are a conflict and must be merged.
"""

from __future__ import annotations

from itertools import combinations, product
from typing import Iterable, Iterator

from .key_spec import overlaps
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


def _candidate_contexts(first: KeyBindingDefinition, second: KeyBindingDefinition) -> Iterator[KeybindingRuntimeContext]:
    """Yield every runtime context the dispatcher can produce for the two definitions."""
    base_modes = set(_BUILTIN_MODES) | set(first.modes) | set(second.modes) | {_OTHER_MODE}
    for base_mode, offline, dialog_open, text_input in product(sorted(base_modes), (False, True), (False, True), (False, True)):
        yield KeybindingRuntimeContext(
            active_mode=derive_active_mode(
                offline=offline, dialog_open=dialog_open, text_input_focused=text_input, base_mode=base_mode
            ),
            offline=offline,
            text_input_focused=text_input,
            dialog_open=dialog_open,
        )


def keys_overlap(first: KeyBindingDefinition, second: KeyBindingDefinition) -> bool:
    """True if a key event exists that matches one key of each definition."""
    return any(overlaps(a, b) for a in first.keys for b in second.keys)


def definitions_overlap(first: KeyBindingDefinition, second: KeyBindingDefinition) -> bool:
    """True if both definitions can fire for the same key event in the same runtime context."""
    if not keys_overlap(first, second):
        return False
    for context in _candidate_contexts(first, second):
        if evaluate_binding(first, context)[0] and evaluate_binding(second, context)[0]:
            return True
    return False


def find_conflicts(definitions: Iterable[KeyBindingDefinition]) -> list[tuple[str, str]]:
    """Return every pair of binding ids that conflict (sorted, each pair once)."""
    items = list(definitions)
    conflicts = {
        tuple(sorted((a.binding_id, b.binding_id))) for a, b in combinations(items, 2) if definitions_overlap(a, b)
    }
    return sorted(conflicts)
