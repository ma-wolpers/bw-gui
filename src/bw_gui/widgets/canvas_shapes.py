"""Canvas shapes Tk does not offer natively: rounded rectangles.

``tkinter.Canvas`` has no corner-radius option. The standard technique is a
twelve-point polygon along the four corners, interpolated to soft curves by
``smooth=True``. :func:`rounded_rect_points` computes those points (pure, so a
:class:`~bw_gui.widgets.canvas_item_pool.CanvasItemPool` of kind ``"polygon"``
can place them); :func:`create_rounded_rectangle` is the one-shot variant.
"""

from __future__ import annotations

from typing import Any


def rounded_rect_points(x0: float, y0: float, x1: float, y1: float, *, radius: float = 12.0) -> tuple[float, ...]:
    """Return the flat point list of a rounded rectangle for a smoothed polygon.

    The radius is clamped to half the width/height, so small boxes keep a
    clean pill shape instead of a distorted ("potato") outline.

    Args:
        x0, y0, x1, y1: Bounding box corners like ``canvas.create_rectangle``.
        radius: Wanted corner radius in pixels.

    Returns:
        24 coordinates (12 points) to pass to ``create_polygon(..., smooth=True)``.
    """
    r = max(0.0, min(radius, abs(x1 - x0) / 2.0, abs(y1 - y0) / 2.0))
    return (
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    )  # fmt: skip


def create_rounded_rectangle(
    canvas: Any, x0: float, y0: float, x1: float, y1: float, *, radius: float = 12.0, **kwargs: Any
) -> int:
    """Draw a rounded rectangle on *canvas* and return its item id.

    Args:
        canvas: Target canvas.
        x0, y0, x1, y1: Bounding box corners like ``canvas.create_rectangle``.
        radius: Wanted corner radius in pixels (clamped, see :func:`rounded_rect_points`).
        **kwargs: Passed unchanged to ``canvas.create_polygon`` (``fill``,
            ``outline``, ``width``, ``tags`` …) -- callers treat the result like
            an ordinary rectangle item.

    Returns:
        The canvas item id of the smoothed polygon.
    """
    return canvas.create_polygon(rounded_rect_points(x0, y0, x1, y1, radius=radius), smooth=True, **kwargs)
