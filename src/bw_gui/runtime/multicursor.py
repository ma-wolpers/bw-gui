"""Several cursors and selections in one ``Text`` (``docs/MULTICURSOR_CONTRACT.md``).

:func:`attach_multicursor` adds to a ``Text``: Ctrl+click and Ctrl+drag, multi-region
typing, Backspace/Delete, arrows, Home/End (with Shift), copy/cut/paste, and undo/redo
that restores the cursors. While inactive the widget behaves natively; only undo/redo
always pass through the controller, because undoing back into a multi-cursor edit
restores its cursors and reactivates the mode.

The regions are offsets, valid for exactly one text state. Any change the controller did
not make itself (:meth:`MultiCursorController.sync`) ends the mode.
"""

from __future__ import annotations

import tkinter
from dataclasses import replace
from typing import Any, Callable, Sequence

from bw_gui.contracts.key_event import KeyEvent
from bw_gui.contracts.key_modifiers import KeyModifiers
from bw_gui.contracts.key_spec import Key, KeySpec
from bw_gui.contracts.events import EventResult
from bw_gui.contracts.multicursor import (
    Edit,
    Region,
    moved,
    normalize,
    plan_delete,
    plan_edits,
    plan_lines_or_text,
    plan_text,
    primary,
    region_at,
    regions_after,
)
from bw_gui.contracts.multicursor_history import CursorHistory, TxRecord, text_digest

from .multicursor_text import TextSurface
from .multicursor_view import MultiCursorView
from .pointer import bind_click, bind_drag
from .widget_keys import WidgetShortcutBinder, on_key

_WHITESPACE_KEYS = {Key.SPACE: " ", Key.ENTER: "\n", Key.TAB: "\t"}
_WORD_MOTION_KEYS = {Key.LEFT, Key.RIGHT, Key.UP, Key.DOWN, Key.HOME, Key.END}
_PAGE_KEYS = {Key.PAGE_UP, Key.PAGE_DOWN}


