"""Central keybinding registry with mode-aware activation rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .key_modifiers import UNKNOWN_MODIFIERS, KeyModifiers, TkBackend, UnknownModifiers
from .key_sequence import binding_signature

UI_MODE_GLOBAL = "global"
UI_MODE_EDITOR = "editor"
UI_MODE_PREVIEW = "preview"
UI_MODE_DIALOG = "dialog"
UI_MODE_OFFLINE = "offline"


@dataclass(frozen=True)
class KeyBindingDefinition:
    """Declarative keybinding contract used across all apps.

    ``allow_modifiers`` allows *additional, undeclared* shortcut modifiers
    (Control, Alt/Option, Command) to be held while the binding fires. With the
    default ``False``, a binding for ``a`` does not fire on Ctrl+a / Alt+a, while
    ``<Control-a>`` still fires on Ctrl+a because Control is declared in its
    sequence. Shift is never a shortcut modifier and never blocks. The rule is only
    enforced when the runtime context carries modifier information (see
    :class:`KeybindingRuntimeContext` and ``docs/KEYBINDING_CONTRACT.md``).
    """

    binding_id: str
    sequence: str
    intent: str
    modes: tuple[str, ...] = (UI_MODE_GLOBAL,)
    description: str = ""
    allow_modifiers: bool = False
    allow_when_text_input: bool = False
    allow_when_offline: bool = True
    metadata: dict[str, str] = field(default_factory=dict)
    handler: Callable[[], None] | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class KeybindingRuntimeContext:
    """Runtime context contract for mode-aware keybinding resolution.

    ``modifiers`` has three distinct states:

    * ``None`` -- this runtime path supplies no modifier information at all
      (legacy contexts); no modifier gating is applied.
    * :data:`~bw_gui.contracts.key_modifiers.UNKNOWN_MODIFIERS` -- an event exists,
      but its modifier state could not be decoded; gated fail-closed.
    * :class:`~bw_gui.contracts.key_modifiers.KeyModifiers` -- decoded state.

    ``backend`` selects the Tk backend used to interpret the modifier tokens of a
    binding's sequence; ``None`` derives it from ``sys.platform``.
    """

    active_mode: str
    offline: bool = False
    text_input_focused: bool = False
    dialog_open: bool = False
    modifiers: KeyModifiers | UnknownModifiers | None = None
    backend: TkBackend | None = None


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
    ``"offline-disabled"``, ``"text-input-focus"``, ``"dialog-priority"``,
    ``"modifier-held"`` (an undeclared shortcut modifier is held) and
    ``"modifier-unknown"`` (modifier state undecodable; fail-closed).

    Raises:
        ValueError: If modifier gating applies and the binding's sequence is outside
            the keyboard-shortcut contract (see :func:`binding_signature`).
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

    held = context.modifiers
    if held is not None and not definition.allow_modifiers:
        if held is UNKNOWN_MODIFIERS:
            return False, "modifier-unknown"
        declared = binding_signature(definition.sequence, context.backend).modifiers
        if held.shortcut_modifiers_not_in(declared).has_shortcut_modifier:
            return False, "modifier-held"

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
    ) -> str | None:
        """Resolve first matching shortcut sequence for one intent."""
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
                return definition.sequence
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

    def conflicts(self) -> dict[str, list[str]]:
        """List *raw-string* sequence collisions per mode (sequence to binding ids).

        Deprecated: compares sequence strings literally, so semantically equal
        sequences (``<Control-,>`` vs ``<Control-comma>``) are missed and
        disjoint runtime scopes are reported. Use :meth:`find_conflicts`.
        """
        collisions: dict[str, list[str]] = {}
        usage: dict[tuple[str, str], list[str]] = defaultdict(list)
        for definition in self._bindings:
            for mode in definition.modes:
                usage[(mode, definition.sequence)].append(definition.binding_id)
        for (mode, sequence), binding_ids in usage.items():
            if len(binding_ids) > 1:
                collisions[f"{mode}:{sequence}"] = sorted(binding_ids)
        return collisions

    def find_conflicts(self, backend: TkBackend | None = None) -> list[tuple[str, str]]:
        """Return pairs of binding ids that could both fire for the same key event.

        Uses semantic :func:`binding_signature` equality plus overlap of the complete
        runtime applicability (see :mod:`bw_gui.contracts.keybinding_conflicts`).
        """
        from .keybinding_conflicts import find_conflicts

        return find_conflicts(self._bindings, backend)

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
