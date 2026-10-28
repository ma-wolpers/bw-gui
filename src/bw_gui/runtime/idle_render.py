"""IdleRenderScheduler — coalesce "something changed, redraw" into one render per idle cycle.

The one mechanism for change-driven rendering: callers only *mark* a named
render as dirty; the scheduler runs each dirty render exactly once, in the
order it was first marked, when Tk becomes idle. Holding a navigation key
therefore never queues a render per key event, and several state changes in
one handler cost one render. ``flush_now()`` runs pending renders
synchronously for the few readers that need up-to-date widgets immediately
(e.g. placing an inline editor on a cell). Pending work is cancelled when the
owner widget is destroyed, so no ``after`` callback outlives its widgets.
"""

from __future__ import annotations

from typing import Any, Callable

from .widget_events import on_destroy


class IdleRenderScheduler:
    """Runs marked renders once per idle cycle, in first-marked order."""

    def __init__(self, owner: Any) -> None:
        """Bind the scheduler's lifetime to *owner*.

        Args:
            owner: Widget whose ``after_idle`` is used; destroying it cancels pending renders.
        """
        self._owner = owner
        self._dirty: dict[str, Callable[[], None]] = {}
        self._after_id: str | None = None
        self._alive = True
        on_destroy(owner, lambda _widget: self._dispose())

    def mark(self, key: str, render: Callable[[], None]) -> None:
        """Mark the render *key* dirty; schedule a flush if none is pending.

        Marking an already dirty key keeps its original position and replaces
        the callable (last wins).

        Args:
            key: Name of the render (e.g. ``"body"``, ``"header"``).
            render: Parameterless callable performing that render.
        """
        if not self._alive:
            return
        self._dirty[key] = render
        if self._after_id is None:
            self._after_id = self._owner.after_idle(self._flush)

    def flush_now(self) -> None:
        """Run all pending renders synchronously (and cancel the scheduled idle flush)."""
        if self._after_id is not None:
            self._owner.after_cancel(self._after_id)
            self._after_id = None
        self._run_pending()

    @property
    def pending(self) -> tuple[str, ...]:
        """Keys currently marked dirty, in run order (for tests and diagnostics)."""
        return tuple(self._dirty)

    def _flush(self) -> None:
        """Idle callback: run the renders marked so far."""
        self._after_id = None
        self._run_pending()

    def _run_pending(self) -> None:
        """Run and clear the current dirty set.

        Renders marked *while* flushing go into the next idle cycle instead of
        being run in this loop, so a render that marks itself cannot spin.
        """
        if not self._alive:
            return
        batch, self._dirty = self._dirty, {}
        for render in batch.values():
            render()

    def _dispose(self) -> None:
        """Owner destroyed: drop pending renders and cancel the idle callback."""
        self._alive = False
        self._dirty = {}
        if self._after_id is not None:
            try:
                self._owner.after_cancel(self._after_id)
            except Exception:  # interpreter already gone during shutdown
                pass
            self._after_id = None
