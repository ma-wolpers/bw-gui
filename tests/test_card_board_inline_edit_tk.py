"""CardBoard on a real Tk root: renaming a card in place, typing a new card into a draft slot, CARDS_TEXT clicks.

The test window sits off-screen (no visible flicker while the suite runs).
"""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.testing.keys import press_key
from bw_gui.widgets.card_board import BoardCard, BoardCell, BoardLane, BoardRow, BoardSlot, CardBoard, LaneKind

LANES = (BoardLane("left", "Inhalt"), BoardLane("ideas", "Ideen", LaneKind.CARDS_TEXT))


def _rows():
    cards = {"left": (BoardCard("a", "A"), BoardCard("b", "B")), "ideas": (BoardCard("m", "AB 1"),)}
    return (
        BoardRow("r2", "Sprosse 2", cards, {"ideas": "Idee"}),
        BoardRow("r1", "Sprosse 1", {"left": (BoardCard("c", "C"),)}),
        BoardRow("lzk", "LZK", locked=True),
    )


@pytest.fixture
def make_board(_shared_tk_root):
    windows = []

    def factory(**callbacks):
        window = ui.Toplevel(_shared_tk_root)
        window.geometry("900x500-3000+0")
        board = CardBoard(window, **callbacks)
        board.frame.pack(fill="both", expand=True)
        board.set_lanes(LANES)
        board.set_rows(_rows())
        window.update()
        board.flush_now()
        windows.append(window)
        return board

    yield factory
    for window in windows:
        window.destroy()


def _unique(text):
    return "gibt es schon" if text.strip().casefold() in {"a", "b", "c"} else None


def test_edit_card_opens_over_the_card_and_enter_reports_the_new_text(make_board):
    board = make_board()
    done = []
    assert board.edit_card("b", on_done=done.append, validate=_unique) is True
    assert board.editing == "b"
    field = board.editor.field
    assert field.get() == "B"
    field.set("B neu")
    assert press_key(field.text, "Return") is True
    assert done == ["B neu"]
    assert board.editing is None


def test_unchanged_rename_reports_nothing(make_board):
    board = make_board()
    done = []
    board.edit_card("a", on_done=done.append, validate=_unique)
    press_key(board.editor.field.text, "Return")
    assert done == [] and board.editing is None


def test_invalid_card_text_shows_inline_error_and_keeps_editor_open(make_board):
    board = make_board()
    done = []
    board.edit_card("b", on_done=done.append, validate=_unique)
    board.editor.field.set("a")
    press_key(board.editor.field.text, "Return")
    assert done == []
    assert board.editing == "b"
    assert board.editor.error_message == "gibt es schon"
    board.editor.field.set("D")
    press_key(board.editor.field.text, "Return")
    assert done == ["D"]


def test_focus_loss_discards_invalid_and_commits_valid_text(make_board):
    board = make_board()
    done = []
    board.edit_card("b", on_done=done.append, validate=_unique)
    board.editor.field.set("a")
    board.editor.commit(from_focus=True)
    assert done == [] and board.editing is None
    board.edit_card("b", on_done=done.append, validate=_unique)
    board.editor.field.set("E")
    board.editor.commit(from_focus=True)
    assert done == ["E"]


def test_draft_card_reserves_space_and_escape_drops_it(make_board):
    board = make_board()
    before = board._layout.cards["b"].box
    done = []
    assert board.draft_card(BoardSlot("r2", "left", 1), on_done=done.append, validate=_unique) is True
    assert board.editing == BoardSlot("r2", "left", 1)
    assert board._layout.draft_box is not None
    assert board._layout.cards["b"].box[1] > before[1]
    press_key(board.editor.field.text, "Escape")
    board.flush_now()
    assert done == [] and board.editing is None
    assert board._layout.draft_box is None
    assert board._layout.cards["b"].box == before


def test_draft_card_enter_reports_text_even_with_initial_value(make_board):
    board = make_board()
    done = []
    board.draft_card(BoardSlot("r1", "left", 1), on_done=done.append, initial="Kopie", validate=_unique)
    assert board.editor.field.get() == "Kopie"
    press_key(board.editor.field.text, "Return")
    assert done == ["Kopie"]


def test_draft_card_refuses_locked_cells(make_board):
    board = make_board()
    assert board.draft_card(BoardSlot("lzk", "left", 0), on_done=print) is False
    assert board.editing is None


def test_cards_text_click_on_text_edits_and_add_reports_the_cell(make_board):
    commits, adds = [], []
    board = make_board(on_text_commit=lambda cell, text: commits.append((cell, text)), on_add=adds.append)
    cell = board._layout.cells[BoardCell("r2", "ideas")]
    x0, y0, x1, y1 = cell.text_box
    widget = board.key_widget
    widget.event_generate("<ButtonPress-1>", x=int((x0 + x1) / 2), y=int((y0 + y1) / 2))
    widget.event_generate("<ButtonRelease-1>", x=int((x0 + x1) / 2), y=int((y0 + y1) / 2))
    assert board.editing_cell == BoardCell("r2", "ideas")
    board.editor.field.set("Idee 2")
    board.editor.commit()
    assert commits == [(BoardCell("r2", "ideas"), "Idee 2")]
    ax0, ay0, ax1, ay1 = cell.add_box
    widget.event_generate("<ButtonPress-1>", x=int((ax0 + ax1) / 2), y=int((ay0 + ay1) / 2))
    widget.event_generate("<ButtonRelease-1>", x=int((ax0 + ax1) / 2), y=int((ay0 + ay1) / 2))
    assert adds == [BoardCell("r2", "ideas")]


def test_open_editor_follows_new_rows_and_closes_when_its_card_vanishes(make_board):
    board = make_board()
    board.edit_card("b", on_done=print)
    board.set_rows(_rows()[1:])
    board.flush_now()
    assert board.editing is None
