"""PointerGroup: one shared tag for many widgets (click, double click, wheel, membership, cost)."""

from __future__ import annotations

from bw_gui.contracts.events import EventResult
from bw_gui.runtime import PointerGroup, ui
from bw_gui.runtime.pointer import wheel_subscribed


def _cells(root, count):
    top = ui.Toplevel(root)
    cells = [ui.Label(top, text=str(i)) for i in range(count)]
    for cell in cells:
        cell.pack()
    top.update()
    return top, cells


def test_click_reports_the_member_and_handled_stops_class_bindings(_shared_tk_root):
    top, cells = _cells(_shared_tk_root, 3)
    group = PointerGroup(_shared_tk_root, "cells")
    seen: list[object] = []
    reached_class: list[object] = []
    top.bind_class("Label", "<ButtonPress-1>", lambda e: reached_class.append(e.widget), add="+")
    try:
        group.on_click(lambda event: seen.append(event.widget) or EventResult.HANDLED)
        for cell in cells[:2]:
            group.add(cell)
        cells[1].event_generate("<ButtonPress-1>", x=1, y=1)
        cells[2].event_generate("<ButtonPress-1>", x=1, y=1)  # not a member
        top.update()
        assert seen == [cells[1]]
        assert reached_class == [cells[2]]  # member press was consumed before the class tag
        group.discard(cells[1])
        cells[1].event_generate("<ButtonPress-1>", x=1, y=1)
        top.update()
        assert seen == [cells[1]]
    finally:
        top.unbind_class("Label", "<ButtonPress-1>")
        group.dispose()
        top.destroy()


def test_wheel_marks_members_as_subscribed_and_dispose_unbinds(_shared_tk_root):
    top, cells = _cells(_shared_tk_root, 2)
    group = PointerGroup(_shared_tk_root, "wheel")
    steps: list[int] = []
    try:
        subscription = group.on_wheel(lambda event: steps.append(event.whole_steps) or EventResult.HANDLED)
        group.add(cells[0])
        assert wheel_subscribed(cells[0]) and not wheel_subscribed(cells[1])
        cells[0].event_generate("<MouseWheel>", delta=-120, x=1, y=1)
        top.update()
        assert steps == [1]
        subscription.remove()
        assert not wheel_subscribed(cells[0])
        group.dispose()
        assert str(_shared_tk_root.tk.call("bind", group.tag)) == ""
    finally:
        group.dispose()
        top.destroy()


def test_add_is_idempotent_and_sits_before_the_class_tag(_shared_tk_root):
    top, cells = _cells(_shared_tk_root, 1)
    group = PointerGroup(_shared_tk_root, "order")
    try:
        group.add(cells[0])
        group.add(cells[0])
        tags = list(cells[0].bindtags())
        assert tags.count(group.tag) == 1
        assert tags.index(group.tag) < tags.index("Label")
    finally:
        group.dispose()
        top.destroy()
