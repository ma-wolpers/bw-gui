from __future__ import annotations

from collections.abc import Callable

from bw_gui.runtime import ui, widgets

from .scrollable_frame import ScrollableFrame

RenderCallback = Callable[[int], "ui.PhotoImage | None"]


class ScrollableImagePreview(ScrollableFrame):
    """Vertically scrollable, width-fitted image preview (e.g. one PDF page) - the bw-gui SSOT for it.

    Built on `ScrollableFrame` (scrollbar shown only on overflow, mousewheel
    dispatch), with a single `widgets.Label` in `.content` that shows the
    image. bw-gui knows nothing about what is rendered: the caller passes
    ``render(width) -> PhotoImage | None`` and decides how to draw an image
    of that width (for a PDF page: scale the page to ``width`` pixels).

    Typical use is a popup whose control bars must always stay visible:
    pack the bars first and this preview last with ``expand=True``, so a
    smaller window only shrinks (and scrolls) the preview.

    Contract:

    - **Render width** = the width available to the content *if the
      scrollbar were shown*: canvas width, plus the scrollbar's requested
      width while it is visible, minus that same requested width. Showing or
      hiding the scrollbar therefore never changes the render width, so there
      is no render -> taller/shorter image -> scrollbar toggles -> re-render
      oscillation. Deliberate stability trade-off: while no scrollbar is
      needed, the image is a scrollbar-width narrower than the space would
      allow. Before the widget is mapped, ``initial_width`` is used.
    - **Re-render only on width changes** of at least 2 px, debounced via
      ``after(resize_debounce_ms)``. Height changes never re-render - the
      visible part of the image just gets smaller and scrolls.
    - A pending debounce timer is cancelled by `refresh()` and on
      ``<Destroy>``.
    - The preview keeps the reference to the returned `PhotoImage` (Tk
      images are garbage-collected otherwise). ``render`` returning ``None``
      clears the image.
    - **Exceptions** raised by ``render`` are not caught: from `refresh()`
      they propagate to the caller; from a debounced resize render they reach
      Tk's ``report_callback_exception``. Callers that want a friendly error
      display catch inside ``render`` and return ``None``.
    """

    _MIN_WIDTH_DELTA = 2

    def __init__(
        self,
        master,
        *,
        render: RenderCallback,
        initial_width: int = 700,
        resize_debounce_ms: int = 120,
        **frame_kwargs,
    ) -> None:
        """Build the preview. Nothing is rendered until the first `refresh()`; after that, width changes re-render.

        Args:
            master: Parent widget.
            render: ``render(width)`` returning the image for that pixel width,
                or ``None`` for "nothing to show".
            initial_width: Render width used while the widget is not mapped yet.
            resize_debounce_ms: Delay before a width change triggers ``render``.
            **frame_kwargs: Forwarded to `ScrollableFrame` (and the ttk frame).
        """
        super().__init__(master, orient="vertical", **frame_kwargs)
        self._render = render
        self._initial_width = max(1, int(initial_width))
        self._resize_debounce_ms = max(0, int(resize_debounce_ms))
        self._photo: ui.PhotoImage | None = None
        self._last_render_width: int | None = None
        self._pending_render: str | None = None

        self.image_label = widgets.Label(self.content, anchor="nw")
        self.image_label.pack(anchor="nw")

        self.canvas.bind("<Configure>", self._on_preview_canvas_configure, add="+")
        self.bind("<Destroy>", self._on_preview_destroy, add="+")

    def render_width(self) -> int:
        """Return the width ``render`` is called with right now (see the class contract)."""
        canvas_width = int(self.canvas.winfo_width())
        if canvas_width <= 1:
            return self._initial_width
        scrollbar_width = int(self._scrollbar.winfo_reqwidth())
        available = canvas_width + (scrollbar_width if self._scrollbar_visible else 0)
        return max(1, available - scrollbar_width)

    def refresh(self, *, scroll_to_top: bool = False) -> None:
        """Render immediately at the current width, cancelling a pending resize render.

        Args:
            scroll_to_top: Also scroll the view back to the top, e.g. after
                switching to another page.
        """
        self._cancel_pending_render()
        self._render_now()
        if scroll_to_top:
            self.canvas.yview_moveto(0)

    def scroll(self, steps: int, what: str = "units") -> None:
        """Scroll the preview by ``steps`` units or pages; a no-op while nothing overflows.

        Args:
            steps: Negative scrolls up, positive scrolls down.
            what: ``"units"`` (like the mousewheel) or ``"pages"`` (one viewport).
        """
        if what not in ("units", "pages"):
            raise ValueError(f"what must be 'units' or 'pages', got {what!r}")
        if not self._overflows():
            return
        self.canvas.yview_scroll(int(steps), what)

    def _render_now(self) -> None:
        """Call ``render`` with the current width and show the result."""
        width = self.render_width()
        photo = self._render(width)
        self._last_render_width = width
        self._photo = photo
        self.image_label.configure(image=photo if photo is not None else "")

    def _on_preview_canvas_configure(self, _event=None) -> None:
        """Schedule a debounced re-render when the render width changed noticeably."""
        if self._last_render_width is None:
            return
        if abs(self.render_width() - self._last_render_width) < self._MIN_WIDTH_DELTA:
            return
        self._cancel_pending_render()
        self._pending_render = self.after(self._resize_debounce_ms, self._run_pending_render)

    def _run_pending_render(self) -> None:
        """Debounce timer target: render unless the widget is already gone."""
        self._pending_render = None
        if not int(self.winfo_exists()):
            return
        self._render_now()

    def _cancel_pending_render(self) -> None:
        if self._pending_render is None:
            return
        try:
            self.after_cancel(self._pending_render)
        except Exception:
            pass
        self._pending_render = None

    def _on_preview_destroy(self, _event=None) -> None:
        self._cancel_pending_render()
