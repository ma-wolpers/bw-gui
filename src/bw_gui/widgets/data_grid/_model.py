"""Tk-free model of the DataGrid: columns, rows, per-region layout, visibility, clipping.

Everything here is pure arithmetic over column widths and row counts, so it
is unit-testable without Tk. The view (``_region.py``) asks this module
*which* rows and columns are visible and *where* they are; it never computes
geometry itself.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping, Sequence


class Region(Enum):
    """The three horizontal areas of the grid, left to right."""

    LEFT = "left"      # e.g. names; scrolls vertically with the rest
    SCROLL = "scroll"  # the main, horizontally scrolling area (e.g. dates)
    RIGHT = "right"    # e.g. totals


@dataclass(frozen=True)
class GridColumn:
    """One column.

    Attributes:
        key: Stable column key used in all API calls.
        title: Header text.
        width: Width in pixels at width scale 1.0.
        region: Area the column belongs to.
        anchor: ``"w"`` (left) or ``"center"`` text alignment.
    """

    key: str
    title: str
    width: int
    region: Region
    anchor: str = "w"


@dataclass(frozen=True)
class GridRow:
    """One row: its stable id and the display text per column key (missing key = empty)."""

    row_id: str
    cells: Mapping[str, str] = field(default_factory=dict)


class RegionLayout:
    """Scaled widths and x offsets of one region's columns."""

    def __init__(self, columns: Sequence[GridColumn], scale: float) -> None:
        """Lay out *columns* left to right at *scale*.

        Args:
            columns: Columns of one region, in display order.
            scale: Global width scale (1.0 = configured widths).
        """
        self.columns = tuple(columns)
        self.widths = tuple(max(8, round(column.width * scale)) for column in self.columns)
        offsets = [0]
        for width in self.widths:
            offsets.append(offsets[-1] + width)
        self._offsets = tuple(offsets)
        self._index_by_key = {column.key: index for index, column in enumerate(self.columns)}

    @property
    def total_width(self) -> int:
        """Width of all columns together."""
        return self._offsets[-1]

    def index_of(self, key: str) -> int | None:
        """Position of column *key* in this region, or ``None``."""
        return self._index_by_key.get(key)

    def span(self, index: int) -> tuple[int, int]:
        """Content x range ``(x0, x1)`` of column *index*."""
        return self._offsets[index], self._offsets[index + 1]

    def index_at(self, content_x: float) -> int | None:
        """Column index under content x *content_x*, or ``None`` outside all columns."""
        if not self.columns or content_x < 0 or content_x >= self.total_width:
            return None
        return bisect_right(self._offsets, content_x) - 1

    def visible(self, x_offset: int, viewport_width: int) -> range:
        """Indices of columns intersecting the viewport ``[x_offset, x_offset + viewport_width)``."""
        if not self.columns or viewport_width <= 0:
            return range(0)
        first = max(0, bisect_right(self._offsets, x_offset) - 1)
        last = bisect_right(self._offsets, x_offset + viewport_width - 1) - 1
        return range(first, min(len(self.columns), last + 1))


def clamp_offset(offset: int, content: int, viewport: int) -> int:
    """Clamp a scroll offset so the viewport never shows space beyond the content."""
    return max(0, min(offset, max(0, content - viewport)))


def visible_rows(top_row: int, row_count: int, viewport_height: int, row_height: int) -> range:
    """Row indices visible from *top_row* (including a partially visible last row)."""
    if row_count <= 0 or row_height <= 0:
        return range(0)
    count = viewport_height // row_height + 1
    return range(top_row, min(row_count, top_row + count))


def fully_visible_row_count(viewport_height: int, row_height: int) -> int:
    """How many rows fit completely (at least 1)."""
    return max(1, viewport_height // max(1, row_height))


class TextClipper:
    """Shortens text to a pixel width with "…", measuring as little as possible.

    Measuring is a Tk call, so: a cheap upper bound (``len(text) *
    widest_char``) skips measuring short texts entirely, and results are cached
    per (text, width).
    """

    def __init__(self, measure: Callable[[str], int], widest_char: int) -> None:
        """Bind to a font.

        Args:
            measure: Pixel width of a string in the grid font.
            widest_char: Width of the font's widest character (upper bound per char).
        """
        self._measure = measure
        self._widest = max(1, widest_char)
        self._cache: dict[tuple[str, int], str] = {}

    def clip(self, text: str, available: int) -> str:
        """Return *text* or its longest prefix + "…" that fits into *available* pixels.

        Args:
            text: Cell text.
            available: Usable width in pixels.
        """
        if not text or len(text) * self._widest <= available:
            return text
        key = (text, available)
        cached = self._cache.get(key)
        if cached is None:
            cached = self._clip_measured(text, available)
            if len(self._cache) > 4096:
                self._cache.clear()
            self._cache[key] = cached
        return cached

    def _clip_measured(self, text: str, available: int) -> str:
        """Binary-search the longest prefix that fits together with the ellipsis."""
        if self._measure(text) <= available:
            return text
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if self._measure(text[:middle] + "…") <= available:
                low = middle
            else:
                high = middle - 1
        return text[:low] + "…" if low else ""
