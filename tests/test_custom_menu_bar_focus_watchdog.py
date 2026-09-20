from bw_gui.menu.custom_menu_bar import CustomMenuBar


class _FakeRoot:
    """Stands in for the Tk root: only the calls `_focus_watchdog_suspended`/
    `_close_if_focus_outside_menu` themselves make, no real Tk widgets needed."""

    def __init__(self):
        self.after_idle_calls = 0

    def after_idle(self, _fn):
        self.after_idle_calls += 1
        return f"idle-{self.after_idle_calls}"

    def after_cancel(self, _job_id):
        pass


def _bar_with_one_popup():
    root = _FakeRoot()
    bar = CustomMenuBar(root, (), theme_key="mono_day")
    bar._popup_stack = [object()]  # placeholder: never touched while suspended
    return bar, root


def test_close_if_focus_outside_menu_is_a_noop_while_suspended():
    bar, _root = _bar_with_one_popup()
    with bar._focus_watchdog_suspended():
        assert bar._focus_watchdog_suspend_depth == 1
        bar._close_if_focus_outside_menu()  # would normally call close_all_popups()
        assert len(bar._popup_stack) == 1  # untouched


def test_watchdog_rearms_exactly_once_after_the_outermost_suspension_ends():
    bar, root = _bar_with_one_popup()
    with bar._focus_watchdog_suspended():
        pass
    assert bar._focus_watchdog_suspend_depth == 0
    assert root.after_idle_calls == 1


def test_nested_suspension_only_rearms_after_the_outermost_exit():
    bar, root = _bar_with_one_popup()
    with bar._focus_watchdog_suspended():
        with bar._focus_watchdog_suspended():
            assert bar._focus_watchdog_suspend_depth == 2
        assert bar._focus_watchdog_suspend_depth == 1
        assert root.after_idle_calls == 0  # inner exit must not rearm yet
    assert bar._focus_watchdog_suspend_depth == 0
    assert root.after_idle_calls == 1


def test_no_rearm_scheduled_when_no_popups_are_open():
    root = _FakeRoot()
    bar = CustomMenuBar(root, (), theme_key="mono_day")
    with bar._focus_watchdog_suspended():
        pass
    assert root.after_idle_calls == 0
