from __future__ import annotations

from collections.abc import Callable

from bw_gui.runtime import ui


class DragDropController:
    """Minimal press-drag-release primitive: drag a widget's payload onto a registered drop target.

    Not a general DnD framework - deliberately narrow, built for small
    assignment UIs (e.g. dragging list rows onto named buckets), not
    file-manager/OS-level drag-and-drop:

    - One drag session at a time (a second `<ButtonPress-1>` while a drag
      is already in progress is ignored by Tk's own event delivery, since
      the mouse is already captured by the in-progress drag).
    - The dragged payload is shown as a small floating label following the
      cursor; no ghost/outline of the source widget itself.
    - Drop resolution is by *widget containment* at release: the widget
      directly under the cursor (`Misc.winfo_containing`) is walked up its
      `.master` parent chain looking for a registered target, so dropping
      onto a *child* of a registered target (e.g. a label inside a frame)
      still counts as dropping onto that target.
    """

    def __init__(self, root: ui.Misc) -> None:
        self._root = root
        self._drag_window: ui.Toplevel | None = None
        self._active_payload: object | None = None
        self._targets: dict[str, tuple[ui.Misc, Callable[[object], None]]] = {}

    def register_source(
        self,
        widget: ui.Misc,
        *,
        get_payload: Callable[[], object | None],
        preview_text: Callable[[object], str] | None = None,
    ) -> None:
        """Make `widget` a drag source.

        `get_payload()` is called at drag-start (e.g. "which row is
        currently selected") - returning `None` means "nothing to drag
        right now" and starts no drag. `preview_text(payload)` formats the
        floating label shown while dragging; defaults to `str(payload)`.
        Bindings use `add="+"` so a widget's own existing bindings (e.g. a
        Treeview's row-selection handling) keep working alongside dragging.
        """
        widget.bind("<ButtonPress-1>", lambda event: self._start_drag(event, get_payload(), preview_text), add="+")
        widget.bind("<B1-Motion>", self._on_motion, add="+")
        widget.bind("<ButtonRelease-1>", self._on_release, add="+")

    def register_target(self, widget: ui.Misc, *, on_drop: Callable[[object], None]) -> None:
        """Register `widget` (and implicitly all its children, via the parent-chain walk) as a drop target."""
        self._targets[str(widget)] = (widget, on_drop)

    def unregister_target(self, widget: ui.Misc) -> None:
        self._targets.pop(str(widget), None)

    def _start_drag(self, _event: ui.Event[ui.Misc], payload: object | None, preview_text: Callable[[object], str] | None) -> None:
        if payload is None:
            return
        self._active_payload = payload
        label_text = preview_text(payload) if preview_text is not None else str(payload)

        self._drag_window = ui.Toplevel(self._root)
        self._drag_window.overrideredirect(True)
        self._drag_window.attributes("-topmost", True)
        ui.Label(
            self._drag_window,
            text=label_text,
            background="#ffffe0",
            foreground="#111111",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def _on_motion(self, event: ui.Event[ui.Misc]) -> None:
        if self._drag_window is None:
            return
        self._drag_window.geometry(f"+{event.x_root + 12}+{event.y_root + 8}")

    def _on_release(self, event: ui.Event[ui.Misc]) -> None:
        if self._drag_window is None:
            return
        payload = self._active_payload
        self._drag_window.destroy()
        self._drag_window = None
        self._active_payload = None
        if payload is None:
            return

        target_widget = self._root.winfo_containing(event.x_root, event.y_root)
        callback = self._resolve_drop_callback(target_widget, self._targets)
        if callback is not None:
            callback(payload)

    @staticmethod
    def _resolve_drop_callback(
        widget: ui.Misc | None,
        targets: dict[str, tuple[ui.Misc, Callable[[object], None]]],
    ) -> Callable[[object], None] | None:
        """Walk `widget`'s `.master` parent chain, returning the first registered target's callback.

        Pure enough to unit-test with simple fake objects (only needs
        `str(widget)` identity plus a `.master` attribute) - no real Tk
        root required. The 64-step cap guards against a pathological/
        accidental cycle in a fake `.master` chain; real Tk widget trees
        are never anywhere near that deep.
        """
        current = widget
        steps = 0
        while current is not None and steps < 64:
            entry = targets.get(str(current))
            if entry is not None:
                return entry[1]
            current = getattr(current, "master", None)
            steps += 1
        return None
