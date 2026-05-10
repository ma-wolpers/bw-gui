"""Shared dialog services."""

from .service import FileDialogService, MessageDialogService, TextPromptDialogService
from .scrollable_popup import ScrollablePopupWindow
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
	"ScrollablePopupWindow",
	"SettingsDialogSpec",
	"SettingsFieldSpec",
	"SettingsSectionSpec",
	"TabbedSettingsDialog",
	"coerce_settings_payload",
	"open_tabbed_settings_dialog",
]
