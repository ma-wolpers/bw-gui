"""CardBoard without Tk: ``CARDS_TEXT`` lanes (cards above a text) and the draft slot of a new card."""

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
    lane_entries,
    lane_holds_cards,
    lane_holds_text,
    neighbor,
    slot_at,
)
from bw_gui.widgets.card_board._layout import cursor_box

LINE = 16
LANES = (BoardLane("left", "Inhalt"), BoardLane("ideas", "Ideen", LaneKind.CARDS_TEXT, placeholder="Ideen …"))


def _measure(text: str) -> int:
    return 7 * len(text)


def _layout(rows, draft=None):
    return compute_layout(rows, LANES, 900, line_height=LINE, wrapper=TextWrapper(_measure), badge_width=_measure,
                          draft=draft)  # fmt: skip


def _rows():
    return (
        BoardRow("r2", "Sprosse 2", {"ideas": (BoardCard("m1", "AB 1"), BoardCard("m2", "Buch"))}, {"ideas": "Idee"}),
        BoardRow("r1", "Sprosse 1", {"left": (BoardCard("c", "C"),)}, {"ideas": ""}),
    )


def _middle(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def test_lane_kind_rules():
    assert lane_holds_cards(LaneKind.CARDS) and not lane_holds_text(LaneKind.CARDS)
    assert lane_holds_text(LaneKind.TEXT) and not lane_holds_cards(LaneKind.TEXT)
    assert lane_holds_cards(LaneKind.CARDS_TEXT) and lane_holds_text(LaneKind.CARDS_TEXT)


def test_cards_stack_above_a_small_add_box_above_the_text():
    layout = _layout(_rows())
    cell = layout.cells[BoardCell("r2", "ideas")]
    assert layout.cards["m1"].box[3] < layout.cards["m2"].box[1]
    assert layout.cards["m2"].box[3] < cell.add_box[1]
    assert cell.add_box[2] - cell.add_box[0] < 40  # small "+" even without a neighbour lane full of cards
    assert cell.add_box[3] <= cell.text_box[1]
    assert cell.text_lines == ("Idee",) and not cell.is_placeholder


def test_empty_cards_text_cell_has_small_add_and_placeholder_text():
    cell = _layout(_rows()).cells[BoardCell("r1", "ideas")]
    assert cell.card_keys == ()
    assert cell.add_box[2] - cell.add_box[0] < 40
    assert cell.is_placeholder and cell.text_lines == ("Ideen …",)


def test_text_only_lane_text_box_is_the_whole_cell():
    lanes = (BoardLane("ideas", "Ideen", LaneKind.TEXT),)
    layout = compute_layout((BoardRow("r", "R", texts={"ideas": "x"}),), lanes, 400, line_height=LINE,
                            wrapper=TextWrapper(_measure), badge_width=_measure)  # fmt: skip
    cell = layout.cells[BoardCell("r", "ideas")]
    assert cell.text_box == cell.box and cell.add_box is None


def test_hit_test_distinguishes_card_add_and_text():
    layout = _layout(_rows())
    cell = layout.cells[BoardCell("r2", "ideas")]
    assert hit_test(layout, *_middle(layout.cards["m1"].box)).kind is HitKind.CARD
    assert hit_test(layout, *_middle(cell.add_box)).kind is HitKind.ADD
    assert hit_test(layout, *_middle(cell.text_box)).kind is HitKind.TEXT


def test_slot_over_the_text_is_the_end_of_the_cards():
    layout = _layout(_rows())
    x, y = _middle(layout.cells[BoardCell("r2", "ideas")].text_box)
    assert slot_at(layout, x, y) == BoardSlot("r2", "ideas", 2)
    x, y = _middle(layout.cards["m1"].box)
    assert slot_at(layout, x, y - 4) == BoardSlot("r2", "ideas", 0)


def test_navigation_runs_cards_then_text_per_row():
    layout = _layout(_rows())
    assert lane_entries(layout, "ideas") == ["m1", "m2", BoardCell("r2", "ideas"), BoardCell("r1", "ideas")]
    assert neighbor(layout, "m2", Direction.DOWN) == BoardCell("r2", "ideas")
    assert neighbor(layout, BoardCell("r2", "ideas"), Direction.UP) == "m2"
    assert neighbor(layout, BoardCell("r2", "ideas"), Direction.DOWN) == BoardCell("r1", "ideas")


def test_cell_cursor_frames_only_the_text_area():
    layout = _layout(_rows())
    cell = layout.cells[BoardCell("r2", "ideas")]
    assert cursor_box(layout, BoardCell("r2", "ideas")) == cell.text_box


def test_draft_reserves_space_and_moves_following_cards_down():
    plain = _layout(_rows())
    drafted = _layout(_rows(), draft=BoardSlot("r2", "ideas", 1))
    box = drafted.draft_box
    assert box is not None
    assert drafted.cards["m1"].box == plain.cards["m1"].box
    assert drafted.cards["m1"].box[3] < box[1] and box[3] < drafted.cards["m2"].box[1]
    assert drafted.cards["m2"].box[1] > plain.cards["m2"].box[1]
    assert plain.draft_box is None


def test_draft_index_is_clamped_to_the_end_and_works_in_an_empty_cell():
    layout = _layout(_rows(), draft=BoardSlot("r1", "left", 99))
    assert layout.draft_box[1] > layout.cards["c"].box[3]
    empty = _layout(_rows(), draft=BoardSlot("r1", "ideas", 0))
    cell = empty.cells[BoardCell("r1", "ideas")]
    assert empty.draft_box[3] <= cell.add_box[1] <= cell.text_box[1]
