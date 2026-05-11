"""Intent routing helpers for LaufKern."""

from __future__ import annotations

from .models import LaufKernManifest


def resolve_intent_target(intent: str, manifest: LaufKernManifest) -> str:
    """Resolve canonical target intent, considering declared equivalence mapping."""

    return manifest.equivalence.get(intent, intent)
