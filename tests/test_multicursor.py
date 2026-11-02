"""Multi-cursor controller on a real ``Text``: gestures, keys, transactions, undo, drawing."""

from __future__ import annotations

import pytest

from bw_gui.contracts.multicursor import Edit, Region
from bw_gui.runtime import attach_multicursor, on_text_modified, ui
from bw_gui.runtime.widget_events import reset_text_modified
from bw_gui.testing.keys import press_key

CTRL, SHIFT = 0x4, 0x1
BUTTON1 = 0x100


@pytest.fixture
def text(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    top.geometry("500x300+30+30")
    widget = ui.Text(top, undo=True, wrap="word", font=("Courier", 10), width=50, height=10)
    widget.pack(fill="both", expand=True)
    top.update()
    yield widget
    top.destroy()


@pytest.fixture
def mc(text):
    return attach_multicursor(text)


def _load(text, content):
    text.delete("1.0", "end")
    text.insert("1.0", content)
    text.edit_reset()
    text.update()


def _value(text):
    return text.get("1.0", "end-1c")


def _click(text, index, state=CTRL):
    text.see(index)
    x, y, _w, height = text.bbox(index)
    text.event_generate("<ButtonPress-1>", x=x + 1, y=y + height // 2, state=state)
    text.event_generate("<ButtonRelease-1>", x=x + 1, y=y + height // 2, state=state | BUTTON1)
    text.update()


def _drag(text, start, end, state=CTRL):
    x1, y1, _w, h1 = text.bbox(start)
    x2, y2, _w, h2 = text.bbox(end)
    text.event_generate("<ButtonPress-1>", x=x1 + 1, y=y1 + h1 // 2, state=state)
    text.event_generate("<B1-Motion>", x=x2 + 1, y=y2 + h2 // 2, state=state | BUTTON1)
    text.event_generate("<ButtonRelease-1>", x=x2 + 1, y=y2 + h2 // 2, state=state | BUTTON1)
    text.update()


def _type(text, chars):
    for char in chars:
        press_key(text, char, char=char)
    text.update()


def _heads(mc):
    return [region.head for region in mc.regions]


def _three_lines(text, mc):
    """Three carets at the start of the lines ``aaa``, ``bbb``, ``ccc``."""
    _load(text, "aaa\nbbb\nccc\n")
    text.mark_set("insert", "1.0")
    _click(text, "2.0")
    _click(text, "3.0")


def test_ctrl_click_adds_a_cursor_and_typing_writes_at_all(text, mc):
    _three_lines(text, mc)
    assert mc.is_active() and _heads(mc) == [0, 4, 8]
    _type(text, "XY")
    assert _value(text) == "XYaaa\nXYbbb\nXYccc\n"
    assert _heads(mc) == [2, 8, 14]


def test_ctrl_click_on_an_existing_cursor_removes_it_but_never_the_last(text, mc):
    _three_lines(text, mc)
    _click(text, "2.0")
    assert _heads(mc) == [0, 8]
    _click(text, "3.0")
    assert not mc.is_active() and text.index("insert") == "1.0"


def test_ctrl_click_on_the_only_native_cursor_stays_inactive(text, mc):
    _load(text, "abc\n")
    text.mark_set("insert", "1.1")
    _click(text, "1.1")
    assert not mc.is_active() and text.index("insert") == "1.1"


def test_native_selection_becomes_a_region_on_the_first_ctrl_click(text, mc):
    _load(text, "hello world\nsecond\n")
    text.tag_add("sel", "1.0", "1.5")
    text.mark_set("insert", "1.5")
    _click(text, "2.0")
    assert mc.is_active() and [(r.start, r.end) for r in mc.regions] == [(0, 5), (12, 12)]
    assert not text.tag_ranges("sel") and text.tag_ranges("mc_sel")
    _type(text, "Z")
    assert _value(text) == "Z world\nZsecond\n"


def test_ctrl_drag_adds_a_second_selection_without_native_selection(text, mc):
    _load(text, "hello world\nsecond line\n")
    text.tag_add("sel", "1.0", "1.5")
    text.mark_set("insert", "1.5")
    _drag(text, "2.0", "2.6")
    assert [(r.start, r.end) for r in mc.regions] == [(0, 5), (12, 18)]
    _type(text, "#")
    assert _value(text) == "# world\n# line\n"


def test_drag_over_an_existing_selection_merges(text, mc):
    _load(text, "0123456789\n")
    text.mark_set("insert", "1.9")
    _drag(text, "1.1", "1.4")
    _drag(text, "1.3", "1.6")
    assert [(r.start, r.end) for r in mc.regions] == [(1, 6), (9, 9)]


def test_plain_click_ends_the_mode(text, mc):
    _three_lines(text, mc)
    _click(text, "1.2", state=0)
    assert not mc.is_active() and mc.view.visible_bars() == 0


def test_escape_keeps_the_primary_region(text, mc):
    _three_lines(text, mc)
    assert mc.handle_escape() is True
    assert not mc.is_active() and text.index("insert") == "3.0"
    assert mc.handle_escape() is False


def test_cursor_inside_a_selection_is_swallowed_and_on_the_edge_stays(text, mc):
    _load(text, "abcdefgh\n")
    text.mark_set("insert", "1.2")
    _drag(text, "1.2", "1.6")
    assert [(r.start, r.end) for r in mc.regions] == [(2, 2), (2, 6)]
    _click(text, "1.8")
    _type(text, "x")
    assert _value(text) == "abxxghx\n"


def test_arrows_move_from_the_head_and_drop_the_selection(text, mc):
    _load(text, "abcdefgh\nabcdefgh\n")
    text.tag_add("sel", "1.1", "1.3")
    text.mark_set("insert", "1.3")
    _click(text, "2.0")
    press_key(text, "Right")
    assert [(r.anchor, r.head) for r in mc.regions] == [(4, 4), (10, 10)]
    press_key(text, "Left")
    assert _heads(mc) == [3, 9]


def test_shift_arrows_extend_every_region_from_its_anchor(text, mc):
    _load(text, "abcdefgh\nabcdefgh\n")
    text.mark_set("insert", "1.2")
    _click(text, "2.2")
    press_key(text, "Right", state=SHIFT)
    press_key(text, "Right", state=SHIFT)
    assert [(r.anchor, r.head) for r in mc.regions] == [(2, 4), (11, 13)]
    press_key(text, "Left", state=SHIFT)
    assert [(r.anchor, r.head) for r in mc.regions] == [(2, 3), (11, 12)]


def test_up_down_keep_the_goal_column_across_short_lines(text, mc):
    _load(text, "abcdefgh\nab\nabcdefgh\n\nabcdefgh\nab\nabcdefgh\n")
    text.mark_set("insert", "1.6")
    _click(text, "5.6")
    press_key(text, "Down")
    assert [text.index(f"1.0 + {head} chars") for head in _heads(mc)] == ["2.2", "6.2"]
    press_key(text, "Down")
    assert [text.index(f"1.0 + {head} chars") for head in _heads(mc)] == ["3.6", "7.6"]


def test_home_end_work_per_region(text, mc):
    _load(text, "abcd\nefgh\n")
    text.mark_set("insert", "1.2")
    _click(text, "2.2")
    press_key(text, "End")
    assert [text.index(f"1.0 + {head} chars") for head in _heads(mc)] == ["1.4", "2.4"]
    press_key(text, "Home", state=SHIFT)
    assert [(text.index(f"1.0 + {r.anchor} chars"), text.index(f"1.0 + {r.head} chars")) for r in mc.regions] == [("1.4", "1.0"), ("2.4", "2.0")]


def test_add_cursor_above_and_below(text, mc):
    _load(text, "abcd\nabcd\nabcd\nabcd\n")
    text.mark_set("insert", "2.2")
    mc.add_cursor(1)
    mc.add_cursor(-1)
    assert [text.index(f"1.0 + {head} chars") for head in _heads(mc)] == ["1.2", "2.2", "3.2"]


def test_backspace_and_delete_on_empty_lines_and_line_ends(text, mc):
    _load(text, "ab\n\ncd\n")
    text.mark_set("insert", "2.0")
    _click(text, "1.2")
    press_key(text, "BackSpace")
    text.update()
    assert _value(text) == "a\ncd\n"
    assert not mc.is_active() and text.index("insert") == "1.1"  # beide Cursor fielen zusammen


def test_delete_merges_across_regions(text, mc):
    _load(text, "abcd\nefgh\n")
    text.mark_set("insert", "1.1")
    _click(text, "2.1")
    press_key(text, "Delete")
    assert _value(text) == "acd\negh\n"


def test_enter_and_tab_write_at_every_cursor(text, mc):
    _load(text, "ab\ncd\n")
    text.mark_set("insert", "1.1")
    _click(text, "2.1")
    press_key(text, "Tab")
    press_key(text, "Return")
    assert _value(text) == "a\t\nb\nc\t\nd\n"


def test_emoji_are_never_split(text, mc):
    _load(text, "a😀b\nc😀d\n")
    text.mark_set("insert", "1.0 + 2 chars")
    mc.add_cursor(1)
    assert text.get("1.0", "end-1c") == "a😀b\nc😀d\n" and mc.is_active()
    press_key(text, "BackSpace")
    assert _value(text) == "ab\ncd\n"
    _type(text, "😀")
    assert _value(text) == "a😀b\nc😀d\n"
    press_key(text, "Left")
    press_key(text, "Delete")
    assert _value(text) == "ab\ncd\n"


def test_copy_cut_paste_distribute_lines(text, mc):
    _load(text, "one two\nthree four\n")
    text.tag_add("sel", "1.0", "1.3")
    text.mark_set("insert", "1.3")
    _drag(text, "2.0", "2.5")
    press_key(text, "c", state=CTRL)
    assert text.clipboard_get() == "one\nthree"
    press_key(text, "x", state=CTRL)
    assert _value(text) == " two\n four\n"
    press_key(text, "v", state=CTRL)
    assert _value(text) == "one two\nthree four\n"
    text.clipboard_clear()
    text.clipboard_append("Q")
    press_key(text, "v", state=CTRL)
    assert _value(text) == "oneQ two\nthreeQ four\n"


def test_transaction_over_three_regions_is_one_undo_step_and_restores_cursors(text, mc):
    _three_lines(text, mc)
    before = _heads(mc)
    _type(text, "X")
    after = _heads(mc)
    press_key(text, "z", state=CTRL)
    assert _value(text) == "aaa\nbbb\nccc\n" and _heads(mc) == before and mc.is_active()
    press_key(text, "y", state=CTRL)
    assert _value(text) == "Xaaa\nXbbb\nXccc\n" and _heads(mc) == after


def test_undo_reactivates_the_mode_after_it_was_left(text, mc):
    _three_lines(text, mc)
    before = _heads(mc)
    _type(text, "X")
    mc.exit()
    text.edit_separator()
    text.insert("insert", "plain")
    text.edit_separator()
    press_key(text, "z", state=CTRL)
    assert "plain" not in _value(text) and not mc.is_active()
    press_key(text, "z", state=CTRL)
    assert _value(text) == "aaa\nbbb\nccc\n" and mc.is_active() and _heads(mc) == before


def test_plain_undo_stays_native(text, mc):
    _load(text, "abc")
    text.edit_separator()
    text.insert("end", "d")
    press_key(text, "z", state=CTRL)
    assert _value(text) == "abc" and not mc.is_active()


def test_new_input_after_undo_empties_redo_and_no_record_applies(text, mc):
    _three_lines(text, mc)
    _type(text, "X")
    press_key(text, "z", state=CTRL)
    _type(text, "Y")
    text_after = _value(text)
    regions_after = mc.regions
    press_key(text, "y", state=CTRL)
    assert _value(text) == text_after and mc.regions == regions_after


def test_reset_history_clears_records_and_the_undo_stack(text, mc):
    _three_lines(text, mc)
    _type(text, "X")
    mc.reset_history()
    assert not mc.is_active()
    press_key(text, "z", state=CTRL)
    assert _value(text) == "Xaaa\nXbbb\nXccc\n" and not mc.is_active()


def test_failing_edit_rolls_the_transaction_back(text, mc, monkeypatch):
    _three_lines(text, mc)
    regions = mc.regions
    previous = text.cget("autoseparators")
    original = mc.surface.apply_one
    calls = []

    def failing(edit):
        calls.append(edit)
        if len(calls) == 2:
            raise RuntimeError("boom")
        original(edit)

    monkeypatch.setattr(mc.surface, "apply_one", failing)
    with pytest.raises(RuntimeError):
        mc.run_on_regions(lambda region: Edit(region.head, region.head, "X"))
    assert _value(text) == "aaa\nbbb\nccc\n"
    assert str(text.cget("autoseparators")) == str(previous)
    assert mc.regions == regions
    monkeypatch.undo()
    press_key(text, "z", state=CTRL)  # kein Historieneintrag: bleibt normales Tk-Undo


def test_failure_after_the_delete_of_an_edit_is_rolled_back(text, mc, monkeypatch):
    # Früher zählte nur ein ganz angewandtes Edit: gelang das delete und scheiterte
    # das insert, blieb der gelöschte Text weg.
    _three_lines(text, mc)

    def failing_insert(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(text, "insert", failing_insert)
    with pytest.raises(RuntimeError):
        mc.surface.transact([Edit(0, 3, "XYZ")])
    monkeypatch.undo()
    assert _value(text) == "aaa\nbbb\nccc\n"


def test_failure_on_the_first_edit_does_not_undo_an_earlier_step(text, mc, monkeypatch):
    _three_lines(text, mc)
    _type(text, "X")
    monkeypatch.setattr(mc.surface, "apply_one", lambda _edit: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        mc.run_on_regions(lambda region: Edit(region.head, region.head, "Y"))
    assert _value(text) == "Xaaa\nXbbb\nXccc\n"


def test_transaction_reports_one_modified_event_with_the_final_text(text, mc):
    _three_lines(text, mc)
    text.update()
    seen = []
    on_text_modified(text, lambda widget: seen.append(_value(widget)))
    reset_text_modified(text)
    text.update()
    _type(text, "X")
    text.update()
    assert seen == ["Xaaa\nXbbb\nXccc\n"]


def test_foreign_change_ends_the_mode(text, mc):
    _three_lines(text, mc)
    text.insert("1.0", "foreign")
    assert mc.sync() is False and not mc.is_active() and mc.view.visible_bars() == 0
    assert press_key(text, "a", char="a") is False


def test_apply_per_region_marks_selections_and_types_at_carets(text, mc):
    _load(text, "foo bar\n")
    text.tag_add("sel", "1.0", "1.3")
    text.mark_set("insert", "1.3")
    _click(text, "1.7")

    def plan(region):
        selected = text.get(mc.surface.index(region.start), mc.surface.index(region.end))
        return Edit(region.start, region.end, f"*{selected}*", select=(1, 1 + len(selected)))

    assert mc.apply_per_region(plan, caret_text="*") is True
    assert _value(text) == "*foo* bar*\n"
    assert [(r.start, r.end) for r in mc.regions] == [(1, 4), (10, 10)]
    assert mc.apply_per_region(lambda _r: None, caret_text="!") is False
    assert _value(text) == "*foo* bar*\n"


def test_bars_follow_scrolling_and_the_original_scroll_command_keeps_working(text, mc, _shared_tk_root):
    calls = []
    text.configure(yscrollcommand=lambda first, last: calls.append((first, last)))
    original = str(text.cget("yscrollcommand"))
    _load(text, "\n".join(f"line {n}" for n in range(200)))
    text.mark_set("insert", "1.0")
    _click(text, "2.0")
    assert mc.view.visible_bars() == 1 and str(text.cget("yscrollcommand")) != original
    calls.clear()
    text.yview_moveto(1.0)
    text.update()
    assert calls and mc.view.visible_bars() == 0  # Zeile außerhalb des Sichtbereichs
    text.yview_moveto(0.0)
    text.update()
    assert mc.view.visible_bars() == 1
    wrapper = str(text.cget("yscrollcommand"))
    mc.exit()
    assert str(text.cget("yscrollcommand")) == original
    assert not text.tk.call("info", "commands", wrapper)


def test_bar_sits_on_empty_lines_and_line_ends(text, mc):
    _load(text, "abc\n\nxyz\nabc\n")
    text.mark_set("insert", "1.3")
    _click(text, "3.0")
    assert mc.view.visible_bars() == 1
    press_key(text, "Down")
    text.update()
    assert text.index(f"1.0 + {_heads(mc)[0]} chars") == "2.0" and mc.view.visible_bars() == 1


def test_page_keys_and_ctrl_arrows_leave_the_mode_for_native_motion(text, mc):
    _three_lines(text, mc)
    assert press_key(text, "Next") is False and not mc.is_active()
    _three_lines(text, mc)
    assert press_key(text, "Right", state=CTRL) is False and not mc.is_active()


def test_regions_are_public_read_only_values(text, mc):
    _three_lines(text, mc)
    assert all(isinstance(region, Region) for region in mc.regions)


def test_consumer_shortcut_with_applies_when_leaves_the_key_to_the_controller(text, mc):
    """A consumer shortcut sharing a key declares `applies_when`, so it does not count as executed."""
    from bw_gui.contracts.key_spec import KeySpec
    from bw_gui.runtime import WidgetShortcutBinder

    binder = WidgetShortcutBinder(text)
    binder.bind(
        KeySpec.parse("Down"), lambda _e: None, binding_id="consumer.down", intent="consumer.down",
        allow_when_text_input=True, applies_when=lambda _e: not mc.is_active(),
    )
    _load(text, "abc\nabc\nabc\n")
    text.mark_set("insert", "1.1")
    _click(text, "2.1")
    assert press_key(text, "Down") is True
    assert [text.index(f"1.0 + {head} chars") for head in _heads(mc)] == ["2.1", "3.1"]
