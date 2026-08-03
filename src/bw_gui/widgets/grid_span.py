"""Grid-column grouping for widgets that visually span several Tk grid columns.

Provides ``compute_contiguous_spans`` — a pure, Tk-free function that groups a
set of Tk grid column numbers into the maximal contiguous blocks they form.
Consumer programs use this to map a domain-level "this spans several adjacent
columns" concept (e.g. a merged header cell, a Gantt-style bar, a grouped
summary row) onto one or more ``columnspan`` placements, without having to
write the column-grouping arithmetic themselves::

    from bw_gui.widgets.grid_span import compute_contiguous_spans

    for segment in compute_contiguous_spans(visible_columns):
        widget = tk.Label(parent, text=summary_text)
        widget.grid(row=row, column=segment.start_column, columnspan=segment.column_span, sticky="nsew")

If some of the domain columns are currently hidden (e.g. a column-visibility
filter removed them from the grid), the remaining visible columns may no
longer be contiguous — ``compute_contiguous_spans`` then returns more than one
segment, one per visible run, which is the correct and expected outcome: the
consumer places one spanning widget per segment instead of a single one that
would silently bridge a hidden gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class GridSpanSegment:
    """One contiguous block of Tk grid columns.

    Attributes:
        start_column: First Tk grid column number of the block.
        column_span:  Number of columns the block covers (pass straight to
                      the widget's ``columnspan`` option).
    """

    start_column: int
    column_span: int


def compute_contiguous_spans(grid_columns: Sequence[int]) -> list[GridSpanSegment]:
    """Group grid column numbers into maximal contiguous blocks.

    Args:
        grid_columns: Tk grid column numbers of the currently visible members
            of one logical group, in any order.

    Returns:
        The segments in ascending column order. An empty input yields an
        empty list.
    """
    sorted_columns = sorted(set(grid_columns))
    if not sorted_columns:
        return []

    segments: list[GridSpanSegment] = []
    segment_start = sorted_columns[0]
    previous = sorted_columns[0]

    for column in sorted_columns[1:]:
        if column == previous + 1:
            previous = column
            continue
        segments.append(GridSpanSegment(start_column=segment_start, column_span=previous - segment_start + 1))
        segment_start = column
        previous = column

    segments.append(GridSpanSegment(start_column=segment_start, column_span=previous - segment_start + 1))
    return segments
