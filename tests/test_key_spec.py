"""KeySpec contract: canonical form, parse grammar, exact matching, overlaps."""

import itertools

import pytest

from bw_gui.contracts.key_modifiers import TkBackend
from bw_gui.contracts.key_spec import (
    MOD_ORDER,
    UNKNOWN,
    Key,
    KeyIdentity,
    KeySpec,
    Mod,
    matches,
    overlaps,
)

CTRL, ALT, SHIFT, CMD = Mod.CTRL, Mod.ALT, Mod.SHIFT, Mod.CMD


def ident(key, char=None, mods=()):
    return KeyIdentity(key, char, frozenset(mods))


# -- parse / str ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ctrl+Shift+Z", KeySpec.char("Z", {CTRL})),
        ("Ctrl+Z", KeySpec.char("z", {CTRL})),
        ("Ctrl+z", KeySpec.char("z", {CTRL})),
        ("ctrl+alt+x", KeySpec.char("x", {CTRL, ALT})),
        ("Ctrl++", KeySpec.char("+", {CTRL})),
        ("+", KeySpec.char("+")),
        ("Ctrl+(", KeySpec.char("(", {CTRL})),
        ("€", KeySpec.char("€")),
        ("ß", KeySpec.char("ß")),
        ("Space", KeySpec(Key.SPACE)),
        ("Shift+Tab", KeySpec(Key.TAB, {SHIFT})),
        ("escape", KeySpec(Key.ESCAPE)),
        ("F5", KeySpec(Key.F5)),
        ("Escape (tolerate: Shift)", KeySpec(Key.ESCAPE, (), {SHIFT})),
        ("Escape (tolerate: shift ,CTRL)", KeySpec(Key.ESCAPE, (), {CTRL, SHIFT})),
        ("Ctrl+Z (tolerate: Alt)", KeySpec.char("z", {CTRL}, {ALT})),
    ],
)
def test_parse(text, expected):
    assert KeySpec.parse(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "", "Ctrl+Shift++", "Shift+1", "Shift+ß", "Ctrl+Alt", "Hello", "Ctrl+Ctrl+a",
        "Escape (tolerate: )", "Escape (tolerate: Shift, Shift)", "Ctrl+Z (tolerate: Ctrl)",
        "Ctrl+Z (tolerate: Shift)", "Escape (tolerate: Foo)", "Escape (tolerate: Shift", "Escape (x: Shift)",
    ],
)
def test_parse_rejects(text):
    with pytest.raises(ValueError):
        KeySpec.parse(text)


@pytest.mark.parametrize(
    "spec",
    [
        KeySpec.char("z", {CTRL}),
        KeySpec.char("Z", {CTRL}),
        KeySpec.char("+", {CTRL}),
        KeySpec(Key.SPACE),
        KeySpec(Key.ESCAPE, (), {CTRL, SHIFT}),
    ],
)
def test_canonical_str(spec):
    assert KeySpec.parse(str(spec)) == spec


def test_canonical_letters():
    assert str(KeySpec.char("z", {CTRL})) == "Ctrl+Z"
    assert str(KeySpec.char("Z", {CTRL})) == "Ctrl+Shift+Z"
    assert str(KeySpec(Key.ESCAPE, (), {SHIFT, CTRL})) == "Escape (tolerate: Ctrl, Shift)"


def _all_chars():
    ascii_printable = [chr(c) for c in range(33, 127)]
    return ascii_printable + list("äöüÄÖÜ€ß²µ")


@pytest.mark.parametrize("char", _all_chars())
def test_roundtrip_every_character(char):
    for mods in ((), (CTRL,), (CTRL, ALT)):
        spec = KeySpec.char(char, mods)
        assert KeySpec.parse(str(spec)) == spec


def test_roundtrip_named_keys_and_tolerate_subsets():
    named = [k for k in Key if k not in (Key.CHARACTER, Key.OTHER)]
    subsets = [frozenset(c) for n in range(5) for c in itertools.combinations(MOD_ORDER, n)]
    for key in named:
        for tol in subsets:
            spec = KeySpec(key, (), tol)
            assert KeySpec.parse(str(spec)) == spec


@pytest.mark.parametrize("bad", [" ", "\t", "ab", ""])
def test_whitespace_and_multichar_characters_rejected(bad):
    with pytest.raises(ValueError):
        KeySpec.char(bad)


def test_shift_rejected_for_characters():
    with pytest.raises(ValueError):
        KeySpec.char("z", {SHIFT})
    with pytest.raises(ValueError):
        KeySpec.char("z", (), {SHIFT})


def test_backend_check():
    KeySpec.char("a", {CMD}).check_backend(TkBackend.AQUA)
    with pytest.raises(ValueError):
        KeySpec.char("a", {CMD}).check_backend(TkBackend.WIN32)


# -- exact matching -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("identity", "expected"),
    [
        (ident(Key.CHARACTER, "z", {CTRL}), True),
        (ident(Key.CHARACTER, "Z", {CTRL, SHIFT}), False),
        (ident(Key.CHARACTER, "z", {CTRL, ALT}), False),
        (ident(Key.CHARACTER, "z", ()), False),
        (KeyIdentity(Key.CHARACTER, "z", UNKNOWN), False),
    ],
)
def test_exact_modifiers(identity, expected):
    assert matches(KeySpec.char("z", {CTRL}), identity) is expected


def test_tolerate_on_named_key():
    spec = KeySpec(Key.ESCAPE, (), {SHIFT})
    assert matches(spec, ident(Key.ESCAPE))
    assert matches(spec, ident(Key.ESCAPE, mods={SHIFT}))
    assert not matches(spec, ident(Key.ESCAPE, mods={CTRL}))
    assert not matches(KeySpec(Key.ESCAPE), ident(Key.ESCAPE, mods={SHIFT}))


def test_logical_identity_is_layout_based():
    spec = KeySpec.char("z", {CTRL})
    assert matches(spec, ident(Key.CHARACTER, "z", {CTRL}))
    assert not matches(spec, ident(Key.CHARACTER, "я", {CTRL}))
    assert "keycode" not in KeyIdentity.__dataclass_fields__


def _identities():
    chars = ["z", "Z", "+"]
    sets = [frozenset(c) for n in range(5) for c in itertools.combinations(MOD_ORDER, n)]
    for c in chars:
        for s in sets:
            yield ident(Key.CHARACTER, c, s)
    for s in sets:
        yield ident(Key.ESCAPE, mods=s)


SPECS = [
    KeySpec.char("z", {CTRL}),
    KeySpec.char("z", {CTRL}, {ALT}),
    KeySpec.char("Z", {CTRL}),
    KeySpec.char("z"),
    KeySpec(Key.ESCAPE),
    KeySpec(Key.ESCAPE, (), {SHIFT}),
    KeySpec(Key.ESCAPE, {SHIFT}),
]


@pytest.mark.parametrize(("a", "b"), list(itertools.product(SPECS, SPECS)))
def test_overlaps_equals_exhaustive_enumeration(a, b):
    expected = any(matches(a, i) and matches(b, i) for i in _identities())
    assert overlaps(a, b) is expected
