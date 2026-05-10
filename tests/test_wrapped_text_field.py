from bw_gui.widgets.wrapped_text_field import WrappedTextField


def test_wrapped_text_field_left_delete_span_deletes_previous_word_and_spaces():
    assert WrappedTextField._left_delete_span("Hallo Welt") == 4
    assert WrappedTextField._left_delete_span("Hallo Welt   ") == 7


def test_wrapped_text_field_right_delete_span_deletes_next_word_and_spaces():
    assert WrappedTextField._right_delete_span("Welt hier") == 4
    assert WrappedTextField._right_delete_span("   Welt hier") == 7
