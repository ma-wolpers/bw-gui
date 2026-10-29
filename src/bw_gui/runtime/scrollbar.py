"""The bw-gui scrollbar primitive (``docs/SCROLLABILITY_CONTRACT.md``, decision 1).

The only scrollbar of bw-gui and its apps: ``bw_gui.runtime.widgets.Scrollbar`` is this
class (the ttk facade replaces ``ttk.Scrollbar``). It is a native ``tk.Scrollbar`` -- on
Windows the slim system scrollbar -- not a ttk/clam scrollbar with arrow buttons.

* **Options:** only ``orient``, ``command`` and ``takefocus`` (``bool`` or ``None``), plus the
  inherited geometry managers and ``set``/``get``. Any other option -- in the constructor,
  ``configure``/``config`` or item assignment -- raises ``TypeError`` (ttk-only options such
  as ``style`` have no meaning here).
* **``takefocus=None``** keeps the measured behaviour of the former ttk scrollbars: they were
  skipped by Tab traversal (2026-10-18 measurement), and so is a native scrollbar by
  default. ``True``/``False`` force it.
* **Theme:** a theme listener (``THEME_CONTRACT.md``, owner: the scrollbar) follows every
  switch -- on win32 the native dark mode (``_win_dark_controls``) for dark themes, on other
  platforms the theme colours (thumb ``panel_strong``, trough ``bg_surface``, active
  ``accent_soft``). The listener ends with the widget.
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Any

from ._win_dark_controls import set_native_dark_mode
from .widget_events import on_destroy

__all__ = ["Scrollbar"]

_ALLOWED = ("orient", "command", "takefocus")


def _tk_takefocus(value: bool | None) -> Any:
    if value is None:
        return ""
    if not isinstance(value, bool):
        raise TypeError(f"takefocus must be bool or None, got {type(value).__name__}")
    return 1 if value else 0


def _checked(options: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(options) - set(_ALLOWED))
    if unknown:
        raise TypeError(f"Scrollbar accepts only {', '.join(_ALLOWED)}; got {', '.join(unknown)}")
    if "takefocus" in options:
        options["takefocus"] = _tk_takefocus(options["takefocus"])
    return options


class Scrollbar(tk.Scrollbar):
    """Native scrollbar following the bw-gui theme (see module docstring)."""

    def __init__(
        self,
        master: Any = None,
        *,
        orient: str = "vertical",
        command: Any = None,
        takefocus: bool | None = None,
        **options: Any,
    ) -> None:
        """Create the scrollbar.

        Raises:
            TypeError: An option other than ``orient``, ``command``, ``takefocus``.
        """
        _checked(dict(options))
        native = {"orient": orient, "takefocus": _tk_takefocus(takefocus), "highlightthickness": 0, "borderwidth": 0}
        if command is not None:
            native["command"] = command
        super().__init__(master, **native)
        from bw_gui.theming._theme_listeners import register_theme_listener  # late: theming imports runtime pieces

        self._theme_subscription = register_theme_listener(self._on_theme_changed, owner=self)
        # Widget-bound: stop listening on <Destroy>, before the interpreter may be gone
        # (a later winfo_exists() on a destroyed interpreter raises instead of returning 0).
        on_destroy(self, lambda _widget: self._theme_subscription.remove())
        self._apply_theme()

    def configure(self, cnf: dict[str, Any] | None = None, **options: Any) -> Any:
        """Change ``orient``/``command``/``takefocus`` (no arguments: return the options)."""
        merged = {**(cnf or {}), **options}
        if not merged:
            return super().configure()
        return super().configure(**_checked(merged))

    config = configure

    def __setitem__(self, key: str, value: Any) -> None:
        self.configure(**{key: value})

    def _on_theme_changed(self, change: Any) -> None:
        if not self.winfo_exists():
            self._theme_subscription.remove()
            return
        self._apply_theme(change.is_dark)

    def _apply_theme(self, is_dark: bool | None = None) -> None:
        """Dark mode (win32) or theme colours (elsewhere) for the current theme."""
        from bw_gui.theming._color_math import is_dark_color
        from bw_gui.theming._theme_manager import get_theme

        theme = get_theme()
        dark = is_dark_color(theme["bg_main"]) if is_dark is None else is_dark
        if sys.platform == "win32":
            set_native_dark_mode(self, dark)
            return
        tk.Scrollbar.configure(
            self, background=theme["panel_strong"], troughcolor=theme["bg_surface"], activebackground=theme["accent_soft"]
        )
