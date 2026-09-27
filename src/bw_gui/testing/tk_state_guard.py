"""AST guard for consumer apps: never interpret Tk modifier bits (``event.state``) yourself.

Architecture principle E (``docs/ARCHITECTURE.md``): the meaning of ``event.state`` is
backend-specific (on Windows ``0x0008`` is NumLock, on X11 it is Alt) and lives only in
the keybinding contract (``bw_gui.contracts.key_modifiers``). This guard finds exactly
the anti-pattern ``<expr>.state & ...`` / ``getattr(<expr>, "state") & ...`` (also
wrapped in ``int(...)``); any other bitmask stays allowed.

One implementation for every consumer repo (test suites and CI guardrail scripts),
instead of a copy per repo::

    from bw_gui.testing.tk_state_guard import RULE, find_offenders
    assert find_offenders(REPO_ROOT / "app") == {}, RULE
"""

from __future__ import annotations

import ast
from pathlib import Path

RULE = (
    "Apps must not interpret Tk modifier bits themselves (backend-specific: on Windows "
    "0x0008 is NumLock). Use bw-gui's WindowShortcutBinder or "
    "bw_gui.contracts.modifiers_from_event()."
)


def _is_state_access(node: ast.AST) -> bool:
    """True for ``x.state``, ``int(x.state)`` and ``getattr(x, "state"[, default])``."""
    if isinstance(node, ast.Attribute) and node.attr == "state":
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
            name = node.args[1]
            return isinstance(name, ast.Constant) and name.value == "state"
        if isinstance(func, ast.Name) and func.id == "int" and node.args:
            return _is_state_access(node.args[0])
    return False


def raw_state_bitmask_lines(path: Path) -> list[int]:
    """Line numbers in *path* that evaluate ``state & ...``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
            if _is_state_access(node.left) or _is_state_access(node.right):
                lines.append(node.lineno)
    return lines


def find_offenders(app_root: Path) -> dict[str, list[int]]:
    """All findings below *app_root* as ``{relative path: [line numbers]}``."""
    return {
        str(path.relative_to(app_root.parent)): lines
        for path in sorted(app_root.rglob("*.py"))
        if (lines := raw_state_bitmask_lines(path))
    }
