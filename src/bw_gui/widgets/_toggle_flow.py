"""Surface-independent click sequence of the toggle contract (private).

``ToggleFlow`` implements the "Click sequence", "Re-entrancy" and "Exceptions"
sections of ``docs/TOGGLE_CONTRACT.md`` once, for every surface that owns a
``BooleanVar``: the ``Checkbox``/``Switch`` widgets and the native-menu helpers. A
surface only supplies ``render`` (show the current value + mixed flag) and calls
``interact()`` on user interaction.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

ToggleCallback = Callable[[bool], None]


class ToggleFlow:
    """Mixed flag, requested-value resolution, callback, rollback - for one control.

    Attributes:
        variable:           Consumer ``BooleanVar`` (UI state).
        mixed:              Current mixed flag (owned here, never derived).
        in_callback:        True while the callback runs (re-entrancy marker).
    """

    def __init__(
        self,
        variable: tk.BooleanVar,
        callback: ToggleCallback | None,
        *,
        mixed: bool,
        mixed_click_target: bool,
        render: Callable[[], None],
    ) -> None:
        """Store the parts of one toggle.

        Args:
            variable:           Consumer ``BooleanVar``.
            callback:           Receives the requested bool; ``None`` for a
                                ``Checkbox`` without ``on_select``.
            mixed:              Initial mixed flag.
            mixed_click_target: Value a user interaction resolves to while mixed.
            render:             Redraws the surface from ``variable`` and ``mixed``.
        """
        self.variable = variable
        self.mixed = bool(mixed)
        self.in_callback = False
        self._callback = callback
        self._mixed_click_target = bool(mixed_click_target)
        self._render = render

    def set_mixed(self, value: bool) -> None:
        """Set the mixed flag and redraw; never touches ``variable`` or the callback."""
        self.mixed = bool(value)
        self._render()

    def requested_value(self) -> bool:
        """The value a user interaction requests right now (from the consumer variable)."""
        return self._mixed_click_target if self.mixed else not bool(self.variable.get())

    def interact(self) -> bool:
        """Run the contract sequence for one user interaction.

        Steps: remember previous value and mixed flag, resolve the requested value,
        clear mixed, optimistic ``variable.set(requested)``, redraw, callback with
        the re-entrancy marker set; on an exception restore value and mixed flag,
        redraw and re-raise.

        Returns:
            ``False`` without doing anything if called re-entrantly (the surface
            must then undo whatever Tk already changed on its side), else ``True``.
        """
        if self.in_callback:
            return False
        previous_value = bool(self.variable.get())
        previous_mixed = self.mixed
        requested = self.requested_value()
        self.mixed = False
        self.variable.set(requested)
        self._render()
        if self._callback is None:
            return True
        self.in_callback = True
        try:
            self._callback(requested)
        except BaseException:
            self.variable.set(previous_value)
            self.mixed = previous_mixed
            self._render()
            raise
        finally:
            self.in_callback = False
        return True
