"""``RadioGroup``: bw-gui's control for one exclusive choice among several labelled options.

Where a ``Checkbox`` answers "yes or no?", a ``RadioGroup`` answers "which one of
these?" (e.g. "Kategorie: schriftlich / sonstig", "Ansicht: Lehrertisch oben / unten").
Consumers no longer stack raw ``ttk.Radiobutton``s with hand-tuned spacing; every
exclusive choice looks, spaces and behaves the same way in all bw-gui apps.

Semantics follow the staged-selection rule of ``docs/TOGGLE_CONTRACT.md`` (like
``Checkbox``): the group only writes the chosen value into the consumer's
``StringVar``. The business effect happens when the consumer reads the variable on
its submit action. Space activates only without Ctrl/Alt (shared exact-modifier rule
in ``_exact_space``), so application shortcuts such as Ctrl+Space keep working while
a radio button has the focus.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence

from bw_gui.runtime import widgets

from ._exact_space import install_exact_space_activation

# Vertical gap between the title and the first option, and between two options (px).
TITLE_GAP = 6
OPTION_GAP = 4


class RadioGroup(widgets.Frame):
    """A frame with an optional title and one radio button per option, stacked vertically.

    A genuine ``ttk.Frame`` subclass: place it with ``pack``/``grid`` like any frame;
    outer spacing is the consumer's layout decision, inner spacing is fixed here.

    Example::

        category = ui.StringVar(value="schriftlich")
        group = RadioGroup(form, title="Kategorie", variable=category,
                           options=[("schriftlich", "Schriftlich"), ("sonstig", "Sonstig")])
        group.pack(anchor="w", pady=(0, 10))
        focus_later(group.first_button)
        # ... read category.get() when the user presses "OK".
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        options: Sequence[tuple[str, str]],
        variable: tk.StringVar,
        title: str | None = None,
        **frame_options,
    ) -> None:
        """Create the group and one radio button per option.

        Args:
            parent:         Parent widget.
            options:        ``(value, label)`` pairs in display order; values must be
                            unique and labels non-empty.
            variable:       ``StringVar`` holding the chosen value (UI state). A value
                            that matches no option simply leaves every button unselected.
            title:          Optional heading shown above the options.
            **frame_options: Further ``ttk.Frame`` options.

        Raises:
            TypeError:  *variable* is not a ``StringVar``.
            ValueError: No options, duplicate values or an empty label.
        """
        if not isinstance(variable, tk.StringVar):
            raise TypeError(f"RadioGroup needs a tkinter.StringVar, got {type(variable).__name__}")
        pairs = [(str(value), str(label)) for value, label in options]
        _validate_options(pairs)
        super().__init__(parent, **frame_options)
        self.variable = variable
        if title:
            widgets.Label(self, text=title).pack(anchor="w", pady=(0, TITLE_GAP))
        self.buttons: list[widgets.Radiobutton] = []
        for index, (value, label) in enumerate(pairs):
            button = widgets.Radiobutton(self, text=label, value=value, variable=variable)
            button.pack(anchor="w", pady=(OPTION_GAP if index else 0, 0))
            self.buttons.append(button)
        install_exact_space_activation(self, "TRadiobutton")

    @property
    def first_button(self) -> widgets.Radiobutton:
        """The first radio button, e.g. as the initial focus target of a dialog."""
        return self.buttons[0]


def _validate_options(pairs: list[tuple[str, str]]) -> None:
    """Raise ``ValueError`` for an empty option list, duplicate values or empty labels.

    Args:
        pairs: Normalised ``(value, label)`` pairs.
    """
    if not pairs:
        raise ValueError("RadioGroup needs at least one option")
    values = [value for value, _label in pairs]
    if len(set(values)) != len(values):
        raise ValueError(f"RadioGroup option values must be unique, got {values}")
    if any(not label.strip() for _value, label in pairs):
        raise ValueError("RadioGroup option labels must be non-empty")
