"""Formatting helpers for compact button labels and rich hover explanations."""

from __future__ import annotations

from typing import Protocol

from bw_gui.contracts.key_spec import KeySpec


class ShortcutResolver(Protocol):
    def shortcut_for_intent(
        self, intent: str, *, mode: str | None = None, offline: bool = False, text_input_focused: bool = False
    ) -> KeySpec | None:
        ...


_DISPLAY_TOKENS = {
    "control": "Ctrl",
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "option": "Alt",
    "command": "Cmd",
    "cmd": "Cmd",
    "comma": ",",
    "period": ".",
}


def _normalize_display_text(text: str) -> str:
    """Normalize a free-form shortcut display text (``"strg+t"`` -> ``"Strg+T"``).

    Parts are split at ``+``/``-``; known modifier words get their canonical English
    spelling, a single-character last part is upper-cased, every other part is
    capitalized. Localized words (``"Entf"``, ``"Leertaste"``) pass through.
    """
    parts = [part for part in text.replace("+", "-").split("-") if part]
    if not parts:
        return text
    normalized: list[str] = []
    for index, part in enumerate(parts):
        token = _DISPLAY_TOKENS.get(part.lower())
        if token is not None:
            normalized.append(token)
        elif index == len(parts) - 1 and len(part) == 1:
            normalized.append(part.upper())
        else:
            normalized.append(part.capitalize())
    return "+".join(normalized)


def humanize_shortcut(shortcut: KeySpec | str | None) -> str:
    """Return the readable label of a shortcut (``"Ctrl+S"``, ``"Ctrl+Shift+Z"``, ``"F5"``).

    * :class:`KeySpec` -> its canonical notation without the tolerate suffix.
    * ``str`` -> a **display text** chosen by the consumer (also localized, e.g.
      ``"Entf"``, ``"Strg+T"``, ``"Leertaste"``), normalized by the display rules of
      :func:`_normalize_display_text`; it is not parsed as ``KeySpec`` syntax.

    Raises:
        ValueError: For Tk binding syntax (``"<Control-s>"``) -- consumers describe
            keys as ``KeySpec`` or display text, never as Tk sequences.
    """
    if shortcut is None or shortcut == "":
        return ""
    if isinstance(shortcut, KeySpec):
        return str(KeySpec(shortcut.key, shortcut.modifiers, (), character=shortcut.character))
    text = str(shortcut).strip()
    if text.startswith("<") and text.endswith(">"):
        raise ValueError(f"Tk binding syntax is not a shortcut label: {text!r}")
    return _normalize_display_text(text)


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
