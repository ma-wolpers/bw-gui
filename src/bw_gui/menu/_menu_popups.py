"""Popup building and keyboard navigation for ``CustomMenuBar`` (private mixin).

Split out of ``custom_menu_bar`` (file-size rule); method bodies are unchanged. The
mixin relies on the state that ``CustomMenuBar.__init__`` sets up (``root``,
``theme_key``, ``_popup_stack``, ...).
"""

from __future__ import annotations

from typing import Callable
import tkinter as tk

from bw_gui.contracts.screen_geometry import Side, Size
from bw_gui.runtime.screen_placement import place_overlay_now, widget_rect
from bw_gui.theming._theme_manager import get_theme

from ._toggle_glyphs import glyph_image, glyph_row_pady, is_binary, menu_item_command, text_prefix
from .menu_types import MenuItem


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


class _MenuPopupsMixin:
    """Popups, rows, description flyouts and keyboard navigation of the menu bar."""

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

        Runs under ``_focus_watchdog_suspended`` — see its docstring: closing a
        previous popup here to make room, then focusing the new one, is exactly
        the kind of internal focus juggling the click-away watchdog must not
        mistake for the user clicking elsewhere.

        Args:
            anchor_widget: Widget to anchor the popup position to.
            items: The items to render in this popup.
            level: Depth in the popup stack (0 = top-level from strip button).
            top_key: The ``definition.key`` of the originating strip button.
                Used to keep the correct strip button highlighted.
        """
        with self._focus_watchdog_suspended():
            self._open_popup_impl(anchor_widget, items, level, top_key)

    def _open_popup_impl(
        self,
        anchor_widget: tk.Widget,
        items: tuple[MenuItem, ...],
        level: int,
        top_key: str,
    ) -> None:
        """The actual body of ``open_popup``, run inside its watchdog-suspended block."""
        self.close_popups_from_level(level)

        theme = get_theme(self.theme_key)
        popup = tk.Toplevel(self.root)
        setattr(popup, "_bw_menu_popup", True)
        popup.overrideredirect(True)
        popup.transient(self.root)
        popup.configure(bg=theme["border"], bd=1, highlightthickness=0)

        # Rows live in a ScrollableFrame so a popup taller than the work area can be
        # capped and scrolled (screen-placement contract, max_size_policy below)
        # instead of running off the monitor. The canvas is sized to the body.
        from bw_gui.widgets.scrollable_frame import ScrollableFrame  # local: avoids a circular import

        scroll_host = ScrollableFrame(popup, style="Surface.TFrame")
        scroll_host.pack(fill="both", expand=True, padx=1, pady=1)
        body = tk.Frame(scroll_host.content, bg=theme["bg_surface"], bd=0, highlightthickness=0)
        body.pack(fill="both", expand=True)
        setattr(popup, "_bw_menu_body", body)
        setattr(popup, "_bw_menu_scroll_host", scroll_host)

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
            glyph = glyph_image(body, item.type, item.checked, item.mixed) if is_binary(item) else None
            prefix = text_prefix(item.type, item.checked, item.mixed) if is_binary(item) and glyph is None else prefix
            if item.type == "submenu":
                suffix = "   ▸"

            row = tk.Label(
                body,
                text=f"{prefix}{item.label}{suffix}",
                image=glyph or "", compound="left", anchor="w",
                justify="left",
                bg=theme["bg_surface"],
                fg=fg,
                padx=10,
                pady=glyph_row_pady(body, glyph, base_pady=6, font=("Segoe UI", 9)),
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
                row.bind("<Button-1>", lambda _event, cmd=menu_item_command(item): self._execute_menu_command(cmd))

        setattr(popup, "_bw_menu_navigable_rows", navigable_rows)
        setattr(popup, "_bw_menu_active_index", -1)
        setattr(popup, "_bw_menu_level", level)
        setattr(popup, "_bw_menu_top_key", top_key)

        # `popup` must already be on `_popup_stack` at its correct index before
        self._place_menu_popup(popup, anchor_widget, level)

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

    def _place_menu_popup(self, popup: tk.Toplevel, anchor_widget: tk.Widget, level: int) -> None:
        """Size the scroll host to its rows and position the popup on the anchor's monitor.

        Level 0 opens below the strip button (flipping above if it does not fit);
        deeper levels and description flyouts open right of their anchor row
        (flipping left), overlapping it by one pixel as before. If the popup is
        taller than the work area, its height is capped and the rows scroll; the
        placement is then recomputed for the final size (``place_overlay_now``).
        """
        scroll_host = getattr(popup, "_bw_menu_scroll_host")
        body = getattr(popup, "_bw_menu_body")
        popup.update_idletasks()
        scroll_host.canvas.configure(width=body.winfo_reqwidth(), height=body.winfo_reqheight())

        def _cap_height(max_size: Size) -> None:
            # Chrome around the canvas (popup border, host padding) is measured, not
            # assumed, so the capped popup's requested height equals max_size.height.
            chrome = int(popup.winfo_reqheight()) - int(scroll_host.canvas.winfo_reqheight())
            scroll_host.canvas.configure(height=max(1, max_size.height - chrome))

        # lift() BEFORE positioning: on Windows, lift() of a not-yet-mapped
        # overrideredirect Toplevel resets an already applied "+x+y" to +0+0
        # (measured 2026-10-09, Tk 8.6).
        popup.lift()
        placement = (Side.BELOW, Side.ABOVE) if level == 0 else (Side.RIGHT, Side.LEFT)
        place_overlay_now(
            popup,
            anchor=widget_rect(anchor_widget),
            placement=placement,
            tk_context=self.root,
            gap=0 if level == 0 else -1,
            margin=0,
            max_size_policy=_cap_height,
        )

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
            self._execute_menu_command(menu_item_command(item))

    def _on_menu_right_key(self, popup: tk.Toplevel) -> None:
        """Right opens the highlighted row's submenu (no-op on a leaf row)."""
        rows = getattr(popup, "_bw_menu_navigable_rows", [])
        index = getattr(popup, "_bw_menu_active_index", -1)
        if 0 <= index < len(rows) and rows[index][1].type == "submenu":
            self._activate_keyboard_active_row(popup)

    def _on_menu_back_key(self, popup: tk.Toplevel) -> None:
        """Left/Escape closes back to the parent popup, or closes everything at the top level.

        ``popup`` currently holds keyboard focus (it just received the
        Left/Escape key event); `close_popups_from_level` reclaims focus for
        `root` before destroying it (Windows destroy-while-focused hazard,
        see its docstring), so refocusing the parent popup afterward here is
        a normal, safe transfer between two still-live widgets. Runs under
        `_focus_watchdog_suspended` for the same reason `open_popup` does.
        """
        with self._focus_watchdog_suspended():
            level = getattr(popup, "_bw_menu_level", 0)
            if level <= 0:
                self.close_all_popups()
                return
            self.close_popups_from_level(level)
            if self._popup_stack:
                try:
                    self._popup_stack[-1].focus_set()
                except tk.TclError:
                    pass

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

        Restores keyboard focus to the popup that contains ``anchor_row`` (at
        ``level``) once the flyout is built: `open_popup`'s `close_popups_from_level`
        call reclaims focus for `root` before destroying the previous flyout (see its
        docstring), and a description flyout never claims focus back for itself since
        it must stay fully non-interactive — left alone, focus would stay stranded on
        `root`, which the global click-outside watchdog (`_close_if_focus_outside_menu`)
        would then misread as "clicked outside the menu" and close everything. This
        runs on every hover/keyboard move over a described row, so leaving it stranded
        would close the menu almost immediately after opening it. Runs under
        `_focus_watchdog_suspended` (composes correctly with the nested call to
        `open_popup`, itself also suspended — see that context manager's docstring)
        so the watchdog only ever sees this operation's truly final focus state,
        never one of its internal hand-offs.
        """
        with self._focus_watchdog_suspended():
            target_level = level + 1
            if not _is_description_slot_replaceable(self._popup_stack, target_level):
                return

            self.open_popup(anchor_row, (MenuItem(type="description", label=description),), target_level, top_key)
            if self._popup_stack:
                setattr(self._popup_stack[-1], "_bw_menu_description_flyout", True)

            if 0 <= level < len(self._popup_stack):
                try:
                    self._popup_stack[level].focus_set()
                except tk.TclError:
                    pass

    def _execute_menu_command(self, command: Callable[[], None] | None) -> None:
        """Close all popups, then invoke the command if it is callable."""
        with self._focus_watchdog_suspended():
            self.close_all_popups()
        if callable(command):
            command()
