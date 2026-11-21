from __future__ import annotations

from bw_gui.contracts import EventResult
from bw_gui.runtime import ui, widgets

# One wheel notch over a frame's own scrollbar scrolls this many times as far as over
# its content (user decision 2026-10-18: noticeably faster, but by rule -- formerly Tk's
# scrollbar class binding added its own 4 units to bw-gui's 1 by accident).
SCROLLBAR_WHEEL_FACTOR = 3


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
    - The vertical scrollbar itself is shown *only* while content is
      actually taller than the viewport, and hidden the instant it no
      longer is (`_update_scrollbar_visibility`, re-evaluated on every
      content- or canvas-size change) - never a permanently-visible bar
      that sits there unneeded. When it hides because content shrank back
      below the viewport height, the view snaps back to the top rather
      than staying scrolled into what is now empty space.
    - This also holds when the content shrinks while scrolled so far that
      the shrunk content lies entirely outside the viewport: Tk then only
      *unmaps* the embedded window and neither resizes it nor sends
      `<Configure>`, so `.content`'s `<Unmap>` triggers the same
      re-evaluation (`_on_content_unmap`).

    Orientation: vertical by default. ``orient="horizontal"`` builds the
    horizontal counterpart for a *single-row strip* whose natural width can
    outgrow the viewport (e.g. a document tab strip): the Canvas height
    follows the content's requested height, `.content` always keeps its own
    natural width (never squeezed), and the Canvas *requests exactly that
    width*: the frame shrink-wraps a strip that fits (the rest of the row
    shows the frame's own ttk background) and is clipped to whatever the
    parent grants otherwise. Natural width is deliberate - a forced content
    width would suppress `<Configure>` when children are added/removed, so
    growth/shrinkage of the strip would go unnoticed. The scrollbar sits
    below and is shown only while the strip overflows, and the mousewheel
    scrolls horizontally. `see_x_range` scrolls a sub-range (a newly
    selected tab) into view. A repo-wide audit
    (`docs/SCROLLABILITY_CONTRACT.md`, "Audit-Ergebnis") found no consumer
    that relied on the previous, functionally dead horizontal scrollbar of
    `ScrollablePopupWindow`; Kursplaner's spreadsheet-grid horizontal scroll
    (`grid_viewport_sync.py`) is a separate, bespoke mechanism unrelated to
    this class.

    Mousewheel dispatch: one interpreter-wide resolver on the router-owned ``all``
    tag (``bw_gui.runtime.scroll_resolver``) decides which frame scrolls: the
    nearest registered frame along the widget hierarchy, within the event's own
    toplevel; native scrollable widgets (Text, Listbox, Treeview, scrollbars,
    combobox) and widgets with their own ``bind_wheel`` take precedence; a frame
    that does not overflow passes the wheel to the next outer frame. Each frame
    registers its outer frame, canvas and scrollbar and unregisters on destroy, so
    instances never interfere regardless of how many are visible. Over the frame's own
    scrollbar a notch scrolls ``SCROLLBAR_WHEEL_FACTOR`` times as far as over the
    content (`_on_scrollbar_wheel`).
    """

    def __init__(self, master, *, orient: str = "vertical", **frame_kwargs) -> None:
        """Build the viewport.

        Args:
            master: Parent widget.
            orient: ``"vertical"`` (default; content fills the width, scrolls
                in height) or ``"horizontal"`` (content keeps at least its
                requested width, scrolls in width; see the class docstring).
            **frame_kwargs: Forwarded to the underlying ``ttk.Frame``.
        """
        if orient not in ("vertical", "horizontal"):
            raise ValueError(f"orient must be 'vertical' or 'horizontal', got {orient!r}")
        super().__init__(master, **frame_kwargs)
        self._horizontal = orient == "horizontal"

        self.canvas = ui.Canvas(self, highlightthickness=0, borderwidth=0)
        self._default_canvas_height = self.canvas.cget("height")
        self._height_cap: int | None = None
        if self._horizontal:
            self._scrollbar = widgets.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self._scrollbar.set)
            self._scrollbar_grid = {"row": 1, "column": 0, "sticky": "ew"}
        else:
            self._scrollbar = widgets.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=self._scrollbar.set)
            self._scrollbar_grid = {"row": 0, "column": 1, "sticky": "ns"}

        self.canvas.grid(row=0, column=0, sticky="nsw" if self._horizontal else "nsew")
        # Scrollbar is not gridded yet - _update_scrollbar_visibility()
        # grids/hides it on demand, starting from the first <Configure>.
        self._scrollbar_visible = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # A given ttk style is the frame's surface: the content frame uses it too and
        # the canvas (visible below short content) takes its background, so the whole
        # viewport reads as one surface -- also after a theme switch (listener).
        self._surface_style = frame_kwargs.get("style")
        self.content = widgets.Frame(self.canvas, style=self._surface_style) if self._surface_style else widgets.Frame(self.canvas)
        self._content_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self.content.bind("<Unmap>", self._on_content_unmap)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._register_for_mousewheel_dispatch()
        if self._surface_style:
            from bw_gui.theming._theme_listeners import register_theme_listener  # late: theming imports widgets

            self._apply_surface_background()
            self._theme_subscription = register_theme_listener(self._apply_surface_background, owner=self)

    def _apply_surface_background(self, _change: object = None) -> None:
        """Give the canvas the background of the frame's style (no-op if the style has none).

        Args:
            _change: ``ThemeChange`` when called as theme listener (unused).
        """
        background = widgets.Style(self).lookup(self._surface_style, "background")
        if background:
            self.canvas.configure(background=background)

    def refresh_chrome(self) -> None:
        """Reapply canvas chrome (borderless regardless of the active ttk theme).

        Called by `ScrollablePopupWindow.apply_theme()` after a theme
        switch - kept as an explicit method (instead of the caller poking
        `.canvas` directly) so the canvas-chrome detail stays encapsulated
        here, the one place that owns the canvas.
        """
        self.canvas.configure(highlightthickness=0)

    def _register_for_mousewheel_dispatch(self) -> None:
        """Register outer frame, canvas and scrollbar with the interpreter's scroll resolver.

        The single wheel handler on the ``all`` tag belongs to the router-owned
        ``ScrollResolver`` (``bw_gui.runtime.scroll_resolver``); it finds the nearest
        registered frame along the widget hierarchy, independent of registration
        order. The registration ends when this frame is destroyed.
        """
        from bw_gui.runtime.scroll_resolver import scroll_resolver_for

        from bw_gui.runtime.pointer import bind_wheel

        self._wheel_registration = scroll_resolver_for(self).register(self, [self, self.canvas, self._scrollbar])
        self._scrollbar_wheel = bind_wheel(self._scrollbar, self._on_scrollbar_wheel)

    def _on_scrollbar_wheel(self, event) -> EventResult:
        """Scroll ``SCROLLBAR_WHEEL_FACTOR`` times the content distance per notch over the scrollbar.

        Runs on the scrollbar's pointer tag, before Tk's ``Scrollbar`` class binding;
        ``HANDLED`` stops that binding (and the resolver), so the distance is exactly the
        factor times the notches, never a sum of two bindings. Touchpad fractions add up
        through ``whole_steps`` like over the content. A frame that does not overflow
        returns ``NOT_HANDLED`` (its scrollbar is hidden then anyway), and the resolver
        passes the wheel outwards as usual.

        Args:
            event: The ``WheelEvent`` over the scrollbar.

        Returns:
            ``HANDLED`` while the content overflows, otherwise ``NOT_HANDLED``.
        """
        if not self.overflows():
            return EventResult.NOT_HANDLED
        if event.whole_steps:
            self.scroll_units(event.whole_steps * SCROLLBAR_WHEEL_FACTOR)
        return EventResult.HANDLED

    def _on_destroy(self, event=None) -> None:
        if event is not None and getattr(event, "widget", self) is not self:
            return
        registration = getattr(self, "_wheel_registration", None)
        if registration is not None:
            registration.remove()

    @property
    def is_horizontal(self) -> bool:
        """True for ``orient="horizontal"`` (scroll resolver axis)."""
        return self._horizontal

    def overflows(self) -> bool:
        """True while the content is larger than the viewport on the scroll axis."""
        return self._overflows()

    def scroll_units(self, units: int) -> None:
        """Scroll by *units* (positive = towards the content end); used by the scroll resolver."""
        (self.canvas.xview_scroll if self._horizontal else self.canvas.yview_scroll)(int(units), "units")

    def set_height_cap(self, cap: int | None) -> None:
        """Vertical only: request the content's height, but at most *cap* pixels.

        For a panel that should be as tall as its content and scroll only
        beyond a limit (e.g. a details panel docked below a main area, capped
        at a share of the window). ``None`` switches back to the default
        (the frame takes whatever height its parent grants).

        Args:
            cap: Maximum requested height in pixels, or ``None``.

        Raises:
            ValueError: on a horizontal frame.
        """
        if self._horizontal:
            raise ValueError("set_height_cap is only available for vertical ScrollableFrames")
        self._height_cap = cap
        if cap is None:
            self.canvas.configure(height=self._default_canvas_height)
        self._apply_height_cap()

    def see_widget(self, widget) -> None:
        """Vertical only: scroll as little as needed so *widget* (inside ``.content``) is fully visible.

        Args:
            widget: A descendant of ``.content``.
        """
        if self._horizontal or not self._overflows():
            return
        self.update_idletasks()
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + widget.winfo_height()
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + self.canvas.winfo_height()
        total = max(1, self.content.winfo_height())
        if top < view_top:
            self.canvas.yview_moveto(top / total)
        elif bottom > view_bottom:
            self.canvas.yview_moveto(max(0, bottom - self.canvas.winfo_height()) / total)

    def _apply_height_cap(self) -> None:
        """Request ``min(content height, cap)`` while a cap is set (see ``set_height_cap``)."""
        if self._height_cap is not None:
            self.canvas.configure(height=max(1, min(self.content.winfo_reqheight(), self._height_cap)))

    def _on_content_configure(self, _event=None) -> None:
        """Re-fit viewport to the content: height cap (or strip size), scrollregion, scrollbar.

        The one re-evaluation after any content size change; runs on
        `.content`'s `<Configure>` and, for the case Tk sends none, on its
        `<Unmap>` (see `_on_content_unmap`). Reads only requested sizes and
        the canvas bbox (which also uses the requested size), so it is
        correct even while `.content` is unmapped and still has its old size.

        Args:
            _event: The Tk event (unused).
        """
        if self._horizontal:
            self.canvas.configure(width=self.content.winfo_reqwidth(), height=self.content.winfo_reqheight())
        else:
            self._apply_height_cap()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_content_unmap(self, _event=None) -> None:
        """Re-fit when the canvas unmapped `.content` because it scrolled out of view.

        Tk's canvas unmaps an embedded window that lies completely outside
        the visible area -- without resizing it and without `<Configure>`.
        While the canvas is mapped, that only happens when the content
        shrank while the view was scrolled past its new end (e.g. a details
        panel hides its body while scrolled down). Without this
        hook the height cap, scrollregion and scroll position would keep the
        old, larger content's values: the panel stays tall and empty.

        Running `_on_content_configure` here fixes the scrollregion (the
        canvas then confines the view to it) or snaps back to the top; the
        content is back in view, Tk maps and resizes it, and the regular
        `<Configure>` path finishes the job. Ignored while the canvas itself
        is not mapped (the whole frame is hidden, nothing scrolled away).

        Args:
            _event: The Tk ``<Unmap>`` event (unused).
        """
        if self.canvas.winfo_ismapped():
            self._on_content_configure()

    def _on_canvas_configure(self, event) -> None:
        if not self._horizontal:
            self.canvas.itemconfigure(self._content_window, width=max(1, int(event.width)))
        self._update_scrollbar_visibility()

    def _overflows(self) -> bool:
        """Return True while content is larger than the viewport along the scroll axis."""
        bbox = self.canvas.bbox("all")
        if not bbox:
            return False
        if self._horizontal:
            return (bbox[2] - bbox[0]) > self.canvas.winfo_width()
        return (bbox[3] - bbox[1]) > self.canvas.winfo_height()

    def _update_scrollbar_visibility(self) -> None:
        """Show the scrollbar only while content actually overflows the viewport, hide it otherwise.

        Re-run on every content- or canvas-size change (both can flip
        whether an overflow exists): a growing `.content` can start
        needing it, a widening `PanedWindow` pane or a shrinking content
        can stop needing it. Uses `grid`/`grid_remove` (not `grid_forget`)
        so the scrollbar's grid options survive being hidden. When hiding
        because content no longer overflows, also snaps the view back to
        the start - otherwise a since-shrunk `.content` could stay scrolled
        into what is now empty space with no visible scrollbar to fix it.
        """
        needs_scroll = self._overflows()
        if needs_scroll and not self._scrollbar_visible:
            self._scrollbar.grid(**self._scrollbar_grid)
            self._scrollbar_visible = True
        elif not needs_scroll and self._scrollbar_visible:
            self._scrollbar.grid_remove()
            self._scrollbar_visible = False
            (self.canvas.xview_moveto if self._horizontal else self.canvas.yview_moveto)(0)

    def see_x_range(self, left: int, right: int) -> None:
        """Scroll horizontally, only as far as needed, so ``[left, right]`` is visible.

        Horizontal orientation only. Coordinates are in `.content` space
        (for a widget packed at the content's left edge, its own
        ``winfo_x()`` plus offsets within it). A no-op while nothing
        overflows or when the range is already fully visible. Intended for
        bringing a newly selected tab into view; call it after the pending
        geometry has settled (e.g. via ``after_idle``).
        """
        if not self._horizontal:
            raise RuntimeError("see_x_range is only available for orient='horizontal'")
        bbox = self.canvas.bbox("all")
        if not bbox or not self._overflows():
            return
        total = bbox[2] - bbox[0]
        viewport = self.canvas.winfo_width()
        view_left = self.canvas.canvasx(0)
        if left < view_left:
            target = left
        elif right > view_left + viewport:
            target = right - viewport
        else:
            return
        self.canvas.xview_moveto(max(0, target) / total)

