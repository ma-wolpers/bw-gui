"""Contract tests for bw_gui.contracts.key_modifiers (backend normalisation, state decoding)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bw_gui.contracts import (
    NO_MODIFIERS,
    UNKNOWN_MODIFIERS,
    KeyModifiers,
    TkBackend,
    UnknownModifiers,
    backend_for_platform,
    backend_for_windowing_system,
    modifiers_from_event,
    modifiers_from_state,
)


@pytest.mark.parametrize(
    ("platform", "backend"),
    [
        ("win32", TkBackend.WIN32),
        ("darwin", TkBackend.AQUA),
        ("linux", TkBackend.X11),
        ("linux2", TkBackend.X11),
        ("freebsd14", TkBackend.X11),
    ],
)
def test_os_platform_is_normalised_to_tk_backend(platform, backend):
    # sys.platform never says "x11" -- Linux must be mapped explicitly.
    assert backend_for_platform(platform) is backend


def test_unknown_platform_is_rejected():
    with pytest.raises(ValueError):
        backend_for_platform("emscripten")


@pytest.mark.parametrize("name", ["win32", "aqua", "x11", " X11 "])
def test_windowing_system_mapping(name):
    assert backend_for_windowing_system(name).value == name.strip().lower()


def test_unknown_windowing_system_is_rejected():
    with pytest.raises(ValueError):
        backend_for_windowing_system("wayland")


@pytest.mark.parametrize(
    ("backend", "state", "expected"),
    [
        # win32 values measured live (tests/live): NumLock is 0x0008, Alt is 0x20000.
        (TkBackend.WIN32, 0x0, NO_MODIFIERS),
        (TkBackend.WIN32, 0x0008, NO_MODIFIERS),
        (TkBackend.WIN32, 0x0001, KeyModifiers(shift=True)),
        (TkBackend.WIN32, 0x0009, KeyModifiers(shift=True)),
        (TkBackend.WIN32, 0x0004, KeyModifiers(control=True)),
        (TkBackend.WIN32, 0x000C, KeyModifiers(control=True)),
        (TkBackend.WIN32, 0x20000, KeyModifiers(alt=True)),
        (TkBackend.WIN32, 0x20008, KeyModifiers(alt=True)),
        (TkBackend.WIN32, 0x0002, NO_MODIFIERS),  # CapsLock
        (TkBackend.AQUA, 0x0001, KeyModifiers(shift=True)),
        (TkBackend.AQUA, 0x0004, KeyModifiers(control=True)),
        (TkBackend.AQUA, 0x0008, KeyModifiers(command=True)),
        (TkBackend.AQUA, 0x0010, KeyModifiers(alt=True)),
        (TkBackend.X11, 0x0001, KeyModifiers(shift=True)),
        (TkBackend.X11, 0x0004, KeyModifiers(control=True)),
        (TkBackend.X11, 0x0008, KeyModifiers(alt=True)),
        (TkBackend.X11, 0x0010, NO_MODIFIERS),  # usually NumLock (Mod2)
    ],
)
def test_modifiers_from_state_mask_table(backend, state, expected):
    assert modifiers_from_state(state, backend) == expected


def test_shift_is_not_a_shortcut_modifier():
    assert not KeyModifiers(shift=True).has_shortcut_modifier
    for flag in ("control", "alt", "command"):
        assert KeyModifiers(**{flag: True}).has_shortcut_modifier


def test_shortcut_modifiers_not_in_ignores_declared_and_shift():
    held = KeyModifiers(shift=True, control=True, alt=True)
    extra = held.shortcut_modifiers_not_in(KeyModifiers(control=True))
    assert extra == KeyModifiers(alt=True)


@pytest.mark.parametrize("state", [None, "??", 1.5, True, -1])
def test_undecodable_event_state_is_unknown_never_no_modifiers(state):
    event = SimpleNamespace() if state is None else SimpleNamespace(state=state)
    assert modifiers_from_event(event, TkBackend.WIN32) is UNKNOWN_MODIFIERS


def test_decodable_event_state():
    assert modifiers_from_event(SimpleNamespace(state=0x4), TkBackend.WIN32) == KeyModifiers(control=True)


def test_unknown_modifiers_is_a_singleton_without_truth_value():
    assert UnknownModifiers() is UNKNOWN_MODIFIERS
    with pytest.raises(TypeError):
        bool(UNKNOWN_MODIFIERS)
