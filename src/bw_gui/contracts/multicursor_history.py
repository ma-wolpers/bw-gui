"""Cursor history of multi-cursor edits, synchronous with a text widget's undo stack.

The widget's undo stack knows nothing about cursors, and a second independent stack
could drift from it. So a record is matched by **content**: it holds a digest of the
whole text before and after one transaction. After an undo, the record with
``after == text before the undo`` and ``before == text after the undo`` is the one that
was undone. A record can therefore only ever apply when the text is exactly the state
its offsets belong to; stale or foreign records are harmless.

Records survive leaving multi-cursor mode (undoing back into a transaction restores
its cursors and reactivates the mode) and are dropped by :meth:`CursorHistory.reset`
whenever the widget's undo stack is reset. If the same text occurs several times the
youngest matching record wins; its offsets are valid for that text.
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass

from .multicursor import Region

MAX_RECORDS = 500


def text_digest(text: str) -> str:
    """Digest identifying a complete text state."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


@dataclass(frozen=True)
class TxRecord:
    """One successful transaction."""

    before_digest: str
    after_digest: str
    regions_before: tuple[Region, ...]
    regions_after: tuple[Region, ...]


class CursorHistory:
    """Bounded list of transaction records, oldest dropped first."""

    def __init__(self, limit: int = MAX_RECORDS) -> None:
        self._records: deque[TxRecord] = deque(maxlen=limit)

    def __len__(self) -> int:
        return len(self._records)

    def record(self, record: TxRecord) -> None:
        self._records.append(record)

    def reset(self) -> None:
        self._records.clear()

    def match_undo(self, pre: str, post: str) -> tuple[Region, ...] | None:
        """Regions to restore after an undo from *pre* to *post*; ``None`` for a plain edit."""
        for record in reversed(self._records):
            if record.after_digest == pre and record.before_digest == post:
                return record.regions_before
        return None

    def match_redo(self, pre: str, post: str) -> tuple[Region, ...] | None:
        """Regions to restore after a redo from *pre* to *post*; ``None`` for a plain edit."""
        for record in reversed(self._records):
            if record.before_digest == pre and record.after_digest == post:
                return record.regions_after
        return None
