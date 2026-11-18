"""``CheckList``: bw-gui's control for choosing *several* of many labelled options, optionally grouped.

Where a ``RadioGroup`` answers "which one of these?", a ``CheckList`` answers
"which of these?" (e.g. "Welche Kompetenzen gehören zu diesem Symbol?"). It
stacks one ``Checkbox`` per option under optional group headings, with fixed
spacing, so every multi-select looks and behaves the same in all bw-gui apps.

Semantics follow the staged-selection rule of ``docs/TOGGLE_CONTRACT.md``: the
list only tracks which options are ticked. The business effect happens when the
consumer reads :meth:`CheckList.selected_values` on its submit action.
``on_select`` may update local presentation state only (e.g. enable an "OK"
button once at least one option is ticked).

The list is a plain frame, not a scroll viewport: long lists are placed inside a
``ScrollableFrame`` by the consumer, so a form that already scrolls never ends up
with two nested wheel targets.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable, Sequence

from bw_gui.runtime import ui, widgets

from .toggles import Checkbox

# Vertical gap between two options and above every group heading but the first (px).
OPTION_GAP = 2
GROUP_GAP = 10
# Indent of the options below a group heading (px).
GROUP_INDENT = 12

CheckListGroups = Sequence[tuple[str, Sequence[tuple[str, str]]]]
"""``(group title, [(value, label), ...])`` pairs in display order; an empty title shows no heading."""


class CheckList(widgets.Frame):
    """A frame with one ``Checkbox`` per option, grouped under optional headings.

    A genuine ``ttk.Frame`` subclass: place it with ``pack``/``grid`` like any frame.

    Example::

        picker = CheckList(form, groups=[("Konzentration", [("k.arbeiten", "konzentriert arbeiten"),
                                                            ("k.zurueck", "zur Aufgabe zurückfinden")])],
                           selected=["k.arbeiten"])
        picker.pack(fill="x")
        # ... read picker.selected_values() when the user presses "Speichern".
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        groups: CheckListGroups,
        selected: Iterable[str] = (),
        on_select: Callable[[tuple[str, ...]], None] | None = None,
        **frame_options,
    ) -> None:
        """Create the list, its headings and one checkbox per option.

        Args:
            parent:          Parent widget.
            groups:          ``(title, options)`` pairs; *options* are ``(value, label)``
                             pairs. Values must be unique across all groups, labels
                             non-empty. Empty groups are skipped.
            selected:        Values ticked initially; unknown values are ignored.
            on_select:       Optional; receives the new selection (display order) after
                             every user click. Local presentation state only.
            **frame_options: Further ``ttk.Frame`` options.

        Raises:
            ValueError: No option at all, duplicate values or an empty label.
        """
        normalized = _normalize_groups(groups)
        super().__init__(parent, **frame_options)
        self._on_select = on_select
        self._variables: dict[str, tk.BooleanVar] = {}
        self.checkboxes: dict[str, Checkbox] = {}
        initial = set(selected)
        for group_index, (title, options) in enumerate(normalized):
            if title:
                widgets.Label(self, text=title).pack(anchor="w", pady=(GROUP_GAP if group_index else 0, OPTION_GAP))
            indent = GROUP_INDENT if title else 0
            for value, label in options:
                variable = ui.BooleanVar(master=self, value=value in initial)
                box = Checkbox(self, text=label, variable=variable, on_select=self._on_box)
                box.pack(anchor="w", padx=(indent, 0), pady=(0, OPTION_GAP))
                self._variables[value] = variable
                self.checkboxes[value] = box

    @property
    def values(self) -> tuple[str, ...]:
        """All option values in display order."""
        return tuple(self._variables)

    def selected_values(self) -> tuple[str, ...]:
        """The ticked values in display order (not in click order)."""
        return tuple(value for value, variable in self._variables.items() if variable.get())

    def set_selected(self, values: Iterable[str]) -> None:
        """Tick exactly *values* (unknown ones are ignored); fires no callback.

        Args:
            values: Values to tick; every other option is unticked.
        """
        wanted = set(values)
        for value, variable in self._variables.items():
            variable.set(value in wanted)

    def _on_box(self, _on: bool) -> None:
        """Report the selection after one user click.

        The toggle flow sets the consumer variable optimistically *before* the
        callback (``_toggle_flow.ToggleFlow.interact``), so the selection read here
        already includes this click; a raising ``on_select`` rolls the click back.

        Args:
            _on: Requested state of the clicked option (already in its variable).
        """
        if self._on_select is not None:
            self._on_select(self.selected_values())


def _normalize_groups(groups: CheckListGroups) -> list[tuple[str, list[tuple[str, str]]]]:
    """Normalise *groups* to strings, drop empty groups and validate the options.

    Args:
        groups: Raw ``(title, options)`` pairs from the consumer.

    Raises:
        ValueError: No option at all, duplicate values or an empty label.
    """
    normalized = [
        (str(title or "").strip(), [(str(value), str(label)) for value, label in options])
        for title, options in groups
    ]
    normalized = [(title, options) for title, options in normalized if options]
    values = [value for _title, options in normalized for value, _label in options]
    if not values:
        raise ValueError("CheckList needs at least one option")
    if len(set(values)) != len(values):
        raise ValueError(f"CheckList option values must be unique, got {values}")
    if any(not label.strip() for _title, options in normalized for _value, label in options):
        raise ValueError("CheckList option labels must be non-empty")
    return normalized
