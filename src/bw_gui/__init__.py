"""Shared GUI core package for Blattwerk-family applications."""

from .contracts import (
    HsmContract,
    HsmIntentSpec,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
    PopupPolicy,
    PopupPolicyRegistry,
    PopupSession,
    TransitionRule,
    build_ui_hsm_contract,
)

__all__ = [
    "HsmContract",
    "HsmIntentSpec",
    "KeyBindingDefinition",
    "KeybindingRegistry",
    "KeybindingRuntimeContext",
    "PopupPolicy",
    "PopupPolicyRegistry",
    "PopupSession",
    "TransitionRule",
    "build_ui_hsm_contract",
]
