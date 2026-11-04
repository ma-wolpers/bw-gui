"""CardBoard: rows × lanes of ordered cards with drag & drop and an insertion line.

See ``docs/CARD_BOARD_CONTRACT.md``.
"""

from ._board import CardBoard
from ._layout import BoardLayout, Hit, HitKind, TextWrapper, compute_layout, hit_test, insertion_line, slot_at
from ._model import (
    BoardCard,
    BoardCell,
    BoardLane,
    BoardRow,
    BoardSlot,
    CardTone,
    Cursor,
    Direction,
    LaneKind,
    RowTint,
)
from ._navigation import lane_entries, neighbor

__all__ = [
    "BoardCard",
    "BoardCell",
    "BoardLane",
    "BoardLayout",
    "BoardRow",
    "BoardSlot",
    "CardBoard",
    "CardTone",
    "Cursor",
    "Direction",
    "Hit",
    "HitKind",
    "LaneKind",
    "RowTint",
    "TextWrapper",
    "compute_layout",
    "hit_test",
    "insertion_line",
    "lane_entries",
    "neighbor",
    "slot_at",
]
