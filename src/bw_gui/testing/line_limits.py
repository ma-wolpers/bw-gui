"""Line-limit check for every Blattwerk-family repo: at most 300 executable lines per file.

The rule (``docs/ARCHITECTURE.md`` → "Internal module layout") counts only *executable*
lines. Not counted are:

* blank lines,
* lines that hold nothing but a comment,
* docstring lines (module, class, function and async function docstrings),
* ``import``/``from ... import`` statements, over all lines they span.

Everything else counts, including lines of multi-line strings that are not docstrings
(an embedded CSS/JS template is code-adjacent data and belongs in a data module).

Two escape hatches, both explicit:

* **Data-only modules** carry the header comment ``# line-limit: data-only`` and are
  exempt entirely. The check refuses the marker on a file that defines functions or
  classes, so the marker cannot hide logic.
* **Documented exceptions** are listed in the repo's architecture document under a
  heading titled (or starting with) ``Ausnahmen 300-Zeilen-Regel`` (German docs),
  ``Line-limit exceptions`` (English docs) or ``GRENZE(dateigroesse): Benannte Ausnahmen``
  (Kursplaner, title followed by a date), either as one bullet per file::

      - `app/core/foo.py` — Begruendung, warum die Datei nicht zerlegt wird

  or as one table row per file, path in the first cell and justification in the last::

      | `app/core/foo.py` | 312 (2026-10-17) | Begruendung |

  An entry without a justification is itself an error.

One implementation for every consumer::

    from bw_gui.testing.line_limits import check_repo
    errors = check_repo(REPO_ROOT, arch_doc="docs/intern/ARCHITEKTUR.md")
    assert errors == [], "\\n".join(errors)

Command line (from any repo, with bw-gui's ``src`` on the path)::

    python -m bw_gui.testing.line_limits --repo . --arch-doc docs/ARCHITECTURE.md
    python -m bw_gui.testing.line_limits --repo . --paths a.py b.py

Without ``--paths`` the check covers the *touched* Python files (see
:func:`touched_python_files`): untouched legacy files above the limit are not reported,
because the rule applies to files a change actually edits.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

LINE_LIMIT = 300
_BOM = chr(0xFEFF)  # UTF-8 byte-order mark as decoded text
DATA_ONLY_MARKER = "# line-limit: data-only"
DEFAULT_EXCEPTION_HEADINGS = (
    "Ausnahmen 300-Zeilen-Regel",
    "Line-limit exceptions",
    "GRENZE(dateigroesse): Benannte Ausnahmen",
)

_EXCEPTION_BULLET = re.compile(r"^\s*[-*]\s+`(?P<path>[^`]+)`\s*(?:[—–:-]+\s*(?P<reason>.*))?$")
_EXCEPTION_ROW = re.compile(r"^\s*\|\s*`(?P<path>[^`]+)`\s*\|(?P<rest>.*)\|\s*$")
_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")


def _excluded_line_numbers(tree: ast.Module) -> set[int]:
    """Return the 1-based line numbers occupied by docstrings and import statements.

    Docstrings are the leading string-constant expression of a module, class or
    (async) function body -- exactly what ``ast.get_docstring`` would return. Imports
    are excluded over their full span so a parenthesised multi-line ``from x import (...)``
    counts as zero lines, matching the rule's "imports are not counted".
    """
    excluded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            excluded.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
            continue
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            excluded.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return excluded


def count_executable_lines(source: str) -> int:
    """Count the executable lines of Python ``source`` according to the line-limit rule.

    Args:
        source: Full text of a Python module.

    Returns:
        Number of lines that are neither blank, nor pure comment lines, nor part of a
        docstring, nor part of an import statement.

    A leading UTF-8 byte-order mark is ignored (Windows editors write one).

    Raises:
        SyntaxError: If ``source`` is not valid Python (a file that does not parse
            cannot be judged; the caller reports it as an error).

    Example:
        >>> count_executable_lines("'''Doc.'''\\nimport os\\n\\n# note\\nx = 1\\n")
        1

        A string literal that is not the first statement is no docstring and counts:

        >>> count_executable_lines("import os\\n'''Not a docstring.'''\\n")
        1
    """
    source = source.removeprefix(_BOM)
    excluded = _excluded_line_numbers(ast.parse(source))
    count = 0
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or number in excluded:
            continue
        count += 1
    return count


def data_only_problem(source: str) -> str | None:
    """Validate a ``# line-limit: data-only`` marker; return a problem text or ``None``.

    Returns ``None`` when the file carries no marker (nothing to validate) or when the
    marked file really holds data only, i.e. defines no function and no class anywhere.
    A marked file with logic gets a problem text, so the exemption cannot hide code.
    """
    if not has_data_only_marker(source):
        return None
    for node in ast.walk(ast.parse(source.removeprefix(_BOM))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return (
                f"marked '{DATA_ONLY_MARKER}' but defines `{node.name}` (line {node.lineno}); "
                "move the logic out or drop the marker"
            )
    return None


def has_data_only_marker(source: str) -> bool:
    """Return True if a line of ``source`` is exactly the data-only marker comment."""
    return any(line.strip() == DATA_ONLY_MARKER for line in source.splitlines())


def parse_exceptions(
    markdown: str, headings: tuple[str, ...] = DEFAULT_EXCEPTION_HEADINGS
) -> tuple[dict[str, str], list[str]]:
    """Read the documented exceptions from the architecture document.

    The section starts at the Markdown heading whose title is one of ``headings`` or starts
    with one of them followed by a space (e.g. a trailing ``(Stand 2026-08-04)``), at any
    level, and ends at the next heading of the same or a higher level. Each bullet of the
    form ``- `path` — reason`` registers one exception (``—``, ``–``, ``-`` or ``:`` may
    separate path and reason); so does each table row whose first cell is a backticked
    path, the justification being its last cell (header and separator rows have no
    backticked path and are skipped; an empty last cell is a missing justification).

    Returns:
        ``(exceptions, problems)``: ``exceptions`` maps the repo-relative POSIX path to
        its justification; ``problems`` lists bullets without a justification.
    """
    exceptions: dict[str, str] = {}
    problems: list[str] = []
    section_level: int | None = None
    for line in markdown.splitlines():
        heading_match = _HEADING.match(line)
        if heading_match:
            level = len(heading_match.group("hashes"))
            if section_level is not None and level <= section_level:
                break
            title = heading_match.group("title").strip()
            if any(title == heading or title.startswith(heading + " ") for heading in headings):
                section_level = level
            continue
        if section_level is None:
            continue
        bullet = _EXCEPTION_BULLET.match(line)
        row = None if bullet else _EXCEPTION_ROW.match(line)
        if bullet:
            path, reason = bullet.group("path"), (bullet.group("reason") or "")
        elif row:
            cells = [cell.strip() for cell in row.group("rest").split("|")]
            path, reason = row.group("path"), cells[-1]
        else:
            continue
        path = path.strip().replace("\\", "/")
        reason = reason.strip()
        if not reason:
            problems.append(f"exception for `{path}` has no justification")
            continue
        exceptions[path] = reason
    return exceptions, problems


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    """Run ``git`` in ``repo_root`` and return the non-empty output lines (``[]`` on failure)."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(repo_root), check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def touched_python_files(repo_root: Path) -> list[str]:
    """Return the repo-relative ``.py`` files a pending change touches.

    "Touched" means: modified or added against ``HEAD`` (staged or not) plus untracked,
    non-ignored files -- the state just before a commit. If the working tree is clean
    (e.g. in CI after the commit), the files of the last commit are used instead, so
    the check still covers the newest change. Deleted files are skipped.
    """
    root = Path(repo_root)
    names = set(_git_lines(root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD"))
    names.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    if not names:
        names = set(_git_lines(root, "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD"))
    return sorted(name for name in names if name.endswith(".py") and (root / name).is_file())


def check_files(
    repo_root: Path,
    rel_paths: list[str],
    exceptions: dict[str, str] | None = None,
    limit: int = LINE_LIMIT,
) -> list[str]:
    """Check ``rel_paths`` against the limit; return one error text per violation.

    A file passes if it has at most ``limit`` executable lines, is a valid data-only
    module, or is listed in ``exceptions``. Unparsable files are errors.
    """
    exceptions = exceptions or {}
    errors: list[str] = []
    for rel_path in rel_paths:
        posix = rel_path.replace("\\", "/")
        source = (Path(repo_root) / posix).read_text(encoding="utf-8-sig")
        try:
            problem = data_only_problem(source)
            if has_data_only_marker(source):
                if problem:
                    errors.append(f"{posix}: {problem}")
                continue
            count = count_executable_lines(source)
        except SyntaxError as exc:
            errors.append(f"{posix}: cannot be parsed ({exc.msg}, line {exc.lineno})")
            continue
        if count > limit and posix not in exceptions:
            errors.append(
                f"{posix}: {count} executable lines (limit {limit}); split it by "
                "responsibility or document a justified exception"
            )
    return errors


def check_repo(
    repo_root: Path,
    arch_doc: str,
    paths: list[str] | None = None,
    headings: tuple[str, ...] = DEFAULT_EXCEPTION_HEADINGS,
    limit: int = LINE_LIMIT,
) -> list[str]:
    """Check a repo: touched files (or ``paths``) against the limit and the exception list.

    Args:
        repo_root: Repository root directory.
        arch_doc: Repo-relative path of the architecture document holding the
            exception section; a missing document means "no exceptions".
        paths: Explicit repo-relative files; ``None`` checks :func:`touched_python_files`.
        headings: Accepted titles of the exception section.
        limit: Maximum executable lines.

    Returns:
        All error texts (empty list = pass), exception-section problems first.
    """
    root = Path(repo_root)
    doc_path = root / arch_doc
    markdown = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    exceptions, problems = parse_exceptions(markdown, headings)
    errors = [f"{arch_doc}: {problem}" for problem in problems]
    targets = touched_python_files(root) if paths is None else paths
    errors.extend(check_files(root, targets, exceptions, limit))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; exit code 0 = pass, 2 = violations."""
    parser = argparse.ArgumentParser(description="Check the 300-executable-line file limit.")
    parser.add_argument("--repo", default=".", help="repository root (default: current directory)")
    parser.add_argument("--arch-doc", default="docs/ARCHITECTURE.md", help="doc with the exception section")
    parser.add_argument("--paths", nargs="*", default=None, help="explicit files instead of touched files")
    args = parser.parse_args(argv)
    errors = check_repo(Path(args.repo), args.arch_doc, args.paths)
    if errors:
        print("Line-limit check failed:")
        for error in errors:
            print(f" - {error}")
        return 2
    print("Line-limit check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
