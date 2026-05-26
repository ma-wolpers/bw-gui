from bw_gui.runtime.app_shell import AppShellConfig, TkinterAppShell
import bw_gui.runtime.app_shell as app_shell_module


class _FakeRoot:
    def __init__(self):
        self.title_value = None
        self.geometry_value = None
        self.min_size = None
        self.protocol_callbacks = {}
        self.destroy_calls = 0

    def title(self, value):
        self.title_value = value

    def geometry(self, value):
        self.geometry_value = value

    def minsize(self, width, height):
        self.min_size = (width, height)

    def protocol(self, key, callback):
        self.protocol_callbacks[key] = callback

    def destroy(self):
        self.destroy_calls += 1


def test_shell_applies_window_setup_and_registers_close_callback():
    root = _FakeRoot()
    config = AppShellConfig(
        title="Demo",
        geometry="1000x800",
        min_width=720,
        min_height=540,
    )

    TkinterAppShell(root, config)

    assert root.title_value == "Demo"
    assert root.geometry_value == "1000x800"
    assert root.min_size == (720, 540)
    assert "WM_DELETE_WINDOW" in root.protocol_callbacks


def test_shell_close_handler_can_block_window_destroy():
    root = _FakeRoot()
    config = AppShellConfig(title="Demo", geometry="1000x800", min_width=720, min_height=540)
    shell = TkinterAppShell(root, config, on_close=lambda: False)

    shell._handle_close()

    assert root.destroy_calls == 0


def test_shell_close_handler_destroys_window_when_allowed():
    root = _FakeRoot()
    config = AppShellConfig(title="Demo", geometry="1000x800", min_width=720, min_height=540)
    shell = TkinterAppShell(root, config, on_close=lambda: True)

    shell._handle_close()

    assert root.destroy_calls == 1


def test_shell_apply_theme_delegates_to_theme_helpers(monkeypatch):
    root = _FakeRoot()
    config = AppShellConfig(title="Demo", geometry="1000x800", min_width=720, min_height=540)
    shell = TkinterAppShell(root, config)
    calls = []

    monkeypatch.setattr(app_shell_module, "apply_window_theme", lambda widget, key: calls.append(("window", widget, key)))
    monkeypatch.setattr(app_shell_module, "configure_ttk_theme", lambda widget, key: calls.append(("ttk", widget, key)))

    shell.apply_theme("mono_day")

    assert shell.current_theme_key == "mono_day"
    assert calls == [
        ("window", root, "mono_day"),
        ("ttk", root, "mono_day"),
    ]
