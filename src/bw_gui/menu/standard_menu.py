from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .custom_menu_bar import MenuDefinition, MenuItem


@dataclass(frozen=True)
class MenuSectionSpec:
    """Declarative section entry used by the standard menu builder."""

    key: str
    items_provider: Callable[[], Iterable[MenuItem]]
    label: str | None = None
    alt: str | None = None


_DEFAULT_SECTION_META: dict[str, tuple[str, str]] = {
    "file": ("Datei", "d"),
    "edit": ("Bearbeiten", "b"),
    "view": ("Ansicht", "a"),
    "help": ("Hilfe", "h"),
}


def section_spec(
    key: str,
    items_provider: Callable[[], Iterable[MenuItem]],
    *,
    label: str | None = None,
    alt: str | None = None,
) -> MenuSectionSpec:
    """Create one reusable section spec with optional label/alt overrides."""

    normalized_key = str(key or "").strip().lower()
    if not normalized_key:
        raise ValueError("Menu section key must not be empty")
    return MenuSectionSpec(
        key=normalized_key,
        items_provider=items_provider,
        label=label,
        alt=alt,
    )


def build_standard_menu_definitions(
    *,
    file_section: MenuSectionSpec | None = None,
    edit_section: MenuSectionSpec | None = None,
    view_section: MenuSectionSpec | None = None,
    help_section: MenuSectionSpec | None = None,
    extra_sections: Iterable[MenuSectionSpec] = (),
) -> tuple[MenuDefinition, ...]:
    """Build menu definitions with stable core ordering and extension support.

    Order is: file, edit, view, extra sections, help.
    Core sections are optional but should be used where possible for visual parity.
    """

    definitions: list[MenuDefinition] = []
    seen_keys: set[str] = set()

    def _append(section: MenuSectionSpec | None) -> None:
        if section is None:
            return
        key = section.key
        if key in seen_keys:
            raise ValueError(f"Duplicate menu section key: {key}")
        seen_keys.add(key)
        default_label, default_alt = _DEFAULT_SECTION_META.get(key, (key.title(), key[:1]))
        definitions.append(
            MenuDefinition(
                key=key,
                label=section.label or default_label,
                alt=section.alt or default_alt,
                items_provider=section.items_provider,
            )
        )

    _append(file_section)
    _append(edit_section)
    _append(view_section)
    for section in extra_sections:
        _append(section)
    _append(help_section)

    return tuple(definitions)
