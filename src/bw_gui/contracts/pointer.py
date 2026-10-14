"""Pointer contract, pure part (``docs/POINTER_CONTRACT.md``).

The only place that interprets Tk's wheel ``delta``/X11 button numbers. Consumers get
:class:`WheelEvent`, :class:`ClickEvent` and :class:`DragEvent` with semantic modifiers
and never see ``event.delta``, ``event.num`` or ``event.state``.

``WheelEvent.steps`` is continuous, unit "notch" (1.0 = one detent of a standard
mouse wheel), positive towards the end of the content (down/right).
``whole_steps`` is discrete: per subscription and axis ``acc += steps;
whole = trunc(acc); acc -= whole``. There is no time limit and no reset on direction
changes (net movement counts; a counter-movement reduces the remainder); the
accumulator is dropped only when the subscription is removed (decision 23).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .key_modifiers import KeyModifiers, TkBackend, UnknownModifiers


class Axis(str, Enum):
    """Scroll axis of a wheel event."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class Button(int, Enum):
    """Semantic mouse buttons."""

    PRIMARY = 1
    MIDDLE = 2
    SECONDARY = 3


def wheel_steps(*, backend: TkBackend, delta: object = 0, num: object = None) -> float:
    """Normalise one raw wheel event to notches (positive = towards the content end).

    * win32: ``-delta / 120`` (mouse wheels report multiples of 120; precision
      touchpads report fractions, which stay fractional here).
    * x11: button 4 -> ``-1.0``, button 5 -> ``+1.0``.
    * aqua: ``-delta`` (not verified live; documented like the aqua modifier masks).
    """
    if backend is TkBackend.X11 and num in (4, 5, "4", "5"):
        return -1.0 if int(num) == 4 else 1.0
    try:
        value = float(delta)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if backend is TkBackend.AQUA:
        return -value
    return -value / 120.0


class StepAccumulator:
    """Deterministic net accumulator producing ``whole_steps`` (no time component)."""

    def __init__(self) -> None:
        self._remainder: dict[Axis, float] = {}

    def add(self, axis: Axis, steps: float) -> int:
        """Add *steps* on *axis* and return the whole notches now complete."""
        total = self._remainder.get(axis, 0.0) + steps
        whole = math.trunc(round(total, 9))
        self._remainder[axis] = total - whole
        return whole


@dataclass(frozen=True)
class WheelEvent:
    """Semantic wheel event."""

    steps: float
    whole_steps: int
    axis: Axis
    modifiers: KeyModifiers | UnknownModifiers
    x: int
    y: int
    x_root: int
    y_root: int
    widget: object = None


def wheel_axis(event: WheelEvent, *, shift_means_horizontal: bool = True) -> Axis:
    """Return the axis a consumer should scroll, making the Shift interpretation explicit.

    Tk 8.6 on Windows does not distinguish horizontal tilt from Shift+wheel, so
    ``WheelEvent.axis`` is always ``VERTICAL`` there; consumers that want the common
    "Shift scrolls horizontally" convention call this helper.
    """
    if shift_means_horizontal and isinstance(event.modifiers, KeyModifiers) and event.modifiers.shift:
        return Axis.HORIZONTAL
    return event.axis


@dataclass(frozen=True)
class ClickEvent:
    """Semantic click (``count`` 1 = single press, 2 = second press of a double click)."""

    button: Button
    count: int
    modifiers: KeyModifiers | UnknownModifiers
    x: int
    y: int
    x_root: int
    y_root: int
    widget: object = None


class CancelReason(str, Enum):
    """Why a drag ended without ``on_end``."""

    FOCUS_LOST = "focus_lost"
    ESCAPE = "escape"


@dataclass(frozen=True)
class DragEvent:
    """Semantic drag event; ``start_modifiers`` are frozen at press time."""

    x: int
    y: int
    x_root: int
    y_root: int
    start_x_root: int
    start_y_root: int
    start_modifiers: KeyModifiers | UnknownModifiers
    modifiers: KeyModifiers | UnknownModifiers
    widget: object = None
