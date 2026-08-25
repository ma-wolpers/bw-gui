"""``TabbedSettingsDialog`` implementation — side-list + scrollable content area.

Private module; import via ``bw_gui.dialogs.settings_dialog`` or
``bw_gui.dialogs``.  Only ``settings_dialog.py`` (the public module) and
``dialogs/__init__.py`` should import from here.
"""

from __future__ import annotations

from bw_gui.runtime import ui, widgets
from bw_gui.runtime.platform import center_window_over_parent
from bw_gui.theming import apply_window_theme, configure_ttk_theme
from bw_gui.theming._theme_manager import get_theme

from ._settings_spec import SettingsDialogSpec, SettingsFieldSpec, coerce_settings_payload


class TabbedSettingsDialog:
    """Generic tab-based settings dialog driven by section/field specs.

    Displays a sidebar list of section names on the left and a scrollable
    content area with the active section's fields on the right.  Supports
    live-apply previewing (``on_live_apply``), deferred commit (``on_commit``),
    and optional navigation to a specific initial section.

    Args:
        parent:           Tk parent window.
        title:            Window title bar text.
        theme_key:        Active theme key forwarded to bw_gui theming.
        spec:             Full dialog spec (sections + fields).
        initial_values:   Pre-populated values keyed by field key.
        initial_section:  Section key to activate on open; first section used
                          when ``None`` or not found.
        on_live_apply:    Callable invoked with the current values dict on every
                          ``live_apply=True`` field change.
        on_commit:        Callable invoked with the values dict on Apply/Save.
        geometry:         Tk geometry string for initial window size.
        minsize:          ``(width, height)`` minimum window size.
    """

    def __init__(
        self,
        parent,
        *,
        title: str,
        theme_key: str,
        spec: SettingsDialogSpec,
        initial_values: dict[str, object],
        initial_section: str | None = None,
        on_live_apply=None,
        on_commit=None,
        geometry: str = "980x700",
        minsize: tuple[int, int] = (900, 620),
    ):
        """Build and display the dialog; blocks until the user closes it."""
        self.parent = parent
        self.spec = spec
        self.result: dict[str, object] | None = None
        self._on_live_apply = on_live_apply
        self._on_commit = on_commit
        self._theme_key = theme_key
        self._theme = get_theme(theme_key)
        self._field_specs: dict[str, SettingsFieldSpec] = {
            field.key: field
            for section in spec.sections
            for field in section.fields
        }
        self._field_vars: dict[str, ui.Variable] = {}
        self._active_section_key = spec.sections[0].key

        self.window = ui.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.geometry(geometry)
        self.window.minsize(*minsize)
        # geometry above is size-only ("WxH"); without this, Tk/Windows places an
        # un-positioned Toplevel on the primary monitor even when parent lives elsewhere.
        center_window_over_parent(self.window, parent)
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(0, weight=1)

        apply_window_theme(self.window, theme_key)
        configure_ttk_theme(self.window, theme_key)

        root = widgets.Frame(self.window, padding=10)
        root.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)

        self._build_sections_list(root)
        self._build_content_area(root)
        self._build_buttons(root)
        self._initialize_fields(initial_values)

        target = initial_section if self._section_exists(initial_section) else self._active_section_key
        self._select_section(target)

        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.window.grab_set()
        self.window.focus_set()
        self._apply_dialog_theme()
        self.parent.wait_window(self.window)

    def _section_exists(self, section_key: str | None) -> bool:
        """Return True if *section_key* matches any section in the spec."""
        if not section_key:
            return False
        return any(section.key == section_key for section in self.spec.sections)

    def _apply_dialog_theme(self) -> None:
        """Apply the active theme colors to raw-Tk widgets that ttk styles cannot reach."""
        theme = get_theme(self._theme_key)
        self._theme = theme
        self.sections_listbox.configure(
            background=theme["bg_surface"],
            foreground=theme["fg_primary"],
            selectbackground=theme["accent"],
            selectforeground=theme["fg_on_accent"],
            highlightthickness=1,
            highlightbackground=theme["border"],
            highlightcolor=theme["focus_ring"],
            borderwidth=0,
            relief="flat",
        )
        self.content_canvas.configure(
            background=theme["bg_main"],
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
        )

    def _build_sections_list(self, root) -> None:
        """Build the sidebar section list with a vertical scrollbar."""
        side = widgets.Frame(root, style="Settings.Sidebar.TFrame", padding=(6, 6, 6, 6))
        side.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        side.rowconfigure(0, weight=1)

        self.sections_listbox = ui.Listbox(side, exportselection=False, height=24, width=28)
        self.sections_listbox.grid(row=0, column=0, sticky="ns")

        scroll = widgets.Scrollbar(side, orient="vertical", command=self.sections_listbox.yview, style="Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.sections_listbox.configure(yscrollcommand=scroll.set)

        for section in self.spec.sections:
            self.sections_listbox.insert("end", section.label)

        self.sections_listbox.bind("<<ListboxSelect>>", self._on_section_select)

    def _build_content_area(self, root) -> None:
        """Build the scrollable content pane where field widgets are rendered."""
        content = widgets.Frame(root, style="Settings.Panel.TFrame", padding=(6, 6, 6, 6))
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        self.content_canvas = ui.Canvas(content, highlightthickness=0)
        self.content_canvas.grid(row=0, column=0, sticky="nsew")

        scroll = widgets.Scrollbar(content, orient="vertical", command=self.content_canvas.yview, style="Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.content_canvas.configure(yscrollcommand=scroll.set)

        self.content_frame = widgets.Frame(self.content_canvas, style="Settings.Panel.TFrame", padding=(6, 2, 10, 10))
        self.content_window_id = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")

        self.content_frame.bind("<Configure>", self._on_content_configure)
        self.content_canvas.bind("<Configure>", self._on_canvas_configure)
        self.content_canvas.bind("<MouseWheel>", self._on_mouse_wheel)

    def _build_buttons(self, root) -> None:
        """Build the Cancel / Apply / Save button row at the bottom of the dialog."""
        buttons = widgets.Frame(root)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        buttons.columnconfigure(0, weight=1)

        widgets.Button(buttons, text="Cancel", command=self._on_cancel).grid(row=0, column=1, sticky="e")
        widgets.Button(buttons, text="Apply", command=self._on_apply).grid(row=0, column=2, sticky="e", padx=(8, 0))
        widgets.Button(buttons, text="Save", style="PrimaryAction.TButton", command=self._on_save).grid(
            row=0, column=3, sticky="e", padx=(8, 0),
        )

    def _initialize_fields(self, values: dict[str, object]) -> None:
        """Create tk Variables for all fields and wire live-apply + visibility traces."""
        normalized = coerce_settings_payload(values, self.spec)
        for section in self.spec.sections:
            for field in section.fields:
                value = normalized.get(field.key, field.default)
                if field.field_type == "bool":
                    var = ui.BooleanVar(value=bool(value))
                else:
                    var = ui.StringVar(value=str(value))
                self._field_vars[field.key] = var
                if field.live_apply and self._on_live_apply is not None:
                    var.trace_add("write", self._on_live_change)

        controlling_keys = {
            field.visible_when[0]
            for section in self.spec.sections
            for field in section.fields
            if field.visible_when is not None
        }
        for key in controlling_keys:
            self._field_vars[key].trace_add("write", self._on_visibility_controlling_change)

    def _on_visibility_controlling_change(self, *_args) -> None:
        """Re-render the active section so `visible_when` fields re-evaluate."""
        self._select_section(self._active_section_key)

    def _field_is_visible(self, field: SettingsFieldSpec) -> bool:
        """Return True if `field.visible_when` is unset or currently satisfied."""
        if field.visible_when is None:
            return True
        controlling_key, required_value = field.visible_when
        return self._field_vars[controlling_key].get() == required_value

    def _on_section_select(self, _event=None) -> None:
        """Handle listbox selection event and navigate to the chosen section."""
        selection = self.sections_listbox.curselection()
        if not selection:
            return
        section = self.spec.sections[int(selection[0])]
        self._select_section(section.key)

    def _select_section(self, section_key: str) -> None:
        """Activate *section_key*: update the listbox highlight and render fields."""
        self._active_section_key = section_key
        for index, section in enumerate(self.spec.sections):
            if section.key == section_key:
                self.sections_listbox.selection_clear(0, "end")
                self.sections_listbox.selection_set(index)
                self.sections_listbox.see(index)
                break

        for child in self.content_frame.winfo_children():
            child.destroy()

        section = next(item for item in self.spec.sections if item.key == section_key)
        header = widgets.Label(self.content_frame, text=section.label, style="SectionTitle.TLabel")
        header.grid(row=0, column=0, sticky="w", pady=(0, 8))

        row_index = 1
        for field in section.fields:
            row_index = self._render_field(row_index, field)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_canvas.yview_moveto(0.0)

    def _render_field(self, row_index: int, field: SettingsFieldSpec) -> int:
        """Render one field row; return the next available row index.

        Bool fields render a checkbutton; enum fields render a combobox;
        all other types render a text entry with optional hint labels below.

        Args:
            row_index: Grid row to place the label and input widget.
            field:     Field spec describing label, type, and constraints.

        Returns:
            Row index after the rendered field (accounting for hint rows).
        """
        if not self._field_is_visible(field):
            return row_index

        label = widgets.Label(self.content_frame, text=field.label)
        label.grid(row=row_index, column=0, sticky="w", padx=(0, 12), pady=5)

        var = self._field_vars[field.key]
        if field.field_type == "bool":
            widgets.Checkbutton(self.content_frame, variable=var).grid(row=row_index, column=1, sticky="w", pady=5)
            return row_index + 1

        if field.field_type == "enum":
            widgets.Combobox(
                self.content_frame,
                textvariable=var,
                values=list(field.enum_values),
                state="readonly",
                width=36,
            ).grid(row=row_index, column=1, sticky="w", pady=5)
            return row_index + 1

        widgets.Entry(self.content_frame, textvariable=var, width=40).grid(row=row_index, column=1, sticky="w", pady=5)

        hints: list[str] = []
        if field.field_type == "int":
            hints.append("integer")
        if field.field_type == "float":
            hints.append("decimal")
        if field.min_value is not None or field.max_value is not None:
            hints.append(f"min={field.min_value} max={field.max_value}")
        if field.hint:
            hints.append(field.hint)

        if hints:
            widgets.Label(
                self.content_frame,
                text=" | ".join(hints),
                style="SettingsHint.TLabel",
            ).grid(row=row_index + 1, column=1, sticky="w", pady=(0, 6))
            return row_index + 2

        return row_index + 1

    def _collect_values(self) -> dict[str, object]:
        """Read all field variables and return a coerced values dict."""
        raw: dict[str, object] = {key: var.get() for key, var in self._field_vars.items()}
        return coerce_settings_payload(raw, self.spec)

    def _on_live_change(self, *_args) -> None:
        """Trigger live-apply callback when a traced field variable changes."""
        if self._on_live_apply is None:
            return
        self._on_live_apply(self._collect_values())

    def _on_apply(self) -> None:
        """Collect current values and fire both commit and live-apply callbacks."""
        values = self._collect_values()
        if self._on_commit is not None:
            self._on_commit(values)
        if self._on_live_apply is not None:
            self._on_live_apply(values)
        self.result = values

    def _on_save(self) -> None:
        """Apply changes and close the dialog."""
        self._on_apply()
        self.window.destroy()

    def _on_cancel(self) -> None:
        """Discard changes and close the dialog."""
        self.result = None
        self.window.destroy()

    def _on_content_configure(self, _event=None) -> None:
        """Update the canvas scroll region when the inner frame resizes."""
        bbox = self.content_canvas.bbox("all")
        if bbox is not None:
            self.content_canvas.configure(scrollregion=bbox)

    def _on_canvas_configure(self, event) -> None:
        """Keep the inner frame the same width as the canvas viewport."""
        self.content_canvas.itemconfigure(self.content_window_id, width=event.width)

    def _on_mouse_wheel(self, event) -> None:
        """Scroll the content canvas on mouse-wheel events."""
        delta = 0
        if hasattr(event, "delta"):
            delta = int(event.delta)
        if delta == 0:
            return
        steps = -1 * int(delta / 120) if delta % 120 == 0 else (-1 if delta > 0 else 1)
        self.content_canvas.yview_scroll(steps, "units")
