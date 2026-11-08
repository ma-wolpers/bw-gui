"""Helpers for rendering consistent shortcut labels and hints."""

from .label_formatter import (
	compose_action_label,
	compose_hover_text,
	compose_hover_text_for_intent,
	compose_menu_label,
	format_shortcut_label,
	humanize_shortcut,
)

__all__ = [
	"compose_action_label",
	"compose_hover_text",
	"compose_hover_text_for_intent",
	"compose_menu_label",
	"format_shortcut_label",
	"humanize_shortcut",
]
