import bw_gui.runtime.platform as platform_module
from bw_gui.runtime.platform import center_window_over_parent, get_monitor_bounds


class _FakeScreenWidget:
    def __init__(self, screen_width: int, screen_height: int):
        self._screen_width = screen_width
        self._screen_height = screen_height

    def winfo_screenwidth(self):
        return self._screen_width

    def winfo_screenheight(self):
        return self._screen_height


class _FakeToplevel:
    def __init__(self, width: int, height: int, root_x: int = 0, root_y: int = 0):
        self._width = width
        self._height = height
        self._root_x = root_x
        self._root_y = root_y
        self.geometry_calls: list[str] = []

    def update_idletasks(self):
        pass

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def winfo_reqwidth(self):
        return self._width

    def winfo_reqheight(self):
        return self._height

    def winfo_rootx(self):
        return self._root_x

    def winfo_rooty(self):
        return self._root_y

    def geometry(self, spec: str):
        self.geometry_calls.append(spec)


def test_get_monitor_bounds_falls_back_to_primary_screen_on_non_windows(monkeypatch):
    monkeypatch.setattr(platform_module.sys, "platform", "linux")
    widget = _FakeScreenWidget(1920, 1080)

    assert get_monitor_bounds(widget) == (0, 0, 1920, 1080)


def test_center_window_over_parent_centers_on_parents_actual_monitor(monkeypatch):
    # Parent lives on a secondary monitor to the right of the primary display
    # (1920-3840 horizontally). Centering must land inside that monitor, not
    # the primary one at (0, 0)-(1920, 1080).
    monkeypatch.setattr(platform_module, "get_monitor_bounds", lambda _widget: (1920, 0, 3840, 1080))

    parent = _FakeToplevel(width=1200, height=800, root_x=2100, root_y=100)
    window = _FakeToplevel(width=400, height=300)

    center_window_over_parent(window, parent)

    assert len(window.geometry_calls) == 1
    expected_x = 2100 + (1200 - 400) // 2
    expected_y = 100 + (800 - 300) // 2
    assert window.geometry_calls[0] == f"+{expected_x}+{expected_y}"


def test_center_window_over_parent_clamps_to_monitor_right_edge(monkeypatch):
    # Parent sits near the right edge of its (secondary) monitor, so a naive
    # centered position for a wide popup would spill past the monitor's own
    # right bound (3840) rather than the primary monitor's (1920).
    monkeypatch.setattr(platform_module, "get_monitor_bounds", lambda _widget: (1920, 0, 3840, 1080))

    parent = _FakeToplevel(width=200, height=200, root_x=3700, root_y=50)
    window = _FakeToplevel(width=500, height=300)

    center_window_over_parent(window, parent)

    x_str, y_str = window.geometry_calls[0].split("+")[1:]
    assert int(x_str) == 3840 - 500
    assert int(x_str) >= 1920
