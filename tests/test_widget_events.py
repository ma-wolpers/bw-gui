"""Widget-event contract: lifecycle hooks, hover and canvas items (real Tk, no OS focus needed)."""

from __future__ import annotations

import pytest

from bw_gui.runtime import (
    bind_canvas_item,
    bind_hover,
    on_destroy,
    on_focus_change,
    on_resize,
    on_tab_changed,
    on_text_modified,
    on_visibility,
    ui,
    widgets,
)


@pytest.fixture
def top(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    window.geometry("240x160+20+20")
    window.update()
    yield window
    if window.winfo_exists():
        window.destroy()


def test_on_resize_reports_own_changes_only_unless_within(top):
    frame = ui.Frame(top, width=50, height=40)
    frame.pack()
    seen, seen_within = [], []
    sub = on_resize(frame, lambda e: seen.append((e.width, e.height)))
    on_resize(top, lambda e: seen_within.append(str(e.widget)), within=True)
    top.update()
    frame.configure(width=80)
    top.update()
    assert seen[-1] == (80, 40)
    assert str(frame) in seen_within  # descendant change seen through within=True
    sub.remove()
    frame.configure(width=90)
    top.update()
    assert seen[-1] == (80, 40)


def test_within_requires_a_toplevel(top):
    with pytest.raises(ValueError):
        on_resize(ui.Frame(top), lambda e: None, within=True)


def test_on_focus_change_gained_and_lost(top):
    entry = ui.Entry(top)
    entry.pack()
    top.update()
    seen = []
    on_focus_change(entry, on_gained=lambda e: seen.append(("in", e.gained)), on_lost=lambda e: seen.append(("out", e.gained)))
    entry.event_generate("<FocusIn>")
    entry.event_generate("<FocusOut>")
    assert seen == [("in", True), ("out", False)]


def test_on_focus_change_within_sees_descendants(top):
    entry = ui.Entry(top)
    entry.pack()
    top.update()
    seen = []
    on_focus_change(top, on_gained=lambda e: seen.append(str(e.widget)), within=True)
    entry.event_generate("<FocusIn>")
    assert seen == [str(entry)]


def test_on_visibility_reports_viewable_transitions_without_duplicates(top):
    outer = ui.Frame(top)
    outer.pack()
    inner = ui.Label(outer, text="x")
    inner.pack()
    top.update()
    seen = []
    on_visibility(inner, on_shown=lambda w: seen.append("shown"), on_hidden=lambda w: seen.append("hidden"))
    assert seen == []  # registration stores the state silently
    outer.pack_forget()  # parent unmapped -> child no longer viewable
    top.update()
    outer.pack()
    top.update()
    top.withdraw()
    top.update()
    top.deiconify()
    top.update()
    assert seen == ["hidden", "shown", "hidden", "shown"]


def test_on_destroy_fires_for_the_widget_only(top):
    frame = ui.Frame(top)
    child = ui.Label(frame)
    seen = []
    sub = on_destroy(frame, lambda w: seen.append(str(w)))
    child.destroy()
    assert seen == []
    frame.destroy()
    assert seen == [str(frame)] and not sub.active


def test_on_text_modified_resets_the_flag_and_reports_every_change(top):
    text = ui.Text(top)
    text.pack()
    seen = []
    on_text_modified(text, lambda t: seen.append(t.get("1.0", "end-1c")))
    text.insert("end", "a")
    top.update()
    text.insert("end", "b")
    top.update()
    assert seen == ["a", "ab"]
    assert text.edit_modified() is False or text.edit_modified() == 0


def test_on_tab_changed(top):
    notebook = widgets.Notebook(top)
    first, second = widgets.Frame(notebook), widgets.Frame(notebook)
    notebook.add(first, text="A")
    notebook.add(second, text="B")
    notebook.pack()
    top.update()
    seen = []
    on_tab_changed(notebook, lambda e: seen.append(e.index))
    notebook.select(1)
    top.update()
    assert seen == [1]


def test_bind_hover(top):
    label = ui.Label(top, text="hover me")
    label.pack()
    top.update()
    seen = []
    bind_hover(label, on_enter=lambda e: seen.append("enter"), on_leave=lambda e: seen.append("leave"),
               on_motion=lambda e: seen.append(("move", e.x)))
    label.event_generate("<Enter>", x=1, y=1)
    label.event_generate("<Motion>", x=3, y=2)
    label.event_generate("<Leave>", x=3, y=2)
    assert seen == ["enter", ("move", 3), "leave"]


def test_bind_canvas_item_replaces_like_tag_bind(top):
    canvas = ui.Canvas(top, width=100, height=60)
    canvas.pack()
    canvas.create_rectangle(0, 0, 50, 50, fill="red", tags=("node",))
    top.update()
    seen = []
    old = bind_canvas_item(canvas, "node", on_click=lambda e: seen.append("old"))
    bind_canvas_item(canvas, "node", on_click=lambda e: seen.append("new"))
    canvas.event_generate("<ButtonPress-1>", x=10, y=10)
    canvas.event_generate("<ButtonRelease-1>", x=10, y=10)
    top.update()
    assert seen == ["new"]
    old.remove()  # replaced hook: removing it must not drop the newer one
    canvas.event_generate("<ButtonPress-1>", x=10, y=10)
    top.update()
    assert seen == ["new", "new"]
