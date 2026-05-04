"""Formatting helpers for compact button labels and rich hover explanations."""

from __future__ import annotations


def format_shortcut_label(symbol_label: str, shortcut: str | None = None) -> str:
    """Return compact icon-centric button label with optional shortcut suffix."""
    label = (symbol_label or "").strip()
    hint = (shortcut or "").strip()
    if not hint:
        return label
    return f"{label} [{hint}]"


def compose_hover_text(description: str, shortcut: str | None = None) -> str:
    """Compose hover text with explanation and optional shortcut line."""
    desc = (description or "").strip()
    hint = (shortcut or "").strip()
    if not hint:
        return desc
    if not desc:
        return f"Shortcut: {hint}"
    return f"{desc}\nShortcut: {hint}"
