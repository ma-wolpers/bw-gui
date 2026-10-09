"""Semantic key events: the only place that interprets Tk's ``keysym``/``char``.

:func:`classify_key` turns the raw Tk fields of one key press into two values on two
deliberately separate levels (``docs/WIDGET_EVENTS_CONTRACT.md``):

==================  ==========================================  =========================
                    ``KeyIdentity.character`` (internal)        ``KeyEvent.text`` (public)
==================  ==========================================  =========================
meaning             logical, layout-based key/character         character actually typed
used for            shortcut matching, menu mnemonics           type-ahead, filtering
Ctrl+Z / Alt+Z      ``"z"`` (present)                           ``None``
AltGr char (``@``)  ``"@"``                                     ``"@"``
whitespace keys     never (named ``Key``)                       ``" "`` for Space
==================  ==========================================  =========================

``text`` rule (decision 22):

1. No character, or a Unicode control/format character (``Cc``/``Cf``) -> ``None``.
2. A printable character and **no shortcut modifier** in the decoded state -> the
   character. On win32, AltGr characters arrive with Ctrl/Alt already stripped by Tk
   (measured, ``KEYBINDING_AUDIT.md``), so they fall under this rule; there is no
   ``state == 0`` heuristic.
3. A printable character **with** shortcut modifiers -> ``None``, except for
   combinations in the per-backend exception table below (only aqua Option, derived
   from macOS conventions and not verified live). In those cases the modifier is
   removed from both ``KeyEvent.modifiers`` and the identity.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from typing import Final

from .key_modifiers import (
    UNKNOWN_MODIFIERS,
    KeyModifiers,
    TkBackend,
    UnknownModifiers,
    modifiers_from_state,
    resolve_backend,
)
from .key_spec import UNKNOWN, Key, KeyIdentity, Mod

_NAMED_KEYSYMS: Final[dict[str, Key]] = {
    "Up": Key.UP, "KP_Up": Key.UP, "Down": Key.DOWN, "KP_Down": Key.DOWN,
    "Left": Key.LEFT, "KP_Left": Key.LEFT, "Right": Key.RIGHT, "KP_Right": Key.RIGHT,
    "Return": Key.ENTER, "KP_Enter": Key.ENTER, "Escape": Key.ESCAPE,
    "Tab": Key.TAB, "ISO_Left_Tab": Key.TAB, "BackSpace": Key.BACKSPACE,
    "Delete": Key.DELETE, "KP_Delete": Key.DELETE, "Insert": Key.INSERT, "KP_Insert": Key.INSERT,
    "Home": Key.HOME, "KP_Home": Key.HOME, "End": Key.END, "KP_End": Key.END,
    "Prior": Key.PAGE_UP, "KP_Prior": Key.PAGE_UP, "Next": Key.PAGE_DOWN, "KP_Next": Key.PAGE_DOWN,
    "space": Key.SPACE, "KP_Space": Key.SPACE,
    **{f"F{i}": Key(f"F{i}") for i in range(1, 13)},
}

# Tk keysym names of printable characters that are not the character itself.
_KEYSYM_CHARS: Final[dict[str, str]] = {
    "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$", "percent": "%",
    "ampersand": "&", "apostrophe": "'", "quoteright": "'", "parenleft": "(", "parenright": ")",
    "asterisk": "*", "plus": "+", "comma": ",", "minus": "-", "period": ".", "slash": "/",
    "colon": ":", "semicolon": ";", "less": "<", "equal": "=", "greater": ">", "question": "?",
    "at": "@", "bracketleft": "[", "backslash": "\\", "bracketright": "]", "asciicircum": "^",
    "underscore": "_", "grave": "`", "quoteleft": "`", "braceleft": "{", "bar": "|", "braceright": "}",
    "asciitilde": "~", "EuroSign": "€", "section": "§", "degree": "°", "twosuperior": "²",
    "threesuperior": "³", "mu": "µ", "acute": "´", "ssharp": "ß", "adiaeresis": "ä",
    "odiaeresis": "ö", "udiaeresis": "ü", "Adiaeresis": "Ä", "Odiaeresis": "Ö", "Udiaeresis": "Ü",
    "KP_Add": "+", "KP_Subtract": "-", "KP_Multiply": "*", "KP_Divide": "/",
    **{f"KP_{d}": str(d) for d in range(10)},
}

# Combinations whose printable character counts as text although a shortcut modifier
# bit is set: backend -> modifiers that are text modifiers in that case.
_TEXT_MODIFIER_EXCEPTIONS: Final[dict[TkBackend, frozenset[str]]] = {
    TkBackend.WIN32: frozenset(),
    TkBackend.X11: frozenset(),
    TkBackend.AQUA: frozenset({"alt"}),  # Option composes characters (unverified live)
}


@dataclass(frozen=True)
class RawKey:
    """The raw Tk fields of one key press (built only inside bw-gui)."""

    keysym: str
    char: str
    state: object


@dataclass(frozen=True)
class KeyEvent:
    """Public semantic key event (no ``keysym``/``char``/``state``)."""

    key: Key
    text: str | None
    modifiers: KeyModifiers | UnknownModifiers
    widget: object = None


def _is_text_char(char: str) -> bool:
    """True for one character that is not a control/format character."""
    return len(char) == 1 and unicodedata.category(char) not in ("Cc", "Cf")


def _logical_character(keysym: str, char: str) -> str | None:
    """Return the layout-based logical character (Shift folded in) or ``None``."""
    if len(char) == 1 and char.isprintable() and not char.isspace():
        return char
    if len(keysym) == 1 and keysym.isprintable() and not keysym.isspace():
        return keysym
    return _KEYSYM_CHARS.get(keysym)


def _mods_of(modifiers: KeyModifiers) -> frozenset[Mod]:
    result = set()
    if modifiers.control:
        result.add(Mod.CTRL)
    if modifiers.alt:
        result.add(Mod.ALT)
    if modifiers.shift:
        result.add(Mod.SHIFT)
    if modifiers.command:
        result.add(Mod.CMD)
    return frozenset(result)


def classify_key(raw: RawKey, backend: TkBackend | None = None, widget: object = None) -> tuple[KeyEvent, KeyIdentity]:
    """Classify one key press into its public :class:`KeyEvent` and internal :class:`KeyIdentity`."""
    resolved = resolve_backend(backend)
    state = raw.state
    if isinstance(state, bool) or not isinstance(state, int) or state < 0:
        modifiers: KeyModifiers | UnknownModifiers = UNKNOWN_MODIFIERS
    else:
        modifiers = modifiers_from_state(state, resolved)

    named = _NAMED_KEYSYMS.get(raw.keysym)
    if raw.keysym == "ISO_Left_Tab" and isinstance(modifiers, KeyModifiers):
        modifiers = replace(modifiers, shift=True)
    character = None if named is not None else _logical_character(raw.keysym, raw.char)
    key = named if named is not None else (Key.CHARACTER if character is not None else Key.OTHER)

    text: str | None = None
    if isinstance(modifiers, KeyModifiers) and _is_text_char(raw.char) and raw.char not in "\r\n\t\x1b":
        exceptions = _TEXT_MODIFIER_EXCEPTIONS[resolved]
        held = {name for name in ("control", "alt", "command") if getattr(modifiers, name)}
        if not held:
            text = raw.char
        elif held <= exceptions and key is Key.CHARACTER:
            text = raw.char
            modifiers = replace(modifiers, **{name: False for name in held})

    identity_mods = UNKNOWN if not isinstance(modifiers, KeyModifiers) else _mods_of(modifiers)
    event = KeyEvent(key=key, text=text, modifiers=modifiers, widget=widget)
    return event, KeyIdentity(key=key, character=character, modifiers=identity_mods)
