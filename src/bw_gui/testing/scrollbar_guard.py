"""AST guard for consumer apps: scrollbars only through the bw-gui primitive.

Three levels:

1. **Semantic rule.** Every scrollbar of an app is the bw-gui primitive
   (``bw_gui.runtime.widgets.Scrollbar``: native, themed, dark mode on Windows;
   ``SCROLLABILITY_CONTRACT.md``). No app creates a ``ttk.Scrollbar`` (clam scrollbar with
   arrow buttons) or a raw ``tk.Scrollbar`` it would have to colour itself.
2. **Detected patterns:** a call ``<name>.Scrollbar(...)`` where ``<name>`` is ``tk``,
   ``tkinter``, ``ttk`` or ``ui`` (bw-gui's alias of ``tkinter``), and ``Scrollbar`` imported
   by name from ``tkinter``/``tkinter.ttk``. ``widgets.Scrollbar`` and its aliases (e.g.
   ``tui``) are the primitive and allowed.
3. **Known gaps:** other aliases of ``tkinter`` (``import tkinter as t``), ``getattr`` and
   scrollbars created by third-party widgets (e.g. a combobox popdown, which ttk styles)
   are not detected.

``find_offenders(app_root) == {}`` means "no known, statically detectable violation".
"""

from __future__ import annotations

import ast
from pathlib import Path

RULE = (
    "Apps create scrollbars only as bw_gui.runtime.widgets.Scrollbar (native, themed, dark mode on "
    "Windows) -- never ttk.Scrollbar or a raw tk/ui.Scrollbar."
)

_RAW_NAMESPACES = frozenset({"tk", "tkinter", "ttk", "ui"})
_RAW_MODULES = frozenset({"tkinter", "tkinter.ttk"})


def scrollbar_lines(source: str) -> list[int]:
    """Line numbers of raw scrollbar creations/imports in *source*."""
    tree = ast.parse(source)
    lines: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "Scrollbar"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in _RAW_NAMESPACES
        ):
            lines.add(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module in _RAW_MODULES:
            if any(alias.name == "Scrollbar" for alias in node.names):
                lines.add(node.lineno)
    return sorted(lines)


def find_offenders(app_root: Path) -> dict[str, list[int]]:
    """All findings below *app_root* as ``{relative path: [line numbers]}``."""
    result: dict[str, list[int]] = {}
    for path in sorted(app_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        found = scrollbar_lines(path.read_text(encoding="utf-8-sig"))
        if found:
            result[str(path.relative_to(app_root.parent))] = found
    return result
