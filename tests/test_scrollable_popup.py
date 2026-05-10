from types import SimpleNamespace

from bw_gui.dialogs.scrollable_popup import ScrollablePopupWindow


class _FakeEditable:
    pass


class _FakePopup:
    def __init__(self, focused_widget, is_descendant: bool):
        self._focused_widget = focused_widget
        self._is_descendant = is_descendant
        self.focus_force_calls = 0
        self.request_close_calls = 0

    def focus_get(self):
        return self._focused_widget

    def _is_descendant_of_popup(self, _widget):
        return self._is_descendant

    def focus_force(self):
        self.focus_force_calls += 1

    def _request_close(self):
        self.request_close_calls += 1
        return "break"


def test_escape_with_text_focus_only_lifts_focus(monkeypatch):
    popup = _FakePopup(focused_widget=_FakeEditable(), is_descendant=True)

    monkeypatch.setattr(ScrollablePopupWindow, "_is_editable_widget", staticmethod(lambda widget: True))

    result = ScrollablePopupWindow._handle_escape_request(popup)

    assert result == "break"
    assert popup.focus_force_calls == 1
    assert popup.request_close_calls == 0


def test_escape_with_popup_focus_closes_popup(monkeypatch):
    popup = _FakePopup(focused_widget=SimpleNamespace(), is_descendant=True)

    monkeypatch.setattr(ScrollablePopupWindow, "_is_editable_widget", staticmethod(lambda widget: False))

    result = ScrollablePopupWindow._handle_escape_request(popup)

    assert result == "break"
    assert popup.focus_force_calls == 0
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
