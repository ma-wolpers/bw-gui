"""Pure screen-geometry contract (docs/SCREEN_PLACEMENT_CONTRACT.md); no Tk needed."""

import pytest

from bw_gui.contracts.screen_geometry import (
    MonitorInfo,
    MonitorSource,
    Point,
    Rect,
    Side,
    Size,
    calculate_clamped_position,
    calculate_overlay_placement,
    round_rect_inward,
    select_monitor,
)

PRIMARY = MonitorInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040), MonitorSource.WIN32, primary=True)
RIGHT = MonitorInfo(Rect(1920, 0, 3840, 1080), Rect(1920, 0, 3840, 1040), MonitorSource.WIN32)
LEFT_NEG = MonitorInfo(Rect(-1680, 0, 0, 1050), Rect(-1680, 0, 0, 1010), MonitorSource.WIN32)
ABOVE_NEG = MonitorInfo(Rect(0, -1080, 1920, 0), Rect(0, -1080, 1920, -40), MonitorSource.WIN32)
ALL = (PRIMARY, RIGHT, LEFT_NEG, ABOVE_NEG)


def test_module_imports_no_tk_or_platform_api():
    import ast
    from pathlib import Path

    import bw_gui.contracts.screen_geometry as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not imported & {"tkinter", "ctypes", "bw_gui"}


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (Rect(100, 100, 200, 200), PRIMARY),
        (Rect(2000, 10, 2100, 50), RIGHT),
        (Rect(-500, 10, -400, 50), LEFT_NEG),
        (Rect(10, -500, 50, -400), ABOVE_NEG),
        (Rect(1800, 100, 2200, 200), RIGHT),  # centre 2000 on RIGHT
        (Rect(1900, 1100, 2100, 1200), RIGHT),  # centre outside all, nearest/area tie handled
    ],
)
def test_select_monitor_rect_rule(target, expected):
    assert select_monitor(ALL, target) == expected


def test_select_monitor_tie_prefers_primary():
    twin = MonitorInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080), MonitorSource.WIN32)
    assert select_monitor((twin, PRIMARY), Rect(10, 10, 20, 20)) is PRIMARY


def test_select_monitor_largest_intersection_when_centre_is_in_gap():
    a = MonitorInfo(Rect(0, 0, 100, 100), Rect(0, 0, 100, 100), MonitorSource.WIN32)
    b = MonitorInfo(Rect(200, 0, 300, 100), Rect(200, 0, 300, 100), MonitorSource.WIN32)
    # centre at x=145 lies in the gap; 'a' overlaps 40px, 'b' 10px
    assert select_monitor((a, b), Rect(60, 10, 230, 20)) is a


def test_select_monitor_requires_monitors():
    with pytest.raises(ValueError):
        select_monitor((), Rect(0, 0, 1, 1))


def test_below_fits():
    p = calculate_overlay_placement(
        anchor=Rect(100, 100, 200, 120), size=Size(150, 80), monitor=PRIMARY, placement=(Side.BELOW, Side.ABOVE)
    )
    assert (p.position, p.side, p.fits, p.overflow) == (Point(100, 120), Side.BELOW, True, Size(0, 0))


def test_priority_list_flips_only_within_list():
    anchor = Rect(100, 1000, 200, 1020)
    p = calculate_overlay_placement(anchor=anchor, size=Size(150, 80), monitor=PRIMARY, placement=(Side.BELOW, Side.ABOVE))
    assert p.side is Side.ABOVE and p.position == Point(100, 1000 - 80) and p.fits
    q = calculate_overlay_placement(anchor=anchor, size=Size(150, 80), monitor=PRIMARY, placement=(Side.BELOW,))
    assert q.fits is False and q.position.y == 1040 - 8 - 80


def test_cross_axis_is_shifted_into_work_area():
    p = calculate_overlay_placement(
        anchor=Rect(1850, 100, 1900, 120), size=Size(300, 80), monitor=PRIMARY, placement=(Side.BELOW,)
    )
    assert p.fits and p.position == Point(1920 - 8 - 300, 120)


def test_submenu_right_then_left_on_right_monitor_edge():
    p = calculate_overlay_placement(
        anchor=Rect(3700, 100, 3800, 120), size=Size(200, 300), monitor=RIGHT, placement=(Side.RIGHT, Side.LEFT)
    )
    assert p.side is Side.LEFT and p.position == Point(3700 - 200, 100)


def test_overlay_larger_than_work_area_keeps_top_left_inside():
    p = calculate_overlay_placement(
        anchor=Rect(100, 100, 200, 120), size=Size(500, 2000), monitor=PRIMARY, placement=(Side.BELOW, Side.ABOVE)
    )
    assert p.fits is False
    assert p.position.y == 0 + 8
    assert p.overflow.height == 8 + 2000 - (1040 - 8)
    assert PRIMARY.work_area.contains_point(p.position.x, p.position.y)


def test_center_over_clamps():
    p = calculate_overlay_placement(
        anchor=Rect(3700, 50, 3900, 250), size=Size(500, 300), monitor=RIGHT, placement=(Side.CENTER_OVER,), margin=0
    )
    assert p.position == Point(3840 - 500, 0) and p.fits


def test_negative_monitors_left_and_above():
    p = calculate_overlay_placement(
        anchor=Rect(-1650, 10, -1600, 30), size=Size(100, 50), monitor=LEFT_NEG, placement=(Side.LEFT, Side.RIGHT)
    )
    assert p.side is Side.RIGHT and p.position == Point(-1600, 10)
    q = calculate_overlay_placement(
        anchor=Rect(10, -1070, 50, -1060), size=Size(100, 50), monitor=ABOVE_NEG, placement=(Side.ABOVE, Side.BELOW)
    )
    assert q.side is Side.BELOW and q.position == Point(10, -1060)


def test_anchor_partly_outside_is_clamped():
    p = calculate_overlay_placement(
        anchor=Rect(-50, 100, 10, 120), size=Size(100, 50), monitor=PRIMARY, placement=(Side.BELOW,)
    )
    assert p.position.x == 8


def test_placement_is_deterministic():
    kwargs = dict(anchor=Rect(5, 5, 9, 9), size=Size(1000, 1000), monitor=PRIMARY, placement=(Side.ABOVE, Side.LEFT))
    assert len({calculate_overlay_placement(**kwargs) for _ in range(20)}) == 1


def test_empty_placement_rejected():
    with pytest.raises(ValueError):
        calculate_overlay_placement(anchor=Rect(0, 0, 1, 1), size=Size(1, 1), monitor=PRIMARY, placement=())


@pytest.mark.parametrize(
    ("desired", "expected"),
    [
        (Point(100, 100), Point(100, 100)),
        (Point(1900, 100), Point(1920 - 50, 100)),
        (Point(100, 1030), Point(100, 1040 - 20)),
        (Point(-30, -30), Point(0, 0)),
    ],
)
def test_clamped_position(desired, expected):
    assert calculate_clamped_position(desired=desired, size=Size(50, 20), bounds=PRIMARY.work_area) == expected


def test_clamped_position_margin_and_oversize():
    assert calculate_clamped_position(desired=Point(1900, 5), size=Size(50, 20), bounds=RIGHT.work_area, margin=8) == Point(1920 + 8, 8)
    assert calculate_clamped_position(desired=Point(-1000, 5), size=Size(5000, 20), bounds=LEFT_NEG.work_area, margin=8).x == -1680 + 8


def test_round_rect_inward():
    assert round_rect_inward(0.5, 1.2, 99.7, 50.9) == Rect(1, 2, 99, 50)
