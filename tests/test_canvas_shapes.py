"""canvas_shapes: rounded-rectangle points (pure) and the one-shot canvas helper."""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.widgets.canvas_shapes import create_rounded_rectangle, rounded_rect_points


def test_points_trace_the_box_with_radius_inset():
    points = rounded_rect_points(0, 0, 100, 40, radius=10)
    assert len(points) == 24
    xs, ys = points[0::2], points[1::2]
    assert (min(xs), max(xs), min(ys), max(ys)) == (0, 100, 0, 40)
    assert points[:2] == (10, 0)  # top edge starts after the corner radius


def test_radius_is_clamped_to_half_the_smaller_side():
    points = rounded_rect_points(0, 0, 200, 20, radius=50)
    assert points[:2] == (10, 0)


def test_negative_radius_degrades_to_plain_corners():
    assert rounded_rect_points(0, 0, 10, 10, radius=-5)[:2] == (0, 0)


@pytest.fixture
def canvas(_shared_tk_root):
    widget = ui.Canvas(_shared_tk_root)
    yield widget
    widget.destroy()


def test_create_returns_a_smoothed_polygon_with_tags(canvas):
    item = create_rounded_rectangle(canvas, 0, 0, 60, 30, radius=8, tags=("node",))
    assert canvas.type(item) == "polygon"
    assert "node" in canvas.gettags(item)
    assert str(canvas.itemcget(item, "smooth")) in {"1", "true", "bezier"}
