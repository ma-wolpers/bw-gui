"""Inline validation message below an input field -- the one look for "this text is not accepted".

Used by the text prompt dialog (``TextPromptDialogService.askstring``) and the
CardBoard inline editor, so a rejected text reads the same everywhere: a
``Error.TLabel`` line (theme token ``danger``) directly under the field instead
of a second popup. The label manages its own visibility: it takes no space
while there is nothing to say.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any


class FieldErrorLabel:
    """A hideable error line packed below a field.

    Args:
        master: Container that lays out its children with ``pack``.
        wraplength: Pixel width at which the message wraps.
        pack_options: Extra ``pack`` options used whenever the message is shown
            (``fill="x"`` and ``anchor="w"`` are the defaults).
    """

    def __init__(self, master: Any, *, wraplength: int = 400, **pack_options: Any) -> None:
        """Create the (hidden) label."""
        self._label = ttk.Label(master, text="", style="Error.TLabel", justify="left", wraplength=wraplength)
        self._pack_options = {"fill": "x", "anchor": "w", **pack_options}

    @property
    def widget(self) -> ttk.Label:
        """The underlying label (tests, geometry)."""
        return self._label

    @property
    def message(self) -> str:
        """The message currently shown, ``""`` when hidden."""
        return str(self._label.cget("text"))

    def show(self, message: str | None) -> None:
        """Show *message* below the field; ``None`` or ``""`` hides the line."""
        if message:
            self._label.configure(text=message)
            if not self._label.winfo_manager():
                self._label.pack(**self._pack_options)
            return
        self._label.configure(text="")
        if self._label.winfo_manager():
            self._label.pack_forget()
