"""Multi-cursor: Transaktionen als ein Undo-Schritt, Undo/Redo der Cursor, Rücknahme bei Fehlern."""

from __future__ import annotations

import pytest

from bw_gui.contracts.multicursor import Edit
from bw_gui.runtime import on_text_modified
from bw_gui.runtime.widget_events import reset_text_modified
from bw_gui.testing.keys import press_key
from multicursor_support import (  # noqa: F401  (Fixtures werden über den Namen genutzt)
    CTRL,
    _heads,
    _load,
    _three_lines,
    _type,
    _value,
    mc,
    text,
)


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
