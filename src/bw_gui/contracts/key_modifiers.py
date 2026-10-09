"""Semantic keyboard-modifier contract: Tk backend normalisation and ``event.state`` decoding.

This module is the single place in the bw-gui ecosystem that interprets Tk's
``event.state`` bit field. Consuming apps must never test ``event.state & <mask>``
themselves; they ask this contract (or, more commonly, let
:class:`~bw_gui.runtime.WindowShortcutBinder` / :meth:`KeybindingRegistry.evaluate_runtime`
do the gating for them).

Why a contract at all -- the Windows NumLock trap
    Tk's modifier bits are *not* portable. On X11, ``0x0008`` (Mod1) is usually Alt,
    which is why a lot of Tk code in the wild tests ``state & 0x0008`` for "Alt is held".
    On Windows, however, Tk reports **NumLock** in ``0x0008`` and Alt in ``0x20000``.
    Code written with the X11 assumption therefore treats every keypress as
    "Alt held" as soon as NumLock is switched on -- which is exactly how single-letter
    shortcuts in Kartograph and Blattwerk silently stopped working.

Terminology
    * **OS platform** -- ``sys.platform`` (``"win32"``, ``"darwin"``, ``"linux"``, ...).
    * **Tk backend** -- the windowing system Tk actually talks to (``tk windowingsystem``:
      ``"win32"``, ``"aqua"``, ``"x11"``). The modifier *semantics* depend on the backend,
      not on the OS: Linux maps to the X11 backend, macOS to Aqua. ``sys.platform`` never
      returns ``"x11"``, so the OS value is always normalised through
      :func:`backend_for_platform` first.
    * **Shortcut modifier** -- a modifier that turns a key into a *different command*:
      Control, Alt/Option or Command. Shift is deliberately *not* a shortcut modifier,
      because it changes the produced character (``a`` -> ``A``, ``=`` -> ``+``) rather
      than the meaning of the shortcut.

This module has no Tk import; it only needs the integer ``state`` and the backend.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Final


class TkBackend(str, Enum):
    """Tk windowing-system backend whose modifier semantics apply."""

    WIN32 = "win32"
    AQUA = "aqua"
    X11 = "x11"


def backend_for_platform(platform: str | None = None) -> TkBackend:
    """Normalise an OS platform string (``sys.platform``) to the Tk backend semantics.

    Args:
        platform: OS platform string; defaults to ``sys.platform``.

    Returns:
        ``WIN32`` for Windows, ``AQUA`` for macOS, ``X11`` for Linux/BSD.

    Raises:
        ValueError: For platforms without a defined Tk-backend mapping in this contract.
    """
    value = sys.platform if platform is None else platform
    if value == "win32" or value == "cygwin":
        return TkBackend.WIN32
    if value == "darwin":
        return TkBackend.AQUA
    if value.startswith(("linux", "freebsd", "openbsd", "netbsd")):
        return TkBackend.X11
    raise ValueError(f"No Tk backend mapping defined for platform {value!r}")


def backend_for_windowing_system(windowing_system: str) -> TkBackend:
    """Map the result of Tk's ``tk windowingsystem`` command to a :class:`TkBackend`.

    This is the authoritative source at runtime (a Linux box could in theory run a
    non-X11 Tk); :func:`backend_for_platform` is only the fallback when no Tk
    interpreter is at hand.

    Raises:
        ValueError: For windowing systems this contract does not define.
    """
    try:
        return TkBackend(str(windowing_system).strip().lower())
    except ValueError:
        raise ValueError(f"Unsupported Tk windowing system {windowing_system!r}") from None


def resolve_backend(backend: TkBackend | None) -> TkBackend:
    """Return *backend*, or the backend derived from ``sys.platform`` if it is ``None``."""
    return backend if backend is not None else backend_for_platform()


@dataclass(frozen=True)
class KeyModifiers:
    """Semantic modifier state relevant for shortcut decisions.

    Deliberately *not* a mirror of every Tk state bit: lock keys (CapsLock, NumLock,
    ScrollLock) and mouse buttons are not represented, because they never change the
    meaning of a keyboard shortcut.

    ``alt`` also represents the macOS Option key (same role in shortcuts).
    ``command`` is only ever set on the Aqua backend. On Windows Tk's ``Command``
    token is an alias of ``Mod1`` = the NumLock bit, so it has no shortcut meaning
    there (``Mod.CMD`` is rejected on win32, see :mod:`bw_gui.contracts.key_spec`).
    """

    shift: bool = False
    control: bool = False
    alt: bool = False
    command: bool = False

    @property
    def has_shortcut_modifier(self) -> bool:
        """True if Control, Alt/Option or Command is held (Shift alone does not count)."""
        return self.control or self.alt or self.command

    def shortcut_modifiers_not_in(self, declared: "KeyModifiers") -> "KeyModifiers":
        """Return the shortcut modifiers held here but not present in *declared*.

        Shift is never part of the result (it is not a shortcut modifier).
        """
        return KeyModifiers(
            control=self.control and not declared.control,
            alt=self.alt and not declared.alt,
            command=self.command and not declared.command,
        )


NO_MODIFIERS: Final = KeyModifiers()


class UnknownModifiers:
    """Sentinel type: an event exists, but its modifier state could not be decoded.

    Distinct from ``None`` on :class:`KeybindingRuntimeContext.modifiers`, which means
    "this runtime path supplies no modifier information at all" (legacy contexts).
    An unknown state must never be treated as "no modifiers held"; the registry
    gates it fail-closed.
    """

    _instance: "UnknownModifiers | None" = None

    def __new__(cls) -> "UnknownModifiers":
        """Return the single shared instance, so identity checks (``is``) are reliable."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        """Readable name in logs and test output."""
        return "UNKNOWN_MODIFIERS"

    def __bool__(self) -> bool:
        """Refuse truthiness: ``if modifiers:`` would silently mean "no modifiers"."""
        raise TypeError("UNKNOWN_MODIFIERS has no truth value; compare with 'is UNKNOWN_MODIFIERS'")


UNKNOWN_MODIFIERS: Final = UnknownModifiers()

_SHIFT_MASK: Final = 0x0001
_CONTROL_MASK: Final = 0x0004

# Per-backend masks for the non-universal modifiers. Verification status:
#   win32: verified live (Windows 11, Tk 8.6.15, real key strokes via keybd_event,
#          see tests/live/): plain=0x0, Shift=0x1, Ctrl=0x4, Alt=0x20000,
#          NumLock=0x0008 (added to every state while on). AltGr / Ctrl+Alt that
#          produce a character arrive with state=0x0 (Tk strips them), so AltGr
#          characters are never gated. Tk's *binding matcher* also treats 0x0010 as
#          Alt, but real keyboards never produced it in the measurement.
#   aqua:  Command=Mod1 (0x0008), Option=Mod2 (0x0010) -- derived from Tk's macOS
#          sources (tkMacOSXKeyEvent.c), not verified live.
#   x11:   Alt=Mod1 (0x0008) -- the usual xmodmap assignment, but X11 lets users
#          remap Mod1..Mod5; NumLock is usually Mod2 (0x0010) and thus ignored.
_ALT_MASK: Final[dict[TkBackend, int]] = {
    TkBackend.WIN32: 0x20000,
    TkBackend.AQUA: 0x0010,
    TkBackend.X11: 0x0008,
}
_COMMAND_MASK: Final[dict[TkBackend, int]] = {
    TkBackend.WIN32: 0,
    TkBackend.AQUA: 0x0008,
    TkBackend.X11: 0,
}


def modifiers_from_state(state: int, backend: TkBackend | None = None) -> KeyModifiers:
    """Decode a Tk ``event.state`` integer into semantic :class:`KeyModifiers`.

    Lock bits (CapsLock ``0x2``, NumLock, ScrollLock) and mouse-button bits are
    ignored by construction -- only the masks listed for the backend are read.

    Args:
        state: Tk ``event.state`` value.
        backend: Tk backend; defaults to the one derived from ``sys.platform``.
    """
    resolved = resolve_backend(backend)
    command_mask = _COMMAND_MASK[resolved]
    return KeyModifiers(
        shift=bool(state & _SHIFT_MASK),
        control=bool(state & _CONTROL_MASK),
        alt=bool(state & _ALT_MASK[resolved]),
        command=bool(command_mask and state & command_mask),
    )


def modifiers_from_event(event: object, backend: TkBackend | None = None) -> KeyModifiers | UnknownModifiers:
    """Decode the modifier state of a Tk event.

    Returns:
        :class:`KeyModifiers` if ``event.state`` is a non-negative ``int``;
        :data:`UNKNOWN_MODIFIERS` if the event has no state or a non-integer one
        (Tk uses strings such as ``"??"`` for some synthetic events). Never ``None``
        -- ``None`` is reserved for runtime contexts that carry no modifier
        information at all.
    """
    state = getattr(event, "state", None)
    if isinstance(state, bool) or not isinstance(state, int) or state < 0:
        return UNKNOWN_MODIFIERS
    return modifiers_from_state(state, backend)
