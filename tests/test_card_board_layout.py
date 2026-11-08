"""CardBoard without Tk: wrapping, layout, hit testing, slots, insertion line, navigation."""

from __future__ import annotations

from bw_gui.widgets.card_board import (
    BoardCard,
    BoardCell,
    BoardLane,
    BoardRow,
    BoardSlot,
    CardTone,
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
from bw_gui.widgets.card_board._layout import PAD

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


def test_card_tone_reaches_the_layout():
    rows = (BoardRow("r", "R", {"left": (BoardCard("a", "A", tone=CardTone.EMPHASIS), BoardCard("b", "B"))}),)
    layout = _layout(rows)
    assert layout.cards["a"].tone is CardTone.EMPHASIS
    assert layout.cards["b"].tone is CardTone.NORMAL


def test_locked_row_has_no_plus_boxes_no_slots_and_no_placeholder():
    lanes = (BoardLane("left", "Inhalt"), BoardLane("ideas", "Ideen", LaneKind.TEXT, placeholder="Idee …"))
    rows = (
        BoardRow("open", "Sprosse 2"),
        BoardRow("lzk", "LZK", {"left": (BoardCard("x", "X"),)}, locked=True),
        BoardRow("empty", "Ausfall", locked=True),
    )
    layout = compute_layout(rows, lanes, 900, line_height=LINE, wrapper=TextWrapper(_measure), badge_width=_measure)

    for key in ("lzk", "empty"):
        cell = layout.cells[BoardCell(key, "left")]
        assert cell.locked and cell.add_box is None
        x0, y0, x1, y1 = cell.box
        assert slot_at(layout, (x0 + x1) / 2, (y0 + y1) / 2) is None
        assert hit_test(layout, x0 + PAD + 1, y1 - 2).kind is not HitKind.ADD
        ideas = layout.cells[BoardCell(key, "ideas")]
        assert ideas.locked and ideas.is_placeholder and ideas.text_lines == ("",)
    assert layout.cells[BoardCell("open", "ideas")].text_lines == ("Idee …",)
    open_cell = layout.cells[BoardCell("open", "left")]
    assert open_cell.add_box is not None
    assert slot_at(layout, (open_cell.box[0] + open_cell.box[2]) / 2, open_cell.box[1] + 2) is not None


def test_row_action_button_sits_below_the_label_and_is_hit_first():
    plain = _layout((BoardRow("r", "Sprosse 3\n??"),))
    with_action = _layout((BoardRow("r", "Sprosse 3\n??", action="→ Einheit"),))
    row = with_action.rows[0]
    assert plain.rows[0].action_box is None
    x0, y0, x1, y1 = row.action_box
    assert x0 == PAD and x1 - x0 == _measure("→ Einheit") + 16
    assert y0 >= row.y0 + PAD + 2 * LINE and y1 <= row.y1
    assert with_action.rows[0].y1 > plain.rows[0].y1  # Platz für den Knopf
    hit = hit_test(with_action, (x0 + x1) / 2, (y0 + y1) / 2)
    assert (hit.kind, hit.row_key) == (HitKind.ROW_ACTION, "r")
    assert hit_test(with_action, x1 + 2, (y0 + y1) / 2).kind is HitKind.NONE
