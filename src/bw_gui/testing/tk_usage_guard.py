"""AST guard for consumer apps: Tk event knowledge stays behind the bw-gui contracts.

Three levels, kept apart on purpose (plan "Aussagekraft aller Guards"):

1. **Semantic rule.** Consumer code binds no Tk event sequences and does not interpret
   Tk events or mutate selections directly. It uses the keyboard
   (``KEYBINDING_CONTRACT.md``), pointer (``POINTER_CONTRACT.md``) and widget-events
   (``WIDGET_EVENTS_CONTRACT.md``) contracts.
2. **Statically detected AST patterns** (the complete list, rule ids in brackets):

   * ``[bind]`` a call of ``bind``/``bind_all``/``bind_class``/``tag_bind``/``unbind``/
     ``unbind_all``/``unbind_class``/``tag_unbind`` whose first or second positional
     argument is a string literal starting with ``<`` (keyboard, mouse, virtual and
     lifecycle sequences alike).
   * ``[sequence]`` any other string literal that is a Tk event sequence -- a virtual
     event ``<<Name>>`` or ``<...>`` starting with a Tk event type, modifier or key name
     (``<Button-1>``, ``<Control-z>``, ``<Configure>``) -- outside docstrings, e.g.
     sequences kept in a table and bound later. Markup like ``"<td>"``/``"<br>"`` is
     not a sequence.
   * ``[break]`` ``return "break"``.
   * ``[event-field]`` reading ``.keysym``, ``.keycode``, ``.keysym_num``, ``.char`` or
     ``.delta`` (the raw Tk event fields) -- not calling them (``KeySpec.char("z")`` is
     the contract). ``event.state`` bit tests are covered by ``tk_state_guard``.
   * ``[selection]`` raw selection mutations: ``selection_set``/``select_set``/
     ``selection_add``/``selection_remove``/``selection_toggle`` (any arguments),
     ``selection_clear``/``select_clear`` *with* a range argument (the no-argument form
     clears an ``Entry``'s text selection and is allowed), ``.current(<index>)`` and
     ``.selection("set" | "add" | "remove" | "toggle", ...)``.

3. **Known false negatives/positives.**

   * False negatives: aliases (``b = widget.bind``), ``getattr``, sequences built at
     runtime (f-strings, concatenation), mutations through variables holding the bound
     method, star imports.
   * False positives: generic names on non-Tk objects (an own ``.delta`` or
     ``.char`` attribute, a ``current(i)`` method of a domain class) and literals that
     merely look like sequences (``"<b>"`` in markup).

``find_offenders(...) == {}`` means "no known, statically detectable violation", not a
formal proof of the rule; the contract and runtime tests (``router.verify()``, binder
ownership checks) back the semantic rule. A deliberate exception is marked on its line
with ``# bw-tk: <reason>``; such lines are not findings but are counted by
:func:`opt_outs` so they stay visible.

Usage in a consumer test suite::

    from bw_gui.testing.tk_usage_guard import RULE, find_offenders
    assert find_offenders(REPO_ROOT / "app") == {}, RULE
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RULE = (
    "Apps bind no Tk event sequences, do not read raw Tk event fields, never return "
    '"break" and never mutate selections directly -- use the bw-gui keyboard, pointer and '
    "widget-events contracts (opt-out per line: '# bw-tk: <reason>')."
)

OPT_OUT = "# bw-tk:"
_BIND_METHODS = frozenset(
    {"bind", "bind_all", "bind_class", "tag_bind", "unbind", "unbind_all", "unbind_class", "tag_unbind"}
)
_EVENT_FIELDS = frozenset({"keysym", "keycode", "keysym_num", "char", "delta"})
_SELECTION_ALWAYS = frozenset({"selection_set", "select_set", "selection_add", "selection_remove", "selection_toggle"})
_SELECTION_WITH_RANGE = frozenset({"selection_clear", "select_clear"})
_SELECTION_COMMANDS = frozenset({"set", "add", "remove", "toggle"})
_TK_WORDS = (
    "Key|KeyPress|KeyRelease|Button|ButtonPress|ButtonRelease|Motion|Enter|Leave|FocusIn|FocusOut|"
    "Configure|Map|Unmap|Destroy|Visibility|Expose|Activate|Deactivate|MouseWheel|Property|Circulate|"
    "Control|Alt|Shift|Lock|Command|Option|Meta|Mod[1-5]|Double|Triple|Quadruple|B[1-5]|Any|"
    "Return|Escape|Tab|BackSpace|Delete|Insert|Up|Down|Left|Right|Home|End|Prior|Next|space|"
    "KP_\\w+|F[1-9]|F1[0-2]|ISO_Left_Tab|[1-5]"
)
_SEQUENCE = re.compile(rf"^(?:<<[A-Za-z][\w-]*>>|<(?:{_TK_WORDS})(?:-[\w]+)*>)$")


def _docstring_ids(tree: ast.AST) -> set[int]:
    """``id()`` of every docstring constant (module, class, function)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _is_sequence_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(_SEQUENCE.match(node.value))


