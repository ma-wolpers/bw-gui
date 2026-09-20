"""Real-Tk geometry/behavior tests for `ScrollableFrame` (bw-gui scroll SSOT).

Uses an actual, visible/deiconified `tk.Tk()` root rather than fakes -
`ScrollableFrame`'s whole point is geometry management (scrollregion,
itemconfigure width, PanedWindow interplay), which cannot be verified
against a stub. A *withdrawn* root gives unreliable geometry/focus values
(lesson from an earlier, separate investigation into Ctrl+Z keybinding
behavior in this same GUI stack) - the fixture here keeps the root visible
and calls `update()` after every geometry-affecting action so pending
`<Configure>` events have actually been processed before assertions run.

Reuses the session-scoped `_shared_tk_root` fixture (`conftest.py`, see its
docstring for why: creating/destroying multiple real `Tk()` interpreters in
one process was intermittently flaky on this Windows setup) and tears down
its children between tests for a clean slate.
"""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui, widgets
from bw_gui.widgets.scrollable_frame import ScrollableFrame


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    _shared_tk_root.geometry("300x150+0+0")
    _shared_tk_root.update()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _add_rows(frame: ScrollableFrame, count: int) -> None:
    for i in range(count):
        widgets.Label(frame.content, text=f"row {i}", padding=(0, 8)).pack(fill="x")


def test_scrollregion_grows_with_content_height(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    root.update()

    _add_rows(frame, 3)
    root.update()
    small_region = frame.canvas.bbox("all")

    _add_rows(frame, 30)
    root.update()
    large_region = frame.canvas.bbox("all")

    assert large_region[3] - large_region[1] > small_region[3] - small_region[1]
    assert tuple(map(int, frame.canvas["scrollregion"].split())) == large_region


def test_content_width_follows_canvas_width_on_resize(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 5)
    root.update()

    root.geometry("500x150+0+0")
    root.update()

    canvas_width = frame.canvas.winfo_width()
    applied_width = int(frame.canvas.itemcget(frame._content_window, "width"))
    assert applied_width == canvas_width


def test_mousewheel_scrolls_when_content_taller_than_viewport(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 40)
    root.update()

    before = frame.canvas.yview()[0]
    frame.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    after = frame.canvas.yview()[0]

    assert after > before


def test_mousewheel_is_noop_when_content_fits_viewport(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 2)
    root.update()

    before = frame.canvas.yview()
    frame.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    after = frame.canvas.yview()

    assert after == before
    assert before == (0.0, 1.0)


def test_embedded_in_panedwindow_keeps_correct_outer_dimensions_after_resize(root):
    paned = widgets.PanedWindow(root, orient=ui.HORIZONTAL)
    paned.pack(fill="both", expand=True)
    left = widgets.Frame(paned)
    paned.add(left, weight=1)
    frame = ScrollableFrame(paned)
    paned.add(frame, weight=2)
    _add_rows(frame, 5)
    root.update()

    root.geometry("600x150+0+0")
    root.update()
    paned.sashpos(0, 150)
    root.update()

    pane_width = frame.winfo_width()
    assert pane_width > 0
    assert frame.canvas.winfo_width() <= pane_width
    applied_width = int(frame.canvas.itemcget(frame._content_window, "width"))
    assert applied_width == frame.canvas.winfo_width()


def test_two_simultaneous_instances_do_not_interfere(root):
    paned = widgets.PanedWindow(root, orient=ui.HORIZONTAL)
    paned.pack(fill="both", expand=True)
    frame_a = ScrollableFrame(paned)
    frame_b = ScrollableFrame(paned)
    paned.add(frame_a, weight=1)
    paned.add(frame_b, weight=1)
    _add_rows(frame_a, 40)
    _add_rows(frame_b, 40)
    root.update()

    a_before = frame_a.canvas.yview()[0]
    b_before = frame_b.canvas.yview()[0]

    frame_a.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert frame_a.canvas.yview()[0] > a_before
    assert frame_b.canvas.yview()[0] == b_before

    frame_b.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    b_after_own_scroll = frame_b.canvas.yview()[0]
    assert b_after_own_scroll > b_before

    # Scrolling A again must still only move A, not re-trigger B.
    frame_a.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert frame_b.canvas.yview()[0] == b_after_own_scroll


def test_mousewheel_over_child_widget_of_content_scrolls_owning_instance(root):
    """A wheel event whose target is nested inside `.content` (not the bare canvas) must still resolve."""
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 40)
    root.update()
    child_label = widgets.Label(frame.content, text="deeply nested")
    child_label.pack()
    root.update()

    before = frame.canvas.yview()[0]
    child_label.event_generate("<MouseWheel>", delta=-120)
    root.update()
    after = frame.canvas.yview()[0]

    assert after > before


def test_refresh_chrome_keeps_canvas_borderless(root):
    """`refresh_chrome()` is what `ScrollablePopupWindow.apply_theme()` calls after a theme switch."""
    frame = ScrollableFrame(root)
    frame.canvas.configure(highlightthickness=3)

    frame.refresh_chrome()

    assert int(frame.canvas["highlightthickness"]) == 0
