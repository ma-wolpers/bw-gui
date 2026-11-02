"""Tests for ``bw_gui.testing.tk_root``: skip only for environmental Tk failures."""

from __future__ import annotations

import tkinter

import pytest

from bw_gui.testing.tk_root import create_tk_root, is_missing_display, is_tcl_init_race

_NO_DISPLAY = tkinter.TclError("no display name and no $DISPLAY environment variable")
_RACE = tkinter.TclError("Can't find a usable init.tcl in the following directories")


def _factory(*outcomes):
    """Return a factory that raises/returns *outcomes* in order and counts its calls."""
    calls = []

    def factory():
        outcome = outcomes[len(calls)]
        calls.append(outcome)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    factory.calls = calls
    return factory


def test_returns_what_the_factory_returns():
    assert create_tk_root(_factory("root")) == "root"


def test_missing_display_skips_without_retry():
    factory = _factory(_NO_DISPLAY, "root")
    with pytest.raises(pytest.skip.Exception, match="no Tk display"):
        create_tk_root(factory)
    assert len(factory.calls) == 1


def test_init_race_is_retried():
    factory = _factory(_RACE, _RACE, "root")
    assert create_tk_root(factory) == "root"
    assert len(factory.calls) == 3


def test_persistent_init_race_skips():
    with pytest.raises(pytest.skip.Exception, match="init race"):
        create_tk_root(_factory(_RACE, _RACE), attempts=2)


def test_other_tcl_errors_are_real_failures():
    with pytest.raises(tkinter.TclError, match="bad option"):
        create_tk_root(_factory(tkinter.TclError('bad option "-colour"')))


def test_classifiers_only_accept_tcl_errors():
    assert is_missing_display(tkinter.TclError("couldn't connect to display \":0\""))
    assert not is_missing_display(RuntimeError("no display name"))
    assert is_tcl_init_race(tkinter.TclError("invalid command name \"tcl_findLibrary\""))
    assert not is_tcl_init_race(_NO_DISPLAY)
