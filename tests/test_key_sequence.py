"""Contract tests for bw_gui.contracts.key_sequence (parsing, declared modifiers, signatures)."""

from __future__ import annotations

import pytest

from bw_gui.contracts import KeyModifiers, TkBackend, binding_signature, declared_modifiers, parse_sequence


@pytest.mark.parametrize("sequence", ["a", "<a>", "<Key-a>", "<KeyPress-a>"])
def test_equivalent_plain_key_forms(sequence):
    parsed = parse_sequence(sequence)
    assert (parsed.event_type, parsed.modifier_tokens, parsed.keysym) == ("KeyPress", (), "a")


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("<Control-,>", "<Control-comma>"),
        ("+", "<KeyPress-plus>"),
        ("<Control-Shift-s>", "<Shift-Control-KeyPress-s>"),
        ("<Control-->", "<Control-minus>"),
        ("<Alt-a>", "<Alt-Key-a>"),
    ],
)
def test_semantically_equal_sequences_share_a_signature(first, second):
    assert binding_signature(first, TkBackend.WIN32) == binding_signature(second, TkBackend.WIN32)


@pytest.mark.parametrize(("sequence", "tokens"), [("<KeyPress-M>", ()), ("<M>", ()), ("<Control-M>", ("Control",))])
def test_last_field_is_the_keysym_even_if_it_spells_a_modifier_alias(sequence, tokens):
    # Tk reads "<M>" as keysym M, not as the Meta alias "M" (verified with Tk 8.6.15).
    parsed = parse_sequence(sequence)
    assert (parsed.modifier_tokens, parsed.keysym) == (tokens, "M")


def test_keysym_case_and_shift_distinguish_signatures():
    assert binding_signature("<KeyPress-a>", TkBackend.WIN32) != binding_signature("<KeyPress-A>", TkBackend.WIN32)
    assert binding_signature("<Control-a>", TkBackend.WIN32) != binding_signature("<Control-Shift-a>", TkBackend.WIN32)


@pytest.mark.parametrize(
    "sequence",
    [
        "<<Copy>>",
        "<Button-1>",
        "<ButtonPress-1>",
        "<Motion>",
        "<KeyRelease-a>",
        "<KeyPress>",
        "<Alt-KeyPress>",
        "<Double-a>",
        "<Any-KeyPress-a>",
        "<Lock-a>",
        "<Lock>",
        "<Key-M1>",
        "<Control-Shift>",
        "<Control-x><Control-s>",
        "ab",
        "",
        "<Frobnicate-a>",
    ],
)
def test_sequences_outside_the_keyboard_contract_are_rejected(sequence):
    with pytest.raises(ValueError):
        parse_sequence(sequence)


@pytest.mark.parametrize(
    ("backend", "sequence", "expected"),
    [
        (TkBackend.WIN32, "<Control-Alt-Shift-a>", KeyModifiers(shift=True, control=True, alt=True)),
        (TkBackend.AQUA, "<Command-a>", KeyModifiers(command=True)),
        (TkBackend.AQUA, "<Mod1-a>", KeyModifiers(command=True)),
        (TkBackend.AQUA, "<Option-a>", KeyModifiers(alt=True)),
        (TkBackend.X11, "<Mod1-a>", KeyModifiers(alt=True)),
        (TkBackend.X11, "<Alt-a>", KeyModifiers(alt=True)),
    ],
)
def test_declared_modifiers_per_backend(backend, sequence, expected):
    assert declared_modifiers(parse_sequence(sequence), backend) == expected


@pytest.mark.parametrize(
    ("backend", "sequence"),
    [
        # Measured on Tk 8.6.15/win32: Command == Mod1 == the NumLock bit -> no shortcut meaning.
        (TkBackend.WIN32, "<Command-a>"),
        (TkBackend.WIN32, "<Mod1-a>"),
        (TkBackend.WIN32, "<Option-a>"),
        (TkBackend.WIN32, "<Meta-a>"),
        (TkBackend.AQUA, "<Alt-a>"),
        (TkBackend.X11, "<Meta-a>"),
        (TkBackend.X11, "<Command-a>"),
        (TkBackend.X11, "<Mod2-a>"),
    ],
)
def test_aliases_without_defined_backend_meaning_are_rejected(backend, sequence):
    with pytest.raises(ValueError):
        declared_modifiers(parse_sequence(sequence), backend)
