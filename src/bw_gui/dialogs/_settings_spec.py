"""Data classes and value-coercion helpers for the settings dialog.

Defines the three spec classes (``SettingsFieldSpec``, ``SettingsSectionSpec``,
``SettingsDialogSpec``) that consumers use to declare their settings structure,
and the pure helper ``coerce_settings_payload`` that normalises raw form values
back to typed Python objects before handing them to the caller.

This module has no UI or theming dependency so it can be imported independently
of a running Tk display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldType = Literal["bool", "string", "int", "float", "enum"]


@dataclass(frozen=True)
class SettingsFieldSpec:
    """Declares one editable field inside a settings section.

    Args:
        key:          Unique identifier; used as the key in the values dict.
        label:        Human-readable label displayed next to the input widget.
        field_type:   Controls widget type and value coercion (default ``"string"``).
        default:      Value used when no saved setting exists.
        enum_values:  Ordered choices for ``field_type="enum"`` fields.
        min_value:    Lower bound for numeric fields (``None`` = unbounded).
        max_value:    Upper bound for numeric fields (``None`` = unbounded).
        hint:         Optional hint text shown below the entry widget.
        live_apply:   When ``True``, the dialog fires ``on_live_apply`` on every
                      keystroke / toggle, enabling real-time previewing.
        visible_when: ``(controlling_field_key, required_value)``. When set,
                      this field is only rendered while the field named
                      ``controlling_field_key`` currently holds
                      ``required_value`` — e.g. a "fixed cutoff time" field
                      that only appears once a sibling mode field is switched
                      to ``"fixed"``. ``None`` (default) means always visible.
    """

    key: str
    label: str
    field_type: FieldType = "string"
    default: object = ""
    enum_values: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None
    hint: str = ""
    live_apply: bool = False
    visible_when: tuple[str, object] | None = None

    def __post_init__(self) -> None:
        if self.field_type == "enum" and not self.enum_values:
            raise ValueError(f"SettingsFieldSpec '{self.key}' of type enum needs enum_values")


@dataclass(frozen=True)
class SettingsSectionSpec:
    """Groups related fields into a named tab/section.

    Args:
        key:    Unique identifier for the section; also used by ``initial_section``.
        label:  Human-readable name shown in the section list.
        fields: Ordered tuple of field specs belonging to this section.
    """

    key: str
    label: str
    fields: tuple[SettingsFieldSpec, ...]


@dataclass(frozen=True)
class SettingsDialogSpec:
    """Top-level spec aggregating all sections for a settings dialog.

    Args:
        sections: Ordered tuple of section specs; must contain at least one.
    """

    sections: tuple[SettingsSectionSpec, ...]

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError("SettingsDialogSpec requires at least one section")
        all_keys = {field.key for section in self.sections for field in section.fields}
        for section in self.sections:
            for field in section.fields:
                if field.visible_when is not None and field.visible_when[0] not in all_keys:
                    raise ValueError(
                        f"SettingsFieldSpec '{field.key}' has visible_when referencing "
                        f"unknown field '{field.visible_when[0]}'"
                    )


def _parse_bool(value: object) -> bool:
    """Return the boolean interpretation of a stored settings value."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on", "ja"}


def _coerce_number(value: object, *, as_float: bool) -> float | int:
    """Parse *value* as a number; return 0 on empty/None input."""
    if value is None or str(value).strip() == "":
        return 0.0 if as_float else 0
    parsed = float(str(value).strip())
    return parsed if as_float else int(round(parsed))


def _apply_bounds(value: float | int, spec: SettingsFieldSpec) -> float | int:
    """Clamp *value* to the min/max defined in *spec*."""
    bounded = value
    if spec.min_value is not None:
        bounded = max(spec.min_value, float(bounded))
    if spec.max_value is not None:
        bounded = min(spec.max_value, float(bounded))
    if spec.field_type == "int":
        return int(round(float(bounded)))
    return float(bounded)


def _coerce_one(value: object, spec: SettingsFieldSpec) -> object:
    """Coerce a single raw field value to the type declared in *spec*."""
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
    """Return a fully typed settings dict by coercing every raw form value.

    Iterates all sections and fields in *spec* and applies ``_coerce_one`` to
    each raw value.  Missing keys in *raw_values* fall back to
    ``field.default``.

    Args:
        raw_values: Mapping of field keys to raw (uncoerced) values from the UI.
        spec:       Full dialog spec that declares field types and defaults.

    Returns:
        A new dict with the same keys, values coerced to their declared types.
    """
    out: dict[str, object] = {}
    for section in spec.sections:
        for field in section.fields:
            out[field.key] = _coerce_one(raw_values.get(field.key, field.default), field)
    return out
