"""Central contracts for keybindings, popups, and UI state-machine behavior."""

from .hsm import (
    ESCAPE_CLOSE_POPUP,
    ESCAPE_EXIT_INLINE_EDITOR,
    ESCAPE_POP_PARENT,
    ESCAPE_ROOT_NOOP,
    HsmContract,
    HsmIntentSpec,
    TransitionRule,
    build_ui_hsm_contract,
)
from .button import ButtonDefinition, ButtonRegistry
from .key_modifiers import (
    NO_MODIFIERS,
    UNKNOWN_MODIFIERS,
    KeyModifiers,
    TkBackend,
    UnknownModifiers,
    backend_for_platform,
    backend_for_windowing_system,
    modifiers_from_event,
    modifiers_from_state,
)
from .events import EventResult, coerce_result
from .key_event import KeyEvent
from .key_spec import Key, KeySpec, Mod
from .subscription import Subscription
from .keybinding_conflicts import definitions_overlap, find_conflicts
from .keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
    derive_active_mode,
    evaluate_binding,
)
from .popup import (
    POPUP_KIND_MODAL,
    POPUP_KIND_NON_MODAL,
    PopupPolicy,
    PopupPolicyRegistry,
    PopupSession,
)

__all__ = [
    "ESCAPE_CLOSE_POPUP",
    "ESCAPE_EXIT_INLINE_EDITOR",
    "ESCAPE_POP_PARENT",
    "ESCAPE_ROOT_NOOP",
    "HsmContract",
    "HsmIntentSpec",
    "TransitionRule",
    "UI_MODE_DIALOG",
    "UI_MODE_EDITOR",
    "UI_MODE_GLOBAL",
    "UI_MODE_OFFLINE",
    "UI_MODE_PREVIEW",
    "KeyBindingDefinition",
    "KeybindingRegistry",
    "KeybindingRuntimeContext",
    "derive_active_mode",
    "evaluate_binding",
    "NO_MODIFIERS",
    "UNKNOWN_MODIFIERS",
    "KeyModifiers",
    "TkBackend",
    "UnknownModifiers",
    "backend_for_platform",
    "backend_for_windowing_system",
    "modifiers_from_event",
    "modifiers_from_state",
    "EventResult",
    "coerce_result",
    "Key",
    "KeyEvent",
    "KeySpec",
    "Mod",
    "Subscription",
    "definitions_overlap",
    "find_conflicts",
    "POPUP_KIND_MODAL",
    "POPUP_KIND_NON_MODAL",
    "PopupPolicy",
    "PopupPolicyRegistry",
    "PopupSession",
    "build_ui_hsm_contract",
    "ButtonDefinition",
    "ButtonRegistry",
]
