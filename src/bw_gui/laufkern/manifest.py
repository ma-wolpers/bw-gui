"""Manifest build and validation helpers for LaufKern."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from bw_gui.contracts.keybinding import KeyBindingDefinition, KeybindingRegistry

from .models import LaufKernManifest, LaufKernRoute
from .reason_codes import REASON_CODE_CATALOG

ALLOWED_ROUTE_TYPES = frozenset({"shortcut", "focus", "composite"})


def build_manifest(
    *,
    manifest_id: str,
    repo_name: str,
    intents: Iterable[str],
    routes: Iterable[LaufKernRoute],
    keybinding_registry: KeybindingRegistry | None = None,
    keybindings: Iterable[KeyBindingDefinition] | None = None,
    exclusions: Mapping[str, str] | None = None,
    equivalence: Mapping[str, str] | None = None,
    metadata: Mapping[str, str] | None = None,
) -> LaufKernManifest:
    """Build one canonical manifest object from repo-provided inputs."""

    if keybinding_registry is not None and keybindings is not None:
        raise ValueError("Provide either keybinding_registry or keybindings, not both")

    if keybinding_registry is not None:
        keybinding_values = keybinding_registry.all()
    else:
        keybinding_values = tuple(keybindings or ())

    manifest = LaufKernManifest(
        manifest_id=manifest_id,
        repo_name=repo_name,
        intents=tuple(intents),
        keybindings=tuple(keybinding_values),
        routes=tuple(routes),
        exclusions=dict(exclusions or {}),
        equivalence=dict(equivalence or {}),
        metadata=dict(metadata or {}),
    )
    return manifest


def verify_manifest(manifest: LaufKernManifest) -> tuple[bool, tuple[str, ...]]:
    """Validate one manifest against LaufKern v1 invariants."""

    errors: list[str] = []
    known_intents = set(manifest.intents)
    binding_ids = {definition.binding_id for definition in manifest.keybindings}
    route_ids: set[str] = set()

    for route in manifest.routes:
        if route.route_id in route_ids:
            errors.append(f"duplicate-route-id:{route.route_id}")
        route_ids.add(route.route_id)

        if route.route_type not in ALLOWED_ROUTE_TYPES:
            errors.append(f"invalid-route-type:{route.route_id}:{route.route_type}")

        if route.intent not in known_intents:
            errors.append(f"route-intent-unknown:{route.route_id}:{route.intent}")

        if route.route_type == "shortcut":
            if not route.binding_id:
                errors.append(f"shortcut-missing-binding:{route.route_id}")
            elif route.binding_id not in binding_ids:
                errors.append(f"shortcut-binding-unknown:{route.route_id}:{route.binding_id}")

    for intent, reason_code in manifest.exclusions.items():
        if intent not in known_intents:
            errors.append(f"exclusion-intent-unknown:{intent}")
        if reason_code not in REASON_CODE_CATALOG:
            errors.append(f"exclusion-reason-unknown:{intent}:{reason_code}")

    for source_intent, target_intent in manifest.equivalence.items():
        if source_intent not in known_intents:
            errors.append(f"equivalence-source-unknown:{source_intent}")
        if target_intent not in known_intents:
            errors.append(f"equivalence-target-unknown:{target_intent}")

    return (len(errors) == 0, tuple(errors))
