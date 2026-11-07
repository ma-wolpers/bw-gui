"""Exact-modifier Space activation for ttk button classes (private, shared by all bw-gui choice controls).

Tk's class bindings ``TCheckbutton <Key-space>`` and ``TRadiobutton <Key-space>`` use
Tk's minimum-set matching, so they also activate on Ctrl+Space / Alt+Space (and
Cmd+Space on aqua). bw-gui's keyboard contract makes modifiers exact: only Space
(Shift tolerated, as Tk always did) activates a choice control. A more specific class
binding with a no-op script wins inside the class tag (Tk runs the most specific
binding per tag); it does not ``break``, so the key still reaches window and
application shortcuts (e.g. Ctrl+Space = "all").

Example: a correction view binds Space = "this person finished" and Ctrl+Space =
"everybody finished" as application shortcuts. With the focus on the "finished"
switch, Tk's own ``<Key-space>`` used to fire for Ctrl+Space as well and toggled the
focused switch instead.
"""

from __future__ import annotations

import tkinter as tk

_EXACT_SPACE_MODIFIERS = ("Control", "Alt")
_EXACT_SPACE_MODIFIERS_AQUA = ("Command", "Option")
_NO_OP_SCRIPT = "# bw-gui: modified Space is not a toggle activation (exact modifiers)"


def install_exact_space_activation(widget: tk.Misc, class_tag: str) -> None:
    """Make Space with Ctrl/Alt (aqua: Cmd/Option) no activation for *class_tag*, once per interpreter.

    The class tag is shared by all widgets of that ttk class; in bw-gui apps these are
    only bw-gui's own controls (``Checkbox``/``Switch`` for ``TCheckbutton``,
    ``RadioGroup`` for ``TRadiobutton``). Existing bindings are left untouched, so
    repeated calls are cheap no-ops.

    Args:
        widget: Any widget of the interpreter (used for the Tcl calls only).
        class_tag: ttk class tag, e.g. ``"TCheckbutton"`` or ``"TRadiobutton"``.
    """
    modifiers = _EXACT_SPACE_MODIFIERS
    if str(widget.tk.call("tk", "windowingsystem")) == "aqua":
        modifiers = modifiers + _EXACT_SPACE_MODIFIERS_AQUA
    for modifier in modifiers:
        sequence = f"<{modifier}-Key-space>"
        if not str(widget.tk.call("bind", class_tag, sequence)):
            widget.tk.call("bind", class_tag, sequence, _NO_OP_SCRIPT)
