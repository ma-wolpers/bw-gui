from types import SimpleNamespace

from bw_gui.dialogs.scrollable_popup import ScrollablePopupWindow


class _FakePopup:
    def __init__(self):
        self.request_close_calls = 0

    def _request_close(self):
        self.request_close_calls += 1
        return "break"


def test_escape_always_closes_regardless_of_focus():
    """Escape must close the popup unconditionally.

    Regression test: a previous implementation refocused instead of closing when an
    editable widget had focus, via a self.focus_force() call that had no observable
    effect (it re-asserted focus on a window that already had it) — Escape appeared
    to do nothing while typing in a popup's text field.
    """
    popup = _FakePopup()

    result = ScrollablePopupWindow._handle_escape_request(popup)

    assert result == "break"
    assert popup.request_close_calls == 1


def test_activate_modal_focus_ignores_non_active_popup(monkeypatch):
    class _FocusPopup:
        def __init__(self):
            self.lift_calls = 0
            self.focus_force_calls = 0

        def winfo_exists(self):
            return True

        def lift(self):
            self.lift_calls += 1

        def focus_get(self):
            return None

        def _is_descendant_of_popup(self, _widget):
            return False

        def focus_force(self):
            self.focus_force_calls += 1

        def grab_current(self):
            return None

        def grab_set(self):
            return None

    popup = _FocusPopup()

    monkeypatch.setattr(ScrollablePopupWindow, "active_popup", classmethod(lambda cls: object()))

    ScrollablePopupWindow._activate_modal_focus(popup)

    assert popup.lift_calls == 0
    assert popup.focus_force_calls == 0


def test_request_close_respects_confirmation_callback():
    class _ClosePopup:
        def __init__(self):
            self.destroy_calls = 0
            self._request_close_confirmation = lambda: False

        def destroy(self):
            self.destroy_calls += 1

    popup = _ClosePopup()

    result = ScrollablePopupWindow._request_close(popup)

    assert result == "break"
    assert popup.destroy_calls == 0


def test_scrollable_popup_str_delegates_to_popup_window_path():
    class _FakePopupWindow:
        def __str__(self):
            return ".popup"

    popup = SimpleNamespace(_popup_window=_FakePopupWindow())

    assert ScrollablePopupWindow.__str__(popup) == ".popup"
