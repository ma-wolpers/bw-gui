from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class MenuItem:
    """One item in a menu popup — action, separator, radio, or submenu.

    ``description``: optional explanatory text shown, on hover over this item, as a
    non-interactive, submenu-positioned flyout. It is not a generic tooltip: it has
    no open delay, replaces any previously shown sibling description immediately
    (never two visible at once), stays open for as long as the surrounding popup
    context stays open (leaving the anchor row alone does not close it), accepts no
    mouse interaction of its own, and is torn down only by the existing popup
    lifecycle (replacement by another described row, or the popup context closing via
    outside click, focus loss, deactivation, or an ancestor popup closing). Optional
    and `None` by default — an item without a description is a normal, valid state.
    """

    type: str  # "command", "separator", "disabled", "radio", "checkbox", "submenu"
    label: str = ""
    command: Callable[[], None] | None = None
    checked: bool = False
    items: tuple[MenuItem, ...] = ()
    description: str | None = None


@dataclass(frozen=True)
class MenuDefinition:
    """One section in the menu bar strip."""

    key: str
    label: str
    alt: str
    items_provider: Callable[[], Iterable[MenuItem]]
