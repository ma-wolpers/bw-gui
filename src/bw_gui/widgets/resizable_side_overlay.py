"""Full-height side panel laid over its parent's right edge (``ResizableSideOverlay``).

The panel is ``place()``d into its parent, so it floats above whatever the
parent lays out with ``grid``/``pack`` (e.g. a scrollable table) instead of
pushing it aside. A header carries the title and a close button "×"; a grip
on the left edge resizes the panel by dragging (``bind_drag``, Tk's implicit
grab keeps the drag alive outside the grip). The width stays within
``[min_width, parent width * max_ratio]`` -- also when the parent shrinks.
Build the panel's content into ``.content``.
"""

from __future__ import annotations

from collections.abc import Callable

from bw_gui.contracts.pointer import DragEvent
from bw_gui.contracts.widget_events import ResizeEvent
from bw_gui.runtime import ui, widgets
from bw_gui.runtime.pointer import bind_drag
from bw_gui.runtime.widget_events import on_destroy, on_resize

__all__ = ["ResizableSideOverlay"]

GRIP_WIDTH = 6
"""Width of the drag grip on the left edge, in pixels."""


class ResizableSideOverlay(widgets.Frame):
    """A right-anchored, resizable, closable overlay panel.

    Args:
        parent: The widget to float over (the panel is ``place()``d into it).
        title: Header text (``set_title`` changes it later).
        width: Initial width in pixels (clamped on every show/resize).
        min_width: Smallest width the grip allows.
        max_ratio: Largest width as a share of the parent's width.
        on_close: Called after the close button hid the panel.
        on_width_changed: Called with the final width when a grip drag ends.
    """

    def __init__(
        self,
        parent: ui.Misc,
        *,
        title: str = "",
        width: int = 420,
        min_width: int = 240,
        max_ratio: float = 0.8,
        on_close: Callable[[], object] | None = None,
        on_width_changed: Callable[[int], object] | None = None,
    ) -> None:
        super().__init__(parent, style="Panel.TFrame")
        self._parent = parent
        self._min_width = min_width
        self._max_ratio = max_ratio
        self._width = int(width)
        self._visible = False
        self._drag_start_width = self._width
        self._on_close = on_close
        self._on_width_changed = on_width_changed
        self._grip = widgets.Frame(self, width=GRIP_WIDTH, cursor="sb_h_double_arrow", style="ControlStrip.TFrame")
        self._grip.pack(side="left", fill="y")
        widgets.Separator(self, orient="vertical").pack(side="left", fill="y")
        header = widgets.Frame(self, style="Panel.TFrame")
        header.pack(side="top", fill="x", padx=(8, 4), pady=(4, 2))
        self._title = widgets.Label(header, text=title, style="SectionTitle.TLabel", anchor="w")
        self._title.pack(side="left", fill="x", expand=True)
        self.close_button = widgets.Button(header, text="×", width=3, command=self.close)
        self.close_button.pack(side="right")
        self.content = widgets.Frame(self, style="Panel.TFrame")
        """Target frame for the caller's content."""
        self.content.pack(side="top", fill="both", expand=True)
        bind_drag(self._grip, on_start=self._on_drag_start, on_move=self._on_drag_move, on_end=self._on_drag_end)
        resize_subscription = on_resize(parent, self._on_parent_resize)
        on_destroy(self, lambda _widget: resize_subscription.remove())

    @property
    def is_visible(self) -> bool:
        """Whether the panel is currently placed (shown)."""
        return self._visible

    @property
    def width(self) -> int:
        """Requested width in pixels (before clamping to the parent)."""
        return self._width

    def set_title(self, title: str) -> None:
        """Changes the header text."""
        self._title.configure(text=title)

    def show(self) -> None:
        """Places the panel over the parent's right edge and raises it above siblings."""
        self._visible = True
        self.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne", width=self.effective_width())
        self.lift()

    def hide(self) -> None:
        """Removes the panel from the parent's layout (state and content are kept)."""
        self._visible = False
        self.place_forget()

    def close(self) -> None:
        """Hides the panel and reports it (the close button's command)."""
        self.hide()
        if self._on_close is not None:
            self._on_close()

    def effective_width(self) -> int:
        """The width actually shown: the requested width clamped to the parent."""
        return self._clamp(self._width)

    def _clamp(self, width: int) -> int:
        parent_width = self._parent.winfo_width()
        upper = int(parent_width * self._max_ratio) if parent_width > 1 else width
        return max(self._min_width, min(int(width), max(self._min_width, upper)))

    def _on_drag_start(self, _event: DragEvent) -> None:
        self._drag_start_width = self.effective_width()

    def _on_drag_move(self, event: DragEvent) -> None:
        self._width = self._clamp(self._drag_start_width + event.start_x_root - event.x_root)
        if self._visible:
            self.place_configure(width=self._width)

    def _on_drag_end(self, event: DragEvent) -> None:
        self._on_drag_move(event)
        if self._on_width_changed is not None:
            self._on_width_changed(self._width)

    def _on_parent_resize(self, _event: ResizeEvent) -> None:
        if self._visible:
            self.place_configure(width=self.effective_width())
