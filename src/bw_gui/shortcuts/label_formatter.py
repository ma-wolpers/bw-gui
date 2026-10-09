"""Formatting helpers for compact button labels and rich hover explanations."""

from __future__ import annotations

from typing import Protocol

from bw_gui.contracts.key_spec import KeySpec


class ShortcutResolver(Protocol):
    def shortcut_for_intent(
        self, intent: str, *, mode: str | None = None, offline: bool = False, text_input_focused: bool = False
    ) -> KeySpec | None:
        ...


def humanize_shortcut(shortcut: KeySpec | str | None) -> str:
    """Return the readable label of a shortcut (``"Ctrl+S"``, ``"Ctrl+Shift+Z"``, ``"F5"``).

    Accepts a :class:`KeySpec` or its canonical notation (``KeySpec.parse``); Tk
    binding syntax is not accepted. The tolerate suffix is not shown.

    Raises:
        ValueError: For a string outside the ``KeySpec`` notation.
    """
    if shortcut is None or shortcut == "":
        return ""
    spec = shortcut if isinstance(shortcut, KeySpec) else KeySpec.parse(str(shortcut).strip())
    return str(KeySpec(spec.key, spec.modifiers, (), character=spec.character))


def format_shortcut_label(symbol_label: str, shortcut: KeySpec | str | None = None) -> str:
    """Return compact icon-centric button label with optional shortcut suffix."""
    label = (symbol_label or "").strip()
    hint = humanize_shortcut(shortcut)
    if not hint:
        return label
    return f"{label} [{hint}]"


def compose_hover_text(description: str, shortcut: KeySpec | str | None = None) -> str:
    """Compose hover text with explanation and optional shortcut line."""
    desc = (description or "").strip()
    hint = humanize_shortcut(shortcut)
    if not hint:
        return desc
    if not desc:
        return f"Shortcut: {hint}"
    return f"{desc}\nShortcut: {hint}"


def compose_action_label(
    label: str,
    *,
    icon: str | None = None,
    shortcut: KeySpec | str | None = None,
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
