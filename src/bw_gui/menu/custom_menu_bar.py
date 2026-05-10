"""Themed custom menubar replacing native Tk menubar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable
import tkinter as tk

from bw_gui.theming.theme_manager import get_theme


@dataclass(frozen=True)
class MenuItem:
    """Declarative menu row entry for popup rendering."""

    type: str
    label: str = ""
    command: Callable[[], None] | None = None
    checked: bool = False
    items: tuple["MenuItem", ...] = ()


@dataclass(frozen=True)
class MenuDefinition:
    """Top-level menu definition."""

    key: str
    label: str
    alt: str
    items_provider: Callable[[], Iterable[MenuItem]]


class CustomMenuBar:
    """Reusable themed menu strip with popup support and mnemonic access."""

    def __init__(self, root: tk.Misc, definitions: Iterable[MenuDefinition], *, theme_key: str):
        self.root = root
        self.definitions = tuple(definitions)
        self.theme_key = theme_key
        self.strip: tk.Frame | None = None
        self._buttons: dict[str, tk.Button] = {}
        self._popup_stack: list[tk.Toplevel] = []
        self._active_key: str | None = None
        self._bound = False

    def set_definitions(self, definitions: Iterable[MenuDefinition]) -> None:
        """Replace menu definitions and rebuild if strip already exists."""
        self.definitions = tuple(definitions)
        if self.strip is not None and self.strip.winfo_exists():
            self.build()

    def build(self) -> None:
        """Build or rebuild the top menu strip."""
        self.destroy()
        theme = get_theme(self.theme_key)
        strip = tk.Frame(self.root, bg=theme["bg_surface"], highlightthickness=1, highlightbackground=theme["border"], bd=0)
        children = [child for child in self.root.winfo_children() if child is not strip]
        if children:
            strip.pack(fill="x", side="top", before=children[0])
        else:
            strip.pack(fill="x", side="top")
        self.strip = strip

        for definition in self.definitions:
            underline_index = self._underline_index(definition.label, definition.alt)
            button = tk.Button(
                strip,
                text=definition.label,
                underline=underline_index,
                relief="flat",
                bd=0,
                padx=10,
                pady=5,
                bg=theme["bg_surface"],
                fg=theme["fg_primary"],
                activebackground=theme["accent_soft"],
                activeforeground=theme["fg_primary"],
                command=lambda d=definition: self.open_top_menu(d),
            )
            button.pack(side="left", padx=(0, 2))
            self._buttons[definition.key] = button

        self._bind_handlers()
        self._refresh_button_states()

    def refresh_theme(self, theme_key: str) -> None:
        """Apply another theme and update visible widgets."""
        self.theme_key = theme_key
        if self.strip is None or not self.strip.winfo_exists():
            return
        theme = get_theme(theme_key)
        self.strip.configure(bg=theme["bg_surface"], highlightbackground=theme["border"])
        self._refresh_button_states()
        self._refresh_popup_theme()

    def destroy(self) -> None:
        """Destroy strip and close open popup windows."""
        self.close_all_popups()
        if self.strip is not None and self.strip.winfo_exists():
            self.strip.destroy()
        self.strip = None
        self._buttons = {}

    def close_all_popups(self) -> None:
        """Close all open menu popups."""
        for popup in list(self._popup_stack):
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass
        self._popup_stack = []
        self._active_key = None
        self._refresh_button_states()

    def close_popups_from_level(self, level: int) -> None:
        """Close submenus deeper than a requested level."""
        stack = list(self._popup_stack)
        while len(stack) > level:
            popup = stack.pop()
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass
        self._popup_stack = stack

    def open_top_menu(self, definition: MenuDefinition) -> None:
        """Open one top-level popup below its button."""
        button = self._buttons.get(definition.key)
        if button is None or not button.winfo_exists():
            return

        if self._active_key == definition.key and self._popup_stack:
            self.close_all_popups()
            return

        self.open_popup(button, tuple(definition.items_provider()), 0, definition.key)

    def open_popup(self, anchor_widget: tk.Widget, items: tuple[MenuItem, ...], level: int, top_key: str) -> None:
        """Render one popup level with command and submenu entries."""
        self.close_popups_from_level(level)

        theme = get_theme(self.theme_key)
        popup = tk.Toplevel(self.root)
        setattr(popup, "_bw_menu_popup", True)
        popup.overrideredirect(True)
        popup.transient(self.root)
        popup.attributes("-topmost", True)
        popup.configure(bg=theme["border"], bd=1, highlightthickness=0)

        body = tk.Frame(popup, bg=theme["bg_surface"], bd=0, highlightthickness=0)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        setattr(popup, "_bw_menu_body", body)

        if level == 0:
            x_pos = anchor_widget.winfo_rootx()
            y_pos = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        else:
            x_pos = anchor_widget.winfo_rootx() + anchor_widget.winfo_width() - 1
            y_pos = anchor_widget.winfo_rooty()
        popup.geometry(f"+{int(x_pos)}+{int(y_pos)}")
        popup.lift()

        for item in items:
            if item.type == "separator":
                separator = tk.Frame(body, height=1, bg=theme["border"], bd=0, highlightthickness=0)
                setattr(separator, "_bw_menu_separator", True)
                separator.pack(fill="x", padx=8, pady=4)
                continue

            fg = theme["fg_muted"] if item.type == "disabled" else theme["fg_primary"]
            prefix = ""
            suffix = ""
            if item.type == "radio":
                prefix = "● " if item.checked else "○ "
            if item.type == "submenu":
                suffix = "   ▸"

            row = tk.Label(
                body,
                text=f"{prefix}{item.label}{suffix}",
                anchor="w",
                justify="left",
                bg=theme["bg_surface"],
                fg=fg,
                padx=10,
                pady=6,
                font=("Segoe UI", 9),
            )
            setattr(row, "_bw_menu_row", True)
            setattr(row, "_bw_menu_base_fg", fg)
            row.pack(fill="x")

            if item.type == "disabled":
                continue

            def _hover_on(_event, widget=row):
                widget.configure(bg=theme["accent_soft"], fg=theme["fg_primary"])

            def _hover_off(_event, widget=row, base_fg=fg):
                widget.configure(bg=theme["bg_surface"], fg=base_fg)

            row.bind("<Enter>", _hover_on)
            row.bind("<Leave>", _hover_off)

            if item.type == "submenu":
                submenu_items = item.items
                row.bind(
                    "<Button-1>",
                    lambda _event, parent=row, children=submenu_items: self.open_popup(parent, children, level + 1, top_key),
                )
            else:
                row.bind("<Button-1>", lambda _event, cmd=item.command: self._execute_menu_command(cmd))

        self._popup_stack.append(popup)
        self._active_key = top_key
        self._refresh_button_states()

    def _execute_menu_command(self, command: Callable[[], None] | None) -> None:
        self.close_all_popups()
        if callable(command):
            command()

    def _refresh_button_states(self) -> None:
        if self.strip is None or not self.strip.winfo_exists():
            return
        theme = get_theme(self.theme_key)
        for key, button in self._buttons.items():
            if not button.winfo_exists():
                continue
            active = key == self._active_key and bool(self._popup_stack)
            button.configure(
                bg=theme["accent_soft"] if active else theme["bg_surface"],
                fg=theme["fg_primary"],
                activebackground=theme["accent_soft"],
                activeforeground=theme["fg_primary"],
            )

    def _refresh_popup_theme(self) -> None:
        theme = get_theme(self.theme_key)
        for popup in list(self._popup_stack):
            try:
                if not popup.winfo_exists():
                    continue
                popup.configure(bg=theme["border"])
                body = getattr(popup, "_bw_menu_body", None)
                if body is not None and body.winfo_exists():
                    body.configure(bg=theme["bg_surface"])
                    for child in body.winfo_children():
                        if getattr(child, "_bw_menu_separator", False):
                            child.configure(bg=theme["border"])
                            continue
                        if not getattr(child, "_bw_menu_row", False):
                            continue
                        base_fg = getattr(child, "_bw_menu_base_fg", theme["fg_primary"])
                        child.configure(bg=theme["bg_surface"], fg=base_fg)
            except tk.TclError:
                continue

    def _bind_handlers(self) -> None:
        if self._bound:
            return

        self.root.bind_all("<Button-1>", self._on_global_click, add="+")
        self.root.bind_all("<Alt-KeyPress>", self._on_alt_keypress, add="+")
        self.root.bind("<Unmap>", self._on_deactivate, add="+")
        self.root.bind("<Deactivate>", self._on_deactivate, add="+")

        self._bound = True

    @staticmethod
    def _underline_index(label: str, mnemonic: str) -> int:
        if not label or not mnemonic:
            return -1
        lowered = label.lower()
        target = mnemonic.lower()
        return lowered.find(target)

    def _on_alt_keypress(self, event) -> str | None:
        key = str(getattr(event, "keysym", "") or getattr(event, "char", "")).lower()
        if not key:
            return None
        for definition in self.definitions:
            if definition.alt.lower() == key:
                return self._on_mnemonic(definition)
        return None

    def _on_mnemonic(self, definition: MenuDefinition) -> str:
        self.open_top_menu(definition)
        return "break"

    def _on_deactivate(self, _event=None) -> None:
        if self._popup_stack:
            self.close_all_popups()

    def _on_global_click(self, event) -> None:
        if not self._popup_stack:
            return
        if self._is_menu_managed(getattr(event, "widget", None)):
            return
        self.close_all_popups()

    def _is_menu_managed(self, widget: tk.Widget | None) -> bool:
        if widget is None:
            return False

        roots: list[tk.Widget] = []
        if self.strip is not None and self.strip.winfo_exists():
            roots.append(self.strip)
        for popup in self._popup_stack:
            if popup.winfo_exists():
                roots.append(popup)

        current = widget
        while current is not None:
            if any(current == root for root in roots):
                return True
            parent_name = current.winfo_parent()
            if not parent_name:
                break
            try:
                current = current._nametowidget(parent_name)
            except Exception:
                break
        return False
