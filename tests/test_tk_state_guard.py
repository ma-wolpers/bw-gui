"""Tests for bw_gui.testing.tk_state_guard."""

from __future__ import annotations

from pathlib import Path

from bw_gui.testing.tk_state_guard import find_offenders, raw_state_bitmask_lines


def test_guard_detects_the_anti_pattern_only(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f(event):\n"
        "    a = event.state & 0x0008\n"
        "    b = int(getattr(event, 'state', 0)) & 4\n"
        "    c = flags & 0x10\n"
        "    d = self.state.value\n",
        encoding="utf-8",
    )
    assert raw_state_bitmask_lines(sample) == [2, 3]


def test_find_offenders_reports_paths_relative_to_repo(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "ok.py").write_text("x = 1 & 2\n", encoding="utf-8")
    (app / "bad.py").write_text("y = e.state & 4\n", encoding="utf-8")
    assert find_offenders(app) == {str(Path("app") / "bad.py"): [1]}
