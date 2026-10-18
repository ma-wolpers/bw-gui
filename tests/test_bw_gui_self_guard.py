"""bw-gui guards itself (plan 2j): only the router writes ``all``, and no module binds a specific key.

Three levels (as for the consumer guards):

1. Semantic rule: keyboard matching decisions are bw-gui's alone -- the catch-all entry
   per bw-gui tag (``_key_channel``) and the ``all`` router (``key_router``) are the only
   keyboard bindings; nothing in bw-gui binds a concrete key sequence that Tk would
   match by specificity.
2. Detected patterns: ``bind_all``/``unbind_all`` calls outside ``runtime/key_router.py``;
   ``bind``/``bind_all``/``bind_class``/``tag_bind`` with a literal keyboard sequence
   (``<Return>``, ``<Control-z>``, ``<KeyPress>`` ...) anywhere.
3. Known gaps: sequences built at runtime and raw ``tk.call("bind", ...)`` are not
   detected; the catch-alls in ``_key_channel`` use exactly that form on purpose
   (``router.verify()`` and the ownership checks cover them at runtime).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "bw_gui"
ROUTER = Path("runtime") / "key_router.py"
_KEY_SEQUENCE = re.compile(
    r"<(?:(?:Control|Alt|Shift|Command|Option|Meta|Lock|Mod[1-5])-)*"
    r"(?:Key|KeyPress|KeyRelease|Return|Escape|Tab|BackSpace|Delete|Insert|Up|Down|Left|Right|Home|End|"
    r"Prior|Next|space|F\d{1,2}|KP_\w+|ISO_Left_Tab|[A-Za-z0-9])(?:-\w+)?>"
)


def _calls():
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                yield path.relative_to(SRC), node


def test_only_the_router_uses_bind_all():
    offenders = [
        f"{rel}:{node.lineno}"
        for rel, node in _calls()
        if node.func.attr in {"bind_all", "unbind_all"} and rel != ROUTER
    ]
    assert offenders == []


def test_no_module_binds_a_specific_key_sequence():
    offenders = [
        f"{rel}:{node.lineno} {arg.value}"
        for rel, node in _calls()
        if node.func.attr in {"bind", "bind_all", "bind_class", "tag_bind"}
        for arg in node.args[:2]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _KEY_SEQUENCE.fullmatch(arg.value)
    ]
    assert offenders == []