class MultiCursorController:
    """Regions, mode and history of one ``Text``; create it with :func:`attach_multicursor`."""

    def __init__(self, text: Any) -> None:
        self._text = text
        self._surface = TextSurface(text)
        self._view = MultiCursorView(self._surface)
        self._history = CursorHistory()
        self._regions: tuple[Region, ...] = ()
        self._active = False
        self._digest = ""
        self._next_order = 0
        self._drag_base: tuple[Region, ...] | None = None
        self._drag_anchor = 0
        self._bind()

    def _bind(self) -> None:
        bind_drag(
            self._text, on_start=self._on_drag_start, on_move=self._on_drag_move, on_end=self._on_drag_end,
            on_cancel=self._on_drag_cancel, consume_when=lambda modifiers: isinstance(modifiers, KeyModifiers) and modifiers.control,
        )
        bind_click(self._text, self._on_plain_click)
        on_key(self._text, self._on_key)
        binder = WidgetShortcutBinder(self._text)
        rows: list[tuple[Sequence[KeySpec] | KeySpec, str, Callable[[Any], object]]] = [
            (KeySpec.parse("Ctrl+Z"), "undo", lambda _e: self.undo()),
            ([KeySpec.parse("Ctrl+Y"), KeySpec.parse("Ctrl+Shift+Z")], "redo", lambda _e: self.redo()),
            (KeySpec.parse("Ctrl+C"), "copy", lambda _e: self._copy()),
            (KeySpec.parse("Ctrl+X"), "cut", lambda _e: self._cut()),
            (KeySpec.parse("Ctrl+V"), "paste", lambda _e: self._paste()),
            (KeySpec.parse("Ctrl+A"), "select_all", lambda _e: self._leave_for_native()),
        ]
        for spec, name, handler in rows:
            binder.bind(spec, handler, binding_id=f"multicursor.{name}", intent=f"multicursor.{name}", allow_when_text_input=True)
        self._binder = binder

    # Public API --------------------------------------------------------------------------

    def is_active(self) -> bool:
        return self._active

    @property
    def regions(self) -> tuple[Region, ...]:
        return self._regions

    @property
    def surface(self) -> TextSurface:
        """Offset helpers, for consumers building edits for :meth:`apply_per_region`."""
        return self._surface

    @property
    def view(self) -> MultiCursorView:
        return self._view

    def exit(self) -> None:
        """Leave the mode: the primary region stays as the native cursor or selection."""
        if not self._active:
            return
        keep = primary(self._regions)
        self._active = False
        self._regions = ()
        self._view.hide()
        self._to_native(keep)

    def handle_escape(self) -> bool:
        """Escape priority: returns ``True`` when the mode consumed the key."""
        if not self._active:
            return False
        self.exit()
        return True

    def sync(self) -> bool:
        """Check the text against the last known state; a foreign change ends the mode.

        Consumers call it from their text-modified handler. Returns whether the mode is
        still active.
        """
        if self._active and text_digest(self._surface.content()) != self._digest:
            self._active = False
            self._regions = ()
            self._view.hide()
        return self._active

    def reset_history(self) -> None:
        """A new document: forget all cursor records and clear the widget's undo stack."""
        self._active = False
        self._regions = ()
        self._view.hide()
        self._history.reset()
        self._text.edit_reset()

    def undo(self) -> EventResult:
        return self._history_step(self._text.edit_undo, self._history.match_undo)

    def redo(self) -> EventResult:
        return self._history_step(self._text.edit_redo, self._history.match_redo)

    def add_cursor(self, direction: int) -> EventResult:
        """Add a cursor one display line above (-1) or below (+1) the outermost one."""
        base = self._regions if self.sync() else self._seed()
        outer = (min if direction < 0 else max)(base, key=lambda region: region.head)
        head, goal = self._surface.vertical(outer.head, direction, outer.goal)
        if head != outer.head:
            base = tuple(replace(region, goal=goal) if region is outer else region for region in base)
            self._commit_regions((*base, Region(head, head, goal, self._take_order())))
        return EventResult.HANDLED

    def apply_per_region(self, plan: Callable[[Region], Edit | None], caret_text: str | None = None) -> bool:
        """One transaction with a consumer-planned edit per selection (marker keys).

        Args:
            plan: Maps a selection to its edit; ``None`` aborts the whole action unchanged.
            caret_text: What plain carets write; ``None`` leaves them where they are.

        Returns:
            Whether the action ran.
        """
        edits = []
        for region in self._regions:
            if region.is_caret:
                edits.append(Edit(region.head, region.head, caret_text or "", region.order))
                continue
            edit = plan(region)
            if edit is None:
                return False
            edits.append(replace(edit, order=region.order))
        self._commit_edits(edits)
        return True

    def run_on_regions(self, plan: Callable[[Region], Edit]) -> None:
        """One transaction with a consumer-planned edit per region, carets included (word deletion)."""
        self._commit_edits([replace(plan(region), order=region.order) for region in self._regions])

    # Mode and regions --------------------------------------------------------------------

    def _take_order(self) -> int:
        self._next_order += 1
        return self._next_order

    def _seed(self) -> tuple[Region, ...]:
        """The native cursor or selection as the first region."""
        ranges = self._text.tag_ranges("sel")
        head = self._surface.offset("insert")
        if ranges:
            first, last = self._surface.offset(str(ranges[0])), self._surface.offset(str(ranges[1]))
            anchor = first if head == last else last
            head = last if head == last else first
            return (Region(anchor, head, order=self._take_order()),)
        return (Region(head, head, order=self._take_order()),)

    def _to_native(self, region: Region) -> None:
        self._text.tag_remove("sel", "1.0", "end")
        if not region.is_caret:
            self._text.tag_add("sel", self._surface.index(region.start), self._surface.index(region.end))
        self._text.mark_set("insert", self._surface.index(region.head))
        self._text.see("insert")

    def _commit_regions(self, regions: Sequence[Region]) -> None:
        """Adopt normalised regions: several keep or start the mode, a single one ends it."""
        normalized = normalize(regions)
        if len(normalized) > 1:
            self._regions = normalized
            self._active = True
            self._digest = text_digest(self._surface.content())
            lead = primary(normalized)
            self._text.mark_set("insert", self._surface.index(lead.head))
            self._text.see("insert")
            self._view.show(normalized, lead)
        else:
            self._active = False
            self._regions = ()
            self._view.hide()
            self._to_native(normalized[0])

    def _commit_edits(self, edits: Sequence[Edit]) -> None:
        planned = plan_edits(edits)
        before = self._regions
        pre = self._digest
        if any(edit.end > edit.start or edit.text for edit in planned):
            self._surface.transact(planned)
            after = regions_after(planned)
            self._history.record(TxRecord(pre, text_digest(self._surface.content()), before, after))
        else:
            after = regions_after(planned)
        self._commit_regions(after)

    def _history_step(self, action: Callable[[], None], match: Callable[[str, str], tuple[Region, ...] | None]) -> EventResult:
        pre = text_digest(self._surface.content())
        try:
            action()
        except tkinter.TclError:
            return EventResult.HANDLED  # nothing to undo or redo
        post = text_digest(self._surface.content())
        regions = match(pre, post)
        if regions is not None:
            self._commit_regions(regions)
        elif self._active:
            self._active = False
            self._regions = ()
            self._view.hide()
        return EventResult.HANDLED

    def _leave_for_native(self) -> None:
        """A native command follows (the key goes on to the Text class binding)."""
        self.exit()

    # Mouse -------------------------------------------------------------------------------

    def _on_drag_start(self, event: Any) -> None:
        self._text.focus_set()
        self._drag_base = self._regions if self.sync() else self._seed()
        self._drag_anchor = self._surface.closest_gap(event.x, event.y)

    def _on_drag_move(self, event: Any) -> None:
        head = self._surface.closest_gap(event.x, event.y)
        preview = normalize((*(self._drag_base or ()), Region(self._drag_anchor, head, order=self._next_order + 1)))
        self._view.show(preview, primary(preview))

    def _on_drag_end(self, event: Any) -> None:
        base, self._drag_base = self._drag_base or (), None
        head = self._surface.closest_gap(event.x, event.y)
        if head != self._drag_anchor:
            self._commit_regions((*base, Region(self._drag_anchor, head, order=self._take_order())))
            return
        hit = region_at(base, head)
        if hit is None:
            self._commit_regions((*base, Region(head, head, order=self._take_order())))
        elif len(base) > 1:
            self._commit_regions([region for region in base if region is not hit])
        else:
            self._commit_regions(base)

    def _on_drag_cancel(self, _reason: Any) -> None:
        self._drag_base = None
        if self._active:
            self._view.show(self._regions, primary(self._regions))
        else:
            self._view.hide()

    def _on_plain_click(self, event: Any) -> None:
        if self._active and not (isinstance(event.modifiers, KeyModifiers) and event.modifiers.control):
            self.exit()

    # Keyboard ----------------------------------------------------------------------------

    def _on_key(self, event: KeyEvent) -> EventResult | None:
        if not self._active or not self.sync() or not isinstance(event.modifiers, KeyModifiers):
            return None
        modifiers = event.modifiers
        ctrl_only = modifiers.control and not modifiers.alt
        if event.key in _PAGE_KEYS or (ctrl_only and event.key in _WORD_MOTION_KEYS):
            self.exit()  # native motion of one cursor: the mode has no meaning for it
            return None
        if modifiers.control or modifiers.alt:
            if event.text and event.key is Key.CHARACTER and modifiers.control and modifiers.alt:  # AltGr
                self._commit_edits(plan_text(self._regions, event.text))
                return EventResult.HANDLED
            return None
        return self._on_plain_key(event, modifiers.shift)

    def _on_plain_key(self, event: KeyEvent, shift: bool) -> EventResult | None:
        surface = self._surface
        motions = {
            Key.LEFT: lambda region: surface.left(region.head),
            Key.RIGHT: lambda region: surface.right(region.head),
            Key.HOME: lambda region: surface.line_start(region.head),
            Key.END: lambda region: surface.line_end(region.head),
        }
        if event.key in motions:
            self._commit_regions(moved(self._regions, motions[event.key], extend=shift))
        elif event.key in (Key.UP, Key.DOWN):
            self._move_vertically(1 if event.key is Key.DOWN else -1, shift)
        elif event.key is Key.BACKSPACE:
            self._commit_edits(plan_delete(self._regions, forward=False, limit=surface.limit()))
        elif event.key is Key.DELETE:
            self._commit_edits(plan_delete(self._regions, forward=True, limit=surface.limit()))
        elif event.key in _WHITESPACE_KEYS:
            self._commit_edits(plan_text(self._regions, _WHITESPACE_KEYS[event.key]))
        elif event.key is Key.CHARACTER and event.text:
            self._commit_edits(plan_text(self._regions, event.text))
        else:
            return None
        return EventResult.HANDLED

    def _move_vertically(self, direction: int, extend: bool) -> None:
        targets = {region.order: self._surface.vertical(region.head, direction, region.goal) for region in self._regions}
        self._commit_regions(moved(
            self._regions, lambda region: targets[region.order][0], extend=extend, goal=lambda region: targets[region.order][1],
        ))

    def _selected_text(self) -> str:
        parts = [
            self._text.get(self._surface.index(region.start), self._surface.index(region.end))
            for region in self._regions
            if not region.is_caret
        ]
        return "\n".join(parts)

    def _copy(self) -> EventResult | None:
        if not self._active or not self.sync():
            return None
        selected = self._selected_text()
        if selected:
            self._text.clipboard_clear()
            self._text.clipboard_append(selected)
        return EventResult.HANDLED

    def _cut(self) -> EventResult | None:
        if self._copy() is None:
            return None
        selections = [region for region in self._regions if not region.is_caret]
        if selections:
            self._commit_edits([
                Edit(region.start, region.end, "", region.order) if not region.is_caret else Edit(region.head, region.head, "", region.order)
                for region in self._regions
            ])
        return EventResult.HANDLED

    def _paste(self) -> EventResult | None:
        if not self._active or not self.sync():
            return None
        try:
            clipboard = str(self._text.clipboard_get())
        except tkinter.TclError:
            return EventResult.HANDLED
        self._commit_edits(plan_lines_or_text(self._regions, clipboard.replace("\r\n", "\n")))
        return EventResult.HANDLED


def attach_multicursor(text: Any) -> MultiCursorController:
    """Give a ``Text`` multi-cursor editing. Attach after consumer click handlers.

    A consumer click handler returning ``HANDLED`` (e.g. "no document loaded") must run
    first so it also stops the Ctrl gestures of this controller.
    """
    return MultiCursorController(text)
