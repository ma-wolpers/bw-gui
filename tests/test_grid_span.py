from bw_gui.widgets.grid_span import GridSpanSegment, compute_contiguous_spans


def test_contiguous_columns_form_a_single_segment():
    segments = compute_contiguous_spans([2, 3, 4])
    assert segments == [GridSpanSegment(start_column=2, column_span=3)]


def test_gap_produces_two_segments():
    segments = compute_contiguous_spans([1, 2, 5, 6, 7])
    assert segments == [
        GridSpanSegment(start_column=1, column_span=2),
        GridSpanSegment(start_column=5, column_span=3),
    ]


def test_unsorted_and_duplicate_input_is_normalized():
    segments = compute_contiguous_spans([4, 2, 3, 2])
    assert segments == [GridSpanSegment(start_column=2, column_span=3)]


def test_single_column_is_its_own_segment():
    assert compute_contiguous_spans([7]) == [GridSpanSegment(start_column=7, column_span=1)]


def test_empty_input_returns_no_segments():
    assert compute_contiguous_spans([]) == []
