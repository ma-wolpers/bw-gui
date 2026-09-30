"""Focus watchdog and global click/Alt/focus handlers for ``CustomMenuBar`` (private mixin).

Split out of ``custom_menu_bar`` (file-size rule); method bodies are unchanged.
"""

from __future__ import annotations

from contextlib import contextmanager
import tkinter as tk


class _MenuFocusMixin:
    """Closes the menu on outside clicks/focus loss and handles Alt mnemonics."""

    @contextmanager
    def _focus_watchdog_suspended(self):
        """Reentrant context manager: suspends the click-away watchdog for internal focus juggling.

        A single logical operation here (opening/replacing a popup, showing a
        description flyout, going back a level) can call `.focus_set()` more
        than once as it moves focus between this menu's own popups -- e.g.
        `close_popups_from_level` reclaiming it for `root` before destroying a
        focused popup (Windows destroy-while-focused hazard), followed by
        landing it on whichever popup should end up with it. Each individual
        hop looks, from `_close_if_focus_outside_menu`'s point of view,
        identical to the user genuinely clicking away to dismiss the menu --
        without suspension it would (and did: reported immediately after
        shipping keyboard navigation) snap the menu shut mid-hop, before the
        user could even pick a different row.

        Reentrant via a depth counter so a wrapped method calling another
        wrapped method (e.g. `_show_item_description` calling `open_popup`)
        composes correctly: the watchdog stays suspended for the outermost
        call's whole duration, and is re-armed with one fresh check against
        the truly final focus state only once every nested call has returned.
        """
        self._focus_watchdog_suspend_depth += 1
        try:
            yield
        finally:
            self._focus_watchdog_suspend_depth -= 1
            if self._focus_watchdog_suspend_depth == 0 and self._popup_stack:
                self._schedule_focus_check()

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
        """Close all popups if the currently focused widget is not inside the menu.

        Skips the check entirely while `_focus_watchdog_suspend_depth` is nonzero
        (see `_focus_watchdog_suspended`): an internal focus hop between this
        menu's own popups is in progress, and a reading taken mid-hop can look
        "outside" the menu without the user having clicked away at all. Whichever
        operation is holding the suspension re-arms this check itself once it
        finishes, against the operation's actual final focus state -- this only
        ever runs against a settled state, real or user-caused.
        """
        self._focus_check_after_id = None
        if not self._popup_stack or self._focus_watchdog_suspend_depth:
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
