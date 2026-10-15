"""Widget-event contract, pure part (``docs/WIDGET_EVENTS_CONTRACT.md``).

Semantic event values for the lifecycle, selection, activation and hover hooks of
``bw_gui.runtime.widget_events``, ``bw_gui.runtime.selection`` and
``bw_gui.runtime.pointer_hover``. They carry no Tk event objects, no ``event.state`` and
no virtual-event names; the Tk side is the only code that reads raw Tk events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class ResizeEvent:
    """Geometry of a widget after a change (``on_resize``).

    ``x``/``y`` are relative to the parent like Tk's ``<Configure>``; for a toplevel
    they are its screen position, and moving a toplevel reports a change, too.
    """

    width: int
    height: int
    x: int
    y: int
    widget: object = None


@dataclass(frozen=True)
class FocusChange:
    """Keyboard focus gained or lost (``on_focus_change``).

    ``widget`` is the widget whose focus changed -- with ``within=True`` it may be a
    descendant of the subscribed widget.
    """

    gained: bool
    widget: object = None


class SelectionCause(str, Enum):
    """Why a widget's selection changed (shared semantics of all selection hooks)."""

    USER = "user"
    """Mouse or keyboard input on the widget itself."""
    PROGRAMMATIC = "programmatic"
    """A bw-gui selection mutation with ``notify=True``."""
    EXPORT_LOST = "export_lost"
    """Listbox only: another widget took the X selection (``exportselection``)."""
    CONTENT_CHANGED = "content_changed"
    """Treeview only: items were deleted/moved and Tk adjusted the selection (1:1 to Tk)."""


@dataclass(frozen=True)
class ListboxSelectionChange:
    """Selected indices of a listbox changed (``on_listbox_select``)."""

    indices: tuple[int, ...]
    previous: tuple[int, ...]
    cause: SelectionCause
    widget: object = None


@dataclass(frozen=True)
class TreeviewSelectionChange:
    """Selected item ids of a treeview changed (``on_treeview_select``)."""

    item_ids: tuple[str, ...]
    previous: tuple[str, ...]
    cause: SelectionCause
    widget: object = None


@dataclass(frozen=True)
class ComboboxSelectionChange:
    """A value was picked from a combobox list (``on_combobox_select``).

    ``index`` is ``None`` when the current value is not one of the list values.
    """

    index: int | None
    value: str
    cause: SelectionCause
    widget: object = None


@dataclass(frozen=True)
class TabChange:
    """The selected notebook tab changed (``on_tab_changed``); ``index`` is ``None`` without tabs."""

    index: int | None
    tab_id: str
    widget: object = None


class ActivateSource(str, Enum):
    """What activated an element (``on_activate``)."""

    KEY = "key"
    DOUBLE_CLICK = "double_click"


@dataclass(frozen=True)
class ActivateEvent:
    """An element of a listbox/treeview was activated by Enter or a double click.

    ``element`` is the activated listbox index or treeview item id (for Enter: the
    widget's active index / focus item; ``None`` if there is none).
    """

    source: ActivateSource
    element: object
    widget: object = None


@dataclass(frozen=True)
class HoverEvent:
    """Pointer entered, moved over or left a widget or canvas item (``bind_hover``)."""

    x: int
    y: int
    x_root: int
    y_root: int
    widget: object = None
