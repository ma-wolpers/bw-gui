"""press_key: headless walk through the bw-gui dispatchers in bindtag order."""

from __future__ import annotations

from bw_gui.contracts import EventResult, Key, KeySpec, Mod, TkBackend
from bw_gui.runtime import ApplicationShortcutBinder, WidgetShortcutBinder, WindowShortcutBinder, on_key, ui
from bw_gui.testing.keys import press_key

CONTROL = 0x0004


def test_order_widget_then_window_then_application(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    canvas = ui.Canvas(top)
    canvas.pack()
    seen: list[str] = []
    try:
        widget = WidgetShortcutBinder(canvas, backend=TkBackend.WIN32)
        window = WindowShortcutBinder(top, backend=TkBackend.WIN32)
        app = ApplicationShortcutBinder(_shared_tk_root, backend=TkBackend.WIN32)
        widget.bind(KeySpec(Key.UP), lambda _e: seen.append("widget"), binding_id="w", intent="w")
        window.bind(KeySpec(Key.UP), lambda _e: seen.append("window") or EventResult.HANDLED, binding_id="t", intent="t")
        app.bind(KeySpec(Key.UP), lambda _e: seen.append("app"), binding_id="a", intent="a")
        assert press_key(canvas, "Up") is True
        assert seen == ["widget", "window"]  # window HANDLED stops before the router
        app.dispose()
    finally:
        top.destroy()


def test_modifiers_and_unhandled_result(_shared_tk_root):
    top = ui.Toplevel(_shared_tk_root)
    calls: list[str | None] = []
    try:
        binder = WindowShortcutBinder(top, backend=TkBackend.WIN32)
        binder.bind(KeySpec.char("z", {Mod.CTRL}), lambda _e: EventResult.HANDLED, binding_id="u", intent="u")
        on_key(top, lambda event: calls.append(event.text))
        assert press_key(top, "z", state=CONTROL) is True
        assert press_key(top, "x", char="x") is False
        assert calls == ["x"]
    finally:
        top.destroy()
