"""LaufKern public API: interaction runtime, reachability, and tracking."""

from __future__ import annotations

from .context import build_runtime_context
from .focus_nav import focus_routes_for_intent, validate_focus_route_metadata
from .manifest import build_manifest, verify_manifest
from .models import (
    CompletionSummary,
    LaufKernManifest,
    LaufKernRoute,
    ReachabilityResult,
    TrackingArtifact,
)
from .reachability import evaluate_intent_routes, verify_reachability
from .reason_codes import REASON_CODE_CATALOG, is_known_reason_code
from .routing import resolve_intent_target
from .shortcut_resolution import registry_from_bindings, resolve_binding_runtime
from .tracking import aggregate_completion, emit_tracking_artifact, validate_step_id

__all__ = [
    "CompletionSummary",
    "LaufKernManifest",
    "LaufKernRoute",
    "ReachabilityResult",
    "TrackingArtifact",
    "REASON_CODE_CATALOG",
    "aggregate_completion",
    "build_manifest",
    "build_runtime_context",
    "emit_tracking_artifact",
    "evaluate_intent_routes",
    "focus_routes_for_intent",
    "is_known_reason_code",
    "registry_from_bindings",
    "resolve_binding_runtime",
    "resolve_intent_target",
    "validate_focus_route_metadata",
    "validate_step_id",
    "verify_manifest",
    "verify_reachability",
]
