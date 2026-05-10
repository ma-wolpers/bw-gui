"""Shared dialog services."""

from .service import FileDialogService, MessageDialogService, TextPromptDialogService
from .settings_dialog import (
	SettingsDialogSpec,
	SettingsFieldSpec,
	SettingsSectionSpec,
	TabbedSettingsDialog,
	coerce_settings_payload,
	open_tabbed_settings_dialog,
)

__all__ = [
	"FileDialogService",
	"MessageDialogService",
	"TextPromptDialogService",
	"SettingsDialogSpec",
	"SettingsFieldSpec",
	"SettingsSectionSpec",
	"TabbedSettingsDialog",
	"coerce_settings_payload",
	"open_tabbed_settings_dialog",
]
