from types import SimpleNamespace

import pytest

from bw_gui.dialogs.scrollable_popup import ScrollablePopupWindow
from bw_gui.runtime import widgets


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
            self.withdraw_calls = 0
            self._closing = False
            self._request_close_confirmation = lambda: False

        def withdraw(self):
            self.withdraw_calls += 1

        def destroy(self):
            self.destroy_calls += 1

    popup = _ClosePopup()

    result = ScrollablePopupWindow._request_close(popup)

    assert result == "break"
    assert popup.destroy_calls == 0
    assert popup.withdraw_calls == 0
    assert popup._closing is False


def test_request_close_withdraws_before_destroying():
    class _ClosePopup:
        def __init__(self):
            self.calls: list[str] = []
            self._closing = False
            self._request_close_confirmation = None

        def withdraw(self):
            self.calls.append("withdraw")

        def destroy(self):
            self.calls.append("destroy")

    popup = _ClosePopup()

    result = ScrollablePopupWindow._request_close(popup)

    assert result == "break"
    assert popup.calls == ["withdraw", "destroy"]
    assert popup._closing is True


def test_request_close_is_idempotent():
    class _ClosePopup:
        def __init__(self):
            self.destroy_calls = 0
            self._closing = False
            self._request_close_confirmation = None

        def withdraw(self):
            pass

        def destroy(self):
            self.destroy_calls += 1

    popup = _ClosePopup()

    ScrollablePopupWindow._request_close(popup)
    result = ScrollablePopupWindow._request_close(popup)

    assert result == "break"
    assert popup.destroy_calls == 1


def test_apply_theme_does_not_crash_when_not_scrollable():
    """Regression: `scrollable=False` popups have no `self._scroll` -- `apply_theme()` must
    skip the ScrollableFrame chrome-refresh step instead of raising `AttributeError`."""
    popup = SimpleNamespace(_apply_window_theme=None, _configure_ttk_theme=None, theme_key=None, _scroll=None)

    ScrollablePopupWindow.apply_theme(popup)  # must not raise


def test_scrollable_popup_str_delegates_to_popup_window_path():
    class _FakePopupWindow:
        def __str__(self):
            return ".popup"

    popup = SimpleNamespace(_popup_window=_FakePopupWindow())

    assert ScrollablePopupWindow.__str__(popup) == ".popup"


# --- Real-Tk regression coverage for the ScrollableFrame-backed refactor ---
#
# ScrollablePopupWindow used to build its own Canvas/Scrollbar/mousewheel
# machinery directly; it now delegates that to `bw_gui.widgets.ScrollableFrame`
# (see that module and `scrollable_popup.py`'s class docstring) and keeps
# only Toplevel lifecycle. These tests verify end-to-end, through a real
# window, that nothing observable from a consumer's perspective changed:
# `.content` still works, scrolling/mousewheel still work, closing/geometry/
# theme hooks still work. Kursplaner's `kursplaner/adapters/gui/popup_window.py`
# subclasses this class directly and is used across roughly a dozen of its
# dialogs - this is the contract that refactor must not disturb.


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    ScrollablePopupWindow._open_popups = []
    _shared_tk_root.update()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    ScrollablePopupWindow._open_popups = []


def test_content_is_usable_and_scrolls_when_taller_than_popup(root):
    popup = ScrollablePopupWindow(root, title="T", geometry="200x120", minsize=(100, 80))
    root.update()

    for i in range(40):
        widgets.Label(popup.content, text=f"row {i}", padding=(0, 6)).pack(fill="x")
    root.update()

    before = popup._scroll.canvas.yview()[0]
    popup._scroll.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    after = popup._scroll.canvas.yview()[0]

    assert after > before
    popup._request_close()


def test_non_scrollable_popup_has_plain_content_and_no_scroll_frame(root):
    popup = ScrollablePopupWindow(root, title="T", geometry="200x120", minsize=(100, 80), scrollable=False)
    root.update()

    assert popup._scroll is None
    assert popup._canvas is None
    widgets.Label(popup.content, text="hello").pack()
    root.update()

    popup._request_close()


def test_apply_theme_refreshes_scrollable_frame_chrome_without_error(root):
    calls: list[str] = []
    popup = ScrollablePopupWindow(
        root,
        title="T",
        geometry="200x120",
        minsize=(100, 80),
        theme_key="dark",
        apply_window_theme=lambda p, key: calls.append(f"window:{key}"),
        configure_ttk_theme=lambda p, key: calls.append(f"ttk:{key}"),
    )
    root.update()
    popup._scroll.canvas.configure(highlightthickness=5)

    popup.apply_theme()

    assert calls == ["window:dark", "ttk:dark"]
    assert int(popup._scroll.canvas["highlightthickness"]) == 0
    popup._request_close()


def test_escape_closes_popup_built_on_scrollable_frame(root):
    popup = ScrollablePopupWindow(root, title="T", geometry="200x120", minsize=(100, 80))
    root.update()
    assert popup.winfo_exists()

    popup._on_escape_close()
    root.update()

    assert not popup.winfo_exists()
