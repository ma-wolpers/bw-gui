from __future__ import annotations

from collections.abc import Callable

from bw_gui.runtime import ui, widgets
from bw_gui.runtime.platform import center_window_over_parent
from bw_gui.widgets.scrollable_frame import ScrollableFrame


class ScrollablePopupWindow:
    """Reusable popup host with a scrollable content surface and modal helpers.

    The default popup type per `docs/SCROLLABILITY_CONTRACT.md`: builds its
    scrollable content area directly on `bw_gui.widgets.ScrollableFrame`
    (the shared scroll SSOT) instead of maintaining its own parallel
    Canvas/Scrollbar/mousewheel implementation - only Toplevel lifecycle
    (creation, geometry, theme injection, modal focus, Escape/close
    handling) lives here.
    """

    _open_popups: list["ScrollablePopupWindow"] = []

    def __getattr__(self, name: str):
        """Delegate unknown attributes to the composed ``ui.Toplevel`` window."""
        return getattr(self._popup_window, name)

    def __str__(self) -> str:
        """Expose the popup Tk widget path for APIs that stringify owners."""
        return str(self._popup_window)

    def __init__(
        self,
        master,
        *,
        title: str,
        geometry: str,
        minsize: tuple[int, int],
        theme_key: str | None = None,
        scrollable: bool = True,
        apply_window_theme: Callable[[ui.Misc, str | None], None] | None = None,
        configure_ttk_theme: Callable[[ui.Misc, str | None], None] | None = None,
        request_close_confirmation: Callable[[], bool] | None = None,
    ):
        """Build the popup chrome, optionally wrapping the content area in its own scroll surface.

        Args:
            scrollable: When ``True`` (default, unchanged behavior for existing
                callers), the whole content area is a ``bw_gui.widgets.ScrollableFrame``
                (vertical Canvas+Scrollbar, mousewheel handled anywhere inside it,
                including nested child widgets - see that class) -- suited for
                simple forms whose content can exceed the window height.
                Set to ``False`` for a popup that already manages its own
                internal scrolling (e.g. a canvas-based graph plus a
                separately scrollable sidebar) -- a second, window-wide
                scroll layer around such content only produces competing
                mousewheel captures. When ``False``, ``self.content`` is a
                plain Frame packed directly into the popup, and no
                ``ScrollableFrame``/mousewheel handler is created at all.
        """
        self._popup_window = ui.Toplevel(master)
        self.title(title)
        self.geometry(geometry)
        self.minsize(*minsize)
        self.transient(master)
        # geometry above is size-only ("WxH"); without this, Tk/Windows places an
        # un-positioned Toplevel on the primary monitor even when master lives elsewhere.
        center_window_over_parent(self._popup_window, master)

        self.theme_key = theme_key
        self._apply_window_theme = apply_window_theme
        self._configure_ttk_theme = configure_ttk_theme
        self._request_close_confirmation = request_close_confirmation
        self._closing = False
        self._scroll: ScrollableFrame | None = None
        self._canvas: ui.Canvas | None = None

        if scrollable:
            # Canvas/Scrollbar/scrollregion/resize/mousewheel mechanics all
            # live in ScrollableFrame (the bw-gui scroll SSOT, see its
            # module docstring) - this class only owns Toplevel lifecycle.
            # `self._canvas` stays as a thin alias to `self._scroll.canvas`
            # purely for any external/private-attribute access; nothing in
            # this repo or its known consumers (korrektor, Kursplaner) uses
            # it, but it costs nothing to keep.
            self._scroll = ScrollableFrame(self)
            self._scroll.pack(fill="both", expand=True)
            self.content = self._scroll.content
            self._canvas = self._scroll.canvas
        else:
            self.content = widgets.Frame(self)
            self.content.pack(fill="both", expand=True)

        self.bind("<Escape>", self._on_escape_close, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        ScrollablePopupWindow._open_popups.append(self)
        self.after_idle(self._activate_modal_focus)
        self.after(80, self._activate_modal_focus)

    @classmethod
    def _cleanup_open_popups(cls) -> None:
        cls._open_popups = [popup for popup in cls._open_popups if popup.winfo_exists()]

    @classmethod
    def active_popup(cls) -> "ScrollablePopupWindow | None":
        cls._cleanup_open_popups()
        if not cls._open_popups:
            return None
        return cls._open_popups[-1]

    @classmethod
    def has_active_popup(cls) -> bool:
        return cls.active_popup() is not None

    @classmethod
    def close_active_popup(cls) -> bool:
        """Close the currently active popup and return whether one was closed."""
        popup = cls.active_popup()
        if popup is None:
            return False
        popup._handle_escape_request()
        return True

    def _activate_modal_focus(self) -> None:
        if not self.winfo_exists():
            return
        active_popup = getattr(type(self), "active_popup", ScrollablePopupWindow.active_popup)
        if active_popup() is not self:
            return
        try:
            self.lift()
            focused = self.focus_get()
            if not self._is_descendant_of_popup(focused):
                self.focus_force()
        except ui.TclError:
            return
        try:
            if self.grab_current() is None:
                self.grab_set()
        except ui.TclError:
            return

    def _is_descendant_of_popup(self, widget: ui.Misc | None) -> bool:
        if widget is None:
            return False
        popup_window = getattr(self, "_popup_window", self)
        current = widget
        while current is not None:
            if current is self or current is popup_window:
                return True
            try:
                parent_name = current.winfo_parent()
            except ui.TclError:
                return False
            if not parent_name:
                return False
            try:
                current = current.nametowidget(parent_name)
            except KeyError:
                return False
            except ui.TclError:
                return False
        return False

    def _on_destroy(self, _event=None):
        ScrollablePopupWindow._cleanup_open_popups()

    def _request_close(self) -> str:
        """Close the popup, idempotently.

        Reachable from multiple paths (window-close protocol, Escape) that
        could in principle fire in quick succession before the first
        ``destroy()`` has fully run — the ``_closing`` guard makes a second
        call a no-op instead of risking a ``TclError`` on an already-torn-down
        widget. ``withdraw()`` hides the window immediately, before
        ``destroy()`` tears down its (possibly deeply nested/scrollable)
        child widget tree, so no intermediate teardown layout is visible.
        """
        if self._closing:
            return "break"
        if self._request_close_confirmation is not None:
            should_close = bool(self._request_close_confirmation())
            if not should_close:
                return "break"
        self._closing = True
        try:
            self.withdraw()
        except ui.TclError:
            pass
        self.destroy()
        return "break"

    def _handle_escape_request(self) -> str:
        """Close the popup on Escape, unconditionally.

        Previously this refocused instead of closing when an editable widget had
        focus, via ``self.focus_force()`` on the already-focused popup window — which
        does not actually change which widget holds keyboard focus, so it had no
        observable effect and Escape appeared to do nothing while typing.
        """
        return self._request_close()

    def _on_escape_close(self, _event=None):
        if self.active_popup() is not self:
            return "break"
        return self._handle_escape_request()

    def _on_window_close(self):
        self._request_close()

    def apply_theme(self) -> None:
        """Apply optional shared theme callbacks and keep canvas chrome consistent.

        No-ops the canvas chrome step when constructed with ``scrollable=False``
        (no ``self._scroll`` exists in that case) - canvas/scrollregion/
        resize/mousewheel mechanics live in ``ScrollableFrame`` now
        (``self._scroll``), this only asks it to reapply its chrome.
        """
        if self._apply_window_theme is not None:
            self._apply_window_theme(self, self.theme_key)
        if self._configure_ttk_theme is not None:
            self._configure_ttk_theme(self, self.theme_key)
        if self._scroll is not None:
            self._scroll.refresh_chrome()
