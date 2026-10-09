"""Central keybinding registry with mode-aware activation rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .key_spec import KeySpec

UI_MODE_GLOBAL = "global"
UI_MODE_EDITOR = "editor"
UI_MODE_PREVIEW = "preview"
UI_MODE_DIALOG = "dialog"
UI_MODE_OFFLINE = "offline"


@dataclass(frozen=True)
class KeyBindingDefinition:
    """Declarative keybinding contract used across all apps.

    ``keys`` holds one or more :class:`~bw_gui.contracts.key_spec.KeySpec`
    alternatives (any-of; decision 33). Each spec matches exactly its modifiers plus
    its explicit ``tolerate`` set (decision 26); there is no implicit modifier
    tolerance any more (the former ``allow_modifiers`` flag is replaced by
    ``KeySpec.tolerate`` / a second spec for Shift on characters).
    """

    binding_id: str
    keys: tuple[KeySpec, ...]
    intent: str
    modes: tuple[str, ...] = (UI_MODE_GLOBAL,)
    description: str = ""
    allow_when_text_input: bool = False
    allow_when_offline: bool = True
    metadata: dict[str, str] = field(default_factory=dict)
    handler: Callable[[], None] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        keys = (self.keys,) if isinstance(self.keys, KeySpec) else tuple(self.keys)
        if not keys or not all(isinstance(k, KeySpec) for k in keys):
            raise ValueError(f"Binding {self.binding_id!r} needs at least one KeySpec")
        if len(set(keys)) != len(keys):
            raise ValueError(f"Binding {self.binding_id!r} lists a KeySpec twice")
        from .key_spec import overlaps

        for index, first in enumerate(keys):
            for second in keys[index + 1 :]:
                if overlaps(first, second):
                    raise ValueError(f"Binding {self.binding_id!r}: alternatives {first} and {second} overlap")
        object.__setattr__(self, "keys", keys)

    @property
    def primary_key(self) -> KeySpec:
        """The first spec: the one shown in menu hints and overviews."""
        return self.keys[0]


@dataclass(frozen=True)
class KeybindingRuntimeContext:
    """Runtime context contract for mode-aware keybinding resolution.

    Modifier handling is not part of the context any more: whether the held keys
    match a binding is decided by the exact ``KeySpec`` matching
    (``bw_gui.contracts.key_spec.matches``) before gating.
    """

    active_mode: str
    offline: bool = False
    text_input_focused: bool = False
    dialog_open: bool = False


def derive_active_mode(*, offline: bool, dialog_open: bool, text_input_focused: bool, base_mode: str) -> str:
    """Derive the active UI mode from runtime flags (single source for binder and conflict analysis).

    Priority: offline > dialog > text input (editor) > *base_mode* (supplied by the
    app's mode provider, ``UI_MODE_GLOBAL`` by default).
    """
    if offline:
        return UI_MODE_OFFLINE
    if dialog_open:
        return UI_MODE_DIALOG
    if text_input_focused:
        return UI_MODE_EDITOR
    return base_mode


def evaluate_binding(
    definition: KeyBindingDefinition,
    context: KeybindingRuntimeContext,
    *,
    active_mode_override: str | None = None,
) -> tuple[bool, str]:
    """Evaluate whether *definition* may execute in *context* (pure function).

    Returns ``(allowed, reason)``; reasons: ``"active"``, ``"mode=<mode>"``,
    ``"offline-disabled"``, ``"text-input-focus"`` and ``"dialog-priority"``.
    """
    active_mode = active_mode_override or context.active_mode

    if active_mode not in definition.modes and UI_MODE_GLOBAL not in definition.modes:
        return False, f"mode={active_mode}"

    if context.offline and not definition.allow_when_offline:
        return False, "offline-disabled"

    if context.text_input_focused and not definition.allow_when_text_input:
        return False, "text-input-focus"

    if context.dialog_open and UI_MODE_DIALOG not in definition.modes and UI_MODE_GLOBAL not in definition.modes:
        return False, "dialog-priority"

    return True, "active"


class KeybindingRegistry:
    """Stores keybindings centrally and exposes mode and diagnostic views."""

    def __init__(self) -> None:
        self._bindings: list[KeyBindingDefinition] = []
        self._by_id: dict[str, KeyBindingDefinition] = {}

    def register(self, definition: KeyBindingDefinition) -> None:
        """Register one keybinding and reject duplicate binding ids."""
        if definition.binding_id in self._by_id:
            raise ValueError(f"Duplicate keybinding id: {definition.binding_id}")
        self._bindings.append(definition)
        self._by_id[definition.binding_id] = definition

    def register_many(self, definitions: Iterable[KeyBindingDefinition]) -> None:
        """Register multiple keybindings preserving declaration order."""
        for definition in definitions:
            self.register(definition)

    def all(self) -> tuple[KeyBindingDefinition, ...]:
        """Return all keybindings in registry order."""
        return tuple(self._bindings)

    def bindings_for_intent(self, intent: str) -> tuple[KeyBindingDefinition, ...]:
        """Return all keybindings declared for one intent."""
        return tuple(definition for definition in self._bindings if definition.intent == intent)

    def shortcut_for_intent(
        self,
        intent: str,
        *,
        mode: str | None = None,
        offline: bool = False,
        text_input_focused: bool = False,
    ) -> KeySpec | None:
        """Resolve the primary key of the first binding for one intent (``None`` if none)."""
        if mode is None:
            source = self._bindings
        else:
            source = self.active_for_mode(
                mode,
                offline=offline,
                text_input_focused=text_input_focused,
            )

        for definition in source:
            if definition.intent == intent:
                return definition.primary_key
        return None

    def active_for_mode(
        self,
        mode: str,
        *,
        offline: bool,
        text_input_focused: bool,
    ) -> tuple[KeyBindingDefinition, ...]:
        """Return active keybindings for one mode and runtime context."""
        active: list[KeyBindingDefinition] = []
        for definition in self._bindings:
            if mode not in definition.modes and UI_MODE_GLOBAL not in definition.modes:
                continue
            if offline and not definition.allow_when_offline:
                continue
            if text_input_focused and not definition.allow_when_text_input:
                continue
            active.append(definition)
        return tuple(active)

    def find_conflicts(self) -> list[tuple[str, str]]:
        """Return pairs of binding ids that could both fire for the same key event (model A).

        See :mod:`bw_gui.contracts.keybinding_conflicts`.
        """
        from .keybinding_conflicts import find_conflicts

        return find_conflicts(self._bindings)

    def mode_manifest(self) -> dict[str, list[str]]:
        """Expose a compact mode to binding id overview for audit and help UIs."""
        manifest: dict[str, list[str]] = defaultdict(list)
        for definition in self._bindings:
            for mode in definition.modes:
                manifest[mode].append(definition.binding_id)
        return {mode: values for mode, values in sorted(manifest.items())}

    def evaluate_runtime(
        self,
        definition: KeyBindingDefinition,
        context: KeybindingRuntimeContext,
        *,
        active_mode_override: str | None = None,
    ) -> tuple[bool, str]:
        """Evaluate whether a keybinding can execute in a runtime context (see :func:`evaluate_binding`)."""
        return evaluate_binding(definition, context, active_mode_override=active_mode_override)
