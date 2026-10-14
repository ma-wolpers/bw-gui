"""Scroll resolver rules (nearest frame along the hierarchy, natives first, toplevel boundary)."""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui, widgets
from bw_gui.widgets.scrollable_frame import ScrollableFrame


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    _shared_tk_root.geometry("320x200+0+0")
    _shared_tk_root.update()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _rows(parent, count):
    for i in range(count):
        widgets.Label(parent, text=f"row {i}", padding=(0, 8)).pack(fill="x")


def _top(frame):
    return frame.canvas.yview()[0]


def _wheel(widget, delta=-120):
    widget.event_generate("<MouseWheel>", delta=delta)
    widget.update()


def test_inner_frame_that_fits_passes_wheel_to_outer(root):
    outer = ScrollableFrame(root)
    outer.pack(fill="both", expand=True)
    inner = ScrollableFrame(outer.content)
    inner.pack(fill="x")
    _rows(inner.content, 1)
    _rows(outer.content, 40)
    root.update()
    label = inner.content.winfo_children()[0]
    _wheel(label)
    assert _top(outer) > 0.0 and _top(inner) == 0.0


def test_overflowing_inner_frame_wins_and_does_not_chain(root):
    outer = ScrollableFrame(root)
    outer.pack(fill="both", expand=True)
    inner = ScrollableFrame(outer.content, height=60)
    inner.pack(fill="x")
    inner.canvas.configure(height=60)
    _rows(inner.content, 30)
    _rows(outer.content, 40)
    root.update()
    _wheel(inner.content.winfo_children()[0])
    assert _top(inner) > 0.0 and _top(outer) == 0.0


def test_text_in_frame_scrolls_only_itself(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    text = ui.Text(frame.content, height=3)
    text.insert("1.0", "\n".join(f"line {i}" for i in range(50)))
    text.pack()
    _rows(frame.content, 40)
    root.update()
    _wheel(text)
    assert text.yview()[0] > 0.0 and _top(frame) == 0.0


def test_wheel_on_own_scrollbar_does_not_scroll_outer_frame(root):
    outer = ScrollableFrame(root)
    outer.pack(fill="both", expand=True)
    inner = ScrollableFrame(outer.content)
    inner.pack(fill="x")
    inner.canvas.configure(height=60)
    _rows(inner.content, 30)
    _rows(outer.content, 40)
    root.update()
    assert inner._scrollbar.winfo_ismapped()
    _wheel(inner._scrollbar)
    assert _top(outer) == 0.0


def test_wheel_on_outer_padding_resolves_to_own_frame(root):
    frame = ScrollableFrame(root, padding=10)
    frame.pack(fill="both", expand=True)
    _rows(frame.content, 40)
    root.update()
    _wheel(frame)
    assert _top(frame) > 0.0


def test_popup_does_not_scroll_main_window_frame(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _rows(frame.content, 40)
    popup = ui.Toplevel(frame.content)
    label = ui.Label(popup, text="popup")
    label.pack()
    root.update()
    _wheel(label)
    assert _top(frame) == 0.0
    popup.destroy()


def test_registration_order_is_irrelevant(root):
    results = []
    for order in ("outer-first", "inner-first"):
        for child in root.winfo_children():
            child.destroy()
        holder = ui.Frame(root)
        holder.pack(fill="both", expand=True)
        if order == "outer-first":
            outer = ScrollableFrame(holder)
            inner = ScrollableFrame(outer.content)
        else:
            outer = ScrollableFrame(holder)
            inner_parent = outer.content
            inner = ScrollableFrame(inner_parent)
        outer.pack(fill="both", expand=True)
        inner.pack(fill="x")
        _rows(inner.content, 1)
        _rows(outer.content, 40)
        root.update()
        _wheel(inner.content.winfo_children()[0])
        results.append((_top(outer) > 0.0, _top(inner) == 0.0))
    assert results == [(True, True), (True, True)]


def test_widget_without_scroll_context_does_nothing(root):
    label = ui.Label(root, text="x")
    label.pack()
    root.update()
    _wheel(label)  # must simply not raise


def test_destroyed_frame_unregisters(root):
    from bw_gui.runtime.scroll_resolver import scroll_resolver_for

    frame = ScrollableFrame(root)
    paths = [str(frame), str(frame.canvas), str(frame._scrollbar)]
    resolver = scroll_resolver_for(root)
    assert all(p in resolver.frames for p in paths)
    frame.destroy()
    assert not any(p in resolver.frames for p in paths)
