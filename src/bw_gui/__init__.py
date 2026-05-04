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
from .dialogs import FileDialogService, MessageDialogService, TextPromptDialogService
from .runtime import fonts, ui, widgets

__all__ = [
    "HsmContract",
    "HsmIntentSpec",
    "FileDialogService",
    "fonts",
    "KeyBindingDefinition",
    "KeybindingRegistry",
    "KeybindingRuntimeContext",
    "MessageDialogService",
    "PopupPolicy",
    "PopupPolicyRegistry",
    "PopupSession",
    "TextPromptDialogService",
    "TransitionRule",
    "build_ui_hsm_contract",
    "ui",
    "widgets",
]
