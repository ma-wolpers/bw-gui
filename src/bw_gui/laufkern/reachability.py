"""Reachability verifier for keyboard routes declared in LaufKern manifests."""

from __future__ import annotations

from collections.abc import Iterable

from bw_gui.contracts.keybinding import KeyBindingDefinition, KeybindingRuntimeContext, KeybindingRegistry

from .models import LaufKernManifest, LaufKernRoute, ReachabilityResult
from .reason_codes import (
    LK_MAN_INTENT_UNKNOWN,
    LK_MAN_ROUTE_UNKNOWN,
    LK_RCH_MODE_BLOCKED,
    LK_RCH_NO_FOCUS_PATH,
    LK_RCH_NO_SHORTCUT,
    LK_RCH_POPUP_BLOCKED,
    LK_RCH_TEXT_INPUT_BLOCKED,
)
from .routing import resolve_intent_target


def _binding_by_id(bindings: tuple[KeyBindingDefinition, ...]) -> dict[str, KeyBindingDefinition]:
    return {binding.binding_id: binding for binding in bindings}


def _map_runtime_reason(reason: str) -> str:
    if reason == "text-input-focus":
        return LK_RCH_TEXT_INPUT_BLOCKED
    if reason == "dialog-priority":
        return LK_RCH_POPUP_BLOCKED
    return LK_RCH_MODE_BLOCKED


def evaluate_intent_routes(
    *,
    manifest: LaufKernManifest,
    intent: str,
    context: KeybindingRuntimeContext,
) -> ReachabilityResult:
    """Evaluate one intent against all applicable routes in one runtime context."""

    if intent not in set(manifest.intents):
        return ReachabilityResult(intent=intent, reachable=False, reason_code=LK_MAN_INTENT_UNKNOWN)

    if intent in manifest.exclusions:
        return ReachabilityResult(intent=intent, reachable=False, reason_code=manifest.exclusions[intent])

    target_intent = resolve_intent_target(intent, manifest)
    binding_by_id = _binding_by_id(manifest.keybindings)
    registry = KeybindingRegistry()
    registry.register_many(manifest.keybindings)

    routes: tuple[LaufKernRoute, ...] = tuple(route for route in manifest.routes if route.intent == target_intent)
    if not routes:
        has_intent_bindings = any(binding.intent == target_intent for binding in manifest.keybindings)
        reason = LK_RCH_NO_FOCUS_PATH if has_intent_bindings else LK_RCH_NO_SHORTCUT
        return ReachabilityResult(intent=intent, reachable=False, reason_code=reason)

    blocked_reasons: list[str] = []
    active_route_ids: list[str] = []

    for route in routes:
        if route.route_type == "shortcut":
            if not route.binding_id:
                blocked_reasons.append(LK_MAN_ROUTE_UNKNOWN)
                continue
            binding = binding_by_id.get(route.binding_id)
            if binding is None:
                blocked_reasons.append(LK_MAN_ROUTE_UNKNOWN)
                continue

            is_active, runtime_reason = registry.evaluate_runtime(binding, context)
            if is_active:
                active_route_ids.append(route.route_id)
                continue
            blocked_reasons.append(_map_runtime_reason(runtime_reason))
            continue

        if route.modes and context.active_mode not in route.modes:
            blocked_reasons.append(LK_RCH_MODE_BLOCKED)
            continue

        if context.dialog_open and route.metadata.get("popup_blocking") == "true":
            blocked_reasons.append(LK_RCH_POPUP_BLOCKED)
            continue

        active_route_ids.append(route.route_id)

    if active_route_ids:
        return ReachabilityResult(intent=intent, reachable=True, route_ids=tuple(active_route_ids))

    if blocked_reasons:
        return ReachabilityResult(intent=intent, reachable=False, reason_code=blocked_reasons[0])

    return ReachabilityResult(intent=intent, reachable=False, reason_code=LK_RCH_NO_FOCUS_PATH)


def verify_reachability(
    *,
    manifest: LaufKernManifest,
    context: KeybindingRuntimeContext,
    intents: Iterable[str] | None = None,
) -> tuple[ReachabilityResult, ...]:
    """Verify reachability for all in-scope intents in one runtime context."""

    in_scope = tuple(intents) if intents is not None else manifest.intents
    return tuple(
        evaluate_intent_routes(
            manifest=manifest,
            intent=intent,
            context=context,
        )
        for intent in in_scope
    )
