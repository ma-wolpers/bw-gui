"""Tests for ``bw_gui.testing.line_limits`` (300-executable-line file limit)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from bw_gui.testing.line_limits import (
    check_files,
    check_repo,
    count_executable_lines,
    data_only_problem,
    parse_exceptions,
    touched_python_files,
)


def test_blank_comment_docstring_and_import_lines_do_not_count():
    """Only the two assignments and the def/return lines are executable."""
    source = '''"""Module docstring
spanning two lines."""

import os
from pathlib import (
    Path,
    PurePath,
)

# a comment
x = 1


def f():
    """Function docstring."""
    # inner comment
    return x


class C:
    """Class docstring."""

    y = 2
'''
    # x = 1 / def f(): / return x / class C: / y = 2
    assert count_executable_lines(source) == 5


def test_non_docstring_multiline_string_counts():
    """A template string is code-adjacent data and counts line by line."""
    source = 'x = 1\nTEMPLATE = """\na\nb\n"""\n'
    assert count_executable_lines(source) == 5


def test_leading_byte_order_mark_is_ignored(tmp_path):
    """Files saved with a UTF-8 BOM are counted, not rejected as unparsable."""
    assert count_executable_lines("﻿x = 1\n") == 1
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbfx = 1\n")
    assert check_files(tmp_path, ["bom.py"]) == []


def test_data_only_marker_without_logic_is_accepted():
    """A marked pure-data module has no problem."""
    assert data_only_problem("# line-limit: data-only\nVALUES = {'a': 1}\n") is None


def test_data_only_marker_with_def_is_rejected():
    """The marker cannot hide logic."""
    problem = data_only_problem("# line-limit: data-only\ndef helper():\n    return 1\n")
    assert problem is not None and "helper" in problem


def test_parse_exceptions_reads_section_and_rejects_missing_reason():
    """Bullets in the section count; a bullet without reason is a problem; the section ends at the next heading."""
    markdown = """# Doc

## Ausnahmen 300-Zeilen-Regel

- `app/big.py` — eingebettete Vorlage
- `app/naked.py`

## Andere Ueberschrift

- `app/outside.py` — gehoert nicht dazu
"""
    exceptions, problems = parse_exceptions(markdown)
    assert exceptions == {"app/big.py": "eingebettete Vorlage"}
    assert problems == ["exception for `app/naked.py` has no justification"]


def test_parse_exceptions_accepts_english_heading():
    """bw-gui's English architecture doc uses the English title."""
    exceptions, _ = parse_exceptions("### Line-limit exceptions\n- `src/x.py`: generated table\n")
    assert exceptions == {"src/x.py": "generated table"}


def _write_lines(path: Path, count: int) -> None:
    path.write_text("".join(f"v{i} = {i}\n" for i in range(count)), encoding="utf-8")


def test_check_files_limit_exception_and_syntax_error(tmp_path):
    """Over-limit files fail unless excepted; unparsable files fail."""
    _write_lines(tmp_path / "ok.py", 300)
    _write_lines(tmp_path / "big.py", 301)
    _write_lines(tmp_path / "excepted.py", 400)
    (tmp_path / "broken.py").write_text("def (:\n", encoding="utf-8")
    errors = check_files(
        tmp_path, ["ok.py", "big.py", "excepted.py", "broken.py"], {"excepted.py": "reason"}
    )
    assert len(errors) == 2
    assert errors[0].startswith("big.py: 301 executable lines")
    assert errors[1].startswith("broken.py: cannot be parsed")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_touched_files_cover_worktree_untracked_and_fall_back_to_last_commit(tmp_path):
    """Pending changes win; a clean tree falls back to the last commit's files."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("b = 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "b.py").write_text("b = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "b.py")
    _git(tmp_path, "commit", "-q", "-m", "change b")
    assert touched_python_files(tmp_path) == ["b.py"]

    (tmp_path / "a.py").write_text("a = 2\n", encoding="utf-8")
    (tmp_path / "new.py").write_text("n = 1\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x\n", encoding="utf-8")
    assert touched_python_files(tmp_path) == ["a.py", "new.py"]


def test_check_repo_reports_doc_problems_and_explicit_paths(tmp_path):
    """check_repo combines exception-section problems with file results."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "## Line-limit exceptions\n- `big.py` — template\n- `x.py`\n", encoding="utf-8"
    )
    _write_lines(tmp_path / "big.py", 350)
    _write_lines(tmp_path / "other.py", 350)
    errors = check_repo(tmp_path, "docs/ARCHITECTURE.md", paths=["big.py", "other.py"])
    assert errors[0] == "docs/ARCHITECTURE.md: exception for `x.py` has no justification"
    assert len(errors) == 2 and errors[1].startswith("other.py: 350")
