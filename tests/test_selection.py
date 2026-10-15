"""Selection hooks and mutations per widget type, ``cause``, de-duplication and ``on_activate``."""

from __future__ import annotations

import pytest

from bw_gui.contracts.events import EventResult
from bw_gui.contracts.widget_events import ActivateSource, SelectionCause
from bw_gui.runtime import (
    combobox_selection,
    listbox_selection,
    on_activate,
    on_combobox_select,
    on_listbox_select,
    on_treeview_select,
    treeview_selection,
    ui,
    widgets,
)
from bw_gui.testing.keys import press_key


@pytest.fixture
def top(_shared_tk_root):
    window = ui.Toplevel(_shared_tk_root)
    window.geometry("260x220+20+20")
    window.update()
    yield window
    if window.winfo_exists():
        window.destroy()


def _listbox(top, *, exportselection=False):
    listbox = ui.Listbox(top, exportselection=exportselection)
    for item in ("a", "b", "c"):
        listbox.insert("end", item)
    listbox.pack()
    top.update()
    return listbox


def _row_y(listbox, index):
    x, y, w, h = listbox.bbox(index)
    return y + h // 2


def test_listbox_user_click_reports_user_and_dedupes(top):
    listbox = _listbox(top)
    seen = []
    on_listbox_select(listbox, lambda c: seen.append((c.indices, c.previous, c.cause)))
    for _ in range(2):
        listbox.event_generate("<ButtonPress-1>", x=5, y=_row_y(listbox, 1))
        listbox.event_generate("<ButtonRelease-1>", x=5, y=_row_y(listbox, 1))
        top.update()
    assert seen == [((1,), (), SelectionCause.USER)]


def test_listbox_mutation_notify_false_is_silent_true_reports_programmatic(top):
    listbox = _listbox(top)
    seen = []
    on_listbox_select(listbox, lambda c: seen.append((c.indices, c.cause)))
    listbox_selection.set(listbox, [2])
    top.update()
    assert seen == [] and listbox.curselection() == (2,)
    listbox_selection.set(listbox, [0], notify=True)
    assert seen == [((0,), SelectionCause.PROGRAMMATIC)]
    listbox_selection.clear(listbox)
    assert listbox.curselection() == ()


def test_listbox_export_lost(top):
    """With exportselection, another widget taking the X selection clears the listbox (Tk reports it)."""
    listbox = _listbox(top, exportselection=True)
    entry = ui.Entry(top)
    entry.pack()
    top.update()
    seen = []
    on_listbox_select(listbox, lambda c: seen.append((c.indices, c.cause)))
    listbox.event_generate("<ButtonPress-1>", x=5, y=_row_y(listbox, 0))
    listbox.event_generate("<ButtonRelease-1>", x=5, y=_row_y(listbox, 0))
    top.update()
    entry.insert(0, "xyz")
    entry.selection_range(0, "end")  # takes the X selection
    top.update()
    assert seen == [((0,), SelectionCause.USER), ((), SelectionCause.EXPORT_LOST)]


def _tree(top):
    tree = widgets.Treeview(top, show="tree")
    for iid in ("x", "y", "z"):
        tree.insert("", "end", iid=iid, text=iid)
    tree.pack()
    top.update()
    return tree


def test_treeview_mutation_suppresses_tks_queued_event_or_reports_programmatic(top):
    tree = _tree(top)
    seen = []
    on_treeview_select(tree, lambda c: seen.append((c.item_ids, c.cause)))
    treeview_selection.set(tree, ["y"])
    top.update()
    assert seen == []
    treeview_selection.set(tree, ["z"], notify=True)
    top.update()
    assert seen == [(("z",), SelectionCause.PROGRAMMATIC)]
    treeview_selection.clear(tree)
    top.update()
    assert seen == [(("z",), SelectionCause.PROGRAMMATIC)] and tree.selection() == ()


def test_treeview_content_change_and_user_click(top):
    tree = _tree(top)
    seen = []
    on_treeview_select(tree, lambda c: seen.append((c.item_ids, c.cause)))
    x, y, _w, h = tree.bbox("x")
    tree.event_generate("<ButtonPress-1>", x=x + 5, y=y + h // 2)
    tree.event_generate("<ButtonRelease-1>", x=x + 5, y=y + h // 2)
    top.update()
    assert seen[-1] == (("x",), SelectionCause.USER)
    top.after(50)
    top.update()
    tree.delete("x")
    top.update()
    assert seen[-1] == ((), SelectionCause.CONTENT_CHANGED)


def test_combobox_pick_and_programmatic(top):
    combo = widgets.Combobox(top, values=("eins", "zwei"), state="readonly")
    combo.pack()
    top.update()
    seen = []
    on_combobox_select(combo, lambda c: seen.append((c.index, c.value, c.cause)))
    combo.current(1)
    combo.event_generate("<<ComboboxSelected>>")
    combo.event_generate("<<ComboboxSelected>>")  # same pick again: de-duplicated
    combobox_selection.set_index(combo, 0)
    combobox_selection.set_value(combo, "frei", notify=True)
    assert seen == [(1, "zwei", SelectionCause.USER), (None, "frei", SelectionCause.PROGRAMMATIC)]


def test_on_activate_enter_and_double_click_on_element(top):
    tree = _tree(top)
    tree.focus("y")
    seen = []
    on_activate(tree, lambda e: seen.append((e.source, e.element)) or EventResult.HANDLED)
    assert press_key(tree, "Return", char="\r") is True
    x, y, _w, h = tree.bbox("z")

    def _double_click(cy):  # second press within Tk's multi-click time = Double-ButtonPress-1
        tree.event_generate("<ButtonPress-1>", x=x + 5, y=cy)
        tree.event_generate("<ButtonRelease-1>", x=x + 5, y=cy)
        tree.event_generate("<ButtonPress-1>", x=x + 5, y=cy)
        tree.event_generate("<ButtonRelease-1>", x=x + 5, y=cy)

    _double_click(y + h // 2)
    top.after(600)  # leave the multi-click window
    _double_click(200)  # empty space: no activation
    assert seen == [(ActivateSource.KEY, "y"), (ActivateSource.DOUBLE_CLICK, "z")]
