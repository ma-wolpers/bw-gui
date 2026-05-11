"""Focus-navigation helpers for LaufKern route evaluation."""

from __future__ import annotations

from .models import LaufKernRoute


def focus_routes_for_intent(routes: tuple[LaufKernRoute, ...], intent: str) -> tuple[LaufKernRoute, ...]:
    """Return focus/composite routes that belong to one intent."""

    return tuple(route for route in routes if route.intent == intent and route.route_type in {"focus", "composite"})


def validate_focus_route_metadata(route: LaufKernRoute) -> tuple[bool, str]:
    """Validate required metadata fields for focus and composite routes."""

    if route.route_type not in {"focus", "composite"}:
        return True, "not-focus-route"

    source = route.metadata.get("from")
    target = route.metadata.get("to")
    if not source or not target:
        return False, "focus-route-missing-endpoint"
    return True, "ok"
