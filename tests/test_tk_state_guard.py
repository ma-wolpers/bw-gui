"""Tests for bw_gui.testing.tk_state_guard."""

from __future__ import annotations

from pathlib import Path

from bw_gui.testing.tk_state_guard import find_offenders, raw_state_bitmask_lines


def _write(tmp_path: Path, name: str, *lines: str) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_guard_detects_the_anti_pattern_only(tmp_path):
    sample = _write(
        tmp_path,
        "sample.py",
        "def f(event):",
        "    a = event.state & 0x0008",
        "    b = int(getattr(event, 'state', 0)) & 4",
        "    c = flags & 0x10",
        "    d = self.state.value",
    )
    assert raw_state_bitmask_lines(sample) == [2, 3]


def test_indirect_state_variable_is_detected_per_function(tmp_path):
    sample = _write(
        tmp_path,
        "alias.py",
        "def wheel(event):",
        "    state = getattr(event, 'state', 0)",
        "    shift = bool(state & 0x0001)",
        "",
        "def unrelated(state):",
        "    return state & 0x0001",
    )
    assert raw_state_bitmask_lines(sample) == [3]


def test_find_offenders_reports_paths_relative_to_repo(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    _write(app, "ok.py", "x = 1 & 2")
    _write(app, "bad.py", "y = e.state & 4")
    assert find_offenders(app) == {str(Path("app") / "bad.py"): [1]}


def test_files_with_utf8_bom_are_parsed(tmp_path):
    sample = tmp_path / "bom.py"
    sample.write_bytes("﻿y = e.state & 4\n".encode("utf-8"))
    assert raw_state_bitmask_lines(sample) == [1]
