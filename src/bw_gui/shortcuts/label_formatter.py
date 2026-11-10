"""Formatting helpers for compact button labels and rich hover explanations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from bw_gui.contracts.key_spec import KeySpec


class ShortcutResolver(Protocol):
    def shortcut_for_intent(
        self,
        intent: str,
        *,
        mode: str | None = None,
        offline: bool = False,
        text_input_focused: bool = False,
        metadata: dict[str, str] | None = None,
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


_GERMAN_DISPLAY: dict[str, str] = {
    "Ctrl": "Strg",
    "Delete": "Entf",
    "Escape": "Esc",
    "Space": "Leertaste",
    "Up": "Hoch",
    "Down": "Runter",
    "Left": "Links",
    "Right": "Rechts",
    "Home": "Pos1",
    "End": "Ende",
    "PageUp": "Bild auf",
    "PageDown": "Bild ab",
    "Insert": "Einfg",
    "Backspace": "Rücktaste",
}
"""Anzeige der kanonischen (englischen) Tastennamen auf Deutsch – einzige Übersetzungstabelle.

Code und Konfiguration schreiben Tasten in der englischen ``KeySpec``-Notation; jede
Anzeige (Tooltips, Menüs, Kürzelübersichten) läuft über `humanize_shortcut` und damit
über diese Tabelle. Nicht aufgeführte Teile (Buchstaben, ``Shift``, ``Alt``, ``F2`` …)
bleiben unverändert."""


def _display_parts(parts: list[str]) -> str:
    return "+".join(_GERMAN_DISPLAY.get(part, part) for part in parts)


def _normalize_display_text(text: str) -> str:
    """Normalize a free-form shortcut display text (``"strg+t"`` -> ``"Strg+T"``).

    Parts are split at ``+``/``-``; known modifier words get their canonical English
    spelling, a single-character last part is upper-cased, every other part is
    capitalized; then every part is shown in German (`_GERMAN_DISPLAY`). Localized
    words (``"Entf"``, ``"Leertaste"``) pass through.
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
    return _display_parts(normalized)


def humanize_shortcut(shortcut: KeySpec | str | None) -> str:
    """Return the readable (German) label of a shortcut (``"Strg+S"``, ``"Strg+Shift+Z"``, ``"F5"``).

    * :class:`KeySpec` -> its parts (`KeySpec.notation_parts`) shown in German.
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
        return _display_parts(list(shortcut.notation_parts()))
    text = str(shortcut).strip()
    if text.startswith("<") and text.endswith(">"):
        raise ValueError(f"Tk binding syntax is not a shortcut label: {text!r}")
    return _normalize_display_text(text)


ShortcutHint = KeySpec | str | Sequence[KeySpec | str | None] | None
"""One shortcut, or several alternatives (``(Ctrl+Delete, Ctrl+Backspace)``)."""


def _shortcut_hint(shortcut: ShortcutHint) -> str:
    """Readable text of one shortcut or of alternatives joined by ``" oder "``.

    The one rule for showing alternatives; empty entries (unbound intents) are left out.
    """
    if isinstance(shortcut, (list, tuple)):
        return " oder ".join(hint for hint in (humanize_shortcut(item) for item in shortcut) if hint)
    return humanize_shortcut(shortcut)


def format_shortcut_label(symbol_label: str, shortcut: ShortcutHint = None) -> str:
    """Return compact icon-centric button label with optional shortcut suffix."""
    label = (symbol_label or "").strip()
    hint = _shortcut_hint(shortcut)
    if not hint:
        return label
    return f"{label} [{hint}]"


def compose_menu_label(label: str, shortcut: ShortcutHint = None) -> str:
    """Menu item text with the shortcut in parentheses (``"Rückgängig (Strg+Z)"``).

    The one menu-label format; without a shortcut the label stays as is.
    """
    text = (label or "").strip()
    hint = _shortcut_hint(shortcut)
    return f"{text} ({hint})" if hint else text


def compose_hover_text(description: str, shortcut: ShortcutHint = None) -> str:
    """Compose hover text with explanation and optional shortcut line.

    *shortcut* may list alternatives; they appear as ``"Strg+Entf oder Strg+Rücktaste"``.
    """
    desc = (description or "").strip()
    hint = _shortcut_hint(shortcut)
    if not hint:
        return desc
    if not desc:
        return f"Shortcut: {hint}"
    return f"{desc}\nShortcut: {hint}"


def compose_action_label(
    label: str,
    *,
    icon: str | None = None,
    shortcut: ShortcutHint = None,
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
    intent: str | Sequence[str],
    shortcuts: ShortcutResolver,
    mode: str | None = None,
    offline: bool = False,
    text_input_focused: bool = False,
    metadata: dict[str, str] | None = None,
) -> str:
    """Compose hover text by resolving the active shortcut of one intent (and metadata).

    Several intents (e.g. two bindings of one button) show their keys as alternatives.
    """
    intents = (intent,) if isinstance(intent, str) else tuple(intent)
    keys = tuple(
        shortcuts.shortcut_for_intent(
            name,
            mode=mode,
            offline=offline,
            text_input_focused=text_input_focused,
            metadata=metadata,
        )
        for name in intents
    )
    return compose_hover_text(description, keys)
