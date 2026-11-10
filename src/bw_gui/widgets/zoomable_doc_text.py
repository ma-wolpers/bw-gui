"""Read-only, themed document view with Ctrl+wheel zoom (``ZoomableDocText``).

Shows ``DocEvent`` lists (``doc_text_events``) in a word-wrapping ``Text``
with a vertical scrollbar. The plain mouse wheel scrolls natively (the
``Text`` class binding), Ctrl+wheel changes the body point size within
``[min_size, max_size]``. Zooming only re-configures the doc tags through
``configure_doc_text_theme`` -- the content is not rendered again -- and a
theme listener re-colours the view after every theme switch.
"""

from __future__ import annotations

from collections.abc import Callable

from bw_gui.contracts.events import EventResult
from bw_gui.contracts.key_modifiers import KeyModifiers
from bw_gui.contracts.pointer import WheelEvent
from bw_gui.runtime import ui, widgets
from bw_gui.runtime.pointer import bind_wheel
from bw_gui.theming._theme_listeners import ThemeChange, register_theme_listener
from bw_gui.theming._widget_utils import theme_text

from .doc_text_events import DocEvent
from .doc_text_view import DEFAULT_DOC_BASE_SIZE, configure_doc_text_theme, render_events_into_text

__all__ = ["ZoomableDocText"]


class ZoomableDocText(widgets.Frame):
    """A ``ttk.Frame`` holding a read-only doc ``Text`` plus scrollbar.

    Args:
        parent: Container widget.
        base_size: Initial body point size (clamped into the zoom range).
        min_size: Smallest body point size reachable by zooming.
        max_size: Largest body point size reachable by zooming.
        on_zoom_changed: Called with the new size after every zoom step
            (e.g. to persist it); not called for ``set_base_size`` no-ops.
        on_copy: Receives a code block's raw text when its "Kopieren"
            button is pressed (default: the Tk clipboard).
    """

    def __init__(
        self,
        parent: ui.Misc,
        *,
        base_size: int = DEFAULT_DOC_BASE_SIZE,
        min_size: int = 7,
        max_size: int = 24,
        on_zoom_changed: Callable[[int], object] | None = None,
        on_copy: Callable[[str], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self._min_size = min_size
        self._max_size = max_size
        self._base_size = self._clamp(base_size)
        self._on_zoom_changed = on_zoom_changed
        self._on_copy = on_copy or self._copy_to_clipboard
        self.text = ui.Text(self, wrap="word", relief="flat", borderwidth=0, padx=10, pady=8, takefocus=0)
        self._scrollbar = widgets.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self._scrollbar.set, state="disabled")
        self.text.grid(row=0, column=0, sticky="nsew")
        self._scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        bind_wheel(self.text, self._on_wheel)
        register_theme_listener(self._on_theme_changed, owner=self)
        self._apply_style()

    @property
    def base_size(self) -> int:
        """Current body point size."""
        return self._base_size

    def render(self, events: list[DocEvent]) -> None:
        """Replaces the content with ``events`` and scrolls back to the top."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        render_events_into_text(self.text, events, on_copy=self._on_copy)
        self.text.configure(state="disabled")
        self.text.yview_moveto(0.0)

    def set_base_size(self, size: int) -> None:
        """Sets the body point size (clamped); re-styles and reports a real change."""
        clamped = self._clamp(size)
        if clamped == self._base_size:
            return
        self._base_size = clamped
        self._apply_style()
        if self._on_zoom_changed is not None:
            self._on_zoom_changed(clamped)

    def _clamp(self, size: int) -> int:
        return max(self._min_size, min(self._max_size, int(size)))

    def _on_wheel(self, event: WheelEvent) -> EventResult | None:
        """Ctrl+wheel zooms (wheel up = larger); the plain wheel stays native scrolling."""
        if not (isinstance(event.modifiers, KeyModifiers) and event.modifiers.control):
            return None
        if event.whole_steps:
            self.set_base_size(self._base_size - int(event.whole_steps))
        return EventResult.HANDLED

    def _apply_style(self) -> None:
        theme_text(self.text)
        configure_doc_text_theme(self.text, base_size=self._base_size)

    def _on_theme_changed(self, _change: ThemeChange) -> None:
        self._apply_style()

    def _copy_to_clipboard(self, code: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(code)
