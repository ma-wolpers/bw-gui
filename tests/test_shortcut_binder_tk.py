"""Opt-in real-Tk key routing through bindtags (``TK_FOCUS_TESTS=1``).

Real synthetic key events only reach a widget while the test window has the OS
keyboard focus, so these tests take the focus (``focus_force``) -- which would steal
keystrokes from a user typing elsewhere. They are skipped by default; the dispatch
logic itself is covered headlessly in ``test_shortcut_binders.py``.
"""

from __future__ import annotations

import os

import pytest

from bw_gui.contracts import EventResult, Key, KeySpec, Mod, TkBackend
from bw_gui.runtime import ApplicationShortcutBinder, WidgetShortcutBinder, WindowShortcutBinder, on_key, ui

pytestmark = pytest.mark.skipif(
    os.environ.get("TK_FOCUS_TESTS") != "1",
    reason="opens windows and takes the keyboard focus; run with TK_FOCUS_TESTS=1",
)

CONTROL = 0x0004


@pytest.fixture
def window(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    top.geometry("240x160+20+20")
    canvas = ui.Canvas(top, width=100, height=40)
    entry = ui.Entry(top)
    canvas.pack()
    entry.pack()
    top.update()
    yield top, canvas, entry
    top.destroy()


def _press(widget, key, state=0):
    widget.focus_force()
    widget.update()
    widget.event_generate(f"<KeyPress-{key}>", state=state, when="now")
    widget.update()


def test_window_binder_fires_for_real_key(window):
    top, canvas, _entry = window
    hits = []
    WindowShortcutBinder(top, backend=TkBackend.WIN32).bind(
        KeySpec.char("k", {Mod.CTRL}), lambda e: hits.append(e.key), binding_id="k", intent="i"
    )
    _press(canvas, "k", CONTROL)
    assert hits == [Key.CHARACTER]


def test_on_key_after_sees_inserted_character(window):
    _top, _canvas, entry = window
    seen = []
    on_key(entry, lambda e: seen.append(entry.get()), phase="after")
    _press(entry, "x")
    assert seen == ["x"]


def test_on_key_after_not_reached_when_class_binding_breaks(window, _shared_tk_root):
    top, _canvas, _entry = window
    # A widget class whose native class binding consumes the key (Tk-level break).
    widget = ui.Frame(top, takefocus=1, class_="BwBreakingClass")
    widget.pack()
    _shared_tk_root.tk.call("bind", "BwBreakingClass", "<KeyPress>", "break")
    seen = []
    on_key(widget, lambda e: seen.append("after"), phase="after")
    _press(widget, "q")
    assert seen == []


def test_before_handled_blocks_insertion_and_app_shortcuts(window, _shared_tk_root):
    _top, _canvas, entry = window
    app_hits = []
    app = ApplicationShortcutBinder(_shared_tk_root, backend=TkBackend.WIN32)
    try:
        app.bind(KeySpec.char("w", {Mod.CTRL}), lambda e: app_hits.append(1), binding_id="w", intent="i", allow_when_text_input=True)
        on_key(entry, lambda e: EventResult.HANDLED)
        _press(entry, "w", CONTROL)
        _press(entry, "x")
        assert app_hits == [] and entry.get() == ""
    finally:
        app.dispose()


def test_popup_toplevel_override_beats_application_binder(window, _shared_tk_root):
    top, canvas, _entry = window
    seen = []
    app = ApplicationShortcutBinder(_shared_tk_root, backend=TkBackend.WIN32)
    try:
        app.bind(KeySpec(Key.ESCAPE), lambda e: seen.append("app"), binding_id="esc", intent="i")
        WindowShortcutBinder(top, backend=TkBackend.WIN32).bind(
            KeySpec(Key.ESCAPE), lambda e: (seen.append("popup"), EventResult.HANDLED)[1], binding_id="pesc", intent="i"
        )
        _press(canvas, "Escape")
        assert seen == ["popup"]
    finally:
        app.dispose()


def test_widget_shortcut_up_does_not_move_text_cursor(window):
    top, _canvas, _entry = window
    text = ui.Text(top, height=3)
    text.pack()
    text.insert("1.0", "a\nb\nc")
    text.mark_set("insert", "3.0")
    WidgetShortcutBinder(text, backend=TkBackend.WIN32).bind(
        KeySpec(Key.UP), lambda e: EventResult.HANDLED, binding_id="up", intent="i", allow_when_text_input=True
    )
    _press(text, "Up")
    assert text.index("insert") == "3.0"


def test_tab_traversal_is_preserved(window):
    _top, canvas, entry = window
    canvas.configure(takefocus=1)
    canvas.focus_force()
    canvas.update()
    _press(canvas, "Tab")
    assert canvas.focus_get() is entry
