"""CardBoard drawing: one full pass for content, a cheap pass for cursor and drop line.

Colours are resolved from the active theme at render time (tokens; row tints
via ``tinted_color``), so a theme switch only needs a re-render. Items come from
:class:`CanvasItemPool`s; unchanged passes cost no Tk calls. Pools carry one
tag each and are re-stacked in a fixed order after every content pass, because
pools create their items lazily and creation order alone would not keep the
stacking stable.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...theming import tinted_color
from ..canvas_item_pool import CanvasItemPool
from ..canvas_shapes import rounded_rect_points
from ._layout import CARD_PAD_X, CARD_PAD_Y, LABEL_WIDTH, PAD, BoardLayout, cursor_box, insertion_line
from ._model import BoardSlot, CardTone, Cursor, LaneKind

_RADIUS = 7

# The one table of card looks: tone -> (fill, outline, outline width, badge fill), all theme tokens.
# The badge fill differs from the card fill so a badge stays visible on an EMPHASIS card.
_CARD_TONES: dict[CardTone, tuple[str, str, int, str]] = {
    CardTone.NORMAL: ("bg_panel", "border", 1, "accent_soft"),
    CardTone.EMPHASIS: ("accent_soft", "border", 1, "bg_panel"),
    CardTone.WARNING: ("bg_panel", "warning", 2, "accent_soft"),
}
_STACK = ("row_bg", "grid_line", "label", "add_box", "add_text", "card", "card_text", "badge", "badge_text",
          "lane_text", "cursor", "drop_line")  # fmt: skip


class BoardRenderer:
    """Draws a :class:`BoardLayout` on the body canvas and lane titles on the header canvas."""

    def __init__(self, body: Any, header: Any, font: Any) -> None:
        """Create the pools.

        Args:
            body: Scrolling body canvas.
            header: Fixed header canvas (lane titles).
            font: Tk font for every text item.
        """
        self._body, self._header, self._font = body, header, font
        kinds = {"row_bg": "rectangle", "grid_line": "line", "label": "text", "add_box": "polygon",
                 "add_text": "text", "card": "polygon", "card_text": "text", "badge": "polygon",
                 "badge_text": "text", "lane_text": "text", "cursor": "polygon", "drop_line": "line"}  # fmt: skip
        self._pools = {name: CanvasItemPool(body, kind, tags=(f"cb_{name}",)) for name, kind in kinds.items()}
        self._head_bg = CanvasItemPool(header, "rectangle")
        self._head_text = CanvasItemPool(header, "text")
        self._head_line = CanvasItemPool(header, "line")

    def render_content(self, layout: BoardLayout, theme: Mapping[str, str], head_height: int) -> None:
        """Full pass: rows, grid lines, labels, cards, badges, "+" boxes, text lanes, header."""
        pools = self._pools
        for name in _STACK[:-2]:
            pools[name].begin()
        self._rows(layout, theme)
        self._cells(layout, theme)
        self._cards(layout, theme)
        for name in _STACK[:-2]:
            pools[name].end()
        for name in _STACK:
            self._body.tag_raise(f"cb_{name}")
        self._render_header(layout, theme, head_height)

    def render_markers(
        self, layout: BoardLayout, theme: Mapping[str, str], cursor: Cursor, drop: BoardSlot | None
    ) -> None:
        """Cheap pass: only the cursor outline and the drop indicator line."""
        cursor_pool, line_pool = self._pools["cursor"], self._pools["drop_line"]
        cursor_pool.begin()
        box = cursor_box(layout, cursor)
        if box is not None:
            x0, y0, x1, y1 = box
            inset = 1 if isinstance(cursor, str) else 3
            points = rounded_rect_points(x0 - inset, y0 - inset, x1 + inset, y1 + inset, radius=_RADIUS + inset)
            cursor_pool.place(points, smooth=True, fill="", outline=theme["accent"], width=2)
        cursor_pool.end()
        line_pool.begin()
        if drop is not None and drop.cell in layout.cells:
            x0, x1, y = insertion_line(layout, drop)
            line_pool.place((x0, y, x1, y), fill=theme["accent"], width=3, capstyle="round")
        line_pool.end()

    def _text(self, pool_name: str, x: float, y: float, text: str, fill: str, anchor: str = "nw") -> None:
        self._pools[pool_name].place((x, y), text=text, fill=fill, anchor=anchor, font=self._font)

    def _rows(self, layout: BoardLayout, theme: Mapping[str, str]) -> None:
        line_h = layout.line_height
        for row in layout.rows:
            fill = theme.get("bg_surface", theme["bg_main"])
            if row.tint is not None:
                fill = tinted_color(row.tint.color_tint, degree=row.tint.degree, base_token=row.tint.base_token)
            self._pools["row_bg"].place((0, row.y0, layout.width, row.y1), fill=fill, outline="")
            self._pools["grid_line"].place((0, row.y1 - 1, layout.width, row.y1 - 1), fill=theme["border"])
            for index, line in enumerate(row.label_lines):
                color = theme["fg_primary"] if index == 0 else theme["fg_muted"]
                self._text("label", PAD, row.y0 + PAD + index * line_h, line, color)
        for lane in layout.lanes:
            self._pools["grid_line"].place((lane.x0, 0, lane.x0, layout.height), fill=theme["border"])
        if not layout.lanes:
            self._pools["grid_line"].place((LABEL_WIDTH, 0, LABEL_WIDTH, layout.height), fill=theme["border"])

    def _cells(self, layout: BoardLayout, theme: Mapping[str, str]) -> None:
        line_h = layout.line_height
        for cell in layout.cells.values():
            x0, y0, _x1, _y1 = cell.box
            if cell.kind is LaneKind.TEXT:
                color = theme["fg_muted"] if cell.is_placeholder else theme["fg_primary"]
                for index, line in enumerate(cell.text_lines):
                    self._text("lane_text", x0 + PAD + CARD_PAD_X, y0 + PAD + CARD_PAD_Y + index * line_h, line, color)
                continue
            if cell.add_box is None:
                continue
            ax0, ay0, ax1, ay1 = cell.add_box
            points = rounded_rect_points(ax0, ay0, ax1, ay1, radius=_RADIUS)
            self._pools["add_box"].place(points, smooth=True, fill="", outline=theme["border"], dash=(3, 3))
            self._text("add_text", (ax0 + ax1) / 2, (ay0 + ay1) / 2, "+", theme["fg_muted"], anchor="center")

    def _cards(self, layout: BoardLayout, theme: Mapping[str, str]) -> None:
        line_h = layout.line_height
        for card in layout.cards.values():
            x0, y0, x1, y1 = card.box
            fill, outline, width, badge_fill = _CARD_TONES[card.tone]
            points = rounded_rect_points(x0, y0, x1, y1, radius=_RADIUS)
            self._pools["card"].place(points, smooth=True, fill=theme[fill], outline=theme[outline], width=width)
            for index, line in enumerate(card.lines):
                self._text("card_text", x0 + CARD_PAD_X, y0 + CARD_PAD_Y + index * line_h, line, theme["fg_primary"])
            if card.badge_box is not None and card.badge:
                bx0, by0, bx1, by1 = card.badge_box
                badge_points = rounded_rect_points(bx0, by0, bx1, by1, radius=line_h)
                self._pools["badge"].place(badge_points, smooth=True, fill=theme[badge_fill], outline="")
                self._text("badge_text", (bx0 + bx1) / 2, (by0 + by1) / 2, card.badge, theme["fg_primary"], "center")

    def _render_header(self, layout: BoardLayout, theme: Mapping[str, str], height: int) -> None:
        self._header.configure(background=theme["bg_panel"])
        self._head_bg.begin()
        self._head_text.begin()
        self._head_line.begin()
        self._head_bg.place((0, 0, max(layout.width, 1), height), fill=theme["bg_panel"], outline="")
        for lane in layout.lanes:
            self._head_text.place((lane.x0 + PAD + CARD_PAD_X, height / 2), text=lane.title, anchor="w",
                                  fill=theme["fg_primary"], font=self._font)  # fmt: skip
            self._head_line.place((lane.x0, 2, lane.x0, height - 2), fill=theme["border"])
        self._head_line.place((0, height - 1, max(layout.width, 1), height - 1), fill=theme["border"])
        self._head_bg.end()
        self._head_text.end()
        self._head_line.end()
