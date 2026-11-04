"""CardBoard data model (no Tk): lanes, rows, cards, slots and the cursor.

A board is a table of *rows* (top to bottom, in display order) and *lanes*
(columns, left to right). A ``CARDS`` lane holds an ordered stack of cards per
row; a ``TEXT`` lane holds one free text per row. The consumer owns all data and
rules (which card may go where, what a row means) -- the board only shows the
model, reports gestures and computes positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Union


class LaneKind(str, Enum):
    """What a lane holds per row."""

    CARDS = "cards"
    TEXT = "text"


@dataclass(frozen=True)
class BoardLane:
    """One column of the board.

    Attributes:
        key: Stable identifier (used in slots, cells and callbacks).
        title: Header text.
        kind: ``CARDS`` (ordered cards per row) or ``TEXT`` (one free text per row).
        weight: Relative share of the width left after the row-label column.
        placeholder: Muted text shown in an empty ``TEXT`` cell.
    """

    key: str
    title: str
    kind: LaneKind = LaneKind.CARDS
    weight: float = 1.0
    placeholder: str = ""


@dataclass(frozen=True)
class RowTint:
    """Background tint of a row, resolved through the theme (never a hex value).

    The three values are passed to ``bw_gui.theming.tinted_color`` at render
    time, so a theme switch recolours the row automatically.

    Attributes:
        color_tint: Token name (e.g. ``"success_soft"``) or a seed colour to mix in.
        degree: Tint strength in [0, 1].
        base_token: Theme token used as the neutral base.
    """

    color_tint: str
    degree: float
    base_token: str = "panel_strong"


class CardTone(str, Enum):
    """How a card stands out; the renderer maps each tone to theme tokens.

    ``NORMAL`` is the plain card, ``EMPHASIS`` a softly filled card (e.g. the
    leading card of a cell), ``WARNING`` a card with a warning outline (e.g. a
    rule the consumer reports as violated).
    """

    NORMAL = "normal"
    EMPHASIS = "emphasis"
    WARNING = "warning"


@dataclass(frozen=True)
class BoardCard:
    """One card.

    Attributes:
        key: Unique across the whole board (cursor, drag and callbacks use it).
        text: Card text; wrapped to the card width.
        badge: Optional short code shown in a small bubble at the card's side.
        tone: How the card stands out (see :class:`CardTone`).
    """

    key: str
    text: str
    badge: str | None = None
    tone: CardTone = CardTone.NORMAL


@dataclass(frozen=True)
class BoardRow:
    """One row.

    Attributes:
        key: Stable identifier.
        label: Row-label text; ``\\n`` separates label lines.
        cards: Cards per ``CARDS`` lane key, top to bottom. Missing lanes are empty.
        texts: Text per ``TEXT`` lane key. Missing lanes are empty.
        tint: Optional background tint of the whole row.
        locked: A locked row takes nothing new: no "+" boxes, no drop slots,
            its ``TEXT`` cells show no placeholder and open no editor. Its
            cells stay selectable with the cursor.
    """

    key: str
    label: str
    cards: Mapping[str, tuple[BoardCard, ...]] = field(default_factory=dict)
    texts: Mapping[str, str] = field(default_factory=dict)
    tint: RowTint | None = None
    locked: bool = False


@dataclass(frozen=True)
class BoardCell:
    """One cell: a row and a lane."""

    row_key: str
    lane_key: str


@dataclass(frozen=True)
class BoardSlot:
    """An insertion position: before the card at ``index`` in a cell (``index`` = count → at the end)."""

    row_key: str
    lane_key: str
    index: int

    @property
    def cell(self) -> BoardCell:
        """The cell this slot belongs to."""
        return BoardCell(self.row_key, self.lane_key)


Cursor = Union[str, BoardCell, None]
"""The keyboard cursor: a card key, an empty/text cell, or nothing."""


class Direction(str, Enum):
    """Arrow directions for :func:`~bw_gui.widgets.card_board.neighbor`."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
