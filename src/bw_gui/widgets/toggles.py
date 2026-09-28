"""``Checkbox`` and ``Switch``: bw-gui's only binary controls.

The two controls differ in *meaning*, not just in looks (``docs/TOGGLE_CONTRACT.md``):

* **Checkbox** - staged selection. Its business effect happens only on a submit
  action. ``on_select`` may change local presentation state only (convention).
* **Switch** - immediate effect. ``on_change`` is required and applies the effect.

Both report the *requested* bool to their callback, fire it only on user interaction
(click, Space, ``invoke()``), never on programmatic ``variable.set`` / ``set_mixed``,
support an optional mixed state, and roll back on callback exceptions.

Mechanism: the underlying ``ttk.Checkbutton`` is bound to a widget-owned *display*
variable. The consumer ``variable`` is mirrored into it by a write trace that never
fires a callback. When the user clicks, Tk flips only the display variable; the
click handler then derives the requested value from the consumer variable, so
observers of ``variable`` never see a Tk-flipped intermediate value.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from bw_gui.theming._toggle_styles import STYLE_NAMES

ToggleCallback = Callable[[bool], None]
_RESERVED_OPTIONS = frozenset({"command", "variable", "style", "onvalue", "offvalue"})


class _Toggle(ttk.Checkbutton):
    """Shared contract implementation for ``Checkbox`` and ``Switch`` (private).

    Subclasses only fix the control kind (style) and the callback name.
    """

    _CONTROL = ""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        variable: tk.BooleanVar,
        callback: ToggleCallback | None,
        mixed: bool,
        mixed_click_target: bool,
        **options,
    ) -> None:
        """Create the widget and wire the display mirror.

        Args:
            parent:             Parent widget.
            text:               Mandatory, non-empty label (part of the click target).
            variable:           Consumer ``BooleanVar`` (UI state, not domain state).
            callback:           Receives the requested bool on user interaction.
            mixed:              Initial mixed state.
            mixed_click_target: Value a click resolves to while mixed.
            **options:          Further ``ttk.Checkbutton`` options (not ``command``,
                                ``variable``, ``style``, ``onvalue``, ``offvalue``).

        Raises:
            TypeError:  Reserved option passed or *variable* is not a ``BooleanVar``.
            ValueError: Empty *text*.
        """
        _reject_reserved(options)
        if not isinstance(variable, tk.BooleanVar):
            raise TypeError(f"{type(self).__name__} needs a tkinter.BooleanVar, got {type(variable).__name__}")
        if not str(text).strip():
            raise ValueError(f"{type(self).__name__} needs a non-empty text label")
        self._variable = variable
        self._display = tk.BooleanVar(master=parent, value=bool(variable.get()))
        self._callback = callback
        self._mixed = bool(mixed)
        self._mixed_click_target = bool(mixed_click_target)
        self._in_callback = False
        super().__init__(
            parent, text=text, variable=self._display, style=STYLE_NAMES[self._CONTROL],
            command=self._on_invoke, **options,
        )
        self._trace_id: str | None = variable.trace_add("write", self._on_variable_write)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._render()

    # -- public API ------------------------------------------------------------------

    def set_mixed(self, value: bool) -> None:
        """Show or clear the mixed indicator. Never touches ``variable``, never fires the callback."""
        self._mixed = bool(value)
        self._render()

    def is_mixed(self) -> bool:
        """Return whether the mixed indicator is currently shown."""
        return self._mixed

    def configure(self, cnf=None, **options):
        """``ttk.Checkbutton.configure`` minus the reserved options (see ``__init__``)."""
        _reject_reserved({**(cnf or {}), **options})
        return super().configure(cnf, **options)

    config = configure

    def __setitem__(self, key: str, value) -> None:
        """``widget[key] = value`` with the same reserved-option check as ``configure``."""
        _reject_reserved({key: value})
        super().__setitem__(key, value)

    # -- internals -------------------------------------------------------------------

    def _render(self) -> None:
        """Re-assert ttk ``selected``/``alternate`` from the display value and mixed flag.

        Needed after every display write: ttk clears ``alternate`` itself whenever its
        variable changes, while the mixed flag lives here in Python.
        """
        selected = "selected" if self._display.get() else "!selected"
        self.state([selected, "alternate" if self._mixed else "!alternate"])

    def _on_variable_write(self, *_trace_args) -> None:
        """Mirror a write to the consumer variable into the display (never a callback)."""
        self._display.set(bool(self._variable.get()))
        self._render()

    def _on_invoke(self) -> None:
        """Handle a user interaction; Tk has already flipped the *display* variable.

        Sequence (contract "Click sequence"): re-entrancy check, remember previous
        value and mixed flag, compute the requested value from the consumer variable,
        clear mixed, optimistic ``variable.set``, callback; roll back and re-raise on
        an exception.
        """
        if self._in_callback:
            # Re-entrant invocation: undo Tk's display flip, change nothing else.
            self._display.set(bool(self._variable.get()))
            self._render()
            return
        previous_value = bool(self._variable.get())
        previous_mixed = self._mixed
        requested = self._mixed_click_target if previous_mixed else not previous_value
        self._mixed = False
        self._variable.set(requested)
        self._render()
        if self._callback is None:
            return
        self._in_callback = True
        try:
            self._callback(requested)
        except BaseException:
            self._variable.set(previous_value)
            self._mixed = previous_mixed
            self._render()
            raise
        finally:
            self._in_callback = False

    def _on_destroy(self, event: tk.Event) -> None:
        """Remove the mirror trace from the consumer variable when this widget dies."""
        if event.widget is self and self._trace_id is not None:
            self._variable.trace_remove("write", self._trace_id)
            self._trace_id = None


def _reject_reserved(options: dict) -> None:
    """Raise ``TypeError`` if *options* contains an option the toggle owns itself."""
    reserved = _RESERVED_OPTIONS.intersection(options)
    if reserved:
        raise TypeError(
            f"option(s) {sorted(reserved)} are managed by the toggle; use on_change/on_select "
            "and the variable argument instead (see docs/TOGGLE_CONTRACT.md)"
        )


class Checkbox(_Toggle):
    """Staged selection: the business effect happens only on a submit action.

    Example::

        include = ui.BooleanVar(value=True)
        Checkbox(form, text="Include solutions", variable=include)
        # ... read include.get() when the user presses "Export".
    """

    _CONTROL = "checkbox"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        variable: tk.BooleanVar,
        on_select: ToggleCallback | None = None,
        mixed: bool = False,
        mixed_click_target: bool = True,
        **options,
    ) -> None:
        """Create a checkbox.

        Args:
            parent:             Parent widget.
            text:               Non-empty label.
            variable:           ``BooleanVar`` holding the selection (UI state).
            on_select:          Optional; receives the requested bool on user
                                interaction. May change *local presentation state
                                only* (tick other boxes, enable controls, local
                                preview) - never commit, persist or apply (convention).
            mixed:              Initial mixed state (e.g. a partly selected group).
            mixed_click_target: What a click from mixed selects (default ``True``).
            **options:          Further ``ttk.Checkbutton`` layout options.
        """
        super().__init__(parent, text=text, variable=variable, callback=on_select, mixed=mixed,
                         mixed_click_target=mixed_click_target, **options)


class Switch(_Toggle):
    """Immediate effect: toggling applies at once and never needs a submit action.

    Example::

        Switch(toolbar, text="Show grid", variable=grid_var,
               on_change=lambda on: canvas_view.set_grid_visible(on))
    """

    _CONTROL = "switch"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        variable: tk.BooleanVar,
        on_change: ToggleCallback,
        mixed: bool = False,
        mixed_click_target: bool = False,
        **options,
    ) -> None:
        """Create a switch.

        Args:
            parent:             Parent widget.
            text:               Non-empty label.
            variable:           ``BooleanVar`` mirroring the effective state (UI state).
            on_change:          Required; receives the requested bool and applies the
                                business effect. Raise to reject: the widget rolls back.
            mixed:              Initial mixed state (e.g. "some, not all finished").
            mixed_click_target: What a click from mixed requests (default ``False``).
            **options:          Further ``ttk.Checkbutton`` layout options.

        Raises:
            TypeError: If *on_change* is missing or ``None``.
        """
        if on_change is None:
            raise TypeError("Switch needs an on_change callback (immediate effect)")
        super().__init__(parent, text=text, variable=variable, callback=on_change, mixed=mixed,
                         mixed_click_target=mixed_click_target, **options)
