"""CardBoard on a real Tk root: clicks, "+", drag with insertion line, text editing, budgets."""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.testing.keys import press_key
from bw_gui.testing.tcl_calls import count_tcl_calls
from bw_gui.widgets.card_board import (
    BoardCard,
    BoardCell,
    BoardLane,
    BoardRow,
    BoardSlot,
    CardBoard,
    CardTone,
    Direction,
    LaneKind,
    RowTint,
)

LANES = (BoardLane("left", "Inhalt"), BoardLane("right", "Prozess"), BoardLane("ideas", "Ideen", LaneKind.TEXT))


def _rows():
    return (
        BoardRow("r2", "Sprosse 2", {"left": (BoardCard("a", "A"), BoardCard("b", "B"))}, {"ideas": "Idee"},
                 tint=RowTint("success_soft", 0.72)),  # fmt: skip
        BoardRow("r1", "Sprosse 1", {"left": (BoardCard("c", "C"),), "right": (BoardCard("k", "K", badge="M-1"),)}),
    )


@pytest.fixture
def make_board(_shared_tk_root):
    windows = []

    def factory(**callbacks):
        window = ui.Toplevel(_shared_tk_root)
        window.geometry("900x500+0+0")
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


def _center(board, key):
    x0, y0, x1, y1 = board._layout.cards[key].box
    return int((x0 + x1) / 2), int((y0 + y1) / 2)


def _event(board, sequence, x, y, **extra):
    canvas = board.key_widget
    canvas.event_generate(sequence, x=x, y=y, rootx=canvas.winfo_rootx() + x, rooty=canvas.winfo_rooty() + y, **extra)


def test_click_on_card_moves_cursor_and_reports_it(make_board):
    seen = []
    board = make_board(on_cursor_change=seen.append)
    _event(board, "<ButtonPress-1>", *_center(board, "b"))
    _event(board, "<ButtonRelease-1>", *_center(board, "b"))
    assert board.cursor == "b" and seen == ["b"]


def test_click_on_plus_reports_the_cell(make_board):
    added = []
    board = make_board(on_add=added.append)
    x0, y0, x1, y1 = board._layout.cells[BoardCell("r2", "right")].add_box
    _event(board, "<ButtonPress-1>", int((x0 + x1) / 2), int((y0 + y1) / 2))
    assert added == [BoardCell("r2", "right")]


def test_drag_shows_line_only_where_allowed_and_drops(make_board):
    drops = []
    board = make_board(can_drop=lambda key, slot: slot.lane_key == "left", on_drop=lambda k, s: drops.append((k, s)))
    ax, ay = _center(board, "a")
    _event(board, "<ButtonPress-1>", ax, ay)
    kx, ky = _center(board, "k")
    _event(board, "<B1-Motion>", kx, ky, state=0x100)
    board.flush_now()
    assert board._drop is None  # right lane forbidden: no indicator
    cx, cy = _center(board, "c")
    _event(board, "<B1-Motion>", cx, cy + 20, state=0x100)
    board.flush_now()
    assert board._drop == BoardSlot("r1", "left", 1)
    line_items = board._renderer._pools["drop_line"].items
    assert any(board.key_widget.itemcget(item, "state") == "normal" for item in line_items)
    _event(board, "<ButtonRelease-1>", cx, cy + 20)
    assert drops == [("a", BoardSlot("r1", "left", 1))]
    board.flush_now()
    assert all(board.key_widget.itemcget(item, "state") == "hidden" for item in line_items)


def test_text_cell_click_opens_editor_and_ctrl_enter_commits_once(make_board):
    commits = []
    board = make_board(on_text_commit=lambda cell, text: commits.append((cell, text)))
    board.edit_text(BoardCell("r2", "ideas"))
    field = board._editor._field
    field.set("Neue Idee")
    assert press_key(field.text, "Return", state=0x4) is True
    assert commits == [(BoardCell("r2", "ideas"), "Neue Idee")]
    assert board.editing_cell is None


def test_escape_cancels_and_unchanged_text_does_not_commit(make_board):
    commits = []
    board = make_board(on_text_commit=lambda cell, text: commits.append(text))
    board.edit_text(BoardCell("r2", "ideas"))
    board._editor._field.set("verworfen")
    press_key(board._editor._field.text, "Escape")
    board.edit_text(BoardCell("r2", "ideas"))
    board._editor.commit()
    assert commits == []


def test_move_cursor_uses_navigation_and_costs_few_tcl_calls(make_board):
    board = make_board()
    board.set_cursor("a")
    board.flush_now()
    assert board.move_cursor(Direction.DOWN) == "b"

    def step():
        board.move_cursor(Direction.DOWN)
        board.flush_now()

    calls = count_tcl_calls(step)
    assert board.cursor == "c"
    assert calls < 25


def test_theme_switch_rerenders_without_errors(make_board):
    from bw_gui.theming import configure_ttk_theme

    board = make_board()
    configure_ttk_theme(board.frame, "dark")
    board.flush_now()
    configure_ttk_theme(board.frame, "light")
    board.flush_now()
    assert board._layout is not None


def _card_items(board):
    canvas = board.key_widget
    return [item for item in board._renderer._pools["card"].items if canvas.itemcget(item, "state") != "hidden"]


def test_card_tones_use_theme_tokens_and_follow_theme_switch(make_board):
    from bw_gui.theming import configure_ttk_theme
    from bw_gui.theming._theme_manager import get_theme

    board = make_board()
    board.set_rows((BoardRow("r", "R", {"left": (BoardCard("e", "E", tone=CardTone.EMPHASIS),
                                                 BoardCard("w", "W", tone=CardTone.WARNING))}),))  # fmt: skip
    canvas = board.key_widget
    for theme_name in ("light", "dark"):
        configure_ttk_theme(board.frame, theme_name)
        board.flush_now()
        theme = get_theme()
        fills = {canvas.itemcget(item, "fill") for item in _card_items(board)}
        outlines = {canvas.itemcget(item, "outline") for item in _card_items(board)}
        assert theme["accent_soft"] in fills
        assert theme["warning"] in outlines
    configure_ttk_theme(board.frame, "light")


def test_locked_row_text_cell_selects_but_does_not_edit(make_board):
    seen = []
    board = make_board(on_cursor_change=seen.append)
    board.set_rows((BoardRow("lzk", "LZK", texts={"ideas": "fest"}, locked=True),))
    board.flush_now()
    x0, y0, x1, y1 = board._layout.cells[BoardCell("lzk", "ideas")].box
    _event(board, "<ButtonPress-1>", int((x0 + x1) / 2), int((y0 + y1) / 2))
    assert seen == [BoardCell("lzk", "ideas")]
    assert board.editing_cell is None
    board.edit_text(BoardCell("lzk", "ideas"))
    assert board.editing_cell is None
