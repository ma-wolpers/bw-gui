"""Tk adapter of the multi-cursor contract: offsets, cursor motion and transactions on a ``Text``.

Offsets count characters like Python does. Measured on Tk 8.6: a column index counts an
emoji twice and so does ``count -chars``, while the index modifier ``+ N chars`` steps
over it as one character. So ``len(get(...))`` and ``+ N chars`` are the matching pair
used here, and an offset can never point into the middle of an emoji.

A transaction is exactly one undo step or nothing: separators around it with
``autoseparators`` off, and if an edit fails midway the part already applied is undone
as that one step, ``autoseparators`` is restored in every case, and the exception
propagates.
"""

from __future__ import annotations

import tkinter
from typing import Any, Sequence

from bw_gui.contracts.multicursor import Edit, application_order


class TextSurface:
    """Offset-based view of one ``Text`` widget."""

    def __init__(self, text: Any) -> None:
        self.text = text
        self._mutations = 0
        """Primitive changes (`delete`/`insert`) of the running transaction (see ``transact``)."""

    def content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def offset(self, index: str) -> int:
        """Characters from the document start to *index*."""
        return len(self.text.get("1.0", index))

    def index(self, offset: int) -> str:
        """Concrete ``line.column`` index of *offset*."""
        return self.text.index(f"1.0 + {offset} chars")

    def limit(self) -> int:
        """Text length."""
        return self.offset("end-1c")

    def left(self, offset: int) -> int:
        return max(0, offset - 1)

    def right(self, offset: int) -> int:
        return min(self.limit(), offset + 1)

    def line_start(self, offset: int) -> int:
        return self.offset(f"{self.index(offset)} display linestart")

    def line_end(self, offset: int) -> int:
        return self.offset(f"{self.index(offset)} display lineend")

    def display_column(self, offset: int) -> int:
        """Display characters between the start of the display line and *offset*."""
        index = self.index(offset)
        return len(self.text.get(f"{index} display linestart", index))

    def vertical(self, offset: int, direction: int, goal: int | None) -> tuple[int, int]:
        """One display line up (-1) or down (+1), keeping the goal column.

        Returns:
            ``(new offset, goal column)``. On the first or last line the cursor stays.
        """
        index = self.index(offset)
        column = self.display_column(offset) if goal is None else goal
        sign = "+" if direction > 0 else "-"
        line = self.text.index(f"{index} {sign}1 display lines")
        if self.text.compare(f"{line} display linestart", "==", f"{index} display linestart"):
            return offset, column
        target = self.text.index(f"{line} display linestart + {column} display chars")
        line_end = self.text.index(f"{line} display lineend")
        if self.text.compare(target, ">", line_end):
            target = line_end
        return self.offset(target), column

    def closest_gap(self, x: int, y: int) -> int:
        """Offset of the gap between characters closest to pixel ``(x, y)``, as a native click picks it."""
        return self.offset(str(self.text.tk.call("::tk::TextClosestGap", str(self.text), x, y)))

    def apply_one(self, edit: Edit) -> None:
        """Apply one edit (separate so a failure midway stays testable).

        Counts each completed primitive change, so ``transact`` also rolls back
        an edit whose ``delete`` succeeded before its ``insert`` failed.
        """
        start = self.index(edit.start)
        if edit.end > edit.start:
            self.text.delete(start, self.index(edit.end))
            self._mutations += 1
        if edit.text:
            self.text.insert(start, edit.text)
            self._mutations += 1

    def transact(self, planned: Sequence[Edit]) -> None:
        """Apply planned edits as exactly one undo step (see module docstring).

        On a failure the transaction is undone only if something was actually
        changed since its opening separator; otherwise Tk's undo would take back
        the user's previous step instead.
        """
        text = self.text
        previous = text.cget("autoseparators")
        text.configure(autoseparators=False)
        self._mutations = 0
        try:
            text.edit_separator()
            for edit in application_order(planned):
                self.apply_one(edit)
            text.edit_separator()
        except Exception:
            if self._mutations:
                text.edit_separator()
                try:
                    text.edit_undo()
                except tkinter.TclError:
                    pass
            raise
        finally:
            text.configure(autoseparators=previous)
