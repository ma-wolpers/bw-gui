from __future__ import annotations

from collections.abc import Callable

from bw_gui.runtime import ui, widgets


class ScrollablePopupWindow:
    """Reusable popup host with a scrollable content surface and modal helpers."""

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
        apply_window_theme: Callable[[ui.Misc, str | None], None] | None = None,
        configure_ttk_theme: Callable[[ui.Misc, str | None], None] | None = None,
        request_close_confirmation: Callable[[], bool] | None = None,
    ):
        self._popup_window = ui.Toplevel(master)
        self.title(title)
        self.geometry(geometry)
        self.minsize(*minsize)
        self.transient(master)

        self.theme_key = theme_key
        self._apply_window_theme = apply_window_theme
        self._configure_ttk_theme = configure_ttk_theme
        self._request_close_confirmation = request_close_confirmation

        container = widgets.Frame(self)
        container.pack(fill="both", expand=True)

        self._canvas = ui.Canvas(container, highlightthickness=0, borderwidth=0)
        self._v_scroll = widgets.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._h_scroll = widgets.Scrollbar(container, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._v_scroll.set, xscrollcommand=self._h_scroll.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._v_scroll.grid(row=0, column=1, sticky="ns")
        self._h_scroll.grid(row=1, column=0, sticky="ew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.content = widgets.Frame(self._canvas)
        self._content_window = self._canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<MouseWheel>", self._on_mousewheel, add="+")
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
        if self._request_close_confirmation is not None:
            should_close = bool(self._request_close_confirmation())
            if not should_close:
                return "break"
        self.destroy()
        return "break"

    @staticmethod
    def _is_editable_widget(widget) -> bool:
        if widget is None:
            return False
        editable_widget_types = (ui.Entry, ui.Text, ui.Spinbox, widgets.Entry, widgets.Combobox)
        return isinstance(widget, editable_widget_types)

    def _handle_escape_request(self) -> str:
        focused = self.focus_get()
        editable_check = getattr(type(self), "_is_editable_widget", ScrollablePopupWindow._is_editable_widget)
        if self._is_descendant_of_popup(focused) and editable_check(focused):
            try:
                self.focus_force()
            except ui.TclError:
                return "break"
            return "break"
        return self._request_close()

    def _on_escape_close(self, _event=None):
        if self.active_popup() is not self:
            return "break"
        return self._handle_escape_request()

    def _on_window_close(self):
        self._request_close()

    def _on_content_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(
            self._content_window,
            width=max(1, int(event.width)),
        )

    def _on_mousewheel(self, event):
        bbox = self._canvas.bbox("all")
        if not bbox:
            return None
        content_height = bbox[3] - bbox[1]
        if content_height <= self._canvas.winfo_height():
            return None
        step = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(step, "units")
        return "break"

    def apply_theme(self) -> None:
        """Apply optional shared theme callbacks and keep canvas chrome consistent."""
        if self._apply_window_theme is not None:
            self._apply_window_theme(self, self.theme_key)
        if self._configure_ttk_theme is not None:
            self._configure_ttk_theme(self, self.theme_key)
        self._canvas.configure(highlightthickness=0)
