"""Overlay stack with semantic categories (``docs/OVERLAY_STACK_CONTRACT.md``).

One stack per interpreter (on the root, decision 31) replaces
``ScrollablePopupWindow._open_popups`` and the consumer-side toplevel scans. Overlays
register themselves at construction and unregister via their ``Subscription``
(automatically on ``<Destroy>``).

Categories keep today's semantics:

* ``MODAL_DIALOG`` -- grabbing popups (``ScrollablePopupWindow``), the settings dialog,
  native message/file dialogs run through ``_run_modal``. Native dialogs have no Tk
  toplevel: their entry is a *modal invocation* with ``toplevel=None``, which is only
  allowed for this category and registered for the duration of the blocking call.
* ``NON_MODAL_POPUP`` -- non-grabbing tool windows.
* ``MENU`` -- ``CustomMenuBar`` popups and description flyouts.
* ``TRANSIENT`` -- tooltips, drag ghost; never part of gating.

Gating never uses one vague "anything open" flag: :func:`overlay_state` reports the
categories and consumers pick an explicit preset (:func:`blocking`).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from bw_gui.contracts.popup import POPUP_KIND_MODAL, PopupPolicy
from bw_gui.contracts.subscription import Subscription

from ._tk_identity import runtime_for

__all__ = [
    "OverlayCategory",
    "OverlayEntry",
    "OverlayState",
    "blocking",
    "modal_affecting_mode",
    "overlay_state",
    "register_overlay",
    "unregistered_visible_toplevels",
]


class OverlayCategory(str, Enum):
    """Semantic overlay categories."""

    MODAL_DIALOG = "modal_dialog"
    NON_MODAL_POPUP = "non_modal_popup"
    MENU = "menu"
    TRANSIENT = "transient"


@dataclass(frozen=True)
class OverlayEntry:
    """One open overlay; ``toplevel`` is ``None`` only for a native modal invocation."""

    overlay_id: int
    category: OverlayCategory
    toplevel: Any
    policy: PopupPolicy | None = None


@dataclass(frozen=True)
class OverlayState:
    """Category view of the open overlays."""

    modal_dialog: bool
    menu_open: bool
    non_modal_popups: int
    modal_affecting_mode: bool
    entries: tuple[OverlayEntry, ...] = field(default=())


class _OverlayStack:
    def __init__(self) -> None:
        self.entries: list[OverlayEntry] = []
        self._ids = itertools.count(1)

    def push(self, category: OverlayCategory, toplevel: Any, policy: PopupPolicy | None) -> tuple[OverlayEntry, Subscription]:
        entry = OverlayEntry(next(self._ids), category, toplevel, policy)
        self.entries.append(entry)

        def _remove() -> None:
            if entry in self.entries:
                self.entries.remove(entry)

        return entry, Subscription(_remove)


def _stack(widget: Any) -> _OverlayStack:
    return runtime_for(widget).part("overlays", lambda _rt: _OverlayStack())


def register_overlay(
    anchor: Any,
    category: OverlayCategory,
    *,
    toplevel: Any = None,
    policy: PopupPolicy | None = None,
) -> Subscription:
    """Register an open overlay; the subscription ends it (also on the toplevel's ``<Destroy>``).

    Args:
        anchor: Any widget of the interpreter (the overlay's toplevel or its parent).
        toplevel: The overlay's Tk toplevel; ``None`` is only allowed for a native modal
            invocation (``MODAL_DIALOG``).

    Raises:
        ValueError: ``toplevel=None`` with a category other than ``MODAL_DIALOG``.
    """
    category = OverlayCategory(category)
    if toplevel is None and category is not OverlayCategory.MODAL_DIALOG:
        raise ValueError("toplevel=None is only allowed for native modal invocations (MODAL_DIALOG)")
    _entry, subscription = _stack(anchor).push(category, toplevel, policy)
    if toplevel is not None:

        def _on_destroy(event: Any, *, _top: Any = toplevel) -> None:
            if event.widget is _top:
                subscription.remove()

        toplevel.bind("<Destroy>", _on_destroy, add="+")
    return subscription


def overlay_state(widget: Any) -> OverlayState:
    """Return the category view of *widget*'s interpreter (entries in opening order)."""
    entries = tuple(_stack(widget).entries)

    def _affects(entry: OverlayEntry) -> bool:
        if entry.category is not OverlayCategory.MODAL_DIALOG:
            return False
        policy = entry.policy
        return policy is None or (policy.kind == POPUP_KIND_MODAL and policy.affects_mode)

    return OverlayState(
        modal_dialog=any(e.category is OverlayCategory.MODAL_DIALOG for e in entries),
        menu_open=any(e.category is OverlayCategory.MENU for e in entries),
        non_modal_popups=sum(e.category is OverlayCategory.NON_MODAL_POPUP for e in entries),
        modal_affecting_mode=any(_affects(e) for e in entries),
        entries=entries,
    )


def blocking(widget: Any, *, include_menus: bool = False, include_non_modal: bool = False) -> Callable[[], bool]:
    """Preset for a binder's ``dialog_open``: modal dialogs, optionally menus/non-modal popups.

    Presets reproducing today's app semantics: Blattwerk, aiza and Kursplaner count menu
    popups as dialogs (``include_menus=True``); Korrektor counts every visible toplevel
    (``include_non_modal=True``). Transient overlays never count.
    """

    def _is_open() -> bool:
        state = overlay_state(widget)
        return (
            state.modal_dialog
            or (include_menus and state.menu_open)
            or (include_non_modal and state.non_modal_popups > 0)
        )

    return _is_open


def modal_affecting_mode(widget: Any) -> Callable[[], bool]:
    """Preset: a modal dialog whose policy ``affects_mode`` is open (``PopupPolicyRegistry.has_mode_blocking_popup``).

    Currently no consumer: Kursplaner's characterization showed that its former scan also
    counted menu popups, so it uses ``blocking(include_menus=True)``.
    """
    return lambda: overlay_state(widget).modal_affecting_mode


def unregistered_visible_toplevels(widget: Any) -> list[Any]:
    """Diagnostics for tests: visible toplevels of the interpreter that are not registered.

    Lets consumer tests notice a popup that was added later without being registered.
    """
    root = runtime_for(widget).root
    registered = {str(e.toplevel) for e in _stack(widget).entries if e.toplevel is not None}
    found: list[Any] = []
    stack = list(root.winfo_children())
    while stack:
        child = stack.pop()
        stack.extend(child.winfo_children())
        if child.winfo_class() == "Toplevel" or child.winfo_toplevel() is child:
            try:
                visible = bool(child.winfo_viewable())
            except Exception:
                visible = False
            if visible and str(child) not in registered:
                found.append(child)
    return found
