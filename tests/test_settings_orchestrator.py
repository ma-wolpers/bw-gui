from __future__ import annotations

from bw_gui.dialogs.settings_dialog import SettingsDialogSpec, SettingsFieldSpec, SettingsSectionSpec
from bw_gui.dialogs.settings_orchestrator import SettingsDialogOrchestrator
import bw_gui.dialogs.settings_orchestrator as orchestrator_module


def _sample_spec() -> SettingsDialogSpec:
    return SettingsDialogSpec(
        sections=(
            SettingsSectionSpec(
                key="general",
                label="General",
                fields=(
                    SettingsFieldSpec(key="theme", label="Theme", field_type="enum", enum_values=("mono_day",), default="mono_day"),
                ),
            ),
        )
    )


def test_settings_orchestrator_forwards_provider_payload(monkeypatch):
    calls: dict[str, object] = {}

    def _fake_open(parent, **kwargs):
        calls["parent"] = parent
        calls.update(kwargs)
        return {"theme": "mono_day"}

    commit_calls = []
    live_calls = []

    monkeypatch.setattr(orchestrator_module, "open_tabbed_settings_dialog", _fake_open)

    orchestrator = SettingsDialogOrchestrator(
        title="Einstellungen",
        theme_key_provider=lambda: "mono_day",
        spec_provider=_sample_spec,
        values_provider=lambda: {"theme": "mono_day"},
        commit_handler=lambda payload: commit_calls.append(payload),
        live_apply_handler=lambda payload: live_calls.append(payload),
    )

    result = orchestrator.open(parent="ROOT", initial_section="general")

    assert result == {"theme": "mono_day"}
    assert calls["parent"] == "ROOT"
    assert calls["title"] == "Einstellungen"
    assert calls["theme_key"] == "mono_day"
    assert calls["initial_values"] == {"theme": "mono_day"}
    assert calls["initial_section"] == "general"
    assert calls["on_commit"] is not None
    assert calls["on_live_apply"] is not None
    assert commit_calls == []
    assert live_calls == []


def test_settings_orchestrator_without_live_handler():
    orchestrator = SettingsDialogOrchestrator(
        title="Einstellungen",
        theme_key_provider=lambda: "mono_day",
        spec_provider=_sample_spec,
        values_provider=lambda: {"theme": "mono_day"},
        commit_handler=lambda payload: None,
    )

    assert orchestrator.live_apply_handler is None
