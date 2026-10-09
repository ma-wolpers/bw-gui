"""Pure screen geometry: monitor selection, overlay placement and clamping.

This module is the functional half of ``docs/SCREEN_PLACEMENT_CONTRACT.md``. It
imports neither ``tkinter`` nor any platform API, performs no IO and has no side
effects: identical inputs always produce identical outputs. The Tk side (measuring
a window, querying monitors, applying a position) lives in
``bw_gui.runtime.screen_placement``.

Coordinates are integer Tk root coordinates of the virtual desktop (the values
``winfo_rootx``/``wm geometry`` use). The origin is the top-left corner of the
primary monitor; negative values are valid. Rectangles are half-open:
``[left, right) x [top, bottom)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Point:
    """A position in virtual-desktop coordinates."""

    x: int
    y: int


@dataclass(frozen=True)
class Size:
    """A width/height pair in pixels (both >= 0)."""

    width: int
    height: int


@dataclass(frozen=True)
class Rect:
    """A half-open rectangle ``[left, right) x [top, bottom)``."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """Return the rectangle width (never negative)."""
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        """Return the rectangle height (never negative)."""
        return max(0, self.bottom - self.top)

    @property
    def center(self) -> tuple[float, float]:
        """Return the exact (possibly fractional) center point."""
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)

    def contains_point(self, x: float, y: float) -> bool:
        """Return True when ``(x, y)`` lies inside the half-open rectangle."""
        return self.left <= x < self.right and self.top <= y < self.bottom

    def intersection_area(self, other: "Rect") -> int:
        """Return the area shared with *other* (0 when they do not overlap)."""
        width = min(self.right, other.right) - max(self.left, other.left)
        height = min(self.bottom, other.bottom) - max(self.top, other.top)
        return max(0, width) * max(0, height)

    @staticmethod
    def from_origin(origin: Point, size: Size) -> "Rect":
        """Build the rectangle with top-left *origin* and extent *size*."""
        return Rect(origin.x, origin.y, origin.x + size.width, origin.y + size.height)


class MonitorSource(str, Enum):
    """Where a :class:`MonitorInfo` came from (visible for tests and diagnostics)."""

    WIN32 = "win32"
    TK_SCREEN = "tk_screen"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class MonitorInfo:
    """Bounds and work area (bounds minus task bars) of one monitor."""

    bounds: Rect
    work_area: Rect
    source: MonitorSource
    primary: bool = False


class Side(str, Enum):
    """Candidate positions of an overlay relative to its anchor."""

    BELOW = "below"
    ABOVE = "above"
    RIGHT = "right"
    LEFT = "left"
    CENTER_OVER = "center_over"


@dataclass(frozen=True)
class Placement:
    """Result of :func:`calculate_overlay_placement`.

    ``size`` records the overlay size the placement was computed for; a placement
    is only valid for exactly that size.
    """

    position: Point
    size: Size
    side: Side
    fits: bool
    overflow: Size


def round_rect_inward(left: float, top: float, right: float, bottom: float) -> Rect:
    """Round a fractional monitor rectangle inward (``ceil`` left/top, ``floor`` right/bottom).

    Used when a DPI conversion yields fractions: an overlay placed inside the
    rounded rectangle can never extend one pixel beyond the real monitor area.
    """
    return Rect(math.ceil(left), math.ceil(top), math.floor(right), math.floor(bottom))


def select_monitor(monitors: list[MonitorInfo] | tuple[MonitorInfo, ...], target: Rect) -> MonitorInfo:
    """Pick the monitor responsible for *target* (contract: centre, then overlap, then nearest).

    1. The monitor whose bounds contain the target's centre.
    2. Otherwise the monitor with the largest intersection.
    3. Otherwise the monitor nearest to the centre.
    4. Ties: primary monitor first, then smaller ``left``, then smaller ``top``.

    Args:
        monitors: All known monitors (at least one).
        target: The rectangle (a point is a 1x1 rectangle) to resolve.

    Raises:
        ValueError: If *monitors* is empty.
    """
    if not monitors:
        raise ValueError("select_monitor needs at least one monitor")

    def tie_key(info: MonitorInfo) -> tuple[int, int, int]:
        return (0 if info.primary else 1, info.bounds.left, info.bounds.top)

    cx, cy = target.center
    containing = [m for m in monitors if m.bounds.contains_point(cx, cy)]
    if containing:
        return min(containing, key=tie_key)

    best_area = max(m.bounds.intersection_area(target) for m in monitors)
    if best_area > 0:
        return min((m for m in monitors if m.bounds.intersection_area(target) == best_area), key=tie_key)

    def distance(info: MonitorInfo) -> float:
        bounds = info.bounds
        dx = max(bounds.left - cx, 0.0, cx - (bounds.right - 1))
        dy = max(bounds.top - cy, 0.0, cy - (bounds.bottom - 1))
        return math.hypot(dx, dy)

    best_distance = min(distance(m) for m in monitors)
    return min((m for m in monitors if distance(m) == best_distance), key=tie_key)


def _clamp_axis(start: int, length: int, low: int, high: int) -> int:
    """Clamp a 1-D interval ``[start, start+length)`` into ``[low, high)``.

    When the interval is longer than the available range its start sits on
    ``low`` (the overflow goes towards ``high``).
    """
    if length >= high - low:
        return low
    return max(low, min(start, high - length))


def calculate_clamped_position(*, desired: Point, size: Size, bounds: Rect, margin: int = 0) -> Point:
    """Clamp a desired top-left position so a box of *size* stays inside *bounds*.

    Pure primitive (e.g. for a drag ghost following the cursor): no side, no flip,
    no anchor. Each axis is clamped independently into
    ``[bounds.left + margin, bounds.right - margin - size.width]`` (vertically
    analogous). If the box is larger than the area in an axis, its left/top edge
    sits on ``bounds + margin``.
    """
    low_x, high_x = bounds.left + margin, bounds.right - margin
    low_y, high_y = bounds.top + margin, bounds.bottom - margin
    return Point(
        _clamp_axis(desired.x, size.width, low_x, high_x),
        _clamp_axis(desired.y, size.height, low_y, high_y),
    )


def _candidate(side: Side, anchor: Rect, size: Size, gap: int) -> Point:
    """Return the unclamped top-left position of *side* relative to *anchor*."""
    if side is Side.BELOW:
        return Point(anchor.left, anchor.bottom + gap)
    if side is Side.ABOVE:
        return Point(anchor.left, anchor.top - gap - size.height)
    if side is Side.RIGHT:
        return Point(anchor.right + gap, anchor.top)
    if side is Side.LEFT:
        return Point(anchor.left - gap - size.width, anchor.top)
    cx, cy = anchor.center
    return Point(int(round(cx - size.width / 2)), int(round(cy - size.height / 2)))


def calculate_overlay_placement(
    *,
    anchor: Rect,
    size: Size,
    monitor: MonitorInfo,
    placement: tuple[Side, ...],
    gap: int = 0,
    margin: int = 8,
) -> Placement:
    """Compute where an overlay of *size* goes next to *anchor* (pure, deterministic).

    *placement* is a priority list. For each side the candidate is aligned to the
    anchor on the main axis and shifted into the work area on the cross axis
    (``center_over`` is clamped on both axes). The first side whose overlay lies
    completely inside ``monitor.work_area`` shrunk by *margin* wins; there is no
    implicit flip outside the list. If no side fits, the side with the largest
    visible area wins (ties: list order), is clamped, and ``fits=False`` with the
    remaining ``overflow`` is reported. The top-left corner always ends up inside
    the work area; the size is never changed.

    Raises:
        ValueError: If *placement* is empty.
    """
    if not placement:
        raise ValueError("placement must name at least one side")
    work = monitor.work_area
    low_x, high_x = work.left + margin, work.right - margin
    low_y, high_y = work.top + margin, work.bottom - margin
    allowed = Rect(low_x, low_y, max(low_x, high_x), max(low_y, high_y))

    best: tuple[int, int, Side, Point] | None = None
    for order, side in enumerate(placement):
        raw = _candidate(side, anchor, size, gap)
        if side in (Side.BELOW, Side.ABOVE):
            raw = Point(_clamp_axis(raw.x, size.width, low_x, high_x), raw.y)
        elif side in (Side.RIGHT, Side.LEFT):
            raw = Point(raw.x, _clamp_axis(raw.y, size.height, low_y, high_y))
        else:
            raw = calculate_clamped_position(desired=raw, size=size, bounds=work, margin=margin)
        box = Rect.from_origin(raw, size)
        visible = box.intersection_area(allowed)
        inside = (
            allowed.left <= box.left
            and box.right <= allowed.right
            and allowed.top <= box.top
            and box.bottom <= allowed.bottom
        )
        if inside:
            return Placement(raw, size, side, True, Size(0, 0))
        if best is None or visible > best[0]:
            best = (visible, order, side, raw)

    assert best is not None
    _visible, _order, side, raw = best
    position = calculate_clamped_position(desired=raw, size=size, bounds=work, margin=margin)
    overflow = Size(
        max(0, position.x + size.width - high_x),
        max(0, position.y + size.height - high_y),
    )
    # No side of the priority list fit: contract says fits=False even when the
    # clamp happens to pull the box fully inside (it then covers the anchor).
    return Placement(position, size, side, False, overflow)
