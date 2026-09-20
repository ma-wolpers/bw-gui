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

from typing import Callable, Iterable
import tkinter as tk

from bw_gui.theming._theme_manager import get_theme

from .menu_types import MenuDefinition, MenuItem  # noqa: F401 — re-exported for callers


def _is_description_slot_replaceable(popup_stack: list, target_level: int) -> bool:
    """Pure decision (no Tk needed): may a description flyout occupy ``target_level``?

    Yes if nothing is open there yet, or if what's open there is itself a
    previously shown description flyout (tagged ``_bw_menu_description_flyout``).
    No if a real, click-opened submenu occupies that level — hovering a sibling row
    must never tear down a submenu the user explicitly opened.
    """
    if len(popup_stack) <= target_level:
        return True
    return bool(getattr(popup_stack[target_level], "_bw_menu_description_flyout", False))


class CustomMenuBar:
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
        """Close all submenus deeper than ``level``.

        Level 0 means the top-level popup from a strip button. Level 1 is the
        first submenu, and so on. Closing level N destroys levels N, N+1, ...

        Args:
            level: The popup depth to close from (inclusive). Popups below this
                level are preserved.
        """
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

    def open_popup(
        self,
        anchor_widget: tk.Widget,
        items: tuple[MenuItem, ...],
        level: int,
        top_key: str,
    ) -> None:
        """Render one popup level as a styled Toplevel window.

        Positions level-0 popups below ``anchor_widget`` (the strip button).
        Positions level-1+ popups to the right of their anchor row.
        Closes any deeper levels before opening this one.

        Also wires up keyboard navigation for the new popup (Up/Down/Enter/Right/
        Left/Escape) and gives it focus, provided it has at least one navigable
        row — a description flyout (see ``_show_item_description``) has none, so
        it is silently skipped and never steals keyboard focus.

        Args:
            anchor_widget: Widget to anchor the popup position to.
            items: The items to render in this popup.
            level: Depth in the popup stack (0 = top-level from strip button).
            top_key: The ``definition.key`` of the originating strip button.
                Used to keep the correct strip button highlighted.
        """
        self.close_popups_from_level(level)

        theme = get_theme(self.theme_key)
        popup = tk.Toplevel(self.root)
        setattr(popup, "_bw_menu_popup", True)
        popup.overrideredirect(True)
        popup.transient(self.root)
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

        navigable_rows: list[tuple[tk.Widget, MenuItem]] = []

        for item in items:
            if item.type == "separator":
                separator = tk.Frame(body, height=1, bg=theme["border"], bd=0, highlightthickness=0)
                setattr(separator, "_bw_menu_separator", True)
                separator.pack(fill="x", padx=8, pady=4)
                continue

            if item.type == "description":
                description_label = tk.Label(
                    body,
                    text=item.label,
                    anchor="w",
                    justify="left",
                    bg=theme["bg_surface"],
                    fg=theme["fg_muted"],
                    padx=10,
                    pady=6,
                    wraplength=280,
                    font=("Segoe UI", 9),
                )
                setattr(description_label, "_bw_menu_row", True)
                setattr(description_label, "_bw_menu_base_fg", theme["fg_muted"])
                description_label.pack(fill="x")
                continue

            fg = theme["fg_muted"] if item.type == "disabled" else theme["fg_primary"]
            prefix = ""
            suffix = ""
            if item.type == "radio":
                prefix = "● " if item.checked else "○ "
            if item.type == "checkbox":
                prefix = "☑ " if item.checked else "☐ "
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

            row_index = len(navigable_rows)
            navigable_rows.append((row, item))

            def _hover_on(_event, widget=row, popup_ref=popup, idx=row_index):
                widget.configure(bg=theme["accent_soft"], fg=theme["fg_primary"])
                setattr(popup_ref, "_bw_menu_active_index", idx)

            def _hover_off(_event, widget=row, base_fg=fg):
                widget.configure(bg=theme["bg_surface"], fg=base_fg)

            row.bind("<Enter>", _hover_on)
            row.bind("<Leave>", _hover_off)

            if item.description:
                row.bind(
                    "<Enter>",
                    lambda _event, r=row, desc=item.description, lvl=level, tk_=top_key: (
                        self._show_item_description(r, desc, lvl, tk_)
                    ),
                    add="+",
                )

            if item.type == "submenu":
                submenu_items = item.items
                row.bind(
                    "<Button-1>",
                    lambda _event, parent=row, children=submenu_items: self.open_popup(parent, children, level + 1, top_key),
                )
            else:
                row.bind("<Button-1>", lambda _event, cmd=item.command: self._execute_menu_command(cmd))

        setattr(popup, "_bw_menu_navigable_rows", navigable_rows)
        setattr(popup, "_bw_menu_active_index", -1)
        setattr(popup, "_bw_menu_level", level)
        setattr(popup, "_bw_menu_top_key", top_key)

        # `popup` must already be on `_popup_stack` at its correct index before
        # `_set_keyboard_active_index` runs below: highlighting row 0 may itself
        # trigger a description flyout (`_show_item_description`), which opens a
        # *nested* popup one level deeper via a re-entrant `open_popup` call. That
        # nested call relies on `_popup_stack[level]` already being this popup --
        # appending afterwards would let the deeper flyout land before it in the
        # stack, breaking the level == stack-index invariant every other method here
        # (`close_popups_from_level`, `_is_menu_managed`, ...) relies on.
        self._popup_stack.append(popup)
        self._active_key = top_key
        self._refresh_button_states()

        if navigable_rows:
            popup.bind("<Down>", lambda _event, p=popup: self._move_keyboard_active_row(p, 1))
            popup.bind("<Up>", lambda _event, p=popup: self._move_keyboard_active_row(p, -1))
            popup.bind("<Return>", lambda _event, p=popup: self._activate_keyboard_active_row(p))
            popup.bind("<KP_Enter>", lambda _event, p=popup: self._activate_keyboard_active_row(p))
            popup.bind("<Right>", lambda _event, p=popup: self._on_menu_right_key(p))
            popup.bind("<Left>", lambda _event, p=popup: self._on_menu_back_key(p))
            popup.bind("<Escape>", lambda _event, p=popup: self._on_menu_back_key(p))
            popup.focus_set()
            self._set_keyboard_active_index(popup, 0)

    def _set_keyboard_active_index(self, popup: tk.Toplevel, index: int) -> None:
        """Moves the keyboard-highlighted row of ``popup`` to ``index`` (wraps around).

        Un-highlights the previously active row (if any) via its stored
        ``_bw_menu_base_fg``, highlights the new one the same way mouse hover
        does, and — like mouse hover — triggers the row's description flyout
        (`_show_item_description`) when it has one, so keyboard and mouse
        navigation feel identical.
        """
        rows = getattr(popup, "_bw_menu_navigable_rows", [])
        if not rows:
            return

        theme = get_theme(self.theme_key)
        previous_index = getattr(popup, "_bw_menu_active_index", -1)
        if 0 <= previous_index < len(rows):
            previous_row, _previous_item = rows[previous_index]
            base_fg = getattr(previous_row, "_bw_menu_base_fg", theme["fg_primary"])
            previous_row.configure(bg=theme["bg_surface"], fg=base_fg)

        index = index % len(rows)
        row, item = rows[index]
        row.configure(bg=theme["accent_soft"], fg=theme["fg_primary"])
        setattr(popup, "_bw_menu_active_index", index)

        if item.description:
            level = getattr(popup, "_bw_menu_level", 0)
            top_key = getattr(popup, "_bw_menu_top_key", "")
            self._show_item_description(row, item.description, level, top_key)

    def _move_keyboard_active_row(self, popup: tk.Toplevel, delta: int) -> None:
        """Moves the keyboard-highlighted row by ``delta`` (Up/Down), wrapping at the ends."""
        rows = getattr(popup, "_bw_menu_navigable_rows", [])
        if not rows:
            return
        current_index = getattr(popup, "_bw_menu_active_index", 0)
        if not (0 <= current_index < len(rows)):
            current_index = 0
        self._set_keyboard_active_index(popup, current_index + delta)

    def _activate_keyboard_active_row(self, popup: tk.Toplevel) -> None:
        """Activates the keyboard-highlighted row (Enter): opens a submenu, or runs a command."""
        rows = getattr(popup, "_bw_menu_navigable_rows", [])
        index = getattr(popup, "_bw_menu_active_index", -1)
        if not (0 <= index < len(rows)):
            return
        row, item = rows[index]
        if item.type == "submenu":
            level = getattr(popup, "_bw_menu_level", 0)
            top_key = getattr(popup, "_bw_menu_top_key", "")
            self.open_popup(row, item.items, level + 1, top_key)
        else:
            self._execute_menu_command(item.command)

    def _on_menu_right_key(self, popup: tk.Toplevel) -> None:
        """Right opens the highlighted row's submenu (no-op on a leaf row)."""
        rows = getattr(popup, "_bw_menu_navigable_rows", [])
        index = getattr(popup, "_bw_menu_active_index", -1)
        if 0 <= index < len(rows) and rows[index][1].type == "submenu":
            self._activate_keyboard_active_row(popup)

    def _on_menu_back_key(self, popup: tk.Toplevel) -> None:
        """Left/Escape closes back to the parent popup, or closes everything at the top level."""
        level = getattr(popup, "_bw_menu_level", 0)
        if level <= 0:
            self.close_all_popups()
            return
        self.close_popups_from_level(level)
        if self._popup_stack:
            self._popup_stack[-1].focus_set()

    def _show_item_description(
        self, anchor_row: tk.Widget, description: str, level: int, top_key: str
    ) -> None:
        """Shows or replaces the non-interactive description flyout for a hovered row.

        Renders at ``level + 1`` — the same popup level a click-opened submenu of
        ``anchor_row`` would occupy — never as an extra level of its own. Reuses
        ``open_popup`` itself (with a single synthetic ``type="description"`` item)
        so the flyout gets the exact same positioning, theming, and popup-stack
        lifecycle as every other popup level; it is tagged via
        ``_bw_menu_description_flyout`` right after creation so later calls can tell
        it apart from a real, click-opened submenu.

        If a real submenu is already open at ``level + 1`` (the user clicked into
        it), this does nothing — hovering a sibling row must never close a submenu
        the user explicitly opened. If a description flyout is already open there
        (from a previously hovered sibling), ``open_popup``'s own
        ``close_popups_from_level`` call replaces it immediately in the same step —
        no intermediate state where both are visible, no delay.
        """
        target_level = level + 1
        if not _is_description_slot_replaceable(self._popup_stack, target_level):
            return

        self.open_popup(anchor_row, (MenuItem(type="description", label=description),), target_level, top_key)
        if self._popup_stack:
            setattr(self._popup_stack[-1], "_bw_menu_description_flyout", True)

    def _execute_menu_command(self, command: Callable[[], None] | None) -> None:
        """Close all popups, then invoke the command if it is callable."""
        self.close_all_popups()
        if callable(command):
            command()

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

    def _bind_handlers(self) -> None:
        """Bind global click, Alt-key, focus, and deactivate handlers (once only)."""
        if self._bound:
            return

        self.root.bind_all("<Button-1>", self._on_global_click, add="+")
        self.root.bind_all("<Alt-KeyPress>", self._on_alt_keypress, add="+")
        self.root.bind_all("<FocusIn>", self._on_focus_change, add="+")
        self.root.bind_all("<FocusOut>", self._on_focus_change, add="+")
        self.root.bind("<Unmap>", self._on_deactivate, add="+")
        self.root.bind("<Deactivate>", self._on_deactivate, add="+")

        self._bound = True

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

    def _on_alt_keypress(self, event) -> str | None:
        """Handle Alt+key presses and open the matching section's menu if found."""
        key = str(getattr(event, "keysym", "") or getattr(event, "char", "")).lower()
        if not key:
            return None
        for definition in self.definitions:
            if definition.alt.lower() == key:
                return self._on_mnemonic(definition)
        return None

    def _on_mnemonic(self, definition: MenuDefinition) -> str:
        """Open the top menu for the matched definition and return "break" to stop propagation."""
        self.open_top_menu(definition)
        return "break"

    def _on_deactivate(self, _event=None) -> None:
        """Close all popups when the window loses focus or is unmapped."""
        if self._popup_stack:
            self.close_all_popups()

    def _on_focus_change(self, _event=None) -> None:
        """Schedule a focus-outside check when any focus event fires with popups open."""
        if not self._popup_stack:
            return
        self._schedule_focus_check()

    def _schedule_focus_check(self) -> None:
        """Schedule ``_close_if_focus_outside_menu()`` to run after idle."""
        self._cancel_focus_check()
        try:
            self._focus_check_after_id = self.root.after_idle(self._close_if_focus_outside_menu)
        except tk.TclError:
            self._focus_check_after_id = None

    def _cancel_focus_check(self) -> None:
        """Cancel a pending after_idle focus-check callback."""
        if not self._focus_check_after_id:
            return
        try:
            self.root.after_cancel(self._focus_check_after_id)
        except tk.TclError:
            pass
        self._focus_check_after_id = None

    def _close_if_focus_outside_menu(self) -> None:
        """Close all popups if the currently focused widget is not inside the menu."""
        self._focus_check_after_id = None
        if not self._popup_stack:
            return
        try:
            focused = self.root.focus_displayof()
        except tk.TclError:
            self.close_all_popups()
            return
        if focused is None or not self._is_menu_managed(focused):
            self.close_all_popups()

    def _on_global_click(self, event) -> None:
        """Close all popups when the user clicks outside the menu area."""
        if not self._popup_stack:
            return
        if self._is_menu_managed(getattr(event, "widget", None)):
            return
        self.close_all_popups()

    def _is_menu_managed(self, widget: tk.Widget | None) -> bool:
        """Return True if ``widget`` is part of the strip or any open popup.

        Walks the widget hierarchy upward to check whether the widget is a
        descendant of the strip frame or any popup Toplevel in the current stack.

        Args:
            widget: The widget to check. None returns False.

        Returns:
            True if the widget is inside the menu system.
        """
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
