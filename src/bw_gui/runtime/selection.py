"""Widget-event contract, Tk side: selection hooks, selection mutations and activation.

Widget-specific on purpose (``docs/WIDGET_EVENTS_CONTRACT.md``): Listbox, Treeview and
Combobox each have their own hook, event type and mutation API; only the meaning of
:class:`SelectionCause` and the de-duplication are shared.

* Hooks report a change only when the selection differs from the last reported one.
* ``cause``: ``USER`` when the change follows mouse/keyboard input on the widget itself
  (an input marker set by bw-gui on press/key, cleared after idle); ``PROGRAMMATIC``
  for a mutation through this module with ``notify=True``; otherwise ``EXPORT_LOST``
  (Listbox, another widget took the selection) or ``CONTENT_CHANGED`` (Treeview,
  Tk adjusted the selection after items changed).
* Mutations (``listbox_selection``, ``treeview_selection``, ``combobox_selection``) are
  the only allowed way to change a selection (guard). ``notify=False`` (default) never
  reports. Tk differs per widget, and the module hides it: a Listbox emits no event
  for programmatic changes (``notify=True`` reports synchronously); a Treeview queues
  ``<<TreeviewSelect>>`` for them, so a Treeview mutation records the expected
  selection (generation mark) and the queued event is suppressed or reported as
  ``PROGRAMMATIC`` -- same timing as Tk's own event.
* ``Listbox.exportselection`` is left untouched.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

from bw_gui.contracts.events import EventResult, coerce_result
from bw_gui.contracts.key_spec import KeySpec
from bw_gui.contracts.subscription import CompositeSubscription, Subscription
from bw_gui.contracts.widget_events import (
    ActivateEvent,
    ActivateSource,
    ComboboxSelectionChange,
    ListboxSelectionChange,
    SelectionCause,
    TreeviewSelectionChange,
)

from ._tk_identity import runtime_for
from .pointer import _bind, _track, bind_click
from .widget_keys import WidgetShortcutBinder, on_key

__all__ = [
    "combobox_selection",
    "listbox_selection",
    "on_activate",
    "on_combobox_select",
    "on_listbox_select",
    "on_treeview_select",
    "treeview_selection",
]

_ENTER = KeySpec.parse("Enter (tolerate: Shift)")


class _State:
    """Per-subscription view: last reported selection, pending programmatic marks, input marker."""

    def __init__(self, initial: tuple, report: Callable[[tuple, tuple], None] | None) -> None:
        self.last = initial
        self.pending: list[tuple[tuple, bool]] = []  # (expected selection, notify)
        self.user_input = False
        self.report = report  # synchronous PROGRAMMATIC report (widgets without a Tk event)

    def classify(self, current: tuple, other: SelectionCause) -> SelectionCause | None:
        for index, (expected, notify) in enumerate(self.pending):
            if expected == current:
                del self.pending[: index + 1]
                return SelectionCause.PROGRAMMATIC if notify and current != self.last else None
        if current == self.last:
            return None
        return SelectionCause.USER if self.user_input else other


def _states(widget: Any) -> list[_State]:
    registry: dict[str, list[_State]] = runtime_for(widget).part("selection_states", lambda _rt: {})
    return registry.setdefault(str(widget), [])


def _subscribe(
    widget: Any,
    initial: tuple,
    sequence: str,
    on_event: Callable[[_State], None],
    report: Callable[[tuple, tuple], None] | None = None,
) -> Subscription:
    """Shared plumbing: state registration, input marker, the virtual-event binding."""
    state = _State(initial, report)
    _states(widget).append(state)

    def _mark(_event: Any = None) -> None:
        state.user_input = True
        widget.after_idle(lambda: setattr(state, "user_input", False))

    def _unregister() -> None:
        if state in _states(widget):
            _states(widget).remove(state)

    # Exactly the sequences bind_click/bind_drag use on the same bw tag: Tk runs only the
    # most specific binding per tag, so a generic <ButtonPress> would be skipped there;
    # equal sequences coexist (add="+"). <Double-...> is left out on purpose -- it would
    # change bind_click's "second press is an ordinary count=1 press" semantics.
    pointer = [f"<ButtonPress-{n}>" for n in (1, 2, 3)] + ["<B1-Motion>", "<ButtonRelease-1>"]
    subs = [_bind(widget, sequence, _mark) for sequence in pointer] + [
        on_key(widget, lambda _key: _mark(), phase="before"),
        _bind(widget, sequence, lambda _event: on_event(state)),
        Subscription(_unregister),
    ]
    return _track(widget, CompositeSubscription(subs))


def _listbox_indices(listbox: Any) -> tuple[int, ...]:
    return tuple(int(index) for index in listbox.curselection())


def on_listbox_select(listbox: Any, handler: Callable[[ListboxSelectionChange], object]) -> Subscription:
    """Report selection changes of a ``Listbox`` as :class:`ListboxSelectionChange`."""

    def _on_event(state: _State) -> None:
        current = _listbox_indices(listbox)
        cause = state.classify(current, SelectionCause.EXPORT_LOST)
        previous, state.last = state.last, current
        if cause is not None:
            handler(ListboxSelectionChange(current, previous, cause, listbox))

    def _report(previous: tuple, current: tuple) -> None:
        handler(ListboxSelectionChange(current, previous, SelectionCause.PROGRAMMATIC, listbox))

    return _subscribe(listbox, _listbox_indices(listbox), "<<ListboxSelect>>", _on_event, _report)


def on_treeview_select(treeview: Any, handler: Callable[[TreeviewSelectionChange], object]) -> Subscription:
    """Report selection changes of a ``ttk.Treeview`` as :class:`TreeviewSelectionChange`."""

    def _on_event(state: _State) -> None:
        current = tuple(str(item) for item in treeview.selection())
        cause = state.classify(current, SelectionCause.CONTENT_CHANGED)
        previous, state.last = state.last, current
        if cause is not None:
            handler(TreeviewSelectionChange(current, previous, cause, treeview))

    return _subscribe(treeview, tuple(str(item) for item in treeview.selection()), "<<TreeviewSelect>>", _on_event)


def _combobox_value(combobox: Any) -> tuple:
    index = int(combobox.current())
    return (index if index >= 0 else None, str(combobox.get()))


def on_combobox_select(combobox: Any, handler: Callable[[ComboboxSelectionChange], object]) -> Subscription:
    """Report picks from a ``ttk.Combobox`` list as :class:`ComboboxSelectionChange` (Tk reports list picks only)."""

    def _on_event(state: _State) -> None:
        current = _combobox_value(combobox)
        cause = state.classify(current, SelectionCause.USER)
        state.last = current
        if cause is not None:
            handler(ComboboxSelectionChange(current[0], current[1], cause, combobox))

    def _report(_previous: tuple, current: tuple) -> None:
        handler(ComboboxSelectionChange(current[0], current[1], SelectionCause.PROGRAMMATIC, combobox))

    return _subscribe(combobox, _combobox_value(combobox), "<<ComboboxSelected>>", _on_event, _report)


def _after_sync_mutation(widget: Any, current: tuple, notify: bool) -> None:
    """Listbox/Combobox: Tk emits no event for programmatic changes -- update and maybe report now."""
    for state in list(_states(widget)):
        previous, state.last = state.last, current
        if notify and current != previous and state.report is not None:
            state.report(previous, current)


class _ListboxSelection:
    """Selection mutations of a ``Listbox`` (``notify=False`` never reports)."""

    @staticmethod
    def set(listbox: Any, indices: Iterable[int], *, notify: bool = False) -> None:
        """Replace the selection by *indices* (empty = clear)."""
        listbox.selection_clear(0, "end")
        for index in indices:
            listbox.selection_set(int(index))
        _after_sync_mutation(listbox, _listbox_indices(listbox), notify)

    @staticmethod
    def clear(listbox: Any, *, notify: bool = False) -> None:
        """Clear the selection."""
        _ListboxSelection.set(listbox, (), notify=notify)


class _TreeviewSelection:
    """Selection mutations of a ``ttk.Treeview`` (generation mark against Tk's queued event)."""

    @staticmethod
    def _apply(treeview: Any, mutate: Callable[[], None], notify: bool) -> None:
        before = tuple(str(item) for item in treeview.selection())
        mutate()
        after = tuple(str(item) for item in treeview.selection())
        if after != before:
            for state in _states(treeview):
                state.pending.append((after, notify))

    @staticmethod
    def set(treeview: Any, item_ids: Iterable[str], *, notify: bool = False) -> None:
        """Replace the selection by *item_ids* (empty = clear)."""
        items = tuple(item_ids)
        _TreeviewSelection._apply(treeview, lambda: treeview.selection_set(items), notify)

    @staticmethod
    def remove(treeview: Any, item_ids: Iterable[str], *, notify: bool = False) -> None:
        """Remove *item_ids* from the selection."""
        items = tuple(item_ids)
        _TreeviewSelection._apply(treeview, lambda: treeview.selection_remove(items), notify)

    @staticmethod
    def clear(treeview: Any, *, notify: bool = False) -> None:
        """Clear the selection."""
        _TreeviewSelection._apply(treeview, lambda: treeview.selection_remove(treeview.selection()), notify)


class _ComboboxSelection:
    """Value mutations of a ``ttk.Combobox`` (Tk itself never reports them)."""

    @staticmethod
    def set_index(combobox: Any, index: int, *, notify: bool = False) -> None:
        """Select list entry *index* (``Combobox.current(index)``)."""
        combobox.current(int(index))
        _after_sync_mutation(combobox, _combobox_value(combobox), notify)

    @staticmethod
    def set_value(combobox: Any, value: str, *, notify: bool = False) -> None:
        """Set the shown value (need not be a list entry; then ``index`` is ``None``)."""
        combobox.set(value)
        _after_sync_mutation(combobox, _combobox_value(combobox), notify)


listbox_selection = _ListboxSelection()
treeview_selection = _TreeviewSelection()
combobox_selection = _ComboboxSelection()


def _element_at(widget: Any, y: int) -> object | None:
    if widget.winfo_class() == "Treeview":
        return widget.identify_row(y) or None
    index = int(widget.nearest(y))
    box = widget.bbox(index)
    return index if box and box[1] <= y < box[1] + box[3] else None


def _key_element(widget: Any) -> object | None:
    if widget.winfo_class() == "Treeview":
        return widget.focus() or None
    return int(widget.index("active")) if widget.size() else None


def on_activate(widget: Any, handler: Callable[[ActivateEvent], object]) -> Subscription:
    """Report Enter (Shift tolerated) or a double click on an element of a Listbox/Treeview.

    Runs before the native class bindings: ``HANDLED`` suppresses the native action
    (e.g. a Treeview's open/close on double click), ``None``/``NOT_HANDLED`` lets it run.
    A double click on empty space is not an activation.
    """

    def _on_key(_event: Any) -> object:
        return handler(ActivateEvent(ActivateSource.KEY, _key_element(widget), widget))

    def _on_double(event: Any) -> object:
        element = _element_at(widget, event.y)
        if element is None:
            return EventResult.NOT_HANDLED
        return coerce_result(handler(ActivateEvent(ActivateSource.DOUBLE_CLICK, element, widget)))

    binder = WidgetShortcutBinder(widget)
    binder.bind(_ENTER, _on_key, binding_id="bw_gui.activate", intent="bw_gui.activate", allow_when_text_input=True)
    subs = [Subscription(binder.dispose), bind_click(widget, _on_double, count=2)]
    return _track(widget, CompositeSubscription(subs))
