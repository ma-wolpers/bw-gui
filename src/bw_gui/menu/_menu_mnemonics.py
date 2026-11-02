"""Mnemonic letters of ``CustomMenuBar`` items and sections (private, no Tk).

Pure helpers behind ``MenuItem.mnemonic`` (contract in its docstring) and the
strip-level ``MenuDefinition.alt``: one normalisation, one subtree search with the
uniqueness check, and the right-aligned label layout. The Tk side (rows, key
bindings) lives in ``_menu_popups``; keeping this part free of Tk makes every rule
testable without a display.
"""

from __future__ import annotations

from typing import Callable, Iterable, Iterator

from .menu_types import MenuDefinition, MenuItem

MNEMONIC_ITEM_TYPES = frozenset({"command", "radio", "checkbox", "switch"})
"""Item types that may carry a mnemonic: the ones a click runs directly. A submenu
cannot -- its letter would have to open a popup of a level that is not shown yet."""


def normalize_mnemonic(letter: str) -> str:
    """Comparison form of a mnemonic letter (case-insensitive, ``casefold``).

    The single normalisation for both ``MenuItem.mnemonic`` and
    ``MenuDefinition.alt``, so the strip and the popups can never disagree on
    whether two letters are "the same".
    """
    return letter.casefold()


def iter_mnemonic_items(items: Iterable[MenuItem]) -> Iterator[MenuItem]:
    """Yield every item with a mnemonic in *items* and all nested submenus, depth-first.

    Raises:
        ValueError: An item's mnemonic is not exactly one character (or, like
            ``ß`` -> ``SS``, has no one-character upper-case form, which the
            popup binds as the Shift variant), or the item type cannot carry one
            (see ``MNEMONIC_ITEM_TYPES``).
    """
    for item in items:
        if item.type == "submenu":
            if item.mnemonic is not None:
                raise ValueError(f"Submenu {item.label!r} cannot carry a mnemonic")
            yield from iter_mnemonic_items(item.items)
            continue
        if item.mnemonic is None:
            continue
        if item.type not in MNEMONIC_ITEM_TYPES:
            raise ValueError(f"Menu item {item.label!r} of type {item.type!r} cannot carry a mnemonic")
        if len(item.mnemonic) != 1 or not item.mnemonic.strip() or len(item.mnemonic.upper()) != 1:
            raise ValueError(
                f"Mnemonic of {item.label!r} must be exactly one character with a one-character "
                f"upper-case form, got {item.mnemonic!r}"
            )
        yield item


def collect_mnemonics(items: Iterable[MenuItem]) -> dict[str, MenuItem]:
    """Map each normalised mnemonic in the subtree of *items* to its item.

    Raises:
        ValueError: Two items in the subtree share a letter (case-insensitive),
            or an item violates ``iter_mnemonic_items``' rules.
    """
    found: dict[str, MenuItem] = {}
    for item in iter_mnemonic_items(items):
        key = normalize_mnemonic(item.mnemonic or "")
        if key in found:
            raise ValueError(
                f"Mnemonic {item.mnemonic!r} is used by both {found[key].label!r} and {item.label!r}"
            )
        found[key] = item
    return found


def check_unique_section_mnemonics(definitions: Iterable[MenuDefinition]) -> None:
    """Raise ``ValueError`` if two strip sections share an ``alt`` letter (case-insensitive).

    Without this check the second section would silently be unreachable by
    keyboard: ``_on_alt_keypress`` opens the first match only.
    """
    seen: dict[str, str] = {}
    for definition in definitions:
        if not definition.alt:
            continue
        key = normalize_mnemonic(definition.alt)
        if key in seen:
            raise ValueError(f"Alt letter {definition.alt!r} is used by both {seen[key]!r} and {definition.label!r}")
        seen[key] = definition.label


def mnemonic_row_texts(
    rows: list[tuple[str, str | None, int]], measure: Callable[[str], int], gap: str = "      "
) -> list[str]:
    """Append each row's letter as a right-aligned column, padded with spaces.

    The letter sits in the same label as the text on purpose: a separate child
    widget would make Tk send ``<Leave>`` to the row as soon as the pointer
    crosses onto it (verified in a spike), breaking hover highlighting. Padding
    is computed from the real font (*measure*), so the letters line up to within
    half a space width.

    Args:
        rows: Per row ``(text, letter, extra_px)``: the text as rendered without a
            letter (prefix/suffix included), the letter (``None`` = no letter) and
            the pixel width the row shows left of the text (a toggle glyph image).
        measure: Pixel width of a string in the row font.
        gap: Minimum distance between the widest row and the letter column.

    Returns:
        The row texts in order; rows without a letter are returned unchanged.
    """
    if not any(letter for _text, letter, _extra in rows):
        return [text for text, _letter, _extra in rows]
    space = max(1, measure(" "))
    column = max(measure(text) + extra for text, _letter, extra in rows) + measure(gap)
    result = []
    for text, letter, extra in rows:
        if letter is None:
            result.append(text)
            continue
        spaces = max(1, round((column - measure(text) - extra) / space))
        result.append(f"{text}{' ' * spaces}{letter.upper()}")
    return result
