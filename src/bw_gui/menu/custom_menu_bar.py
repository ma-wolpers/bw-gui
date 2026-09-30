"""Themed custom menubar replacing the native Tk menubar.

``CustomMenuBar`` renders a horizontal strip of ``tk.Button`` widgets at the top of
the root window. Clicking a button opens a floating ``tk.Toplevel`` popup with the
section's items. Submenus open as nested popups to the right.

This replaces the native ``tk.Menu`` / ``root.config(menu=...)`` approach entirely, which
allows the menubar to be fully themed (colors, fonts, borders) using the same token
system as the rest of the application.

Any ``MenuItem`` may also carry a ``description`` — see ``MenuItem`` for the exact
contract. On hover it opens a non-interactive, submenu-positioned flyout
(``_show_item_description``), living in the same ``_popup_stack`` as every other
popup level.

Every popup with at least one navigable row is keyboard-operable once open: Up/Down
move the highlighted row (wrapping), Enter/Return activates it (opens a submenu or
runs its command), Right opens a highlighted submenu, and Left/Escape closes back to
the parent popup (or closes everything at the top level). The first row is
highlighted and the popup takes keyboard focus as soon as it opens, from a mouse
click or from keyboard activation alike.

Typical usage::

    from bw_gui.menu.custom_menu_bar import CustomMenuBar, MenuItem, MenuDefinition

    defs = (
        MenuDefinition("file", "Datei", "d", items_provider=my_file_items),
    )
    bar = CustomMenuBar(root, defs, theme_key="mono_day")
    bar.build()
"""

from __future__ import annotations

from typing import Iterable
import tkinter as tk

from bw_gui.theming._theme_manager import get_theme

from .menu_types import MenuDefinition, MenuItem  # noqa: F401 — re-exported for callers
from ._menu_focus import _MenuFocusMixin
from ._menu_popups import _MenuPopupsMixin, _is_description_slot_replaceable  # noqa: F401 - re-exported


