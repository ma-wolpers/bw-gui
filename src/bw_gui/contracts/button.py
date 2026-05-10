"""Central contract for icon-first action buttons and tooltip text generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from bw_gui.shortcuts import compose_action_label, compose_hover_text_for_intent
from .keybinding import KeybindingRegistry


@dataclass(frozen=True)
class ButtonDefinition:
    """Declarative button contract for shared menu/toolbar/dialog actions."""

    button_id: str
    intent: str
    label: str
    description: str
    icon: str = ""
    style_role: str = "secondary"
    include_shortcut_in_label: bool = True
    include_shortcut_in_hover: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


class ButtonRegistry:
    """Stores button definitions and renders UX copy from keybinding contracts."""

    def __init__(self) -> None:
        self._buttons: list[ButtonDefinition] = []
        self._by_id: dict[str, ButtonDefinition] = {}

    def register(self, definition: ButtonDefinition) -> None:
        if definition.button_id in self._by_id:
            raise ValueError(f"Duplicate button id: {definition.button_id}")
        self._buttons.append(definition)
        self._by_id[definition.button_id] = definition

    def register_many(self, definitions: Iterable[ButtonDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def all(self) -> tuple[ButtonDefinition, ...]:
        return tuple(self._buttons)

    def by_id(self, button_id: str) -> ButtonDefinition:
        return self._by_id[button_id]

    def render_label(
        self,
        button_id: str,
        *,
        shortcuts: KeybindingRegistry,
        mode: str | None = None,
        offline: bool = False,
        text_input_focused: bool = False,
    ) -> str:
        definition = self.by_id(button_id)
        shortcut = shortcuts.shortcut_for_intent(
            definition.intent,
            mode=mode,
            offline=offline,
            text_input_focused=text_input_focused,
        )
        return compose_action_label(
            definition.label,
            icon=definition.icon,
            shortcut=shortcut,
            include_shortcut=definition.include_shortcut_in_label,
        )

    def render_hover_text(
        self,
        button_id: str,
        *,
        shortcuts: KeybindingRegistry,
        mode: str | None = None,
        offline: bool = False,
        text_input_focused: bool = False,
    ) -> str:
        definition = self.by_id(button_id)
        if not definition.include_shortcut_in_hover:
            return definition.description
        return compose_hover_text_for_intent(
            definition.description,
            intent=definition.intent,
            shortcuts=shortcuts,
            mode=mode,
            offline=offline,
            text_input_focused=text_input_focused,
        )
