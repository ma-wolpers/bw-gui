"""Keyboard-shortcut sequence contract: parsing, declared modifiers and binding signatures.

Consuming apps must not parse or compare Tk event sequences themselves. This module
defines exactly the subset of Tk's binding syntax that the bw-gui keybinding
contract supports for *keyboard shortcuts*, and rejects everything else loudly
(``ValueError`` at bind time) instead of silently misreading it.

Supported syntax
    * A single printable character: ``"a"``, ``"+"`` (Tk shorthand for a KeyPress).
    * ``<[Modifier-]*[KeyPress-|Key-]detail>`` with exactly one event, e.g.
      ``<a>``, ``<Key-a>``, ``<KeyPress-a>``, ``<Control-Shift-s>``, ``<Control-comma>``.
      Single-character details are normalised to their keysym name
      (``<Control-,>`` == ``<Control-comma>``).

Rejected (outside the keyboard-shortcut contract; would need their own contract)
    Virtual events (``<<Copy>>``), mouse events (``Button``, ``Motion`` ...),
    ``KeyRelease``, detail-less ``<KeyPress>``, repeat qualifiers (``Double``,
    ``Triple``, ``Quadruple``), ``Any``, ``Lock``, ``Extended``, button modifiers
    (``B1``/``Button1`` ...), multi-event sequences (``<Control-x><Control-s>``) and
    modifier aliases without a defined meaning on the target backend.

Modifier alias semantics per backend (see :func:`declared_modifiers`)
    =======  ============================  ==========  ==========
    token    win32                         aqua        x11
    =======  ============================  ==========  ==========
    Control  control                       control     control
    Shift    shift                         shift       shift
    Alt      alt                           (rejected)  alt
    Command  (rejected: = Mod1 = NumLock)  command     (rejected)
    Mod1/M1  (rejected: NumLock bit)       command     alt
    Option   (rejected)                    alt         (rejected)
    Mod2/M2  (rejected)                    alt         (rejected)
    Meta/M   (rejected)                    (rejected)  (rejected)
    =======  ============================  ==========  ==========

    "(rejected)" means: no shortcut meaning is defined for that backend in this
    contract, so binding such a sequence raises ``ValueError`` instead of guessing.

    win32 facts behind the table (measured with Tk 8.6.15, ``event_generate``):
    ``<Command-a>`` and ``<Mod1-a>`` match only ``state=0x0008`` -- the NumLock bit --
    so on Windows ``Command`` is *not* Control; a ``<Command-...>`` binding would fire
    only while NumLock is on. ``<Option-a>``/``<Mod2-a>`` match the same states as
    ``<Alt-a>``, but are not needed for shortcuts on Windows and therefore rejected
    rather than aliased.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from .key_modifiers import KeyModifiers, TkBackend, resolve_backend

_KEYPRESS_TYPES: Final = frozenset({"KeyPress", "Key"})

# Canonical spelling for every modifier token Tk accepts in a sequence.
_MODIFIER_ALIASES: Final[dict[str, str]] = {
    "Control": "Control",
    "Shift": "Shift",
    "Alt": "Alt",
    "Command": "Command",
    "Option": "Option",
    "Meta": "Meta",
    "M": "Meta",
    "Mod1": "Mod1",
    "M1": "Mod1",
    "Mod2": "Mod2",
    "M2": "Mod2",
    "Mod3": "Mod3",
    "M3": "Mod3",
    "Mod4": "Mod4",
    "M4": "Mod4",
    "Mod5": "Mod5",
    "M5": "Mod5",
}

# Tk tokens that exist but are outside the keyboard-shortcut contract.
_UNSUPPORTED_TOKENS: Final = frozenset(
    {
        "Lock", "Any", "Double", "Triple", "Quadruple", "Extended",
        "B1", "B2", "B3", "B4", "B5",
        "Button1", "Button2", "Button3", "Button4", "Button5",
        "KeyRelease", "ButtonPress", "ButtonRelease", "Button", "Motion",
        "Enter", "Leave", "FocusIn", "FocusOut", "MouseWheel", "Configure",
    }
)

# Semantic meaning of each canonical token, per backend. Missing -> ValueError.
_TOKEN_SEMANTICS: Final[dict[TkBackend, dict[str, str]]] = {
    TkBackend.WIN32: {"Control": "control", "Shift": "shift", "Alt": "alt"},
    TkBackend.AQUA: {
        "Control": "control", "Shift": "shift",
        "Command": "command", "Mod1": "command",
        "Option": "alt", "Mod2": "alt",
    },
    TkBackend.X11: {"Control": "control", "Shift": "shift", "Alt": "alt", "Mod1": "alt"},
}

# Single printable characters -> Tk keysym names (details and bare-character sequences).
_CHAR_KEYSYMS: Final[dict[str, str]] = {
    " ": "space", "!": "exclam", '"': "quotedbl", "#": "numbersign", "$": "dollar",
    "%": "percent", "&": "ampersand", "'": "apostrophe", "(": "parenleft",
    ")": "parenright", "*": "asterisk", "+": "plus", ",": "comma", "-": "minus",
    ".": "period", "/": "slash", ":": "colon", ";": "semicolon", "<": "less",
    "=": "equal", ">": "greater", "?": "question", "@": "at", "[": "bracketleft",
    "\\": "backslash", "]": "bracketright", "^": "asciicircum", "_": "underscore",
    "`": "grave", "{": "braceleft", "|": "bar", "}": "braceright", "~": "asciitilde",
}


@dataclass(frozen=True)
class ParsedSequence:
    """Backend-neutral parse result of one keyboard-shortcut sequence.

    Attributes:
        event_type: Always ``"KeyPress"`` (``Key`` and the bare form are normalised).
        modifier_tokens: Canonical modifier tokens as written, sorted, de-duplicated.
        keysym: Tk keysym name of the key (case-sensitive: ``"a"`` != ``"A"``).
    """

    event_type: str
    modifier_tokens: tuple[str, ...]
    keysym: str


@dataclass(frozen=True)
class BindingSignature:
    """Comparable semantic identity of a keyboard binding on one backend.

    Two sequences with the same signature match exactly the same key events,
    e.g. ``<Control-,>`` and ``<Control-comma>``, ``a`` and ``<KeyPress-a>``, or
    (on aqua) ``<Command-a>`` and ``<Mod1-a>``.
    """

    event_type: str
    keysym: str
    modifiers: KeyModifiers


def _keysym_for_detail(detail: str) -> str:
    """Return the Tk keysym name for a sequence detail.

    Single printable punctuation characters are mapped to their keysym names
    (``","`` -> ``"comma"``) so that ``<Control-,>`` and ``<Control-comma>`` compare
    equal; letters, digits and multi-character keysyms are returned unchanged.
    """
    if len(detail) == 1:
        return _CHAR_KEYSYMS.get(detail, detail)
    return detail


@lru_cache(maxsize=1024)
def parse_sequence(sequence: str) -> ParsedSequence:
    """Parse one keyboard-shortcut sequence into a :class:`ParsedSequence`.

    Raises:
        ValueError: For any syntax outside the keyboard-shortcut contract
            (see module docstring).
    """
    if not isinstance(sequence, str) or not sequence:
        raise ValueError(f"Empty or non-string key sequence: {sequence!r}")
    if not sequence.startswith("<"):
        if len(sequence) != 1:
            raise ValueError(f"Unsupported key sequence {sequence!r}: bare form must be one character")
        return ParsedSequence("KeyPress", (), _keysym_for_detail(sequence))
    if sequence.startswith("<<"):
        raise ValueError(f"Virtual events are outside the keyboard-shortcut contract: {sequence!r}")
    inner = sequence[1:-1]
    if not sequence.endswith(">") or "<" in inner or ">" in inner:
        raise ValueError(f"Unsupported key sequence {sequence!r}: exactly one <...> event expected")

    if inner.endswith("-") and len(inner) > 1 and inner[-2] == "-":
        # "<Control-->" style: the detail itself is "-".
        parts = inner[:-2].split("-") + ["-"]
    else:
        parts = inner.split("-")
    if not parts or any(part == "" for part in parts):
        raise ValueError(f"Malformed key sequence {sequence!r}")

    # Like Tk, the last field is always the key detail: "<M>" / "<Control-M>" mean the
    # keysym "M", not the Meta alias "M". Multi-letter modifier names and event types
    # are no keysyms (Tk: 'bad event type or keysym'), so they cannot be a detail.
    *prefix, detail = parts
    if (
        detail in _KEYPRESS_TYPES
        or detail in _UNSUPPORTED_TOKENS
        or (detail in _MODIFIER_ALIASES and len(detail) > 1)
    ):
        raise ValueError(f"Key sequence {sequence!r} has no key detail (keysym)")

    tokens: set[str] = set()
    event_type_seen = False
    for token in prefix:
        if token in _KEYPRESS_TYPES:
            if event_type_seen:
                raise ValueError(f"Duplicate event type in {sequence!r}")
            event_type_seen = True
            continue
        if event_type_seen:
            raise ValueError(f"Modifier after event type in {sequence!r}")
        if token in _UNSUPPORTED_TOKENS:
            raise ValueError(f"Token {token!r} in {sequence!r} is outside the keyboard-shortcut contract")
        canonical = _MODIFIER_ALIASES.get(token)
        if canonical is None:
            raise ValueError(f"Unknown modifier or event type {token!r} in {sequence!r}")
        tokens.add(canonical)
    return ParsedSequence("KeyPress", tuple(sorted(tokens)), _keysym_for_detail(detail))


def declared_modifiers(parsed: ParsedSequence, backend: TkBackend | None = None) -> KeyModifiers:
    """Return the semantic modifiers a parsed sequence declares on *backend*.

    Raises:
        ValueError: If a token has no defined meaning on the backend (see module table).
    """
    resolved = resolve_backend(backend)
    semantics = _TOKEN_SEMANTICS[resolved]
    flags = {"shift": False, "control": False, "alt": False, "command": False}
    for token in parsed.modifier_tokens:
        meaning = semantics.get(token)
        if meaning is None:
            raise ValueError(f"Modifier {token!r} has no defined meaning on the {resolved.value} Tk backend")
        flags[meaning] = True
    return KeyModifiers(**flags)


@lru_cache(maxsize=1024)
def _binding_signature_cached(sequence: str, backend: TkBackend) -> BindingSignature:
    """Cached core of :func:`binding_signature` (keyed on a resolved backend, not ``None``)."""
    parsed = parse_sequence(sequence)
    return BindingSignature(parsed.event_type, parsed.keysym, declared_modifiers(parsed, backend))


def binding_signature(sequence: str, backend: TkBackend | None = None) -> BindingSignature:
    """Return the normalised :class:`BindingSignature` of *sequence* on *backend*.

    Raises:
        ValueError: Propagated from :func:`parse_sequence` / :func:`declared_modifiers`.
    """
    return _binding_signature_cached(sequence, resolve_backend(backend))