class CustomMenuBar(_MenuPopupsMixin, _MenuFocusMixin):
    """Themed menu strip widget with popup stack management and mnemonic access.

    Low-level API — not exported from ``bw_gui`` top-level. Use ``BwBaseWindow`` instead.

    Renders as a ``tk.Frame`` strip packed at the top of the root window, containing
    one ``tk.Button`` per registered menu definition. Clicking a button opens a
    styled ``tk.Toplevel`` popup. Submenus open recursively as additional Toplevels.

    The popup stack is tracked explicitly so closing at one level destroys any
    deeper levels first. A global click handler closes all popups when the user
    clicks outside the menu.

    Theme changes are applied via ``refresh_theme()`` which re-colors the strip,
    buttons, and any currently open popup frames without rebuilding the widget tree.

    Attributes:
        root: The root Tk widget that owns this menubar.
        definitions: Ordered tuple of ``MenuDefinition`` objects to render.
        theme_key: The currently active theme key.
        strip: The tk.Frame strip widget, or None before ``build()`` is called.
    """

    def __init__(self, root: tk.Misc, definitions: Iterable[MenuDefinition], *, theme_key: str):
        """Store configuration but do not create any widgets yet.

        Call ``build()`` after construction to create the strip and buttons.

        Args:
            root: The root or host Tk window to attach the strip to.
            definitions: Ordered menu definitions to render.
            theme_key: Initial theme key for colors and styling.
        """
        self.root = root
        self.definitions = tuple(definitions)
        self.theme_key = theme_key
        self.strip: tk.Frame | None = None
        self._buttons: dict[str, tk.Button] = {}
        self._popup_stack: list[tk.Toplevel] = []
        self._active_key: str | None = None
        self._focus_check_after_id: str | None = None
        self._focus_watchdog_suspend_depth = 0
        self._bound = False

    def set_definitions(self, definitions: Iterable[MenuDefinition]) -> None:
        """Replace the menu definitions and rebuild the strip if it already exists.

        Use this to update the menubar after the root window's sections change
        (e.g. after a plugin adds a new menu).

        Args:
            definitions: New ordered menu definitions.
        """
        self.definitions = tuple(definitions)
        if self.strip is not None and self.strip.winfo_exists():
            self.build()

    def build(self) -> None:
        """Create or recreate the strip frame and all menu buttons.

        Destroys any existing strip before building. Inserts the strip before
        the first existing child of ``root`` so it always appears at the top.
        Binds the global click, Alt-key, and focus handlers on the first call.
        """
        self.destroy()
        theme = get_theme(self.theme_key)
        strip = tk.Frame(
            self.root,
            bg=theme["bg_surface"],
            highlightthickness=1,
            highlightbackground=theme["border"],
            bd=0,
        )
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
        """Apply a new theme to the strip, buttons, and any open popup frames.

        Does nothing if the strip has not been built or has been destroyed.

        Args:
            theme_key: The theme key to switch to.
        """
        self.theme_key = theme_key
        if self.strip is None or not self.strip.winfo_exists():
            return
        theme = get_theme(theme_key)
        self.strip.configure(bg=theme["bg_surface"], highlightbackground=theme["border"])
        self._refresh_button_states()
        self._refresh_popup_theme()

    def destroy(self) -> None:
        """Close all open popups and destroy the strip frame, resetting all state."""
        self._cancel_focus_check()
        self.close_all_popups()
        if self.strip is not None and self.strip.winfo_exists():
            self.strip.destroy()
        self.strip = None
        self._buttons = {}


    def close_all_popups(self) -> None:
        """Close every open menu popup and clear the active key highlight."""
        self.close_popups_from_level(0)
        self._active_key = None
        self._refresh_button_states()

    def close_popups_from_level(self, level: int) -> None:
        """Close all submenus deeper than ``level``.

        Level 0 means the top-level popup from a strip button. Level 1 is the
        first submenu, and so on. Closing level N destroys levels N, N+1, ...

        If anything will actually be destroyed, keyboard focus is reclaimed
        for ``root`` *first*: whichever popup here currently holds keyboard
        focus (see ``open_popup``'s ``focus_set()``) is destroyed below, and
        destroying a Toplevel that still holds keyboard focus is unsafe on
        Windows -- it can leave the *whole application's* keyboard input
        stuck (no editor cursor, no typing anywhere) until the user switches
        window focus away and back. This single chokepoint covers every
        caller (mouse-click submenu replacement, `_on_menu_back_key`,
        `close_all_popups`, a hovered description flyout replacing a sibling)
        without each needing to reason about it separately. A caller that
        wants focus to land somewhere more specific afterward (the parent
        popup on Left/Escape, a freshly built popup at the end of
        `open_popup`) sets that itself right after calling this.

        Args:
            level: The popup depth to close from (inclusive). Popups below this
                level are preserved.
        """
        stack = list(self._popup_stack)
        if len(stack) > level:
            try:
                self.root.focus_set()
            except tk.TclError:
                pass
        while len(stack) > level:
            popup = stack.pop()
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass
        self._popup_stack = stack

    def open_top_menu(self, definition: MenuDefinition) -> None:
        """Toggle the top-level popup for one strip button.

        If the same button's popup is already open, this closes it (toggle behavior).
        Otherwise, opens the popup below the button.

        Args:
            definition: The menu definition whose popup to open.
        """
        button = self._buttons.get(definition.key)
        if button is None or not button.winfo_exists():
            return

        if self._active_key == definition.key and self._popup_stack:
            self.close_all_popups()
            return

        self.open_popup(button, tuple(definition.items_provider()), 0, definition.key)


    def _refresh_button_states(self) -> None:
        """Re-color all strip buttons to reflect which menu is currently open."""
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
        """Re-color all open popup frames without closing or rebuilding them."""
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


    @staticmethod
    def _underline_index(label: str, mnemonic: str) -> int:
        """Return the index of the mnemonic character in the label, or -1 if not found.

        Args:
            label: The button label text to search.
            mnemonic: Single character to find (case-insensitive).

        Returns:
            Zero-based index of the first occurrence, or -1.
        """
        if not label or not mnemonic:
            return -1
        lowered = label.lower()
        target = mnemonic.lower()
        return lowered.find(target)


