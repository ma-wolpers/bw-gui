"""Arrow-key navigation over a laid-out CardBoard (no Tk).

Per lane the navigable *entries* run top to bottom: the cards of each row,
followed by the cell itself when it holds a text (``TEXT``, ``CARDS_TEXT``) or
holds no card (empty ``CARDS`` cell). Up/Down step through a lane's entries
across rows; Left/Right switch lanes in the same row, landing on the entry
closest in height.
"""

from __future__ import annotations

from ._layout import BoardLayout, CellBox, cursor_box
from ._model import BoardCell, Cursor, Direction, lane_holds_text


def _cell_entries(cell: CellBox) -> list[Cursor]:
    """Entries of one cell, top to bottom: its cards, then the cell when it holds a text or no card."""
    entries: list[Cursor] = list(cell.card_keys)
    if lane_holds_text(cell.kind) or not entries:
        entries.append(cell.cell)
    return entries


def lane_entries(layout: BoardLayout, lane_key: str) -> list[Cursor]:
    """All entries of one lane, top to bottom."""
    entries: list[Cursor] = []
    for row in layout.rows:
        cell = layout.cells.get(BoardCell(row.key, lane_key))
        if cell is not None:
            entries.extend(_cell_entries(cell))
    return entries


def cursor_cell(layout: BoardLayout, cursor: Cursor) -> BoardCell | None:
    """The cell a cursor sits in (a card's cell, or the cursor cell itself)."""
    if isinstance(cursor, str):
        card = layout.cards.get(cursor)
        return card.cell if card is not None else None
    return cursor if isinstance(cursor, BoardCell) and cursor in layout.cells else None


def neighbor(layout: BoardLayout, cursor: Cursor, direction: Direction) -> Cursor:
    """Entry reached from *cursor* by one arrow step, or ``None`` at the board edge.

    Args:
        layout: Current layout.
        cursor: Card key or cell; must be on the board.
        direction: Arrow direction.
    """
    cell = cursor_cell(layout, cursor)
    if cell is None:
        return None
    if direction in (Direction.UP, Direction.DOWN):
        entries = lane_entries(layout, cell.lane_key)
        if cursor in entries:
            index = entries.index(cursor)
            target = index + (-1 if direction is Direction.UP else 1)
        else:
            # A cell cursor on a cell that holds cards sits "before its first card".
            first = entries.index(layout.cells[cell].card_keys[0])
            target = first - 1 if direction is Direction.UP else first
        return entries[target] if 0 <= target < len(entries) else None
    lane_keys = [lane.key for lane in layout.lanes]
    target_lane = lane_keys.index(cell.lane_key) + (-1 if direction is Direction.LEFT else 1)
    if not 0 <= target_lane < len(lane_keys):
        return None
    target_cell = layout.cells[BoardCell(cell.row_key, lane_keys[target_lane])]
    candidates = _cell_entries(target_cell)
    if len(candidates) == 1:
        return candidates[0]
    origin = cursor_box(layout, cursor)
    middle = (origin[1] + origin[3]) / 2 if origin is not None else 0.0

    def distance(entry: Cursor) -> float:
        box = cursor_box(layout, entry)
        return abs((box[1] + box[3]) / 2 - middle) if box is not None else float("inf")

    return min(candidates, key=distance)
