"""scrollbar_guard: one fixture per detected pattern and per allowed case."""

from __future__ import annotations

import pytest

from bw_gui.testing.scrollbar_guard import find_offenders, scrollbar_lines


@pytest.mark.parametrize(
    "code",
    [
        "bar = ttk.Scrollbar(parent)",
        "bar = tk.Scrollbar(parent, orient='vertical')",
        "bar = ui.Scrollbar(parent)",
        "bar = tkinter.Scrollbar(parent)",
        "from tkinter.ttk import Scrollbar",
        "from tkinter import Scrollbar, Frame",
    ],
)
def test_raw_scrollbars_are_found(code):
    assert scrollbar_lines(code) == [1]


@pytest.mark.parametrize(
    "code",
    ["bar = widgets.Scrollbar(parent)", "bar = tui.Scrollbar(parent, orient='horizontal')", "from tkinter import ttk"],
)
def test_the_primitive_is_allowed(code):
    assert scrollbar_lines(code) == []


def test_bw_gui_creates_no_raw_scrollbar_outside_the_primitive():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "bw_gui"
    offenders = find_offenders(src)
    assert set(offenders) <= {str(Path("bw_gui") / "runtime" / "scrollbar.py")}, offenders
