"""Shared hover tooltip utility with optional theme colors."""

from __future__ import annotations

import tkinter as tk

from bw_gui.theming.theme_manager import get_theme


class HoverTooltip:
    """Simple hover help for Tk widgets, optionally themed."""

    _active_owner: "HoverTooltip | None" = None

    def __init__(self, widget: tk.Widget, text: str, *, theme_key: str | None = None):
        self.widget = widget
        self.text = text.strip()
        self.theme_key = theme_key
        self._tip: tk.Toplevel | None = None
        self._widgets: list[tk.Widget] = []

        if not self.text:
            return

        self.bind_widget(widget)

    def bind_widget(self, widget: tk.Widget) -> None:
        """Register additional hit areas for the same tooltip."""
        if widget in self._widgets:
            return
        self._widgets.append(widget)
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self._tip is not None:
            return

        active = HoverTooltip._active_owner
        if active is not None and active is not self:
            active._hide()

        x_pos = self.widget.winfo_rootx() + 16
        y_pos = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        theme = get_theme(self.theme_key)
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x_pos}+{y_pos}")

        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=460,
            bg=theme["bg_surface"],
            fg=theme["fg_primary"],
            highlightthickness=1,
            highlightbackground=theme["border"],
        )
        label.pack()

        self._tip = tip
        HoverTooltip._active_owner = self

    def _hide(self, _event=None) -> None:
        if self._tip is None:
            return
        self._tip.destroy()
        self._tip = None
        if HoverTooltip._active_owner is self:
            HoverTooltip._active_owner = None
