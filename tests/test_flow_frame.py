"""Tests for `FlowFrame` (wrapping row layout) and its pure `compute_flow_layout`.

The pure function carries the wrapping rule (order, wrap at the width, oversized
child on its own row, rows as tall as their tallest child, vertical centring).
The real-Tk tests check that the widget applies it: children wrap when the frame
is narrow, re-flow when it widens, and the frame requests the wrapped height
(what an enclosing `ScrollableFrame` needs). Shared root as in
`test_scrollable_frame.py`.
"""

from __future__ import annotations

import pytest

from bw_gui.runtime import widgets
from bw_gui.widgets import FlowFrame, compute_flow_layout


def test_single_row_when_everything_fits() -> None:
    positions, height = compute_flow_layout([(10, 5), (20, 5)], 100, gap_x=4, gap_y=2)
    assert positions == [(0, 0), (14, 0)]
    assert height == 5


def test_wraps_at_the_width_and_keeps_order() -> None:
    positions, height = compute_flow_layout([(40, 10), (40, 10), (40, 10)], 90, gap_x=5, gap_y=3)
    assert positions == [(0, 0), (45, 0), (0, 13)]
    assert height == 23


def test_oversized_child_gets_its_own_row() -> None:
    positions, _height = compute_flow_layout([(10, 4), (200, 4), (10, 4)], 50, gap_x=2, gap_y=0)
    assert [y for _x, y in positions] == [0, 4, 8]


def test_rows_take_the_tallest_child_and_centre_the_others() -> None:
    positions, height = compute_flow_layout([(10, 20), (10, 10)], 100, gap_x=0, gap_y=0)
    assert positions == [(0, 0), (10, 5)]
    assert height == 20


def test_unbounded_width_is_one_row_and_empty_is_zero() -> None:
    assert compute_flow_layout([(50, 5)] * 3, None, gap_x=0, gap_y=0)[1] == 5
    assert compute_flow_layout([], 100, gap_x=4, gap_y=4) == ([], 0)


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    _shared_tk_root.geometry("400x300+0+0")
    _shared_tk_root.update()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _flow_with_labels(parent, count: int) -> FlowFrame:
    flow = FlowFrame(parent, gap_x=6, gap_y=2)
    for i in range(count):
        flow.add(widgets.Label(flow, text=f"Badge {i:02d}"))
    return flow


def test_children_wrap_in_a_narrow_frame_and_stay_inside(root) -> None:
    holder = widgets.Frame(root, width=150, height=300)
    holder.pack_propagate(False)
    holder.pack(side="left", fill="y")
    flow = _flow_with_labels(holder, 8)
    flow.pack(fill="x")
    root.update()
    flow.relayout()
    root.update()

    assert len({child.winfo_y() for child in flow.items}) > 1
    for child in flow.items:
        assert child.winfo_x() + child.winfo_width() <= flow.winfo_width()
    assert flow.winfo_reqheight() >= max(child.winfo_y() + child.winfo_height() for child in flow.items)


def test_widening_reflows_into_fewer_rows(root) -> None:
    holder = widgets.Frame(root, width=150, height=300)
    holder.pack_propagate(False)
    holder.pack(side="left", fill="y")
    flow = _flow_with_labels(holder, 6)
    flow.pack(fill="x")
    root.update()
    flow.relayout()
    root.update()
    narrow_rows = len({child.winfo_y() for child in flow.items})

    holder.configure(width=400)
    root.update()
    flow.relayout()
    root.update()

    assert len({child.winfo_y() for child in flow.items}) < narrow_rows


def test_add_rejects_foreign_children_and_clear_destroys(root) -> None:
    flow = _flow_with_labels(root, 2)
    with pytest.raises(ValueError):
        flow.add(widgets.Label(root, text="fremd"))
    children = flow.items
    flow.clear()
    root.update()
    assert flow.items == ()
    assert not any(child.winfo_exists() for child in children)
