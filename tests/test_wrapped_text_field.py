import tkinter

import pytest

from bw_gui.widgets.wrapped_text_field import WrappedTextField


def test_wrapped_text_field_left_delete_span_deletes_previous_word_and_spaces():
    assert WrappedTextField._left_delete_span("Hallo Welt") == 4
    assert WrappedTextField._left_delete_span("Hallo Welt   ") == 7


def test_wrapped_text_field_right_delete_span_deletes_next_word_and_spaces():
    assert WrappedTextField._right_delete_span("Welt hier") == 4
    assert WrappedTextField._right_delete_span("   Welt hier") == 7


def test_wrapped_text_field_str_delegates_to_container_path():
    class _FakeContainer:
        def __str__(self):
            return ".wrapped"

    wrapper = type("_FakeWrapper", (), {"_container": _FakeContainer()})()

    assert WrappedTextField.__str__(wrapper) == ".wrapped"


# --- get_raw / load / set with a real Tk root ---------------------------------------

ROUND_TRIP_CASES = [
    "", "\n", "\n\n", "a   ", "  \tx", "a\r\nb", "a\rb", "a\x00b", "a\x0bb", "a b",
    "﻿a", "x \U0001F600 y", "\U0001F469‍\U0001F4BB", "é", "\tx\t", "x" * 5000,
]


@pytest.fixture
def field(_shared_tk_root):
    """A fresh field on the shared root; destroyed after the test."""
    widget = WrappedTextField(_shared_tk_root)
    yield widget
    widget._container.destroy()


def _undo(widget: WrappedTextField) -> None:
    """Ctrl+Z equivalent; an empty undo stack makes Tk raise TclError (= nothing to undo)."""
    try:
        widget.text.edit_undo()
    except tkinter.TclError:
        pass


@pytest.mark.parametrize("value", ROUND_TRIP_CASES)
def test_get_raw_round_trips_load_and_set(field, value):
    field.load(value)
    assert field.get_raw() == value
    field.set(value)
    assert field.get_raw() == value


def test_load_cannot_be_undone(field):
    field.load("geladen")
    _undo(field)
    assert field.get_raw() == "geladen"


def test_load_resets_cursor_and_modified_flag(field):
    field.text.insert("1.0", "x")
    assert field.text.edit_modified()
    field.load("a\nb")
    assert field.text.index("insert") == "1.0"
    assert not field.text.edit_modified()


def test_undo_after_typing_returns_to_loaded_text(field):
    field.load("geladen")
    field.text.edit_separator()
    field.text.insert("end", " und getippt")
    field.text.edit_separator()
    _undo(field)
    assert field.get_raw() == "geladen"


def test_set_stays_undoable_regression(field):
    field.load("vorher")
    field.set("nachher")
    _undo(field)
    assert field.get_raw() != "nachher"


def test_get_still_strips_regression(field):
    field.load("  a  \n")
    assert field.get() == "a"
    assert field.get_raw() == "  a  \n"


def test_initial_cannot_be_undone(_shared_tk_root):
    widget = WrappedTextField(_shared_tk_root, initial="vorbelegt")
    try:
        _undo(widget)
        assert widget.get_raw() == "vorbelegt"
    finally:
        widget._container.destroy()
