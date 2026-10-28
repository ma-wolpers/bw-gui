"""CanvasItemPool — reuse canvas items and send Tk only what actually changed.

Canvas renders here are "describe everything visible, every time": a render
pass calls :meth:`CanvasItemPool.place` once per wanted item. The pool hands
out its items in order, remembers each item's last coordinates and options,
and issues ``coords``/``itemconfigure`` only for differences; items not
placed in a pass are hidden (and kept for later). Re-rendering an unchanged
view therefore costs no Tk calls at all, and moving one marker costs one.
This keeps render code simple (no manual diffing) *and* cheap.

Example::

    pool = CanvasItemPool(canvas, "text", tags=("cell",))
    pool.begin()
    for x, y, text in visible_cells:
        pool.place((x, y), text=text, anchor="w")
    pool.end()
"""

from __future__ import annotations

from typing import Any

_HIDDEN = "hidden"
_NORMAL = "normal"


class CanvasItemPool:
    """A growing pool of canvas items of one kind with per-item change tracking."""

    def __init__(self, canvas: Any, kind: str, *, tags: tuple[str, ...] = ()) -> None:
        """Create an empty pool.

        Args:
            canvas: The canvas the items live on.
            kind: Canvas item type, e.g. ``"text"``, ``"rectangle"``, ``"line"``.
            tags: Tags given to every item (for stacking via ``tag_raise``/``tag_lower``).
        """
        self._canvas = canvas
        self._kind = kind
        self._tags = tags
        self._items: list[int] = []
        self._applied: list[tuple[tuple[float, ...], dict[str, Any]]] = []
        self._cursor = 0

    def begin(self) -> None:
        """Start a render pass: the next :meth:`place` reuses the first item."""
        self._cursor = 0

    def place(self, coords: tuple[float, ...], **options: Any) -> int:
        """Show the next pooled item at *coords* with *options*; create it if needed.

        Args:
            coords: Item coordinates (e.g. ``(x, y)`` for text, ``(x1, y1, x2, y2)`` for rectangles).
            **options: Item options (``text``, ``fill``, ``outline``, ``anchor`` …).

        Returns:
            The canvas item id (stable across passes for the same position in the pass).
        """
        coords = tuple(float(value) for value in coords)
        wanted = dict(options, state=_NORMAL)
        index = self._cursor
        self._cursor += 1
        if index == len(self._items):
            item = getattr(self._canvas, f"create_{self._kind}")(*coords, tags=self._tags, **wanted)
            self._items.append(item)
            self._applied.append((coords, wanted))
            return item
        item = self._items[index]
        applied_coords, applied_options = self._applied[index]
        if coords != applied_coords:
            self._canvas.coords(item, *coords)
        changed = {key: value for key, value in wanted.items() if applied_options.get(key) != value}
        if changed:
            self._canvas.itemconfigure(item, **changed)
        self._applied[index] = (coords, {**applied_options, **changed})
        return item

    def end(self) -> None:
        """Finish the pass: hide every item that was not placed in it."""
        for index in range(self._cursor, len(self._items)):
            coords, options = self._applied[index]
            if options.get("state") != _HIDDEN:
                self._canvas.itemconfigure(self._items[index], state=_HIDDEN)
                self._applied[index] = (coords, {**options, "state": _HIDDEN})

    @property
    def kind(self) -> str:
        """Canvas item type of this pool (``"text"``, ``"rectangle"`` …)."""
        return self._kind

    @property
    def items(self) -> tuple[int, ...]:
        """All item ids created so far (visible or hidden)."""
        return tuple(self._items)
