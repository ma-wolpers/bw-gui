from __future__ import annotations

from bw_gui.runtime import ui, widgets


class ScrollableFrame(widgets.Frame):
    """A `ttk.Frame` that is itself a scrollable viewport - the bw-gui SSOT for embedded vertical scrolling.

    A genuine widget subclass (not a delegating wrapper around a composed
    Tk object, unlike e.g. `ScrollablePopupWindow`): `ScrollableFrame(...)`
    can be placed anywhere a plain `ttk.Frame` could (`pack`/`grid`, or as
    a `PanedWindow` pane via `paned.add(frame, weight=...)`) with no
    `__getattr__` delegation needed, since it already *is* the widget.
    `self.content` is the actual target `ttk.Frame` for caller-built
    content - build into `.content`, never directly into the
    `ScrollableFrame` instance itself (that would land content behind the
    Canvas/Scrollbar it owns internally).

    Convention (see `docs/SCROLLABILITY_CONTRACT.md`): this is the default
    building block for any embedded, non-popup content area that could
    outgrow its available height - not an opt-in optimization for content
    that "probably doesn't fit". `bw_gui.dialogs.ScrollablePopupWindow` is
    the equivalent default for popups, and builds directly on this class
    (see its module) rather than maintaining a second, parallel Canvas/
    Scrollbar implementation.

    Geometry contract:
    - Content height grows -> the Canvas `scrollregion` grows to match
      (`_on_content_configure`, driven by `.content`'s own `<Configure>`).
    - Canvas/viewport width changes (window resize, `PanedWindow` splitter
      drag) -> `.content`'s width is kept equal to the canvas width
      (`_on_canvas_configure`) - content never gets its own independent
      horizontal extent, it always exactly fills the available width.
    - Content taller than the viewport -> the mousewheel scrolls it;
      content shorter than or equal to the viewport -> the mousewheel
      handler is a no-op (never scrolls into empty space, never swallows
      an event that should reach something else).

    Vertical-only by design: a repo-wide audit (`docs/SCROLLABILITY_CONTRACT.md`,
    "Audit-Ergebnis") found no consumer anywhere (bw-gui, korrektor,
    blattwerk, namenfit, Kursplaner) that relies on `ScrollablePopupWindow`'s
    previous horizontal `Canvas.xview`/`_h_scroll` capability - it was
    already functionally dead there (`_on_canvas_configure` always forced
    content width to match canvas width, leaving nothing to scroll
    horizontally). Kursplaner's own, extensive horizontal-scroll machinery
    (`grid_viewport_sync.py`, guarded by its own
    `tests/test_horizontal_scroll_architecture_guard.py`) is a separate,
    bespoke mechanism for its spreadsheet-like grid `Canvas` and is
    entirely unrelated to `ScrollablePopupWindow`/`ScrollableFrame` - this
    class does not need to (and does not) replicate it. Should a real
    horizontal-scroll consumer for *this* primitive appear later, it
    belongs here once, not duplicated across classes again.

    Mousewheel dispatch: multiple `ScrollableFrame` instances can be
    visible at once (nested, or simply several panels on screen), and a
    naive per-instance `<Enter>`/`<Leave>`-scoped `bind_all`/`unbind_all`
    would let them clobber each other's binding as the cursor moves
    between them. Instead there is exactly **one** `bind_all("<MouseWheel>")`
    per Tk interpreter (keyed by `self.tk`, the actual interpreter handle -
    not a specific `Toplevel`: multiple `Toplevel` windows under the same
    `Tk()` application share one interpreter and therefore one "all"
    bindtag, so keying by a specific `Toplevel` would under- or
    over-register), lazily bound by whichever `ScrollableFrame` happens to
    be constructed first under that interpreter. `_dispatch_mousewheel`
    walks the actual event-target widget's `.master` chain (same
    finite-step-capped walk pattern as `DragDropController._resolve_drop_callback`)
    to find which registered instance's `canvas` it belongs to, so a wheel
    event over a *child* widget inside `.content` (a button, an entry, a
    label - not just bare canvas background) still resolves to the right
    instance, and instances never interfere with each other regardless of
    how many are visible at once.
    """

    _registry_by_interpreter: dict[object, dict[ui.Misc, "ScrollableFrame"]] = {}

    def __init__(self, master, **frame_kwargs) -> None:
        super().__init__(master, **frame_kwargs)

        self.canvas = ui.Canvas(self, highlightthickness=0, borderwidth=0)
        self._v_scroll = widgets.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self._v_scroll.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.content = widgets.Frame(self.canvas)
        self._content_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._register_for_mousewheel_dispatch()

    def refresh_chrome(self) -> None:
        """Reapply canvas chrome (borderless regardless of the active ttk theme).

        Called by `ScrollablePopupWindow.apply_theme()` after a theme
        switch - kept as an explicit method (instead of the caller poking
        `.canvas` directly) so the canvas-chrome detail stays encapsulated
        here, the one place that owns the canvas.
        """
        self.canvas.configure(highlightthickness=0)

    def _register_for_mousewheel_dispatch(self) -> None:
        by_canvas = ScrollableFrame._registry_by_interpreter.setdefault(self.tk, {})
        if not by_canvas:
            self.bind_all("<MouseWheel>", ScrollableFrame._dispatch_mousewheel, add="+")
        by_canvas[self.canvas] = self

    def _on_destroy(self, _event=None) -> None:
        by_canvas = ScrollableFrame._registry_by_interpreter.get(self.tk)
        if by_canvas is None:
            return
        by_canvas.pop(self.canvas, None)
        if not by_canvas:
            del ScrollableFrame._registry_by_interpreter[self.tk]

    def _on_content_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._content_window, width=max(1, int(event.width)))

    def _on_mousewheel(self, event) -> str | None:
        bbox = self.canvas.bbox("all")
        if not bbox:
            return None
        content_height = bbox[3] - bbox[1]
        if content_height <= self.canvas.winfo_height():
            return None
        step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")
        return "break"

    @classmethod
    def _dispatch_mousewheel(cls, event) -> None:
        """Route one `<MouseWheel>` event (bound once per interpreter) to the owning instance, if any.

        `event.widget` is whichever widget actually received the raw
        event (via the interpreter-wide "all" bindtag) - typically a
        child several levels deep inside some `ScrollableFrame.content`,
        not the canvas itself. Walking `.master` from there finds the
        nearest enclosing registered canvas; a 64-step cap guards against
        a pathological parent-chain, matching the existing
        `DragDropController._resolve_drop_callback` convention.
        """
        widget = getattr(event, "widget", None)
        interpreter = getattr(widget, "tk", None)
        by_canvas = cls._registry_by_interpreter.get(interpreter) if interpreter is not None else None
        if not by_canvas:
            return
        current = widget
        steps = 0
        while current is not None and steps < 64:
            instance = by_canvas.get(current)
            if instance is not None:
                instance._on_mousewheel(event)
                return
            current = getattr(current, "master", None)
            steps += 1
