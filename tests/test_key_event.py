"""classify_key: KeyEvent (public text) vs KeyIdentity (matching) on two levels."""

import pytest

from bw_gui.contracts.key_event import KeyEvent, RawKey, classify_key
from bw_gui.contracts.key_modifiers import UNKNOWN_MODIFIERS, KeyModifiers, TkBackend
from bw_gui.contracts.key_spec import UNKNOWN, Key, KeySpec, Mod, matches

W = TkBackend.WIN32
CTRL_W, ALT_W, SHIFT, NUMLOCK = 0x4, 0x20000, 0x1, 0x8


def classify(keysym, char, state, backend=W):
    return classify_key(RawKey(keysym, char, state), backend)


# AltGr characters on a German layout arrive on win32 with Ctrl/Alt stripped
# (state=0, measured: KEYBINDING_AUDIT.md). Rows: keysym, char.
ALTGR_DE = [("at", "@"), ("EuroSign", "€"), ("braceleft", "{"), ("bracketleft", "["),
            ("bar", "|"), ("backslash", "\\"), ("asciitilde", "~"), ("twosuperior", "²"), ("mu", "µ")]


@pytest.mark.parametrize(("keysym", "char"), ALTGR_DE)
def test_altgr_characters_are_text_and_match_char_specs(keysym, char):
    event, identity = classify(keysym, char, 0)
    assert event.text == char
    assert event.modifiers == KeyModifiers()
    assert identity.character == char
    assert matches(KeySpec.char(char), identity)


@pytest.mark.parametrize(("keysym", "char"), ALTGR_DE)
def test_altgr_characters_with_numlock(keysym, char):
    event, identity = classify(keysym, char, NUMLOCK)
    assert event.text == char and identity.modifiers == frozenset()


def test_normal_character_with_state_zero_is_plain_text():
    event, identity = classify("a", "a", 0)
    assert event.text == "a" and identity.modifiers == frozenset()
    assert not hasattr(event, "keysym") and not hasattr(event, "char")


def test_ctrl_letter_has_identity_but_no_text():
    event, identity = classify("z", "\x1a", CTRL_W)
    assert event.text is None
    assert identity.character == "z" and identity.modifiers == {Mod.CTRL}
    assert matches(KeySpec.char("z", {Mod.CTRL}), identity)


def test_ctrl_shift_letter_identity_is_uppercase():
    _event, identity = classify("Z", "\x1a", CTRL_W | SHIFT)
    assert identity.character == "Z"
    assert matches(KeySpec.char("Z", {Mod.CTRL}), identity)
    assert not matches(KeySpec.char("z", {Mod.CTRL}), identity)


def test_alt_letter_win32_has_no_text_but_identity():
    event, identity = classify("z", "z", ALT_W)
    assert event.text is None
    assert identity.character == "z" and identity.modifiers == {Mod.ALT}


def test_aqua_option_character_is_text_exception():
    event, identity = classify("EuroSign", "€", 0x0010, TkBackend.AQUA)
    assert event.text == "€" and event.modifiers.alt is False
    assert identity.modifiers == frozenset()


def test_control_chars_are_never_text():
    event, identity = classify("Return", "\r", 0)
    assert event.key is Key.ENTER and event.text is None and identity.character is None
    event, _ = classify("Tab", "\t", 0)
    assert event.key is Key.TAB and event.text is None


def test_space_is_named_key_with_text():
    event, identity = classify("space", " ", 0)
    assert event.key is Key.SPACE and event.text == " " and identity.character is None


def test_unknown_state_is_fail_closed():
    event, identity = classify("a", "a", "??")
    assert event.modifiers is UNKNOWN_MODIFIERS and identity.modifiers is UNKNOWN
    assert not matches(KeySpec.char("a"), identity)


def test_iso_left_tab_means_shift_tab():
    event, identity = classify("ISO_Left_Tab", "", 0, TkBackend.X11)
    assert event.key is Key.TAB and Mod.SHIFT in identity.modifiers


def test_keypad_digits_and_umlauts():
    _e, identity = classify("KP_5", "5", NUMLOCK)
    assert identity.character == "5"
    _e, identity = classify("adiaeresis", "", CTRL_W)
    assert identity.character == "ä"


def test_modifier_key_itself_is_other():
    event, identity = classify("Shift_L", "", SHIFT)
    assert event.key is Key.OTHER and identity.key is Key.OTHER


def test_keyevent_has_no_tk_fields():
    assert set(KeyEvent.__dataclass_fields__) == {"key", "text", "modifiers", "widget"}
