"""Real-Tk tests for `ScrollableImagePreview` (width-fitted, vertically scrolling image preview).

Covers every promise of the class contract: render width follows width
changes (debounced, >= 2 px), height changes and scrollbar toggles never
re-render, a pending timer dies with the widget, ``render -> None`` clears
the image, exception routing for `refresh()` vs. a debounced resize, and the
keyboard-oriented `scroll()`. Uses the session-scoped real Tk root (see
`conftest.py`) and processes events via `update()` instead of sleeping.
"""

from __future__ import annotations

import time

import pytest

from bw_gui.runtime import ui
from bw_gui.widgets import ScrollableImagePreview


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    _shared_tk_root.geometry("400x300+0+0")
    _shared_tk_root.update()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


class _Renderer:
    """Records every render width; image height comes from `height_for(width)`."""

    def __init__(self, height_for=lambda width: width * 2) -> None:
        self.widths: list[int] = []
        self.height_for = height_for
        self.return_none = False
        self.raise_error: Exception | None = None

    def __call__(self, width: int):
        self.widths.append(width)
        if self.raise_error is not None:
            raise self.raise_error
        if self.return_none:
            return None
        return ui.PhotoImage(width=width, height=self.height_for(width))


def _settle(root, ms: int = 120) -> None:
    """Process events for `ms` milliseconds so debounced `after` callbacks can run."""
    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.005)
    root.update()


def _build(root, renderer, **kwargs) -> ScrollableImagePreview:
    preview = ScrollableImagePreview(root, render=renderer, resize_debounce_ms=kwargs.pop("debounce", 20), **kwargs)
    preview.pack(fill="both", expand=True)
    root.update()
    return preview


def test_nothing_is_rendered_before_the_first_refresh(root):
    renderer = _Renderer()
    _build(root, renderer)
    root.geometry("500x300")
    _settle(root)
    assert renderer.widths == []


def test_render_width_follows_window_width_changes(root):
    renderer = _Renderer()
    preview = _build(root, renderer)
    preview.refresh()
    first = renderer.widths[-1]

    root.geometry("520x300")
    _settle(root)

    assert len(renderer.widths) == 2
    assert renderer.widths[-1] == first + 120


def test_height_change_does_not_render(root):
    renderer = _Renderer()
    preview = _build(root, renderer)
    preview.refresh()

    root.geometry("400x180")
    _settle(root)
    root.geometry("400x420")
    _settle(root)

    assert len(renderer.widths) == 1


def test_scrollbar_toggle_does_not_change_render_width_or_rerender(root):
    tall = {"value": False}
    renderer = _Renderer(height_for=lambda width: 2000 if tall["value"] else 50)
    preview = _build(root, renderer)
    preview.refresh()
    assert preview._scrollbar_visible is False
    width_without_scrollbar = renderer.widths[-1]

    tall["value"] = True
    preview.refresh()
    _settle(root)
    assert preview._scrollbar_visible is True
    tall["value"] = False
    preview.refresh()
    _settle(root)

    assert preview._scrollbar_visible is False
    assert renderer.widths == [width_without_scrollbar] * 3


def test_rapid_width_changes_are_debounced_into_one_render(root):
    renderer = _Renderer()
    preview = _build(root, renderer, debounce=150)
    preview.refresh()

    for width in (420, 440, 460, 480):
        root.geometry(f"{width}x300")
        root.update()
    _settle(root, 300)

    assert len(renderer.widths) == 2
    assert renderer.widths[-1] == preview.render_width()


def test_width_change_below_two_pixels_does_not_render(root):
    renderer = _Renderer()
    preview = _build(root, renderer)
    preview.refresh()

    root.geometry("401x300")
    _settle(root)

    assert len(renderer.widths) == 1


def test_pending_render_is_cancelled_on_destroy(root):
    renderer = _Renderer()
    preview = _build(root, renderer, debounce=150)
    preview.refresh()

    root.geometry("500x300")
    root.update()
    assert preview._pending_render is not None
    preview.destroy()
    _settle(root, 300)

    assert len(renderer.widths) == 1


def test_render_returning_none_clears_the_image(root):
    renderer = _Renderer()
    preview = _build(root, renderer)
    preview.refresh()
    assert str(preview.image_label.cget("image")) != ""

    renderer.return_none = True
    preview.refresh()

    assert str(preview.image_label.cget("image")) == ""


def test_refresh_propagates_render_exceptions(root):
    renderer = _Renderer()
    preview = _build(root, renderer)
    renderer.raise_error = RuntimeError("kaputt")

    with pytest.raises(RuntimeError, match="kaputt"):
        preview.refresh()


def test_resize_render_exception_reaches_report_callback_exception(root, monkeypatch):
    reported: list[BaseException] = []
    monkeypatch.setattr(root, "report_callback_exception", lambda exc, value, tb: reported.append(value))
    renderer = _Renderer()
    preview = _build(root, renderer)
    preview.refresh()
    renderer.raise_error = RuntimeError("resize kaputt")

    root.geometry("520x300")
    _settle(root)

    assert [str(error) for error in reported] == ["resize kaputt"]


def test_refresh_scroll_to_top_and_keyboard_scroll(root):
    renderer = _Renderer(height_for=lambda width: 3000)
    preview = _build(root, renderer)
    preview.refresh()
    _settle(root)

    preview.scroll(3, "pages")
    root.update()
    assert preview.canvas.yview()[0] > 0

    preview.refresh(scroll_to_top=True)
    root.update()
    assert preview.canvas.yview()[0] == 0


def test_scroll_is_noop_without_overflow_and_rejects_unknown_unit(root):
    renderer = _Renderer(height_for=lambda width: 20)
    preview = _build(root, renderer)
    preview.refresh()
    _settle(root)

    preview.scroll(5, "units")
    root.update()
    assert preview.canvas.yview()[0] == 0

    with pytest.raises(ValueError):
        preview.scroll(1, "lines")


def test_initial_width_is_used_before_mapping(root):
    renderer = _Renderer()
    preview = ScrollableImagePreview(root, render=renderer, initial_width=333)
    preview.refresh()
    assert renderer.widths == [333]
