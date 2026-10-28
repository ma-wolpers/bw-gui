"""DataGrid model: layout, visibility, clamping, text clipping (no Tk)."""

from __future__ import annotations

from bw_gui.widgets.data_grid._model import (
    GridColumn,
    Region,
    RegionLayout,
    TextClipper,
    clamp_offset,
    fully_visible_row_count,
    visible_rows,
)


def _layout(scale=1.0):
    return RegionLayout([GridColumn(f"c{i}", f"C{i}", 100, Region.SCROLL) for i in range(10)], scale)


def test_layout_offsets_hit_testing_and_visibility():
    layout = _layout()
    assert layout.total_width == 1000
    assert layout.span(3) == (300, 400)
    assert layout.index_at(299) == 2 and layout.index_at(300) == 3
    assert layout.index_at(-1) is None and layout.index_at(1000) is None
    assert list(layout.visible(250, 300)) == [2, 3, 4, 5]
    assert layout.index_of("c4") == 4 and layout.index_of("x") is None


def test_width_scale_applies_to_all_columns():
    assert _layout(1.5).total_width == 1500
    assert _layout(0.01).widths[0] == 8  # minimum width


def test_row_window_and_clamping():
    assert list(visible_rows(5, 30, 100, 20)) == [5, 6, 7, 8, 9, 10]
    assert list(visible_rows(28, 30, 100, 20)) == [28, 29]
    assert fully_visible_row_count(100, 20) == 5
    assert clamp_offset(50, 30, 5) == 25
    assert clamp_offset(-3, 30, 5) == 0
    assert clamp_offset(10, 3, 5) == 0


def test_text_clipper_measures_only_long_texts_and_caches():
    measured: list[str] = []

    def measure(text: str) -> int:
        measured.append(text)
        return len(text) * 10

    clipper = TextClipper(measure, widest_char=10)
    assert clipper.clip("kurz", 100) == "kurz" and measured == []
    assert clipper.clip("abcdefghijkl", 60) == "abcde…"
    calls = len(measured)
    assert clipper.clip("abcdefghijkl", 60) == "abcde…"
    assert len(measured) == calls  # cached
    assert clipper.clip("abc", 5) == ""
