"""AST guard for consumer apps: no raw Tk/ttk checkbuttons (``docs/TOGGLE_CONTRACT.md``, R6).

Binary controls are ``bw_gui.widgets.Checkbox`` (staged) or ``Switch`` (immediate);
binary menu entries go through ``MenuItem(type="switch"/"checkbox")`` or
``add_menu_switch``/``add_menu_checkbox``. One implementation for every consumer::

    from bw_gui.testing.checkbutton_guard import RULE, find_offenders
    assert find_offenders(REPO_ROOT / "app") == {}, RULE

Detected (per file, following that file's imports):

* ``<source>.Checkbutton(...)`` where ``<source>`` resolves to ``tkinter``,
  ``tkinter.ttk``, or bw-gui's aliases of them (``bw_gui.ui``/``widgets``,
  ``bw_gui.runtime[.primitives].ui``/``widgets``) - also as a full dotted chain.
* ``from <source> import Checkbutton [as X]`` (the import itself, plus calls to ``X``),
  including ``from bw_gui.runtime[.primitives] import Checkbutton`` (not importable
  today, flagged anyway so a later re-export opens no gap).
* ``from <source> import *`` plus bare ``Checkbutton(...)`` in that file.
* Subclassing any of the above (``class Foo(ttk.Checkbutton)``).
* ``.call("checkbutton" | "ttk::checkbutton", ...)`` with a constant string.
* ``*.add_checkbutton(...)``, ``*.insert_checkbutton(...)``,
  ``*.add("checkbutton", ...)``, ``*.insert(i, "checkbutton", ...)`` - these names are
  Tk-menu specific, so the receiver type is not analysed.

Deliberately not detected: a ``Checkbutton`` from any other module (foreign types stay
allowed), dynamic access (``getattr(ttk, "Checkbutton")``), re-exports through the
consumer's own modules, classes stored in variables, non-constant strings. Full type or
alias-flow analysis is not a goal.
"""

from __future__ import annotations

import ast
from pathlib import Path

RULE = (
    "Apps must not use raw Tk/ttk checkbuttons. Use bw_gui.widgets.Checkbox (staged, effective "
    "on submit) or Switch (immediate effect); in menus MenuItem(type='switch'/'checkbox') or "
    "bw_gui.menu.add_menu_switch/add_menu_checkbox (see docs/TOGGLE_CONTRACT.md)."
)

# Module paths whose ``Checkbutton`` attribute is Tk's / ttk's.
TK_SOURCES = frozenset({
    "tkinter", "tkinter.ttk",
    "bw_gui", "bw_gui.ui", "bw_gui.widgets",
    "bw_gui.runtime", "bw_gui.runtime.ui", "bw_gui.runtime.widgets",
    "bw_gui.runtime.primitives", "bw_gui.runtime.primitives.ui", "bw_gui.runtime.primitives.widgets",
})
_MENU_METHODS = frozenset({"add_checkbutton", "insert_checkbutton"})
_TCL_COMMANDS = frozenset({"checkbutton", "ttk::checkbutton"})


class _FileScan:
    """Import resolution and findings for one source file."""

    def __init__(self, tree: ast.AST) -> None:
        self.aliases: dict[str, str] = {}      # local name -> dotted module/attribute path
        self.checkbutton_names: set[str] = set()
        self.lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self._record_import(node)
            elif isinstance(node, ast.ImportFrom):
                self._record_import_from(node)

    def _record_import(self, node: ast.Import) -> None:
        """``import a.b`` binds ``a``; ``import a.b as x`` binds ``x`` to ``a.b``."""
        for alias in node.names:
            if alias.asname:
                self.aliases[alias.asname] = alias.name
            else:
                root = alias.name.split(".")[0]
                self.aliases[root] = root

    def _record_import_from(self, node: ast.ImportFrom) -> None:
        """``from M import n [as x]`` binds ``x`` to ``M.n``; flags Checkbutton/star imports."""
        module = node.module or ""
        if node.level:  # relative imports never reach tkinter or bw_gui
            return
        for alias in node.names:
            if alias.name == "*":
                if module in TK_SOURCES:
                    self.lines.add(node.lineno)
                    self.checkbutton_names.add("Checkbutton")
                continue
            local = alias.asname or alias.name
            self.aliases[local] = f"{module}.{alias.name}"
            if alias.name == "Checkbutton" and module in TK_SOURCES:
                self.lines.add(node.lineno)
                self.checkbutton_names.add(local)

    def dotted(self, node: ast.AST) -> str | None:
        """Resolve ``a.b.c`` through the file's imports, or ``None`` if not import-rooted."""
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self.dotted(node.value)
            return f"{base}.{node.attr}" if base else None
        return None

    def is_checkbutton(self, node: ast.AST) -> bool:
        """True if *node* names Tk's/ttk's Checkbutton class."""
        if isinstance(node, ast.Name) and node.id in self.checkbutton_names:
            return True
        path = self.dotted(node)
        if path is None or not path.endswith(".Checkbutton"):
            return False
        return path.rsplit(".", 1)[0] in TK_SOURCES


def _is_menu_checkbutton_call(node: ast.Call) -> bool:
    """``x.add_checkbutton(...)``, ``x.add("checkbutton", ...)``, ``x.call("ttk::checkbutton", ...)``."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in _MENU_METHODS:
        return True
    constants = [arg.value for arg in node.args[:2] if isinstance(arg, ast.Constant)]
    if func.attr in ("add", "insert"):
        return "checkbutton" in constants
    if func.attr == "call" and constants:
        return isinstance(node.args[0], ast.Constant) and node.args[0].value in _TCL_COMMANDS
    return False


def checkbutton_lines(path: Path) -> list[int]:
    """Line numbers in *path* that create or import a raw Tk/ttk checkbutton."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    scan = _FileScan(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (scan.is_checkbutton(node.func) or _is_menu_checkbutton_call(node)):
            scan.lines.add(node.lineno)
        elif isinstance(node, ast.ClassDef) and any(scan.is_checkbutton(base) for base in node.bases):
            scan.lines.add(node.lineno)
    return sorted(scan.lines)


def find_offenders(app_root: Path) -> dict[str, list[int]]:
    """All findings below *app_root* as ``{relative path: [line numbers]}``."""
    return {
        str(path.relative_to(app_root.parent)): lines
        for path in sorted(app_root.rglob("*.py"))
        if (lines := checkbutton_lines(path))
    }
