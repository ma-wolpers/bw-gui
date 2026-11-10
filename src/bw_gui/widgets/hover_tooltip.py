"""Shared hover tooltip utility with optional theme colors."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from bw_gui.contracts.screen_geometry import Rect, Side
from bw_gui.runtime.overlay_stack import OverlayCategory, register_overlay
from bw_gui.runtime.screen_placement import new_overlay_window, place_overlay_now
from bw_gui.theming._theme_manager import get_theme


class HoverTooltip:
    """Simple hover help for Tk widgets, optionally themed."""

    _active_owner: "HoverTooltip | None" = None

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        *,
        theme_key: str | None = None,
        show_delay_ms: int = 350,
        wraplength: int = 460,
        text_provider: Callable[[], str] | None = None,
    ):
        """Attach the tooltip to *widget*.

        Args:
            widget: First hit area.
            text: Fixed text; ignored when *text_provider* is given.
            theme_key: Explicit theme; otherwise the toplevel's ``theme_var``.
            show_delay_ms: Hover delay before the tip appears.
            wraplength: Line width in pixels.
            text_provider: Builds the text each time the tip appears, e.g. from a
                shortcut registry filled after the widget was built, so the shown key
                always matches the current binding. An empty result shows nothing.
        """
        self.widget = widget
        self.text = text.strip()
        self.text_provider = text_provider
        self.theme_key = theme_key
        self.show_delay_ms = max(0, int(show_delay_ms))
        self.wraplength = max(120, int(wraplength))
        self._tip: tk.Toplevel | None = None
        self._widgets: list[tk.Widget] = []
        self._show_after_id: str | None = None

        if not self.text and text_provider is None:
            return

        self.bind_widget(widget)

    def current_text(self) -> str:
        """The text the tip shows now (from *text_provider* if set, else the fixed text)."""
        if self.text_provider is not None:
            return (self.text_provider() or "").strip()
        return self.text

    def bind_widget(self, widget: tk.Widget) -> None:
        """Register additional hit areas for the same tooltip."""
        if widget in self._widgets:
            return
        self._widgets.append(widget)
        widget.bind("<Enter>", self._schedule_show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")
        widget.bind("<Unmap>", self._hide, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")

    def _schedule_show(self, _event=None) -> None:
        if self._tip is not None:
            return
        self._cancel_scheduled_show()
        try:
            self._show_after_id = self.widget.after(self.show_delay_ms, self._show)
        except tk.TclError:
            self._show_after_id = None

    def _cancel_scheduled_show(self) -> None:
        if not self._show_after_id:
            return
        try:
            self.widget.after_cancel(self._show_after_id)
        except tk.TclError:
            pass
        self._show_after_id = None

    def _resolve_theme_key(self) -> str | None:
        if self.theme_key:
            return self.theme_key
        try:
            root = self.widget.winfo_toplevel()
            theme_var = getattr(root, "theme_var", None)
            if theme_var is not None and hasattr(theme_var, "get"):
                value = theme_var.get()
                if value:
                    return str(value)
        except Exception:
            return None
        return None

    def _show(self, _event=None) -> None:
        self._show_after_id = None
        if self._tip is not None:
            return

        text = self.current_text()
        if not text:
            return

        active = HoverTooltip._active_owner
        if active is not None and active is not self:
            active._hide()

        try:
            widget_x = int(self.widget.winfo_rootx())
            widget_y = int(self.widget.winfo_rooty())
            widget_height = max(1, int(self.widget.winfo_height()))
        except tk.TclError:
            return
        # Anchor: a 1px-wide strip 16px right of the widget's left edge spanning its
        # height, so "below" lands 8px under the widget and "above" 8px over it.
        anchor = Rect(widget_x + 16, widget_y, widget_x + 17, widget_y + widget_height)

        theme = get_theme(self._resolve_theme_key())
        tip = new_overlay_window(self.widget)  # hidden until place_overlay_now reveals it
        register_overlay(tip, OverlayCategory.TRANSIENT, toplevel=tip)

        label = tk.Label(
            tip,
            text=text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=self.wraplength,
            bg=theme["bg_surface"],
            fg=theme["fg_primary"],
            highlightthickness=1,
            highlightbackground=theme["border"],
        )
        label.pack()

        place_overlay_now(tip, anchor=anchor, placement=(Side.BELOW, Side.ABOVE), tk_context=self.widget, gap=8)

        self._tip = tip
        HoverTooltip._active_owner = self

    def _hide(self, _event=None) -> None:
        self._cancel_scheduled_show()
        if self._tip is None:
            return
        try:
            self._tip.destroy()
        except tk.TclError:
            pass
        self._tip = None
        if HoverTooltip._active_owner is self:
            HoverTooltip._active_owner = None
