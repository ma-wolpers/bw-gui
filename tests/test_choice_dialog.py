"""Tests for `ChoiceDialogService.askchoice` (modal "pick one answer" dialog).

Contract under test (see the service docstring): the chosen option's key is
returned; the cancel button, Escape and the window's close button all return
``None``; invalid options raise ``ValueError`` before anything is shown; the
call goes through the parent's modal runner.

The dialog is modal (``wait_window``), so the real-Tk tests act on it from an
``after`` callback scheduled before the call. Every such test also schedules a
watchdog that cancels a still-open dialog, so a broken action fails the
assertion instead of hanging the suite. Key events go to the *focused*
widget, so the Return/Escape tests need the OS keyboard focus and are opt-in
via ``TK_FOCUS_TESTS=1``, like ``test_shortcut_binder_tk.py``.
"""

from __future__ import annotations

import os

import pytest

from bw_gui.dialogs import ChoiceDialogService, ChoiceOption
from bw_gui.dialogs import service as dialog_service

_OPTIONS = (ChoiceOption("folder", "Ordner"), ChoiceOption("split", "Aufteilen", "Eine grosse PDF"))

_focus_only = pytest.mark.skipif(
    os.environ.get("TK_FOCUS_TESTS") != "1",
    reason="sends key events to the focused widget; run with TK_FOCUS_TESTS=1",
)


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    _shared_tk_root.update()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _open_dialog(root):
    """Return the currently open `_ChoiceDialog` (a child of `root`)."""
    dialogs = [child for child in root.winfo_children() if isinstance(child, dialog_service._ChoiceDialog)]
    assert dialogs, "no choice dialog is open"
    return dialogs[-1]


def _ask_with(root, action, *, delay_ms: int = 150) -> str | None:
    """Run `askchoice` while `action(dialog)` fires from the event loop; a watchdog cancels after 5 s."""

    def _act() -> None:
        action(_open_dialog(root))

    def _watchdog() -> None:
        for child in root.winfo_children():
            if isinstance(child, dialog_service._ChoiceDialog):
                child.cancel()

    root.after(delay_ms, _act)
    watchdog_id = root.after(5000, _watchdog)
    try:
        return ChoiceDialogService().askchoice("Neue Klausur", "Wie?", _OPTIONS, parent=root)
    finally:
        root.after_cancel(watchdog_id)


@pytest.mark.parametrize(
    "options, message",
    [
        ((), "at least one option"),
        ((ChoiceOption("", "Leer"),), "must not be empty"),
        ((ChoiceOption("a", "A"), ChoiceOption("a", "B")), "used twice"),
        (("a",), "ChoiceOption instances"),
    ],
)
def test_invalid_options_raise_before_anything_is_shown(monkeypatch, options, message):
    shown: list[object] = []
    monkeypatch.setattr(dialog_service, "_ChoiceDialog", lambda *args, **kwargs: shown.append(args))

    with pytest.raises(ValueError, match=message):
        ChoiceDialogService().askchoice("T", "M", options, parent=object())

    assert shown == []


def test_askchoice_uses_modal_runner_of_parent(monkeypatch):
    class _FakeParent:
        def __init__(self):
            self.titles: list[str] = []

        def _run_modal_dialog_call(self, title, callback):
            self.titles.append(title)
            return callback()

    class _FakeDialog:
        def __init__(self, parent, title, message, options, cancel_label):
            self.choice = options[1].key

    monkeypatch.setattr(dialog_service, "_ChoiceDialog", _FakeDialog)
    parent = _FakeParent()

    result = ChoiceDialogService().askchoice("Neue Klausur", "Wie?", _OPTIONS, parent=parent)

    assert result == "split"
    assert parent.titles == ["Neue Klausur"]


def test_clicking_an_option_returns_its_key(root):
    assert _ask_with(root, lambda dialog: dialog._choice_buttons[1].invoke()) == "split"


def test_cancel_button_returns_none(root):
    def _press_cancel(dialog) -> None:
        cancel_buttons = [
            child
            for frame in dialog.winfo_children()
            for child in frame.winfo_children()
            if child.winfo_class() == "TButton" and str(child.cget("text")) == "Abbrechen"
        ]
        cancel_buttons[0].invoke()

    assert _ask_with(root, _press_cancel) is None


def test_window_close_button_returns_none(root):
    assert _ask_with(root, lambda dialog: dialog.tk.eval(dialog.protocol("WM_DELETE_WINDOW"))) is None


@_focus_only
def test_return_activates_the_focused_option(root):
    def _press_return(dialog) -> None:
        dialog._choice_buttons[0].focus_force()
        dialog.update()
        dialog._choice_buttons[0].event_generate("<Return>")

    assert _ask_with(root, _press_return) == "folder"


@_focus_only
def test_escape_returns_none_and_does_not_reach_bind_all(root):
    leaked: list[str] = []
    root.bind_all("<Escape>", lambda _event: leaked.append("escape"))
    try:

        def _press_escape(dialog) -> None:
            dialog._choice_buttons[0].focus_force()
            dialog.update()
            dialog._choice_buttons[0].event_generate("<Escape>")

        assert _ask_with(root, _press_escape) is None
    finally:
        root.unbind_all("<Escape>")
    assert leaked == []


def test_initial_focus_is_on_first_option(root):
    seen: list[object] = []

    def _record_and_close(dialog) -> None:
        seen.append(dialog.initial_focus is dialog._choice_buttons[0])
        dialog.cancel()

    _ask_with(root, _record_and_close)
    assert seen == [True]

