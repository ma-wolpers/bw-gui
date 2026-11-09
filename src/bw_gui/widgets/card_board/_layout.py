"""CardBoard geometry without Tk: layout, hit testing, insertion slots, lines.

Everything here is a pure function of the model, the width and two measuring
callables, so it is unit-testable and the renderer only draws boxes it gets.
Coordinates are canvas coordinates (the body canvas scrolls; the layout does not).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence

from ._model import (
    BoardCell,
    BoardLane,
    BoardRow,
    BoardSlot,
    CardTone,
    Cursor,
    LaneKind,
    RowTint,
    lane_holds_cards,
    lane_holds_text,
)

LABEL_WIDTH = 132
PAD = 6
CARD_PAD_X = 8
CARD_PAD_Y = 4
GAP = 6
BADGE_PAD = 6
MIN_LANE_WIDTH = 120

Box = tuple[float, float, float, float]


class TextWrapper:
    """Greedy word wrap to a pixel width, cached per (text, width); over-long words are split."""

    def __init__(self, measure: Callable[[str], int]) -> None:
        """Bind to a font's ``measure`` (pixel width of a string)."""
        self._measure = measure
        self._cache: dict[tuple[str, int], tuple[str, ...]] = {}

    def wrap(self, text: str, width: int) -> tuple[str, ...]:
        """Return the display lines of *text* for *width* pixels (``\\n`` starts a new line)."""
        key = (text, width)
        if key not in self._cache:
            lines: list[str] = []
            for paragraph in text.split("\n"):
                lines.extend(self._wrap_paragraph(paragraph, max(1, width)))
            self._cache[key] = tuple(lines)
        return self._cache[key]

    def _wrap_paragraph(self, paragraph: str, width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if self._measure(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
            while self._measure(current) > width and len(current) > 1:
                cut = len(current) - 1
                while cut > 1 and self._measure(current[:cut]) > width:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
        lines.append(current)
        return lines


@dataclass(frozen=True)
class LaneBox:
    """Horizontal extent of a lane."""

    key: str
    title: str
    kind: LaneKind
    x0: float
    x1: float


@dataclass(frozen=True)
class RowBox:
    """Vertical extent of a row plus its label lines, tint and optional row-action button."""

    key: str
    y0: float
    y1: float
    label_lines: tuple[str, ...]
    tint: RowTint | None
    action: str | None = None
    action_box: Box | None = None


@dataclass(frozen=True)
class CardBox:
    """Position of one card; ``badge_box`` is the bubble at its right side."""

    key: str
    cell: BoardCell
    index: int
    box: Box
    lines: tuple[str, ...]
    badge: str | None
    badge_box: Box | None
    tone: CardTone = CardTone.NORMAL


@dataclass(frozen=True)
class CellBox:
    """One cell: its box, its cards, its "+" box and (text-holding lanes) its text area and lines.

    ``locked`` cells (of a locked row) have no "+" box and take no drop.
    ``text_box`` is the part of the cell that shows (and edits) the free text:
    the whole cell in a ``TEXT`` lane, the part below the cards in a
    ``CARDS_TEXT`` lane, ``None`` in a ``CARDS`` lane.
    """

    cell: BoardCell
    kind: LaneKind
    box: Box
    card_keys: tuple[str, ...]
    add_box: Box | None
    text_lines: tuple[str, ...]
    is_placeholder: bool
    locked: bool = False
    text_box: Box | None = None


@dataclass(frozen=True)
class BoardLayout:
    """Everything the renderer and the hit tests need.

    ``draft_box`` is the space reserved for a new card being typed (see the
    ``draft`` argument of :func:`compute_layout`), ``None`` without one.
    """

    width: float
    height: float
    line_height: int
    lanes: tuple[LaneBox, ...]
    rows: tuple[RowBox, ...]
    cells: Mapping[BoardCell, CellBox]
    cards: Mapping[str, CardBox]
    draft_box: Box | None = None


class HitKind(str, Enum):
    """What a point on the body canvas hits."""

    CARD = "card"
    ADD = "add"
    TEXT = "text"
    CELL = "cell"
    ROW_ACTION = "row_action"
    NONE = "none"


@dataclass(frozen=True)
class Hit:
    """Result of :func:`hit_test` (``row_key`` is set for ``ROW_ACTION``)."""

    kind: HitKind
    cell: BoardCell | None = None
    card_key: str | None = None
    row_key: str | None = None


def _lane_boxes(lanes: Sequence[BoardLane], width: float) -> tuple[LaneBox, ...]:
    usable = max(width - LABEL_WIDTH, MIN_LANE_WIDTH * len(lanes))
    total = sum(max(0.01, lane.weight) for lane in lanes) or 1.0
    boxes, x = [], float(LABEL_WIDTH)
    for lane in lanes:
        span = usable * max(0.01, lane.weight) / total
        boxes.append(LaneBox(lane.key, lane.title, lane.kind, x, x + span))
        x += span
    return tuple(boxes)


def compute_layout(
    rows: Sequence[BoardRow],
    lanes: Sequence[BoardLane],
    width: float,
    *,
    line_height: int,
    wrapper: TextWrapper,
    badge_width: Callable[[str], int],
    draft: BoardSlot | None = None,
) -> BoardLayout:
    """Lay out all rows top to bottom; every cell spans its row's full height.

    A cell stacks, top to bottom: its cards (card-holding lanes), its "+" box
    (not in locked rows) and its text (text-holding lanes). An empty ``CARDS``
    cell gets a full-width "+" box, every other card stack a small one.

    Args:
        rows: Rows in display order (top first).
        lanes: Lanes left to right.
        width: Available canvas width in pixels.
        line_height: Font line height.
        wrapper: Word wrapper for card, label and text-lane texts.
        badge_width: Pixel width of a badge text.
        draft: Slot of a new card being typed: one card-high space is reserved
            there (``BoardLayout.draft_box``) and the following cards move down.
    """
    lane_boxes = _lane_boxes(lanes, width)
    placeholders = {lane.key: lane.placeholder for lane in lanes}
    rows_out: list[RowBox] = []
    cells: dict[BoardCell, CellBox] = {}
    cards: dict[str, CardBox] = {}
    draft_box: Box | None = None
    y = 0.0
    for row in rows:
        label_lines = wrapper.wrap(row.label, LABEL_WIDTH - 2 * PAD)
        label_bottom = y + PAD + max(1, len(label_lines)) * line_height
        action_box: Box | None = None
        if row.action:
            action_w = min(badge_width(row.action) + 2 * CARD_PAD_X, LABEL_WIDTH - 2 * PAD)
            action_box = (PAD, label_bottom + GAP, PAD + action_w, label_bottom + GAP + line_height + 2 * CARD_PAD_Y)
            label_bottom = action_box[3]
        bottoms = [label_bottom + PAD]
        pending: list[tuple[LaneBox, tuple[str, ...], Box | None, tuple[str, ...], bool, float | None]] = []
        for lane in lane_boxes:
            x0, x1 = lane.x0 + PAD, lane.x1 - PAD
            cell = BoardCell(row.key, lane.key)
            stack_bottom, keys, add_box = y, [], None  # stack_bottom: lower edge of the last stacked box
            if lane_holds_cards(lane.kind):
                top = y + PAD
                lane_cards = row.cards.get(lane.key, ())
                draft_at = min(max(0, draft.index), len(lane_cards)) if draft is not None and draft.cell == cell else -1
                for index in range(len(lane_cards) + 1):
                    if index == draft_at:
                        draft_box = (x0, top, x1, top + line_height + 2 * CARD_PAD_Y)
                        stack_bottom, top = draft_box[3], draft_box[3] + GAP
                    if index == len(lane_cards):
                        break
                    card = lane_cards[index]
                    badge_w = badge_width(card.badge) + 2 * BADGE_PAD if card.badge else 0
                    text_w = int(x1 - x0 - 2 * CARD_PAD_X - (badge_w + GAP if badge_w else 0))
                    lines = wrapper.wrap(card.text, text_w)
                    bottom = top + max(1, len(lines)) * line_height + 2 * CARD_PAD_Y
                    badge_top = top + CARD_PAD_Y
                    badge_box = (x1 - CARD_PAD_X - badge_w, badge_top, x1 - CARD_PAD_X, badge_top + line_height)
                    cards[card.key] = CardBox(card.key, cell, index, (x0, top, x1, bottom), lines, card.badge,
                                              badge_box if badge_w else None, card.tone)  # fmt: skip
                    keys.append(card.key)
                    stack_bottom, top = bottom, bottom + GAP
                if not row.locked:
                    small = keys or draft_at >= 0 or lane_holds_text(lane.kind)
                    right = x0 + line_height + 2 * CARD_PAD_X if small else x1
                    add_box = (x0, top, right, top + (line_height + 2 if small else line_height + 2 * CARD_PAD_Y))
                    stack_bottom = add_box[3]
                bottoms.append(stack_bottom + PAD if stack_bottom > y else y + PAD)
            text_y0: float | None = None
            lines, is_placeholder = (), False
            if lane_holds_text(lane.kind):
                text = row.texts.get(lane.key, "")
                shown = text or ("" if row.locked else placeholders.get(lane.key, ""))
                lines, is_placeholder = wrapper.wrap(shown, int(x1 - x0 - 2 * CARD_PAD_X)), not text
                text_y0 = stack_bottom
                bottoms.append(text_y0 + 2 * PAD + max(2, len(lines)) * line_height + 2 * CARD_PAD_Y)
            pending.append((lane, tuple(keys), add_box, lines, is_placeholder, text_y0))
        row_bottom = max(bottoms)
        for lane, keys, add_box, lines, is_placeholder, text_y0 in pending:
            cell = BoardCell(row.key, lane.key)
            text_box = (lane.x0, text_y0, lane.x1, row_bottom) if text_y0 is not None else None
            cells[cell] = CellBox(cell, lane.kind, (lane.x0, y, lane.x1, row_bottom), keys, add_box, lines,
                                  is_placeholder, row.locked, text_box)  # fmt: skip
        rows_out.append(RowBox(row.key, y, row_bottom, label_lines, row.tint, row.action, action_box))
        y = row_bottom
    right = lane_boxes[-1].x1 if lane_boxes else float(LABEL_WIDTH)
    return BoardLayout(right, y, line_height, lane_boxes, tuple(rows_out), cells, cards, draft_box)


def _inside(box: Box | None, x: float, y: float) -> bool:
    return box is not None and box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _cell_at(layout: BoardLayout, x: float, y: float) -> BoardCell | None:
    row = next((r for r in layout.rows if r.y0 <= y < r.y1), None)
    lane = next((lane for lane in layout.lanes if lane.x0 <= x < lane.x1), None)
    return BoardCell(row.key, lane.key) if row is not None and lane is not None else None


def hit_test(layout: BoardLayout, x: float, y: float) -> Hit:
    """Return what the canvas point (*x*, *y*) hits.

    In this order: a row-action button, a card, a "+" box, the text area of a
    text-holding cell (``TEXT``), the rest of a cell (``CELL``) or nothing.
    """
    for row in layout.rows:
        if _inside(row.action_box, x, y):
            return Hit(HitKind.ROW_ACTION, row_key=row.key)
    cell = _cell_at(layout, x, y)
    if cell is None:
        return Hit(HitKind.NONE)
    box = layout.cells[cell]
    for key in box.card_keys:
        if _inside(layout.cards[key].box, x, y):
            return Hit(HitKind.CARD, cell, key)
    if _inside(box.add_box, x, y):
        return Hit(HitKind.ADD, cell)
    if _inside(box.text_box, x, y):
        return Hit(HitKind.TEXT, cell)
    return Hit(HitKind.CELL, cell)


def slot_at(layout: BoardLayout, x: float, y: float) -> BoardSlot | None:
    """Insertion slot under (*x*, *y*): before the first card whose middle lies below *y*.

    Points above the first row or below the last row snap to that row, so
    dragging slightly past the edge still targets the outermost row. Locked
    cells and text-only lanes have no slots; over the text of a ``CARDS_TEXT``
    cell the slot is the end of its cards (directly above the text).
    """
    if not layout.rows:
        return None
    y = min(max(y, layout.rows[0].y0), layout.rows[-1].y1 - 1)
    cell = _cell_at(layout, x, y)
    if cell is None or not lane_holds_cards(layout.cells[cell].kind) or layout.cells[cell].locked:
        return None
    keys = layout.cells[cell].card_keys
    index = sum(1 for key in keys if (layout.cards[key].box[1] + layout.cards[key].box[3]) / 2 < y)
    return BoardSlot(cell.row_key, cell.lane_key, index)


def insertion_line(layout: BoardLayout, slot: BoardSlot) -> tuple[float, float, float]:
    """Return ``(x0, x1, y)`` of the indicator line for *slot* (in the gap between cards)."""
    cell = layout.cells[slot.cell]
    x0, y0, x1, _y1 = cell.box
    boxes = [layout.cards[key].box for key in cell.card_keys]
    if not boxes:
        y = y0 + PAD / 2
    elif slot.index <= 0:
        y = boxes[0][1] - GAP / 2
    elif slot.index >= len(boxes):
        y = boxes[-1][3] + GAP / 2
    else:
        y = (boxes[slot.index - 1][3] + boxes[slot.index][1]) / 2
    return (x0 + PAD, x1 - PAD, y)


def cursor_box(layout: BoardLayout, cursor: Cursor) -> Box | None:
    """Box of the cursor, ``None`` if it is not on the board.

    A card cursor frames the card; a cell cursor frames the cell's text area in
    text-holding lanes (below the cards of a ``CARDS_TEXT`` cell), otherwise the cell.
    """
    if isinstance(cursor, str):
        card = layout.cards.get(cursor)
        return card.box if card is not None else None
    if isinstance(cursor, BoardCell) and cursor in layout.cells:
        cell = layout.cells[cursor]
        return cell.text_box or cell.box
    return None
