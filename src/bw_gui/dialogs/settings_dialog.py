from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bw_gui.runtime import ui, widgets
from bw_gui.theming import apply_window_theme, configure_ttk_theme, get_theme

FieldType = Literal["bool", "string", "int", "float", "enum"]


@dataclass(frozen=True)
class SettingsFieldSpec:
    key: str
    label: str
    field_type: FieldType = "string"
    default: object = ""
    enum_values: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None
    hint: str = ""
    live_apply: bool = False

    def __post_init__(self) -> None:
        if self.field_type == "enum" and not self.enum_values:
            raise ValueError(f"SettingsFieldSpec '{self.key}' of type enum needs enum_values")


@dataclass(frozen=True)
class SettingsSectionSpec:
    key: str
    label: str
    fields: tuple[SettingsFieldSpec, ...]


@dataclass(frozen=True)
class SettingsDialogSpec:
    sections: tuple[SettingsSectionSpec, ...]

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError("SettingsDialogSpec requires at least one section")


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on", "ja"}


def _coerce_number(value: object, *, as_float: bool) -> float | int:
    if value is None or str(value).strip() == "":
        return 0.0 if as_float else 0
    parsed = float(str(value).strip())
    return parsed if as_float else int(round(parsed))


def _apply_bounds(value: float | int, spec: SettingsFieldSpec) -> float | int:
    bounded = value
    if spec.min_value is not None:
        bounded = max(spec.min_value, float(bounded))
    if spec.max_value is not None:
        bounded = min(spec.max_value, float(bounded))
    if spec.field_type == "int":
        return int(round(float(bounded)))
    return float(bounded)


def _coerce_one(value: object, spec: SettingsFieldSpec) -> object:
    if spec.field_type == "bool":
        return _parse_bool(value)

    if spec.field_type == "enum":
        text = str(value if value is not None else spec.default).strip()
        if text in spec.enum_values:
            return text
        if str(spec.default).strip() in spec.enum_values:
            return str(spec.default).strip()
        return spec.enum_values[0]

    if spec.field_type == "int":
        try:
            parsed = _coerce_number(value, as_float=False)
        except Exception:
            parsed = _coerce_number(spec.default, as_float=False)
        return _apply_bounds(parsed, spec)

    if spec.field_type == "float":
        try:
            parsed = _coerce_number(value, as_float=True)
        except Exception:
            parsed = _coerce_number(spec.default, as_float=True)
        return _apply_bounds(parsed, spec)

    return str(value if value is not None else spec.default)


def coerce_settings_payload(raw_values: dict[str, object], spec: SettingsDialogSpec) -> dict[str, object]:
    out: dict[str, object] = {}
    for section in spec.sections:
        for field in section.fields:
            out[field.key] = _coerce_one(raw_values.get(field.key, field.default), field)
    return out


class TabbedSettingsDialog:
    """Generic tab-based settings dialog driven by section/field specs."""

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
        if not section_key:
            return False
        return any(section.key == section_key for section in self.spec.sections)

    def _apply_dialog_theme(self) -> None:
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
        buttons = widgets.Frame(root)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        buttons.columnconfigure(0, weight=1)

        widgets.Button(buttons, text="Cancel", command=self._on_cancel).grid(row=0, column=1, sticky="e")
        widgets.Button(buttons, text="Apply", command=self._on_apply).grid(row=0, column=2, sticky="e", padx=(8, 0))
        widgets.Button(buttons, text="Save", style="PrimaryAction.TButton", command=self._on_save).grid(
            row=0,
            column=3,
            sticky="e",
            padx=(8, 0),
        )

    def _initialize_fields(self, values: dict[str, object]) -> None:
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

    def _on_section_select(self, _event=None) -> None:
        selection = self.sections_listbox.curselection()
        if not selection:
            return
        section = self.spec.sections[int(selection[0])]
        self._select_section(section.key)

    def _select_section(self, section_key: str) -> None:
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
        label = widgets.Label(self.content_frame, text=field.label)
        label.grid(row=row_index, column=0, sticky="w", padx=(0, 12), pady=5)

        var = self._field_vars[field.key]
        if field.field_type == "bool":
            widget = widgets.Checkbutton(self.content_frame, variable=var)
            widget.grid(row=row_index, column=1, sticky="w", pady=5)
            return row_index + 1

        if field.field_type == "enum":
            widget = widgets.Combobox(
                self.content_frame,
                textvariable=var,
                values=list(field.enum_values),
                state="readonly",
                width=36,
            )
            widget.grid(row=row_index, column=1, sticky="w", pady=5)
            return row_index + 1

        widget = widgets.Entry(self.content_frame, textvariable=var, width=40)
        widget.grid(row=row_index, column=1, sticky="w", pady=5)

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
            hint_label = widgets.Label(
                self.content_frame,
                text=" | ".join(hints),
                style="SettingsHint.TLabel",
            )
            hint_label.grid(row=row_index + 1, column=1, sticky="w", pady=(0, 6))
            return row_index + 2

        return row_index + 1

    def _collect_values(self) -> dict[str, object]:
        raw: dict[str, object] = {}
        for key, var in self._field_vars.items():
            raw[key] = var.get()
        return coerce_settings_payload(raw, self.spec)

    def _on_live_change(self, *_args) -> None:
        if self._on_live_apply is None:
            return
        self._on_live_apply(self._collect_values())

    def _on_apply(self) -> None:
        values = self._collect_values()
        if self._on_commit is not None:
            self._on_commit(values)
        if self._on_live_apply is not None:
            self._on_live_apply(values)
        self.result = values

    def _on_save(self) -> None:
        self._on_apply()
        self.window.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.window.destroy()

    def _on_content_configure(self, _event=None) -> None:
        bbox = self.content_canvas.bbox("all")
        if bbox is not None:
            self.content_canvas.configure(scrollregion=bbox)

    def _on_canvas_configure(self, event) -> None:
        self.content_canvas.itemconfigure(self.content_window_id, width=event.width)

    def _on_mouse_wheel(self, event) -> None:
        delta = 0
        if hasattr(event, "delta"):
            delta = int(event.delta)
        if delta == 0:
            return
        steps = -1 * int(delta / 120) if delta % 120 == 0 else (-1 if delta > 0 else 1)
        self.content_canvas.yview_scroll(steps, "units")


def open_tabbed_settings_dialog(
    parent,
    *,
    title: str,
    theme_key: str,
    spec: SettingsDialogSpec,
    initial_values: dict[str, object],
    initial_section: str | None = None,
    on_live_apply=None,
    on_commit=None,
) -> dict[str, object] | None:
    dialog = TabbedSettingsDialog(
        parent,
        title=title,
        theme_key=theme_key,
        spec=spec,
        initial_values=initial_values,
        initial_section=initial_section,
        on_live_apply=on_live_apply,
        on_commit=on_commit,
    )
    return dialog.result
