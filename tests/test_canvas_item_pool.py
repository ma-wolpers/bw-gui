"""CanvasItemPool: reuse items, send only differences, hide unused (no Tk needed)."""

from __future__ import annotations

from bw_gui.widgets.canvas_item_pool import CanvasItemPool


class _RecordingCanvas:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._next = 0

    def create_text(self, *coords, **options):
        self._next += 1
        self.calls.append(("create", coords, options))
        return self._next

    def coords(self, item, *coords):
        self.calls.append(("coords", item, coords))

    def itemconfigure(self, item, **options):
        self.calls.append(("config", item, options))


def _pass(pool, specs):
    pool.begin()
    for coords, text in specs:
        pool.place(coords, text=text, fill="black")
    pool.end()


def test_identical_pass_costs_no_calls():
    canvas = _RecordingCanvas()
    pool = CanvasItemPool(canvas, "text")
    _pass(pool, [((0, 0), "a"), ((0, 20), "b")])
    canvas.calls.clear()
    _pass(pool, [((0, 0), "a"), ((0, 20), "b")])
    assert canvas.calls == []


def test_only_changed_coords_and_options_are_sent():
    canvas = _RecordingCanvas()
    pool = CanvasItemPool(canvas, "text")
    _pass(pool, [((0, 0), "a"), ((0, 20), "b")])
    canvas.calls.clear()
    _pass(pool, [((5, 0), "a"), ((0, 20), "B")])
    assert canvas.calls == [("coords", 1, (5.0, 0.0)), ("config", 2, {"text": "B"})]


def test_unused_items_are_hidden_once_and_reshown():
    canvas = _RecordingCanvas()
    pool = CanvasItemPool(canvas, "text")
    _pass(pool, [((0, 0), "a"), ((0, 20), "b")])
    canvas.calls.clear()
    _pass(pool, [((0, 0), "a")])
    _pass(pool, [((0, 0), "a")])
    assert canvas.calls == [("config", 2, {"state": "hidden"})]
    canvas.calls.clear()
    _pass(pool, [((0, 0), "a"), ((0, 20), "b")])
    assert canvas.calls == [("config", 2, {"state": "normal"})]
    assert pool.items == (1, 2) and pool.kind == "text"
