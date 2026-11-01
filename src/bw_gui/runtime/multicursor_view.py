"""Drawing of a multi-cursor mode: selection tag and caret bars on a ``Text``.

The primary region uses Tk's native insertion cursor; every other head gets a thin
frame placed at its ``bbox``. A head scrolled out of view has no ``bbox``, so its bar is
hidden; on line ends and empty lines the ``bbox`` of the newline character applies.

While the mode is active the widget's ``yscrollcommand`` is wrapped: the wrapper first
calls the original command with the same arguments, then repositions the bars.
:meth:`MultiCursorView.hide` restores the original and removes the wrapper, so no stale
Tcl command remains and an inactive editor has no overhead.
"""

from __future__ import annotations

import tkinter
from typing import Any, Iterable

from bw_gui.contracts.multicursor import Region

from .multicursor_text import TextSurface
from .widget_events import on_resize

SELECTION_TAG = "mc_sel"
_BAR_WIDTH = 2


class MultiCursorView:
    """Paints regions on one ``Text``."""

    def __init__(self, surface: TextSurface) -> None:
        self._surface = surface
        self._text = surface.text
        self._bars: list[Any] = []
        self._regions: tuple[Region, ...] = ()
        self._primary: Region | None = None
        self._original_scroll: str | None = None
        self._scroll_command: str | None = None
        on_resize(self._text, lambda _event: self._place_bars())

    def _install_scroll_hook(self) -> None:
        if self._scroll_command is not None:
            return
        self._original_scroll = str(self._text.cget("yscrollcommand"))
        self._scroll_command = self._text.register(self._on_scroll)
        self._text.configure(yscrollcommand=self._scroll_command)

    def _remove_scroll_hook(self) -> None:
        if self._scroll_command is None:
            return
        self._text.configure(yscrollcommand=self._original_scroll or "")
        self._text.deletecommand(self._scroll_command)
        self._scroll_command = None
        self._original_scroll = None

    def _on_scroll(self, first: str, last: str) -> None:
        if self._original_scroll:
            self._text.tk.call(*self._text.tk.splitlist(self._original_scroll), first, last)
        self._place_bars()

    def _configure_tag(self) -> None:
        """Selections look like native ones (colours read fresh, the theme may have changed)."""
        self._text.tag_configure(
            SELECTION_TAG,
            background=self._text.tag_cget("sel", "background"),
            foreground=self._text.tag_cget("sel", "foreground"),
        )
        self._text.tag_raise(SELECTION_TAG)

    def show(self, regions: Iterable[Region], primary: Region) -> None:
        """Draw *regions*; *primary* is the one following Tk's native cursor."""
        self._regions = tuple(regions)
        self._primary = primary
        self._install_scroll_hook()
        self._configure_tag()
        self._text.tag_remove("sel", "1.0", "end")
        self._text.tag_remove(SELECTION_TAG, "1.0", "end")
        for region in self._regions:
            if not region.is_caret:
                self._text.tag_add(SELECTION_TAG, self._surface.index(region.start), self._surface.index(region.end))
        self._place_bars()

    def _place_bars(self) -> None:
        heads = [region.head for region in self._regions if region is not self._primary]
        while len(self._bars) < len(heads):
            self._bars.append(tkinter.Frame(self._text, width=_BAR_WIDTH, cursor="xterm"))
        color = self._text.cget("insertbackground")
        for bar, head in zip(self._bars, heads):
            box = self._text.bbox(self._surface.index(head))
            if box is None:
                bar.place_forget()
            else:
                bar.configure(background=color)
                bar.place(x=box[0], y=box[1], width=_BAR_WIDTH, height=box[3])
        for bar in self._bars[len(heads) :]:
            bar.place_forget()

    def visible_bars(self) -> int:
        """Number of bars currently on screen (for tests)."""
        return sum(1 for bar in self._bars if bar.winfo_manager())

    def hide(self) -> None:
        """Remove all drawing and the scroll hook."""
        self._regions = ()
        self._primary = None
        self._text.tag_remove(SELECTION_TAG, "1.0", "end")
        for bar in self._bars:
            bar.place_forget()
        self._remove_scroll_hook()
