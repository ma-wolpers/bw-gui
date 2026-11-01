"""Multi-cursor model: normalisation, edit planning and cursor history (no Tk)."""

from __future__ import annotations

from bw_gui.contracts.multicursor import (
    Edit,
    Region,
    apply_to_string,
    moved,
    normalize,
    plan_delete,
    plan_edits,
    plan_lines_or_text,
    plan_text,
    primary,
    region_at,
    regions_after,
)
from bw_gui.contracts.multicursor_history import CursorHistory, TxRecord, text_digest


def _caret(pos, order=0):
    return Region(pos, pos, order=order)


def _heads(regions):
    return [(region.anchor, region.head) for region in regions]


def test_identical_carets_collapse_and_keep_the_youngest():
    assert normalize([_caret(3, 1), _caret(3, 2)]) == (_caret(3, 2),)


def test_overlapping_and_touching_selections_merge_keeping_the_earlier_direction():
    assert _heads(normalize([Region(5, 2, order=1), Region(4, 8, order=2)])) == [(8, 2)]
    assert _heads(normalize([Region(1, 3), Region(3, 6)])) == [(1, 6)]
    assert _heads(normalize([Region(1, 3), Region(4, 6)])) == [(1, 3), (4, 6)]


def test_caret_inside_a_selection_is_swallowed_but_on_the_edge_stays():
    assert _heads(normalize([Region(2, 6), _caret(4)])) == [(2, 6)]
    assert _heads(normalize([Region(2, 6), _caret(2), _caret(6)])) == [(2, 2), (2, 6), (6, 6)]


def test_region_at_hits_carets_and_selections():
    regions = (Region(2, 6), _caret(9))
    assert region_at(regions, 4) == regions[0] and region_at(regions, 9) == regions[1]
    assert region_at(regions, 8) is None


def test_primary_is_the_youngest():
    assert primary((_caret(1, 5), _caret(2, 3))).head == 1


def _typed(text, regions, insert):
    planned = plan_edits(plan_text(normalize(regions), insert))
    return apply_to_string(text, planned), regions_after(planned)


def test_typing_at_three_carets_shifts_the_later_ones():
    result, after = _typed("abc", [_caret(0, 1), _caret(1, 2), _caret(3, 3)], "X")
    assert result == "XaXbcX"
    assert [region.head for region in after] == [1, 3, 6]


def test_edge_carets_write_outside_the_replaced_selection():
    regions = [Region(2, 4, order=2), _caret(2, 1), _caret(4, 3)]
    result, after = _typed("abCDef", regions, "x")
    assert result == "abxxxef"
    assert [region.head for region in after] == [3, 4, 5]


def test_selection_is_replaced_and_collapses_to_a_caret():
    result, after = _typed("hello", [Region(1, 3), _caret(5)], "EY")
    assert result == "hEYloEY" and [region.head for region in after] == [3, 7]


def test_backspace_at_a_selection_edge_does_not_delete_twice():
    regions = normalize([Region(3, 5, order=1), _caret(5, 2)])
    planned = plan_edits(plan_delete(regions, forward=False, limit=8))
    assert apply_to_string("abcdefgh", planned) == "abcfgh"
    assert [region.head for region in regions_after(planned)] == [3]


def test_backspace_and_delete_stop_at_the_document_edges():
    backward = plan_edits(plan_delete((_caret(0),), forward=False, limit=3))
    forward = plan_edits(plan_delete((_caret(3),), forward=True, limit=3))
    assert apply_to_string("abc", backward) == "abc" == apply_to_string("abc", forward)


def test_neighbouring_carets_merge_after_backspace():
    planned = plan_edits(plan_delete(normalize([_caret(2, 1), _caret(3, 2)]), forward=False, limit=4))
    assert apply_to_string("abcd", planned) == "ad"
    assert [region.head for region in regions_after(planned)] == [1]


def test_paste_distributes_lines_only_when_the_count_matches():
    regions = (_caret(0, 1), _caret(1, 2))
    assert [edit.text for edit in plan_lines_or_text(regions, "a\nb")] == ["a", "b"]
    assert [edit.text for edit in plan_lines_or_text(regions, "a\nb\nc")] == ["a\nb\nc"] * 2
    assert [edit.text for edit in plan_lines_or_text(regions, "one")] == ["one", "one"]


def test_moved_collapses_from_the_head_or_extends_from_the_anchor():
    regions = (Region(2, 5), _caret(8))
    assert _heads(moved(regions, lambda r: r.head + 1, extend=False)) == [(6, 6), (9, 9)]
    assert _heads(moved(regions, lambda r: r.head + 1, extend=True)) == [(2, 6), (8, 9)]


def test_edit_select_is_relative_to_the_new_text():
    planned = plan_edits([Edit(1, 3, "**bc**", 1, select=(2, 4)), Edit(5, 5, "", 2)])
    assert apply_to_string("abcde", planned) == "a**bc**de"
    assert _heads(regions_after(planned))[0] == (3, 5)


def test_history_matches_by_content():
    history = CursorHistory()
    a, b = text_digest("a"), text_digest("b")
    before, after = (_caret(1),), (_caret(2),)
    history.record(TxRecord(a, b, before, after))
    assert history.match_undo(b, a) == before and history.match_redo(a, b) == after
    assert history.match_undo(a, b) is None and history.match_redo(b, a) is None
    history.reset()
    assert history.match_undo(b, a) is None


def test_history_prefers_the_youngest_and_is_bounded():
    history = CursorHistory(limit=2)
    a, b = text_digest("a"), text_digest("b")
    history.record(TxRecord(a, b, (_caret(1),), ()))
    history.record(TxRecord(a, b, (_caret(2),), ()))
    assert history.match_undo(b, a) == (_caret(2),)
    history.record(TxRecord(b, a, (), ()))
    history.record(TxRecord(b, a, (), ()))
    assert len(history) == 2 and history.match_undo(b, a) is None
