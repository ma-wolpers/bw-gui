"""Formatting helpers for compact button labels and rich hover explanations."""

from __future__ import annotations

from typing import Protocol


class ShortcutResolver(Protocol):
    def shortcut_for_intent(self, intent: str, *, mode: str | None = None, offline: bool = False, text_input_focused: bool = False) -> str | None:
        ...


def humanize_shortcut_sequence(sequence: str | None) -> str:
    """Convert Tk-like sequences into a readable shortcut label."""
    text = (sequence or "").strip()
    if not text:
        return ""

    if text.startswith("<") and text.endswith(">"):
        parts = [part for part in text[1:-1].split("-") if part]
    else:
        parts = [part for part in text.replace("+", "-").split("-") if part]

    if not parts:
        return text

    normalized: list[str] = []
    for index, part in enumerate(parts):
        lower = part.lower()
        if lower in {"control", "ctrl"}:
            normalized.append("Ctrl")
            continue
        if lower in {"shift"}:
            normalized.append("Shift")
            continue
        if lower in {"alt", "option"}:
            normalized.append("Alt")
            continue
        if lower in {"command", "cmd"}:
            normalized.append("Cmd")
            continue
        if lower == "comma":
            normalized.append(",")
            continue
        if lower == "period":
            normalized.append(".")
            continue
        if index == len(parts) - 1 and len(part) == 1:
            normalized.append(part.upper())
            continue
        normalized.append(part.capitalize())

    return "+".join(normalized)


def format_shortcut_label(symbol_label: str, shortcut: str | None = None) -> str:
    """Return compact icon-centric button label with optional shortcut suffix."""
    label = (symbol_label or "").strip()
    hint = humanize_shortcut_sequence(shortcut)
    if not hint:
        return label
    return f"{label} [{hint}]"


def compose_hover_text(description: str, shortcut: str | None = None) -> str:
    """Compose hover text with explanation and optional shortcut line."""
    desc = (description or "").strip()
    hint = humanize_shortcut_sequence(shortcut)
    if not hint:
        return desc
    if not desc:
        return f"Shortcut: {hint}"
    return f"{desc}\nShortcut: {hint}"


def compose_action_label(
    label: str,
    *,
    icon: str | None = None,
    shortcut: str | None = None,
    include_shortcut: bool = True,
) -> str:
    """Compose compact action label with optional icon and shortcut badge."""
    base_label = (label or "").strip()
    icon_text = (icon or "").strip()
    if icon_text and base_label:
        merged = f"{icon_text} {base_label}"
    else:
        merged = icon_text or base_label

    if not include_shortcut:
        return merged
    return format_shortcut_label(merged, shortcut)


def compose_hover_text_for_intent(
    description: str,
    *,
    intent: str,
    shortcuts: ShortcutResolver,
    mode: str | None = None,
    offline: bool = False,
    text_input_focused: bool = False,
) -> str:
    """Compose hover text by resolving the active shortcut sequence for one intent."""
    shortcut = shortcuts.shortcut_for_intent(
        intent,
        mode=mode,
        offline=offline,
        text_input_focused=text_input_focused,
    )
    return compose_hover_text(description, shortcut)
