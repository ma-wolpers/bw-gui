"""DataGrid on a real Tk root: virtualisation, constant-cost cursor, hit testing, scrolling, zoom.

Call budgets are counted (``count_tcl_calls``), never timed, so the tests are
deterministic.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bw_gui.contracts.key_modifiers import KeyModifiers
from bw_gui.contracts.pointer import Axis, WheelEvent
from bw_gui.runtime import ui
from bw_gui.testing.tcl_calls import count_tcl_calls
from bw_gui.widgets.data_grid import DataGrid, GridColumn, GridRow, Region

ROWS = 30


def _columns(dates: int) -> list[GridColumn]:
    cols = [GridColumn("last", "Nachname", 150, Region.LEFT), GridColumn("first", "Vorname", 120, Region.LEFT)]
    cols += [GridColumn(f"d{i}", f"Tag {i}", 120, Region.SCROLL, "center") for i in range(dates)]
    return cols + [GridColumn("sum", "Summe", 180, Region.RIGHT), GridColumn("g", "Note", 120, Region.RIGHT, "center")]


@pytest.fixture
def make_grid(_shared_tk_root):
    windows = []

    def factory(dates: int = 40, **callbacks):
        window = ui.Toplevel(_shared_tk_root)
        window.geometry("1200x500+0+0")
        grid = DataGrid(window, **callbacks)
        grid.frame.pack(fill="both", expand=True)
        cols = _columns(dates)
        grid.set_columns(cols)
        grid.set_rows([GridRow(f"r{i}", {c.key: f"{c.key}:{i}" for c in cols}) for i in range(ROWS)])
        grid.set_cursor("r0", "d0")
        window.update()
        window.update()
        windows.append(window)
        return grid, window

    yield factory
    for window in windows:
        window.destroy()
    _shared_tk_root.update()


def _visible_texts(grid) -> set[str]:
    texts = set()
    for view in grid.regions.values():
        for item in view._cells.items:
            if view.body.itemcget(item, "state") != "hidden":
                texts.add(view.body.itemcget(item, "text"))
    return texts


def test_only_visible_cells_exist(make_grid):
    grid, _ = make_grid(80)
    texts = _visible_texts(grid)
    assert "last:0" in texts and "d0:0" in texts and "sum:0" in texts
    assert "d79:0" not in texts and f"last:{ROWS - 1}" not in texts
    assert sum(len(v._cells.items) for v in grid.regions.values()) < 600


@pytest.mark.parametrize("dates", [10, 80])
def test_cursor_move_has_a_small_constant_call_budget(make_grid, dates):
    grid, window = make_grid(dates)

    def step():
        for index in range(1, 6):
            grid.set_cursor(f"r{index}", f"d{index % 3}")
            window.update()

    assert count_tcl_calls(step) // 5 <= 10


def test_clicks_map_to_row_and_column(make_grid):
    clicks, headers = [], []
    grid, window = make_grid(on_cell_click=lambda *a: clicks.append(a), on_header_click=headers.append)
    left = grid.regions[Region.LEFT]
    row_h = grid._row_h
    grid._on_body_click(Region.LEFT, SimpleNamespace(x=10, y=row_h * 2 + 1), 0)
    grid._on_header_click(left, SimpleNamespace(x=160))
    assert clicks == [("r2", "last", Region.LEFT)]
    assert headers == ["first"]


def _wheel(steps, *, shift=False):
    return WheelEvent(steps=float(steps), whole_steps=steps, axis=Axis.VERTICAL, modifiers=KeyModifiers(shift=shift),
                      x=0, y=0, x_root=0, y_root=0, widget=None)


def test_shift_wheel_scrolls_right_towards_the_content_end(make_grid):
    grid, window = make_grid()
    body = grid.regions[Region.SCROLL]
    window.update()
    grid._on_wheel(body, _wheel(1, shift=True))
    assert body.x_offset > 0 and grid._top_row == 0
    grid._on_wheel(body, _wheel(-1, shift=True))
    assert body.x_offset == 0


def test_wheel_and_see_scroll_rows(make_grid):
    grid, window = make_grid()
    body = grid.regions[Region.SCROLL]
    grid._on_wheel(body, _wheel(2))  # positive = towards the content end
    assert grid._top_row == 6
    grid._on_wheel(body, _wheel(-1))
    assert grid._top_row == 3
    grid._on_wheel(body, _wheel(-5))
    assert grid._top_row == 0
    grid.see("r0")
    assert grid._top_row == 0
    grid.see(f"r{ROWS - 1}", "d39")
    window.update()
    assert grid._top_row > 0 and body.x_offset > 0
    assert f"d39:{ROWS - 1}" in _visible_texts(grid)


def _last_row_fully_visible_in_every_region(grid) -> bool:
    bottom = (len(grid._rows) - grid._top_row) * grid._row_h
    return all(bottom <= view.viewport[1] for view in grid.regions.values())


@pytest.mark.parametrize("how", ["wheel", "see", "keyboard_end"])
def test_last_row_is_not_hidden_by_the_horizontal_scrollbar(make_grid, how):
    grid, window = make_grid(40)  # dates overflow: only the SCROLL region shows a scrollbar
    assert grid.regions[Region.SCROLL]._hbar_shown and not grid.regions[Region.LEFT]._hbar_shown
    last = f"r{ROWS - 1}"
    if how == "wheel":
        grid._on_wheel(grid.regions[Region.SCROLL], _wheel(ROWS))
    elif how == "see":
        grid.see(last)
    else:
        grid.set_cursor(last, "d0")
        grid.see(last, "d0")
    window.update()
    assert _last_row_fully_visible_in_every_region(grid)


def test_scrollbar_appearing_at_the_bottom_keeps_the_last_row_visible(make_grid):
    grid, window = make_grid(3)  # dates fit: no horizontal scrollbar yet
    assert not grid.regions[Region.SCROLL]._hbar_shown
    grid.see(f"r{ROWS - 1}")
    window.update()
    grid.set_width_scale(2.0)  # now the dates overflow and the scrollbar appears
    window.update()
    window.update()
    assert grid.regions[Region.SCROLL]._hbar_shown
    assert _last_row_fully_visible_in_every_region(grid)


def test_cell_bbox_and_width_scale(make_grid):
    grid, window = make_grid()
    widget, x, y, w, h = grid.cell_bbox("r3", "first")
    assert widget is grid.regions[Region.LEFT].body
    assert (x, w) == (150, 120) and y == 3 * grid._row_h and h == grid._row_h
    grid.set_width_scale(1.5)
    window.update()
    _widget, x, _y, w, _h = grid.cell_bbox("r3", "first")
    left = grid.regions[Region.LEFT]
    # Zoomed names are wider than their pane: cell_bbox scrolled the region so the cell is visible.
    assert w == 180 and x + left.x_offset == 225
    assert 0 <= x and x + w <= left.viewport[0]


def test_horizontal_scrollbar_only_when_needed(make_grid):
    grid, window = make_grid(40)
    assert grid.regions[Region.SCROLL]._hbar_shown
    assert not grid.regions[Region.LEFT]._hbar_shown


def test_sort_indicator_and_key_widgets(make_grid):
    grid, window = make_grid()
    grid.set_sort_indicator("last", ascending=False)
    window.update()
    left = grid.regions[Region.LEFT]
    titles = {left.header.itemcget(i, "text") for i in left._head_text.items}
    assert "▼ Nachname" in titles
    assert grid.key_widgets == tuple(v.body for v in grid.regions.values())
    assert grid.region_of_column("g") is Region.RIGHT and grid.region_of_widget(left.body) is Region.LEFT


def test_see_before_first_resize_is_applied_once_the_size_is_known(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    window.geometry("1200x500+0+0")
    try:
        grid = DataGrid(window)
        grid.frame.pack(fill="both", expand=True)
        cols = _columns(40)
        grid.set_columns(cols)
        grid.set_rows([GridRow(f"r{i}", {c.key: "x" for c in cols}) for i in range(ROWS)])
        grid.set_cursor("r0", "d0")
        grid.see("r0", "d0")  # still 1x1: must not scroll against a 1-pixel viewport
        window.update()
        window.update()
        assert grid.regions[Region.SCROLL].x_offset == 0
        grid.see("r0", "d39")
        window.update()
        assert grid.regions[Region.SCROLL].x_offset > 0
    finally:
        window.destroy()


def test_muted_rows_use_fg_muted_and_others_fg_primary(make_grid):
    from bw_gui.theming._theme_manager import get_theme

    grid, window = make_grid(dates=2)
    cols = _columns(2)
    grid.set_rows([GridRow("a", {c.key: "aktiv" for c in cols}), GridRow("m", {c.key: "grau" for c in cols}, muted=True)])
    window.update()
    theme = get_theme()

    fills = {}
    for view in grid.regions.values():
        for item in view._cells.items:
            if view.body.itemcget(item, "state") != "hidden":
                fills.setdefault(view.body.itemcget(item, "text"), set()).add(view.body.itemcget(item, "fill"))
    assert fills["aktiv"] == {theme["fg_primary"]}
    assert fills["grau"] == {theme["fg_muted"]}


def _pane_regions(grid) -> list[Region]:
    """Regions in the splitter, left to right, as Tk reports them."""
    by_frame = {str(view.frame): region for region, view in grid.regions.items()}
    return [by_frame[str(pane)] for pane in grid._paned.panes()]


def test_side_region_without_columns_leaves_the_splitter_and_comes_back(make_grid):
    grid, window = make_grid(dates=5)
    cols = _columns(5)
    grid.set_columns([c for c in cols if c.region is not Region.RIGHT])
    window.update()
    assert grid.shown_regions == (Region.LEFT, Region.SCROLL)
    assert _pane_regions(grid) == [Region.LEFT, Region.SCROLL]
    grid.set_columns([c for c in cols if c.region is not Region.LEFT])
    window.update()
    assert _pane_regions(grid) == [Region.SCROLL, Region.RIGHT]
    grid.set_columns(cols)
    window.update()
    assert _pane_regions(grid) == [Region.LEFT, Region.SCROLL, Region.RIGHT]


def test_scroll_region_stays_even_without_columns(make_grid):
    grid, window = make_grid(dates=5)
    grid.set_columns([c for c in _columns(5) if c.region is Region.LEFT])
    window.update()
    assert _pane_regions(grid) == [Region.LEFT, Region.SCROLL]


def test_split_is_redone_for_the_shown_regions(make_grid):
    grid, window = make_grid(dates=5)
    grid.set_columns([c for c in _columns(5) if c.region is not Region.LEFT])
    window.update()
    window.update()
    # Without LEFT, sash 0 separates SCROLL | RIGHT: RIGHT gets its natural width (180 + 120 + 4).
    sash_x = grid._paned.sash_coord(0)[0]
    assert abs(int(grid._paned.winfo_width()) - sash_x - 304) <= 8


def test_hidden_region_does_not_limit_the_visible_rows(make_grid):
    grid, window = make_grid(dates=5)
    grid.set_columns([c for c in _columns(5) if c.region is not Region.RIGHT])
    window.update()
    grid.regions[Region.RIGHT].viewport = (100, 10)  # stale size of a hidden region
    assert grid._body_height() == min(grid.regions[r].viewport[1] for r in (Region.LEFT, Region.SCROLL))
