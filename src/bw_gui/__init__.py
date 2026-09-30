"""Shared GUI core package for Blattwerk-family applications.

The Tk/ttk aliases live in bw_gui.runtime only (from bw_gui.runtime import ui,
widgets, fonts). They are deliberately *not* re-exported here: a top-level
widgets attribute (the ttk module) would shadow the bw_gui.widgets package
(Checkbox, Switch, ...), so import bw_gui.widgets.toggles as t broke.
"""

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
from .laufkern import (
    CompletionSummary,
    LaufKernManifest,
    LaufKernRoute,
    ReachabilityResult,
    TrackingArtifact,
    aggregate_completion,
    build_manifest,
    build_runtime_context,
    emit_tracking_artifact,
    evaluate_intent_routes,
    verify_manifest,
    verify_reachability,
)
from .runtime import BwBaseWindow

__all__ = [
    "BwBaseWindow",
    "HsmContract",
    "HsmIntentSpec",
    "LaufKernManifest",
    "LaufKernRoute",
    "CompletionSummary",
    "FileDialogService",
    "KeyBindingDefinition",
    "KeybindingRegistry",
    "KeybindingRuntimeContext",
    "MessageDialogService",
    "PopupPolicy",
    "PopupPolicyRegistry",
    "PopupSession",
    "ReachabilityResult",
    "TrackingArtifact",
    "TextPromptDialogService",
    "TransitionRule",
    "build_ui_hsm_contract",
    "build_manifest",
    "build_runtime_context",
    "verify_manifest",
    "verify_reachability",
    "evaluate_intent_routes",
    "emit_tracking_artifact",
    "aggregate_completion",
]
