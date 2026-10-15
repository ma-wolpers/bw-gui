"""Headless key presses through the bw-gui dispatch chain (test helper for consumer apps).

Real ``event_generate`` key events need OS keyboard focus, so focus-free tests cannot
use them. :func:`press_key` instead walks the widget's bindtags in Tk order and, for
every tag that carries a bw-gui keyboard catch-all (``KEYBINDING_CONTRACT.md``,
decision 25), calls exactly the dispatcher that Tk itself would call for that tag.
Processing stops at the first dispatcher that reports ``HANDLED`` -- the same rule
the Tcl prefix implements with ``break``.

Limits (documented, deliberate):

* Only bw-gui dispatchers run. Native class bindings (e.g. Entry text insertion) and
  foreign non-bw-gui bindings are **not** simulated; ``on_key(phase="after")``
  therefore sees the event even when a native class binding would have broken.
* Only the dispatcher is located through Tcl introspection (``bind <tag>
  <KeyPress>``); no private Python object of bw-gui is touched.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["press_key"]

_DISPATCHER = re.compile(r"^if \{\[(::bwgui::kd_\d+) %W %K %A %s\] eq \"handled\"\} break")


def _dispatcher_of(widget: Any, tag: str) -> str | None:
    """Return the bw-gui dispatcher command bound on *tag*, or ``None``."""
    script = str(widget.tk.call("bind", tag, "<KeyPress>"))
    match = _DISPATCHER.match(script.split("\n", 1)[0])
    return match.group(1) if match else None


def press_key(widget: Any, keysym: str, *, char: str = "", state: int = 0) -> bool:
    """Deliver one synthetic key press to *widget* through every bw-gui dispatcher.

    Args:
        widget: Event widget (``%W``); its current bindtags define the order.
        keysym: Tk keysym as Tk would report it (``"a"``, ``"Return"``, ``"plus"``).
        char: Tk ``%A`` value (``""`` for non-printing keys or Ctrl/Alt combinations).
        state: Tk ``%s`` modifier bits of the backend (win32: Ctrl ``0x4``,
            Alt ``0x20000``, Shift ``0x1``, NumLock ``0x8``).

    Returns:
        ``True`` if a bw-gui dispatcher reported ``HANDLED`` (Tk would ``break``).
    """
    for tag in widget.bindtags():
        command = _dispatcher_of(widget, tag)
        if command is None:
            continue
        if str(widget.tk.call(command, str(widget), keysym, char, str(state))) == "handled":
            return True
    return False
