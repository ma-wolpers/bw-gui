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


def _is_state_access(node: ast.AST, aliases: frozenset[str] = frozenset()) -> bool:
    """True for ``x.state``, ``getattr(x, "state"[, default])``, ``int(...)`` of those,
    and plain names in *aliases* (local variables assigned from such an access)."""
    if isinstance(node, ast.Attribute) and node.attr == "state":
        return True
    if isinstance(node, ast.Name) and node.id in aliases:
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
            name = node.args[1]
            return isinstance(name, ast.Constant) and name.value == "state"
        if isinstance(func, ast.Name) and func.id == "int" and node.args:
            return _is_state_access(node.args[0], aliases)
    return False


def _state_aliases(scope: ast.AST) -> frozenset[str]:
    """Names assigned from a state access anywhere inside *scope*.

    Catches the indirect form ``state = getattr(event, "state", 0)`` followed by
    ``state & 0x0004`` (the pattern that hid in several consumer apps).
    """
    names: set[str] = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign) and _is_state_access(node.value):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
            and _is_state_access(node.value)
        ):
            names.add(node.target.id)
    return frozenset(names)


def raw_state_bitmask_lines(path: Path) -> list[int]:
    """Line numbers in *path* that evaluate ``state & ...`` (directly or via a local alias).

    Aliases are tracked per function (including nested functions); module-level code
    is checked with aliases from module-level statements only.
    """
    # utf-8-sig: some consumer files start with a BOM, which ast.parse rejects.
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    scopes: list[tuple[ast.AST, frozenset[str]]] = [
        (node, _state_aliases(node))
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
    ]
    module_level = ast.Module(
        body=[stmt for stmt in tree.body if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))],
        type_ignores=[],
    )
    scopes.append((tree, _state_aliases(module_level)))
    lines: set[int] = set()
    for scope, aliases in scopes:
        for node in ast.walk(scope):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
                if _is_state_access(node.left, aliases) or _is_state_access(node.right, aliases):
                    lines.add(node.lineno)
    return sorted(lines)


def find_offenders(app_root: Path) -> dict[str, list[int]]:
    """All findings below *app_root* as ``{relative path: [line numbers]}``."""
    return {
        str(path.relative_to(app_root.parent)): lines
        for path in sorted(app_root.rglob("*.py"))
        if (lines := raw_state_bitmask_lines(path))
    }
