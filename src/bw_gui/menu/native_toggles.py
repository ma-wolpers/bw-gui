"""Checkbox/Switch entries for native ``tk.Menu`` menus (contract-conform replacement
for ``Menu.add_checkbutton``).

Same semantics as the ``Checkbox``/``Switch`` widgets (``docs/TOGGLE_CONTRACT.md``):
the callback receives the requested bool and fires only on user interaction, a
programmatic ``variable.set``/``set_mixed`` only redraws, callback exceptions roll back
value and mixed flag. The entry is an ``add_command`` entry whose indicator is the
shared themed toggle image, so Tk never toggles anything on its own.

Entries are appended at the end of the menu; do not insert or delete entries *before*
a toggle entry afterwards (the handle addresses its entry by index).
"""

from __future__ import annotations

import tkinter as tk

from bw_gui._toggle_flow import ToggleCallback, ToggleFlow

from ._toggle_glyphs import glyph_image, text_prefix


class NativeMenuToggle:
    """Handle for one toggle entry in a native ``tk.Menu`` (created by the helpers below)."""

    def __init__(
        self,
        menu: tk.Menu,
        control: str,
        *,
        label: str,
        variable: tk.BooleanVar,
        callback: ToggleCallback | None,
        mixed: bool,
        mixed_click_target: bool,
    ) -> None:
        """Append the entry and wire the variable mirror.

        Args:
            menu:               Target native menu.
            control:            ``"checkbox"`` or ``"switch"``.
            label:              Non-empty entry label.
            variable:           Consumer ``BooleanVar`` (UI state).
            callback:           Receives the requested bool on user interaction.
            mixed:              Initial mixed flag.
            mixed_click_target: Value a click resolves to while mixed.

        Raises:
            TypeError:  *variable* is not a ``BooleanVar``.
            ValueError: Empty *label*.
        """
        if not isinstance(variable, tk.BooleanVar):
            raise TypeError(f"menu toggle needs a tkinter.BooleanVar, got {type(variable).__name__}")
        if not str(label).strip():
            raise ValueError("menu toggle needs a non-empty label")
        self._menu = menu
        self._control = control
        self._label = label
        self._flow = ToggleFlow(variable, callback, mixed=mixed, mixed_click_target=mixed_click_target,
                                render=self._render)
        menu.add_command(label=label, compound="left", command=self._on_click)
        self.index = int(menu.index("end"))
        self._trace_id: str | None = variable.trace_add("write", lambda *_: self._render())
        menu.bind("<Destroy>", self._on_destroy, add="+")
        self._render()

    def set_mixed(self, value: bool) -> None:
        """Show or clear the mixed indicator; never touches the variable or the callback."""
        self._flow.set_mixed(value)

    def is_mixed(self) -> bool:
        """Return whether the mixed indicator is currently shown."""
        return self._flow.mixed

    def _render(self) -> None:
        """Show the themed indicator (or a text fallback before the theme is configured)."""
        checked, mixed = bool(self._flow.variable.get()), self._flow.mixed
        image = glyph_image(self._menu, self._control, checked, mixed)
        if image is not None:
            self._menu.entryconfigure(self.index, image=image, label=self._label)
        else:
            self._menu.entryconfigure(self.index, label=text_prefix(self._control, checked, mixed) + self._label)

    def _on_click(self) -> None:
        """User interaction: run the contract sequence (a re-entrant click is ignored).

        Unlike a ``ttk.Checkbutton``, a command entry changes nothing before this
        runs, so a re-entrant click needs no undo.
        """
        self._flow.interact()

    def _on_destroy(self, event: tk.Event) -> None:
        """Remove the mirror trace when the menu is destroyed."""
        if event.widget is self._menu and self._trace_id is not None:
            self._flow.variable.trace_remove("write", self._trace_id)
            self._trace_id = None


def add_menu_switch(
    menu: tk.Menu,
    *,
    label: str,
    variable: tk.BooleanVar,
    on_change: ToggleCallback,
    mixed: bool = False,
    mixed_click_target: bool = False,
) -> NativeMenuToggle:
    """Append a Switch entry (immediate effect) to a native menu.

    Args:
        menu:               Target ``tk.Menu``.
        label:              Entry label.
        variable:           ``BooleanVar`` mirroring the effective state.
        on_change:          Required; receives the requested bool and applies the effect.
        mixed:              Initial mixed flag.
        mixed_click_target: What a click from mixed requests (default ``False``).

    Raises:
        TypeError: If *on_change* is ``None``.
    """
    if on_change is None:
        raise TypeError("add_menu_switch needs an on_change callback (immediate effect)")
    return NativeMenuToggle(menu, "switch", label=label, variable=variable, callback=on_change,
                            mixed=mixed, mixed_click_target=mixed_click_target)


def add_menu_checkbox(
    menu: tk.Menu,
    *,
    label: str,
    variable: tk.BooleanVar,
    on_select: ToggleCallback | None = None,
    mixed: bool = False,
    mixed_click_target: bool = True,
) -> NativeMenuToggle:
    """Append a Checkbox entry (staged: effective only on a later submit) to a native menu.

    Args:
        menu:               Target ``tk.Menu``.
        label:              Entry label.
        variable:           ``BooleanVar`` holding the selection.
        on_select:          Optional; local presentation state only (convention).
        mixed:              Initial mixed flag.
        mixed_click_target: What a click from mixed selects (default ``True``).
    """
    return NativeMenuToggle(menu, "checkbox", label=label, variable=variable, callback=on_select,
                            mixed=mixed, mixed_click_target=mixed_click_target)