def _call_findings(node: ast.Call) -> list[str]:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return []
    name, args = func.attr, node.args
    if name in _BIND_METHODS and any(_is_sequence_literal(arg) for arg in args[:2]):
        return ["bind"]
    if name in _SELECTION_ALWAYS:
        return ["selection"]
    if name in _SELECTION_WITH_RANGE and args:
        return ["selection"]
    if name == "current" and args:
        return ["selection"]
    if name == "selection" and args and isinstance(args[0], ast.Constant) and args[0].value in _SELECTION_COMMANDS:
        return ["selection"]
    return []


def scan_source(source: str, filename: str = "<source>") -> list[tuple[int, str]]:
    """Return ``(line, rule id)`` findings in *source* (opt-out lines excluded), sorted."""
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    docstrings = _docstring_ids(tree)
    called = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    bound_literals: set[int] = set()
    findings: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            rules = _call_findings(node)
            for rule in rules:
                findings.add((node.lineno, rule))
            if "bind" in rules:
                bound_literals.update(id(arg) for arg in node.args[:2])
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value == "break":
            findings.add((node.lineno, "break"))
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in _EVENT_FIELDS
            and isinstance(node.ctx, ast.Load)
            and id(node) not in called
        ):
            findings.add((node.lineno, "event-field"))
    for node in ast.walk(tree):
        if _is_sequence_literal(node) and id(node) not in docstrings and id(node) not in bound_literals:
            findings.add((node.lineno, "sequence"))
    return sorted(
        (line, rule) for line, rule in findings if not (0 < line <= len(lines) and OPT_OUT in lines[line - 1])
    )


def _python_files(app_root: Path):
    return (path for path in sorted(app_root.rglob("*.py")) if "__pycache__" not in path.parts)


def find_offenders(app_root: Path) -> dict[str, list[tuple[int, str]]]:
    """All findings below *app_root* as ``{relative path: [(line, rule id), ...]}``."""
    result: dict[str, list[tuple[int, str]]] = {}
    for path in _python_files(app_root):
        # utf-8-sig: some consumer files start with a BOM, which ast.parse rejects.
        found = scan_source(path.read_text(encoding="utf-8-sig"), str(path))
        if found:
            result[str(path.relative_to(app_root.parent))] = found
    return result


def opt_outs(app_root: Path) -> dict[str, list[int]]:
    """Lines carrying ``# bw-tk:`` below *app_root* (deliberate, documented exceptions)."""
    result: dict[str, list[int]] = {}
    for path in _python_files(app_root):
        numbers = [i for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1) if OPT_OUT in line]
        if numbers:
            result[str(path.relative_to(app_root.parent))] = numbers
    return result
