from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class MenuItem:
    """One item in a menu popup — action, separator, radio, or submenu."""

    type: str  # "command", "separator", "disabled", "radio", "submenu"
    label: str = ""
    command: Callable[[], None] | None = None
    checked: bool = False
    items: tuple[MenuItem, ...] = ()


@dataclass(frozen=True)
class MenuDefinition:
    """One section in the menu bar strip."""

    key: str
    label: str
    alt: str
    items_provider: Callable[[], Iterable[MenuItem]]
