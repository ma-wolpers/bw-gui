"""Wrapping row layout: children flow left to right and wrap at the available width.

``FlowFrame`` is the bw-gui building block for a row of small widgets (badges,
label + entry pairs, chips) that must stay fully visible in a narrow area
instead of being clipped at the right edge. ``pack(side="left")`` cannot wrap;
``FlowFrame`` places its children itself and requests exactly the height the
wrapped rows need, so an enclosing ``ScrollableFrame`` sees the real content
height.

The geometry is computed by the pure function :func:`compute_flow_layout`
(no Tk), so the wrapping rule is testable on its own. The widget only measures
its children, applies the positions with ``place`` and re-runs the layout when
its width changes or a child's size changes (``bw_gui.runtime.on_resize``),
coalesced to one layout per idle cycle.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bw_gui.runtime import on_resize, widgets

__all__ = ["FlowFrame", "compute_flow_layout"]


def compute_flow_layout(
    sizes: Sequence[tuple[int, int]], width: int | None, *, gap_x: int, gap_y: int
) -> tuple[list[tuple[int, int]], int]:
    """Positions of children in wrapping rows.

    Children keep their order. A child starts a new row when it would cross
    *width*; a child wider than *width* gets a row of its own (it is never
    shrunk). Each row is as tall as its tallest child; smaller children are
    centred vertically in their row.

    Args:
        sizes: ``(width, height)`` of each child in flow order.
        width: Available width; ``None`` (or below 1) = unbounded, one row.
        gap_x: Horizontal space between children of a row.
        gap_y: Vertical space between rows.

    Returns:
        ``(positions, total_height)``: top-left ``(x, y)`` per child and the
        height of all rows including the gaps between them (0 without children).
    """
    limit = width if width is not None and width >= 1 else None
    rows: list[list[int]] = []
    row_width = 0
    for index, (child_width, _height) in enumerate(sizes):
        needed = child_width if not rows or not rows[-1] else row_width + gap_x + child_width
        if rows and rows[-1] and (limit is None or needed <= limit):
            rows[-1].append(index)
            row_width = needed
        else:
            rows.append([index])
            row_width = child_width
    positions: list[tuple[int, int]] = [(0, 0)] * len(sizes)
    y = 0
    for row_number, row in enumerate(rows):
        row_height = max(sizes[index][1] for index in row)
        x = 0
        for index in row:
            child_width, child_height = sizes[index]
            positions[index] = (x, y + (row_height - child_height) // 2)
            x += child_width + gap_x
        y += row_height + (gap_y if row_number < len(rows) - 1 else 0)
    return positions, y


class FlowFrame(widgets.Frame):
    """A ``ttk.Frame`` whose children wrap into rows (see the module docstring).

    Children are created with the ``FlowFrame`` as master and registered with
    :meth:`add`; never ``pack``/``grid`` them yourself. The frame requests the
    width of its widest child (it can shrink down to that) and the height of
    the wrapped rows.
    """

    def __init__(self, master: Any, *, gap_x: int = 8, gap_y: int = 4, **frame_kwargs: Any) -> None:
        """Build an empty flow.

        Args:
            master: Parent widget.
            gap_x: Horizontal space between children of a row (pixels).
            gap_y: Vertical space between rows (pixels).
            **frame_kwargs: Forwarded to ``ttk.Frame`` (e.g. ``style``).
        """
        super().__init__(master, **frame_kwargs)
        self._gap_x = gap_x
        self._gap_y = gap_y
        self._items: list[Any] = []
        self._layout_scheduled: str | None = None
        self._laid_out_width: int | None = None
        on_resize(self, self._on_own_resize)

    @property
    def items(self) -> tuple[Any, ...]:
        """The registered children in flow order."""
        return tuple(self._items)

    def add(self, child: Any) -> Any:
        """Append *child* (master must be this frame) to the flow.

        Args:
            child: Widget created with this ``FlowFrame`` as master.

        Returns:
            *child*, for chaining at creation.

        Raises:
            ValueError: *child* has another master.
        """
        if child.master is not self:
            raise ValueError("FlowFrame.add: the child must be created with the FlowFrame as master")
        self._items.append(child)
        on_resize(child, lambda _event: self._schedule_layout())
        self._schedule_layout()
        return child

    def clear(self) -> None:
        """Destroy all registered children."""
        items, self._items = self._items, []
        for child in items:
            child.destroy()
        self._schedule_layout()

    def relayout(self) -> None:
        """Lay the children out now for the current width (also run on idle after changes)."""
        if self._layout_scheduled is not None:
            try:
                self.after_cancel(self._layout_scheduled)
            except Exception:
                pass
            self._layout_scheduled = None
        if not self.winfo_exists():  # idle callback after destroy
            return
        live = [child for child in self._items if child.winfo_exists()]
        self._items = live
        sizes = [(child.winfo_reqwidth(), child.winfo_reqheight()) for child in live]
        width = self.winfo_width() if self.winfo_ismapped() else None
        positions, total_height = compute_flow_layout(sizes, width, gap_x=self._gap_x, gap_y=self._gap_y)
        for child, (x, y) in zip(live, positions):
            child.place(x=x, y=y)
        requested_width = max((size[0] for size in sizes), default=1)
        if (int(self.cget("width") or 0), int(self.cget("height") or 0)) != (requested_width, max(total_height, 1)):
            self.configure(width=requested_width, height=max(total_height, 1))
        self._laid_out_width = width

    def _schedule_layout(self) -> None:
        """Coalesce layout requests to one run per idle cycle."""
        if self._layout_scheduled is None:
            self._layout_scheduled = self.after_idle(self.relayout)

    def _on_own_resize(self, event: Any) -> None:
        """Re-flow only when the width changed (own height changes come from the layout)."""
        if event.width != self._laid_out_width:
            self._schedule_layout()
