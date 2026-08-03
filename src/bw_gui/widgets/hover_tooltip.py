"""Shared hover tooltip utility with optional theme colors."""

from __future__ import annotations

import tkinter as tk

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
    ):
        self.widget = widget
        self.text = text.strip()
        self.theme_key = theme_key
        self.show_delay_ms = max(0, int(show_delay_ms))
        self.wraplength = max(120, int(wraplength))
        self._tip: tk.Toplevel | None = None
        self._widgets: list[tk.Widget] = []
        self._show_after_id: str | None = None

        if not self.text:
            return

        self.bind_widget(widget)

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

    @staticmethod
    def _clamp_to_screen(
        x_pos: int,
        y_pos: int,
        tip_width: int,
        tip_height: int,
        screen_width: int,
        screen_height: int,
    ) -> tuple[int, int]:
        margin = 8
        max_x = max(margin, screen_width - tip_width - margin)
        max_y = max(margin, screen_height - tip_height - margin)
        return (max(margin, min(x_pos, max_x)), max(margin, min(y_pos, max_y)))

    def _show(self, _event=None) -> None:
        self._show_after_id = None
        if self._tip is not None:
            return

        active = HoverTooltip._active_owner
        if active is not None and active is not self:
            active._hide()

        try:
            x_pos = self.widget.winfo_rootx() + 16
            y_pos = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except tk.TclError:
            return

        theme = get_theme(self._resolve_theme_key())
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)

        label = tk.Label(
            tip,
            text=self.text,
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

        tip.update_idletasks()
        tip_width = max(1, int(tip.winfo_reqwidth()))
        tip_height = max(1, int(tip.winfo_reqheight()))
        screen_width = max(1, int(self.widget.winfo_screenwidth()))
        screen_height = max(1, int(self.widget.winfo_screenheight()))

        if y_pos + tip_height + 8 > screen_height:
            y_pos = y_pos - tip_height - self.widget.winfo_height() - 14

        x_pos, y_pos = self._clamp_to_screen(
            x_pos,
            y_pos,
            tip_width,
            tip_height,
            screen_width,
            screen_height,
        )
        tip.wm_geometry(f"+{x_pos}+{y_pos}")

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
