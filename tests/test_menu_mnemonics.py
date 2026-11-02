"""``MenuItem.mnemonic``: pure rules (``_menu_mnemonics``) and the popup key path."""

from __future__ import annotations

import pytest

from bw_gui.menu import CustomMenuBar, MenuDefinition, MenuItem
from bw_gui.menu._menu_mnemonics import (
    check_unique_section_mnemonics,
    collect_mnemonics,
    mnemonic_row_texts,
)
from bw_gui.runtime import ui
from bw_gui.testing.keys import press_key
from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import DEFAULT_THEME

_ALT = 0x20000


def _cmd(label, letter=None, sink=None):
    """A command item that appends its label to *sink* when run."""
    return MenuItem(type="command", label=label, mnemonic=letter,
                    command=(lambda: sink.append(label)) if sink is not None else None)


# --- pure rules ------------------------------------------------------------------------

def test_collect_finds_letters_in_nested_submenus_case_insensitive() -> None:
    items = (_cmd("Top", "T"), MenuItem(type="submenu", label="Sub", items=(_cmd("Deep", "d"),)))
    found = collect_mnemonics(items)
    assert {key: item.label for key, item in found.items()} == {"t": "Top", "d": "Deep"}


def test_duplicate_letter_across_submenus_raises() -> None:
    items = (_cmd("A", "x"), MenuItem(type="submenu", label="Sub", items=(_cmd("B", "X"),)))
    with pytest.raises(ValueError, match="'A' and 'B'"):
        collect_mnemonics(items)


@pytest.mark.parametrize("item", [
    MenuItem(type="submenu", label="Sub", mnemonic="s"),
    MenuItem(type="separator", mnemonic="s"),
    MenuItem(type="disabled", label="Off", mnemonic="s"),
    MenuItem(type="command", label="Two", mnemonic="ab"),
    MenuItem(type="command", label="Eszett", mnemonic="ß"),
])
def test_invalid_mnemonic_raises(item) -> None:
    with pytest.raises(ValueError):
        collect_mnemonics((item,))


def test_duplicate_section_alt_letters_raise() -> None:
    definitions = (MenuDefinition("a", "Ansicht", "a", tuple), MenuDefinition("b", "Ablage", "A", tuple))
    with pytest.raises(ValueError, match="'Ansicht' and 'Ablage'"):
        check_unique_section_mnemonics(definitions)


def test_row_texts_align_letters_and_keep_rows_without_letter() -> None:
    measure = len  # one "pixel" per character makes the padding exact
    texts = mnemonic_row_texts([("Kurz", "k", 0), ("Sehr lang", None, 0), ("Mit Bild", "b", 3)], measure, gap="  ")
    assert texts[1] == "Sehr lang"
    assert texts[0].endswith("K") and texts[2].endswith("B")
    column = len("Mit Bild") + 3 + 2                         # widest row incl. its glyph, plus gap
    assert len(texts[0]) - 1 == column
    assert len(texts[2]) - 1 + 3 == column


# --- popup key path --------------------------------------------------------------------

@pytest.fixture
def root(_shared_tk_root):
    configure_ttk_theme(_shared_tk_root, DEFAULT_THEME)
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _open(root, items):
    bar = CustomMenuBar(root, (), theme_key=DEFAULT_THEME)
    anchor = ui.Label(root, text="anchor")
    anchor.pack()
    bar.open_popup(anchor, items, 0, "insert")
    return bar, bar._popup_stack[0]


@pytest.mark.parametrize("keysym, char, state", [("t", "t", 0), ("T", "T", 0x1), ("t", "", _ALT)])
def test_letter_runs_item_from_a_closed_submenu(root, keysym, char, state) -> None:
    ran: list[str] = []
    items = (_cmd("Top", None, ran), MenuItem(type="submenu", label="Sub", items=(_cmd("Task", "t", ran),)))
    bar, popup = _open(root, items)
    assert press_key(popup, keysym, char=char, state=state) is True
    assert ran == ["Task"]
    assert bar._popup_stack == []


def test_umlaut_letter_and_shown_letter_column(root) -> None:
    ran: list[str] = []
    bar, popup = _open(root, (_cmd("Selbsteinschätzung", "ü", ran), _cmd("Ohne", None, ran)))
    rows = [row for row, _item in popup._bw_menu_navigable_rows]
    assert rows[0].cget("text").startswith("Selbsteinschätzung ") and rows[0].cget("text").endswith("Ü")
    assert rows[1].cget("text") == "Ohne"
    assert press_key(popup, "udiaeresis", char="ü") is True
    assert ran == ["Selbsteinschätzung"]
    bar.close_all_popups()


def test_unbound_letter_is_not_handled(root) -> None:
    ran: list[str] = []
    bar, popup = _open(root, (_cmd("Task", "t", ran),))
    assert press_key(popup, "q", char="q") is False
    assert ran == []
    bar.close_all_popups()
