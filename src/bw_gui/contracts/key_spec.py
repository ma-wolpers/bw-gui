"""Semantic shortcut description (``KeySpec``) and the single matching function.

``KeySpec`` is the only public way to describe a keyboard shortcut in bw-gui; Tk's
binding syntax never appears in consumer code (see ``docs/KEYBINDING_CONTRACT.md``).

Semantics (decisions 26/27/33/34):

* **Logical keys.** A character spec names the character the *current keyboard
  layout* produces, never a physical key position or keycode.
* **Exact modifiers.** ``modifiers`` is exact: ``KeySpec.char("z", {CTRL})``
  matches Ctrl+Z but not Ctrl+Shift+Z or Ctrl+Alt+Z. Additional held modifiers are
  allowed only via the explicit ``tolerate`` set.
* **Shift in characters.** For character keys Shift is part of the character
  (``"Z"`` instead of Shift + ``"z"``); ``Mod.SHIFT`` is invalid there. Tolerating
  Shift on a character shortcut means binding a second spec with the shifted
  character (several specs per binding are allowed).
* **Whitespace keys are named keys only** (``Key.SPACE``, ``Key.TAB``, ``Key.ENTER``).
* **One canonical form.** :meth:`KeySpec.parse` and direct construction yield the
  same value; ``KeySpec.parse(str(spec)) == spec``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Iterable

from .key_modifiers import TkBackend, resolve_backend


class Mod(str, Enum):
    """Semantic shortcut modifiers (``ALT`` also means the macOS Option key)."""

    CTRL = "Ctrl"
    ALT = "Alt"
    SHIFT = "Shift"
    CMD = "Cmd"


MOD_ORDER: Final[tuple[Mod, ...]] = (Mod.CTRL, Mod.ALT, Mod.SHIFT, Mod.CMD)


class Key(str, Enum):
    """Closed set of semantic keys (``CHARACTER`` = a printable character key)."""

    UP = "Up"
    DOWN = "Down"
    LEFT = "Left"
    RIGHT = "Right"
    ENTER = "Enter"
    ESCAPE = "Escape"
    TAB = "Tab"
    BACKSPACE = "Backspace"
    DELETE = "Delete"
    INSERT = "Insert"
    HOME = "Home"
    END = "End"
    PAGE_UP = "PageUp"
    PAGE_DOWN = "PageDown"
    SPACE = "Space"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"
    CHARACTER = "Character"
    OTHER = "Other"


NAMED_KEYS: Final[dict[str, Key]] = {k.value.lower(): k for k in Key if k not in (Key.CHARACTER, Key.OTHER)}

# Modifiers that have no defined shortcut meaning on a backend (decision table of
# the former sequence contract, unchanged): Cmd exists only on aqua; Alt is the
# Option key on aqua.
_SUPPORTED_MODS: Final[dict[TkBackend, frozenset[Mod]]] = {
    TkBackend.WIN32: frozenset({Mod.CTRL, Mod.ALT, Mod.SHIFT}),
    TkBackend.AQUA: frozenset({Mod.CTRL, Mod.ALT, Mod.SHIFT, Mod.CMD}),
    TkBackend.X11: frozenset({Mod.CTRL, Mod.ALT, Mod.SHIFT}),
}


def is_cased_letter(char: str) -> bool:
    """True for a character with an unambiguous, lossless single-character upper/lower form.

    Excludes uncased characters (CJK), multi-character mappings (``ß`` -> ``SS``) and
    non-roundtripping ones (micro sign ``µ`` -> Greek ``Μ`` -> Greek ``μ``).
    """
    if len(char) != 1:
        return False
    upper, lower = char.upper(), char.lower()
    return (
        len(upper) == 1
        and len(lower) == 1
        and upper != lower
        and upper.lower() == lower
        and lower.upper() == upper
    )


def _is_printable_char(char: str) -> bool:
    """True for exactly one printable, non-whitespace character."""
    return isinstance(char, str) and len(char) == 1 and char.isprintable() and not char.isspace()


@dataclass(frozen=True)
class KeySpec:
    """One shortcut: a key or character, an exact modifier set and tolerated extras.

    Construct named keys as ``KeySpec(Key.ESCAPE)`` / ``KeySpec(Key.TAB, {Mod.SHIFT})``
    and characters via :meth:`char`. Invalid combinations raise ``ValueError``.
    """

    key: Key
    modifiers: frozenset[Mod] = frozenset()
    tolerate: frozenset[Mod] = frozenset()
    character: str | None = None

    def __init__(
        self,
        key: Key,
        modifiers: Iterable[Mod] = (),
        tolerate: Iterable[Mod] = (),
        character: str | None = None,
    ) -> None:
        mods = frozenset(Mod(m) for m in modifiers)
        tol = frozenset(Mod(m) for m in tolerate)
        object.__setattr__(self, "key", Key(key))
        object.__setattr__(self, "modifiers", mods)
        object.__setattr__(self, "tolerate", tol)
        object.__setattr__(self, "character", character)
        self._validate()

    def _validate(self) -> None:
        if self.key is Key.OTHER:
            raise ValueError("Key.OTHER cannot be bound")
        if self.modifiers & self.tolerate:
            raise ValueError(f"Modifiers {sorted(m.value for m in self.modifiers & self.tolerate)} both required and tolerated")
        if self.key is Key.CHARACTER:
            if not _is_printable_char(self.character or ""):
                raise ValueError(f"KeySpec.char needs exactly one printable non-whitespace character, got {self.character!r}")
            if Mod.SHIFT in self.modifiers or Mod.SHIFT in self.tolerate:
                raise ValueError("Shift is part of the character for character keys; bind the shifted character instead")
        elif self.character is not None:
            raise ValueError("Only Key.CHARACTER specs carry a character")

    @classmethod
    def char(cls, character: str, modifiers: Iterable[Mod] = (), tolerate: Iterable[Mod] = ()) -> "KeySpec":
        """Spec for the logical character *character* (as produced by the layout, Shift included)."""
        return cls(Key.CHARACTER, modifiers, tolerate, character=character)

    def check_backend(self, backend: TkBackend | None = None) -> None:
        """Raise ``ValueError`` if a modifier has no shortcut meaning on *backend* (e.g. Cmd on win32)."""
        resolved = resolve_backend(backend)
        unsupported = (self.modifiers | self.tolerate) - _SUPPORTED_MODS[resolved]
        if unsupported:
            names = ", ".join(sorted(m.value for m in unsupported))
            raise ValueError(f"Modifier(s) {names} have no shortcut meaning on the {resolved.value} backend")

    # -- notation ---------------------------------------------------------------------

    def __str__(self) -> str:
        """Canonical notation, e.g. ``"Ctrl+Shift+Z"``, ``"Ctrl++"``, ``"Escape (tolerate: Shift)"``."""
        mods = [m for m in MOD_ORDER if m in self.modifiers]
        if self.key is Key.CHARACTER:
            char = self.character or ""
            if is_cased_letter(char):
                if char == char.upper():
                    mods = [m for m in MOD_ORDER if m in self.modifiers or m is Mod.SHIFT]
                token = char.upper()
            else:
                token = char
        else:
            token = self.key.value
        text = "".join(f"{m.value}+" for m in mods) + token
        if self.tolerate:
            text += " (tolerate: " + ", ".join(m.value for m in MOD_ORDER if m in self.tolerate) + ")"
        return text

    @classmethod
    def parse(cls, text: str) -> "KeySpec":
        """Parse the canonical notation (see module docstring and the contract grammar).

        Grammar: ``mods key [" (tolerate: " Mod (", " Mod)* ")"]`` where ``mods`` is
        ``(Ctrl|Alt|Shift|Cmd "+")*`` peeled from the left (case-insensitive) and the
        key token is everything up to the first space: a name (``Space``, ``Escape``,
        ``F5`` ...), one letter (case-insensitive; ``Shift`` is folded into it), or one
        other printable character taken literally (``+``, ``(``, ``€``).

        Raises:
            ValueError: For any text outside the grammar.
        """
        if not isinstance(text, str) or not text:
            raise ValueError(f"Empty key notation: {text!r}")
        rest = text
        mods: list[Mod] = []
        lookup = {m.value.lower(): m for m in Mod}
        while True:
            head, sep, tail = rest.partition("+")
            if sep and tail and head.lower() in lookup:
                mod = lookup[head.lower()]
                if mod in mods:
                    raise ValueError(f"Duplicate modifier {mod.value} in {text!r}")
                mods.append(mod)
                rest = tail
                continue
            break
        token, space, suffix = rest.partition(" ")
        tolerate = cls._parse_tolerate(suffix, text) if space else []
        if not token:
            raise ValueError(f"Missing key in {text!r}")
        named = NAMED_KEYS.get(token.lower())
        if named is not None and len(token) > 1:
            return cls(named, mods, tolerate)
        if len(token) != 1:
            raise ValueError(f"Unknown key name {token!r} in {text!r}")
        if is_cased_letter(token):
            char = token.upper() if Mod.SHIFT in mods else token.lower()
            return cls.char(char, [m for m in mods if m is not Mod.SHIFT], tolerate)
        if Mod.SHIFT in mods:
            raise ValueError(f"Shift is not allowed with the character {token!r}; write the produced character")
        return cls.char(token, mods, tolerate)

    @staticmethod
    def _parse_tolerate(suffix: str, text: str) -> list[Mod]:
        """Parse ``(tolerate: A, B)`` (whitespace around ``:``/``,`` allowed, case-insensitive)."""
        body = suffix.strip()
        if not (body.startswith("(") and body.endswith(")")):
            raise ValueError(f"Malformed tolerate suffix in {text!r}")
        inner = body[1:-1]
        label, colon, names = inner.partition(":")
        if not colon or label.strip().lower() != "tolerate":
            raise ValueError(f"Malformed tolerate suffix in {text!r}")
        lookup = {m.value.lower(): m for m in Mod}
        result: list[Mod] = []
        for raw in names.split(","):
            name = raw.strip().lower()
            if name not in lookup:
                raise ValueError(f"Unknown tolerated modifier {raw.strip()!r} in {text!r}")
            if lookup[name] in result:
                raise ValueError(f"Duplicate tolerated modifier in {text!r}")
            result.append(lookup[name])
        if not result:
            raise ValueError(f"Empty tolerate list in {text!r}")
        return result


class _Unknown:
    """Sentinel: the modifier state of a key event could not be decoded (fail-closed)."""

    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN: Final = _Unknown()


@dataclass(frozen=True)
class KeyIdentity:
    """Internal, logical identity of one key event used for matching (not public).

    ``character`` is the layout-dependent logical character (Shift folded in) and is
    present even when no text is produced (Ctrl+Z, Alt+Z). Whitespace keys are always
    named keys. ``modifiers`` excludes lock keys and AltGr/Option text modifiers.
    """

    key: Key
    character: str | None
    modifiers: frozenset[Mod] | _Unknown


def matches(spec: KeySpec, identity: KeyIdentity) -> bool:
    """The single matching function (runtime and conflict analysis use only this).

    A named key matches when the key is equal and the held modifiers ``M`` satisfy
    ``spec.modifiers ⊆ M ⊆ spec.modifiers ∪ spec.tolerate``. A character matches when
    the logical character is equal and the same holds for the shortcut modifiers
    (Shift is part of the character). Unknown modifier state never matches.
    """
    if identity.modifiers is UNKNOWN:
        return False
    held = frozenset(identity.modifiers)
    if spec.key is Key.CHARACTER:
        if identity.key is not Key.CHARACTER or identity.character != spec.character:
            return False
        held = held - {Mod.SHIFT}
    elif identity.key is not spec.key:
        return False
    return spec.modifiers <= held <= (spec.modifiers | spec.tolerate)


def _all_modifier_sets() -> list[frozenset[Mod]]:
    """Every subset of the four modifiers (16 sets)."""
    result: list[frozenset[Mod]] = []
    for mask in range(16):
        result.append(frozenset(m for i, m in enumerate(MOD_ORDER) if mask & (1 << i)))
    return result


_MODIFIER_SETS: Final = _all_modifier_sets()


def overlaps(first: KeySpec, second: KeySpec) -> bool:
    """True if some key event matches both specs (defined via :func:`matches`, exhaustive)."""
    if first.key is not second.key or first.character != second.character:
        return False
    for held in _MODIFIER_SETS:
        identity = KeyIdentity(first.key, first.character, held)
        if matches(first, identity) and matches(second, identity):
            return True
    return False
