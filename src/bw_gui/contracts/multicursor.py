"""Multi-cursor model, pure part (``docs/MULTICURSOR_CONTRACT.md``).

Regions and planned edits as offsets, without Tk. An offset counts characters as Python
does; the Tk adapter converts (``multicursor_text``), so an emoji can never be split.

Normalisation rules (:func:`normalize`):

* identical carets collapse into one;
* overlapping or touching selections merge, keeping the direction of the earlier one;
* a caret strictly inside a selection (``start < pos < end``) is swallowed;
* a caret exactly on a selection's edge stays independent.

Edit order (:func:`plan_edits`, :func:`apply_to_string`): edits are sorted by
``(start, end, order)`` and clipped so they never overlap. A caret on the start edge of
a selection therefore writes *before* the selection's replacement, a caret on the end
edge *after* it. A widget applies them last-to-first (:func:`application_order`), so
every offset is still valid when its edit runs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class Region:
    """One cursor: ``head`` is where it writes and moves, ``anchor`` where its selection starts.

    Attributes:
        anchor: Fixed end of the selection (equal to ``head`` for a plain caret).
        head: Moving end.
        goal: Remembered display column for vertical moves, ``None`` when not moving vertically.
        order: Creation order; the youngest region is the primary one.
    """

    anchor: int
    head: int
    goal: int | None = None
    order: int = 0

    @property
    def start(self) -> int:
        return min(self.anchor, self.head)

    @property
    def end(self) -> int:
        return max(self.anchor, self.head)

    @property
    def is_caret(self) -> bool:
        return self.anchor == self.head


@dataclass(frozen=True)
class Edit:
    """Replace ``start``-``end`` with ``text``.

    ``select`` is the ``(anchor, head)`` of the region afterwards, relative to the start
    of ``text``; ``None`` places a caret behind the text.
    """

    start: int
    end: int
    text: str
    order: int = 0
    select: tuple[int, int] | None = None


def _sort_key(region: Region) -> tuple[int, int, int]:
    return (region.start, region.end, region.order)


def normalize(regions: Iterable[Region]) -> tuple[Region, ...]:
    """Apply the normalisation rules (module docstring); the result is sorted."""
    ordered = sorted(regions, key=_sort_key)
    selections: list[Region] = []
    for region in (item for item in ordered if not item.is_caret):
        if selections and region.start <= selections[-1].end:
            earlier = selections[-1]
            start, end = earlier.start, max(earlier.end, region.end)
            anchor, head = (start, end) if earlier.anchor <= earlier.head else (end, start)
            selections[-1] = replace(earlier, anchor=anchor, head=head, order=max(earlier.order, region.order))
        else:
            selections.append(region)
    carets: dict[int, Region] = {}
    for region in (item for item in ordered if item.is_caret):
        if any(selection.start < region.head < selection.end for selection in selections):
            continue
        known = carets.get(region.head)
        if known is None or region.order > known.order:
            carets[region.head] = region
    return tuple(sorted([*selections, *carets.values()], key=_sort_key))


def primary(regions: Sequence[Region]) -> Region:
    """The youngest region: it owns Tk's native insertion cursor."""
    return max(regions, key=lambda region: region.order)


def region_at(regions: Iterable[Region], offset: int) -> Region | None:
    """The region hit by a click at *offset* (a caret at it, or a selection containing it)."""
    for region in regions:
        if region.start <= offset <= region.end:
            return region
    return None


def moved(regions: Iterable[Region], step: Callable[[Region], int], *, extend: bool, goal: Callable[[Region], int | None] | None = None) -> tuple[Region, ...]:
    """Move every head with *step*; without *extend* every selection collapses onto its new head.

    Args:
        step: Maps a region to the offset of its new head.
        extend: Shift variant, the anchor stays.
        goal: Goal column of the moved region (vertical moves); others forget it.
    """
    result = []
    for region in regions:
        head = step(region)
        anchor = region.anchor if extend else head
        result.append(replace(region, anchor=anchor, head=head, goal=goal(region) if goal else None))
    return normalize(result)


def plan_text(regions: Iterable[Region], text: str) -> list[Edit]:
    """Every region writes *text*, replacing its selection."""
    return [Edit(region.start, region.end, text, region.order) for region in regions]


def plan_lines_or_text(regions: Sequence[Region], text: str) -> list[Edit]:
    """Paste: one line per region when line and region counts match, else all of *text* everywhere."""
    lines = text.split("\n")
    if len(lines) == len(regions) > 1:
        return [Edit(region.start, region.end, line, region.order) for region, line in zip(regions, lines)]
    return plan_text(regions, text)


def plan_delete(regions: Iterable[Region], *, forward: bool, limit: int) -> list[Edit]:
    """Backspace/Delete: a selection goes away; a caret removes its neighbouring character.

    Args:
        forward: Delete instead of Backspace.
        limit: Text length.
    """
    edits = []
    for region in regions:
        if not region.is_caret:
            edits.append(Edit(region.start, region.end, "", region.order))
        elif forward and region.head < limit:
            edits.append(Edit(region.head, region.head + 1, "", region.order))
        elif not forward and region.head > 0:
            edits.append(Edit(region.head - 1, region.head, "", region.order))
        else:
            edits.append(Edit(region.head, region.head, "", region.order))
    return edits


def plan_edits(edits: Iterable[Edit]) -> list[Edit]:
    """Sort edits by ``(start, end, order)`` and clip them so none overlaps the one before."""
    result: list[Edit] = []
    covered = 0
    for edit in sorted(edits, key=lambda item: (item.start, item.end, item.order)):
        start = max(edit.start, covered)
        end = max(edit.end, start)
        result.append(replace(edit, start=start, end=end))
        covered = end
    return result


def application_order(edits: Iterable[Edit]) -> list[Edit]:
    """Planned edits last-to-first: applying them in this order keeps all offsets valid."""
    return list(reversed(list(edits)))


def regions_after(edits: Sequence[Edit]) -> tuple[Region, ...]:
    """The normalised regions once the planned *edits* have been applied."""
    regions = []
    delta = 0
    for edit in edits:
        position = edit.start + delta
        size = len(edit.text)
        if edit.select is None:
            regions.append(Region(position + size, position + size, order=edit.order))
        else:
            regions.append(Region(position + edit.select[0], position + edit.select[1], order=edit.order))
        delta += size - (edit.end - edit.start)
    return normalize(regions)


def apply_to_string(text: str, edits: Sequence[Edit]) -> str:
    """Apply planned edits to a string (for tests and reasoning)."""
    for edit in application_order(edits):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text
