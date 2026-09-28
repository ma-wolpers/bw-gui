"""Settings dialog: Switch/Checkbox by live_apply, and Cancel semantics (TOGGLE_CONTRACT)."""

from __future__ import annotations

import pytest

from bw_gui.dialogs import SettingsDialogSpec, SettingsFieldSpec, SettingsSectionSpec
from bw_gui.dialogs._settings_dialog import TabbedSettingsDialog
from bw_gui.runtime import ui
from bw_gui.theming._theme_manager import DEFAULT_THEME
from bw_gui.widgets import Checkbox, Switch


def _spec() -> SettingsDialogSpec:
    return SettingsDialogSpec(sections=(SettingsSectionSpec(key="general", label="General", fields=(
        SettingsFieldSpec(key="grid", label="Show grid", field_type="bool", default=False, live_apply=True),
        SettingsFieldSpec(key="backup", label="Backup on save", field_type="bool", default=False),
        SettingsFieldSpec(key="mode", label="Mode", field_type="enum", enum_values=("auto", "fixed"), default="auto"),
        SettingsFieldSpec(key="detail", label="Detailed", field_type="bool", default=False, live_apply=True,
                          visible_when=("grid", True)),
    )),))


@pytest.fixture
def open_dialog(_shared_tk_root, monkeypatch):
    """Build the (normally blocking) dialog without waiting and return it."""
    monkeypatch.setattr(_shared_tk_root, "wait_window", lambda *_: None)
    monkeypatch.setattr(ui.Toplevel, "grab_set", lambda self: None)
    dialogs: list[TabbedSettingsDialog] = []

    def factory(**callbacks) -> TabbedSettingsDialog:
        dialog = TabbedSettingsDialog(_shared_tk_root, title="t", theme_key=DEFAULT_THEME, spec=_spec(),
                                      initial_values={}, **callbacks)
        dialogs.append(dialog)
        return dialog

    yield factory
    for dialog in dialogs:
        if dialog.window.winfo_exists():
            dialog.window.destroy()


def _toggles(dialog) -> dict[str, object]:
    return {child.cget("text"): child for child in dialog.content_frame.winfo_children()
            if isinstance(child, (Checkbox, Switch))}


def test_live_bool_is_switch_and_staged_bool_is_checkbox(open_dialog) -> None:
    toggles = _toggles(open_dialog(on_live_apply=lambda _v: None, on_commit=lambda _v: None))
    assert type(toggles["Show grid"]) is Switch
    assert type(toggles["Backup on save"]) is Checkbox


def test_live_field_without_live_callback_is_checkbox(open_dialog) -> None:
    toggles = _toggles(open_dialog(on_commit=lambda _v: None))
    assert type(toggles["Show grid"]) is Checkbox


def test_live_change_applies_immediately_but_programmatic_set_does_not(open_dialog) -> None:
    live: list[dict] = []
    dialog = open_dialog(on_live_apply=live.append, on_commit=lambda _v: None)
    _toggles(dialog)["Show grid"].invoke()
    assert [values["grid"] for values in live] == [True]
    dialog._field_vars["grid"].set(False)
    assert len(live) == 1


def test_cancel_keeps_live_values_and_discards_staged_ones(open_dialog) -> None:
    live: list[dict] = []
    commits: list[dict] = []
    dialog = open_dialog(on_live_apply=live.append, on_commit=commits.append)
    _toggles(dialog)["Show grid"].invoke()        # live (rebuilds the section: visible_when)
    _toggles(dialog)["Backup on save"].invoke()   # staged
    dialog._on_cancel()
    assert dialog.result is None
    assert live[-1]["grid"] is True      # runtime state was not reset
    assert commits == [{"grid": True, "backup": False, "mode": "auto", "detail": False}]


def test_cancel_without_live_change_commits_nothing(open_dialog) -> None:
    commits: list[dict] = []
    dialog = open_dialog(on_live_apply=lambda _v: None, on_commit=commits.append)
    _toggles(dialog)["Backup on save"].invoke()
    dialog._on_cancel()
    assert commits == [] and dialog.result is None


def test_cancel_after_apply_uses_applied_values_as_baseline(open_dialog) -> None:
    commits: list[dict] = []
    dialog = open_dialog(on_live_apply=lambda _v: None, on_commit=commits.append)
    _toggles(dialog)["Backup on save"].invoke()
    dialog._on_apply()
    _toggles(dialog)["Show grid"].invoke()
    dialog._on_cancel()
    assert commits[-1] == {"grid": True, "backup": True, "mode": "auto", "detail": False}


def test_switch_controlling_visibility_survives_rerender(open_dialog, _shared_tk_root, monkeypatch) -> None:
    """The grid Switch rebuilds its own section mid-click (visible_when) without errors."""
    reported: list[BaseException] = []
    monkeypatch.setattr(_shared_tk_root, "report_callback_exception", lambda *exc: reported.append(exc[1]))
    live: list[dict] = []
    dialog = open_dialog(on_live_apply=live.append, on_commit=lambda _v: None)
    assert "Detailed" not in _toggles(dialog)
    _toggles(dialog)["Show grid"].invoke()
    assert reported == []
    assert [values["grid"] for values in live] == [True]
    toggles = _toggles(dialog)
    assert "Detailed" in toggles and toggles["Show grid"].instate(["selected"])
