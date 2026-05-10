from __future__ import annotations

import pytest

from bw_gui.dialogs import (
    SettingsDialogSpec,
    SettingsFieldSpec,
    SettingsSectionSpec,
    coerce_settings_payload,
)


def _sample_spec() -> SettingsDialogSpec:
    return SettingsDialogSpec(
        sections=(
            SettingsSectionSpec(
                key="general",
                label="General",
                fields=(
                    SettingsFieldSpec(key="feature_enabled", label="Feature", field_type="bool", default=True),
                    SettingsFieldSpec(key="theme", label="Theme", field_type="enum", enum_values=("mono_day", "charcoal"), default="mono_day"),
                ),
            ),
            SettingsSectionSpec(
                key="advanced",
                label="Advanced",
                fields=(
                    SettingsFieldSpec(key="retries", label="Retries", field_type="int", default=3, min_value=1, max_value=5),
                    SettingsFieldSpec(key="zoom", label="Zoom", field_type="float", default=1.0, min_value=0.5, max_value=2.0),
                    SettingsFieldSpec(key="notes", label="Notes", field_type="string", default=""),
                ),
            ),
        ),
    )


def test_coerce_settings_payload_applies_types_and_bounds():
    spec = _sample_spec()

    raw = {
        "feature_enabled": "yes",
        "theme": "unknown-theme",
        "retries": "9",
        "zoom": "0.2",
        "notes": 42,
    }

    out = coerce_settings_payload(raw, spec)

    assert out["feature_enabled"] is True
    assert out["theme"] == "mono_day"
    assert out["retries"] == 5
    assert out["zoom"] == 0.5
    assert out["notes"] == "42"


def test_coerce_settings_payload_uses_defaults_for_missing_values():
    spec = _sample_spec()

    out = coerce_settings_payload({}, spec)

    assert out["feature_enabled"] is True
    assert out["theme"] == "mono_day"
    assert out["retries"] == 3
    assert out["zoom"] == 1.0
    assert out["notes"] == ""


def test_enum_field_requires_values():
    with pytest.raises(ValueError):
        SettingsFieldSpec(key="bad", label="Bad", field_type="enum")


def test_dialog_spec_requires_sections():
    with pytest.raises(ValueError):
        SettingsDialogSpec(sections=())
