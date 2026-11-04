"""CardBoard without Tk: wrapping, layout, hit testing, slots, insertion line, navigation."""

from __future__ import annotations

from bw_gui.widgets.card_board import (
    BoardCard,
    BoardCell,
    BoardLane,
    BoardRow,
    BoardSlot,
    Direction,
    HitKind,
    LaneKind,
    TextWrapper,
    compute_layout,
    hit_test,
    insertion_line,
    lane_entries,
    neighbor,
    slot_at,
)

LINE = 16


def _measure(text: str) -> int:
    return 7 * len(text)


LANES = (BoardLane("left", "Inhalt"), BoardLane("right", "Prozess"), BoardLane("ideas", "Ideen", LaneKind.TEXT))


def _layout(rows, width=900):
    return compute_layout(rows, LANES, width, line_height=LINE, wrapper=TextWrapper(_measure), badge_width=_measure)


def _rows():
    return (
        BoardRow("r2", "Sprosse 2", {"left": (BoardCard("a", "A"), BoardCard("b", "B"))}, {"ideas": "Idee"}),
        BoardRow("r1", "Sprosse 1", {"left": (BoardCard("c", "C"),), "right": (BoardCard("k", "K", badge="Mat-1"),)}),
    )


def test_wrapper_wraps_words_and_splits_overlong_words():
    wrapper = TextWrapper(_measure)
    assert wrapper.wrap("aa bb cc", 35) == ("aa bb", "cc")
    assert wrapper.wrap("abcdefghij", 35) == ("abcde", "fghij")
    assert wrapper.wrap("x\ny", 100) == ("x", "y")


def test_rows_stack_and_cells_span_the_row():
    layout = _layout(_rows())
    top, bottom = layout.rows
    assert top.y0 == 0 and top.y1 == bottom.y0
    for cell in layout.cells.values():
        row = next(r for r in layout.rows if r.key == cell.cell.row_key)
        assert (cell.box[1], cell.box[3]) == (row.y0, row.y1)


def test_cards_are_ordered_top_down_and_badge_sits_inside_the_card():
    layout = _layout(_rows())
    assert layout.cards["a"].box[3] < layout.cards["b"].box[1]
    card = layout.cards["k"]
    assert card.badge_box is not None and card.badge_box[2] <= card.box[2]


def test_empty_cell_gets_a_full_width_add_box_filled_cell_a_small_one():
    layout = _layout(_rows())
    empty = layout.cells[BoardCell("r2", "right")]
    filled = layout.cells[BoardCell("r2", "left")]
    assert empty.add_box[2] - empty.add_box[0] > filled.add_box[2] - filled.add_box[0]
    assert filled.add_box[1] > layout.cards["b"].box[3]


def test_text_lane_shows_placeholder_flag_when_empty():
    lanes = (BoardLane("ideas", "Ideen", LaneKind.TEXT, placeholder="Ideen…"),)
    layout = compute_layout([BoardRow("r", "R")], lanes, 400, line_height=LINE, wrapper=TextWrapper(_measure),
                            badge_width=_measure)  # fmt: skip
    cell = layout.cells[BoardCell("r", "ideas")]
    assert cell.is_placeholder and cell.text_lines == ("Ideen…",)


def test_hit_test_distinguishes_card_add_cell_and_label():
    layout = _layout(_rows())
    a = layout.cards["a"].box
    assert hit_test(layout, (a[0] + a[2]) / 2, (a[1] + a[3]) / 2).card_key == "a"
    add = layout.cells[BoardCell("r2", "right")].add_box
    assert hit_test(layout, (add[0] + add[2]) / 2, (add[1] + add[3]) / 2).kind is HitKind.ADD
    assert hit_test(layout, 5, 5).kind is HitKind.NONE


def test_slot_index_follows_card_midpoints_and_snaps_to_outer_rows():
    layout = _layout(_rows())
    a, b = layout.cards["a"].box, layout.cards["b"].box
    x = (a[0] + a[2]) / 2
    assert slot_at(layout, x, a[1] + 1) == BoardSlot("r2", "left", 0)
    assert slot_at(layout, x, (a[3] + b[1]) / 2) == BoardSlot("r2", "left", 1)
    assert slot_at(layout, x, b[3] + 1) == BoardSlot("r2", "left", 2)
    assert slot_at(layout, x, -50) == BoardSlot("r2", "left", 0)
    assert slot_at(layout, x, layout.height + 50).row_key == "r1"


def test_text_lane_has_no_slots():
    layout = _layout(_rows())
    ideas = layout.cells[BoardCell("r2", "ideas")].box
    assert slot_at(layout, (ideas[0] + ideas[2]) / 2, ideas[1] + 5) is None


def test_insertion_line_lies_in_the_gap_between_cards():
    layout = _layout(_rows())
    a, b = layout.cards["a"].box, layout.cards["b"].box
    _x0, _x1, y = insertion_line(layout, BoardSlot("r2", "left", 1))
    assert a[3] < y < b[1]
    assert insertion_line(layout, BoardSlot("r2", "left", 2))[2] > b[3]


def test_navigation_up_down_runs_through_cards_and_empty_cells_across_rows():
    layout = _layout(_rows())
    assert lane_entries(layout, "right") == [BoardCell("r2", "right"), "k"]
    assert neighbor(layout, "b", Direction.DOWN) == "c"
    assert neighbor(layout, "c", Direction.UP) == "b"
    assert neighbor(layout, "a", Direction.UP) is None


def test_navigation_left_right_lands_on_nearest_card_or_cell():
    layout = _layout(_rows())
    assert neighbor(layout, "c", Direction.RIGHT) == "k"
    assert neighbor(layout, "a", Direction.RIGHT) == BoardCell("r2", "right")
    assert neighbor(layout, BoardCell("r2", "right"), Direction.RIGHT) == BoardCell("r2", "ideas")
    assert neighbor(layout, "a", Direction.LEFT) is None


def test_cell_cursor_on_a_filled_cell_sits_before_its_first_card():
    layout = _layout(_rows())
    filled = BoardCell("r1", "left")
    assert neighbor(layout, filled, Direction.DOWN) == "c"
    assert neighbor(layout, filled, Direction.UP) == "b"
