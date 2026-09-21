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


def test_scrollbar_hidden_when_content_fits_viewport(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 2)
    root.update()

    assert not frame._scrollbar.winfo_ismapped()


def test_scrollbar_appears_when_content_grows_to_overflow(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 2)
    root.update()
    assert not frame._scrollbar.winfo_ismapped()

    _add_rows(frame, 40)
    root.update()

    assert frame._scrollbar.winfo_ismapped()


def test_scrollbar_disappears_and_resets_view_when_content_shrinks_back(root):
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    rows = [widgets.Label(frame.content, text=f"row {i}", padding=(0, 8)) for i in range(40)]
    for row in rows:
        row.pack(fill="x")
    root.update()
    assert frame._scrollbar.winfo_ismapped()

    frame.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert frame.canvas.yview()[0] > 0.0

    for row in rows[2:]:
        row.destroy()
    root.update()

    assert not frame._scrollbar.winfo_ismapped()
    assert frame.canvas.yview() == (0.0, 1.0)


def test_scrollbar_visibility_reacts_to_viewport_resize(root):
    """Shrinking/growing the window (not the content) must flip visibility too."""
    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    _add_rows(frame, 2)
    root.update()
    assert not frame._scrollbar.winfo_ismapped(), "2 short rows should fit the default 150px-tall test window"

    root.geometry("300x60+0+0")
    root.update()
    assert frame._scrollbar.winfo_ismapped(), "shrinking the viewport below content height must reveal the scrollbar"

    root.geometry("300x600+0+0")
    root.update()
    assert not frame._scrollbar.winfo_ismapped(), "growing the viewport back past content height must hide it again"


def test_mousewheel_dispatch_is_not_registered_twice_after_all_instances_die_and_a_new_one_is_created(root):
    """Regression: `bind_all` must stay registered exactly once per interpreter, forever.

    Destroying every `ScrollableFrame` under an interpreter used to delete
    its whole registry entry; the next instance created afterwards then
    saw an empty registry and re-registered `bind_all`, stacking a second,
    independent handler onto the same "all" bindtag - one physical wheel
    click would then scroll by two units instead of one (or, since
    `_dispatch_mousewheel` would then run the same resolution twice for
    one event, produce some other observably-wrong scroll amount). Only
    ever one instance is alive/packed at a time here - packing a second
    `fill="both", expand=True` widget into `root` *alongside* a still-live
    first one would squeeze the second to zero size instead of testing
    the actual regression, so each instance is fully destroyed before the
    next is created and packed.
    """
    first = ScrollableFrame(root)
    first.pack(fill="both", expand=True)
    _add_rows(first, 40)
    root.update()

    before1 = first.canvas.yview()[0]
    first.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    step_before_recreate = first.canvas.yview()[0] - before1
    first.destroy()
    root.update()

    second = ScrollableFrame(root)
    second.pack(fill="both", expand=True)
    _add_rows(second, 40)
    root.update()

    before2 = second.canvas.yview()[0]
    second.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    step_after_recreate = second.canvas.yview()[0] - before2

    assert step_after_recreate == pytest.approx(step_before_recreate), (
        "one wheel click scrolled by a different amount after the only live instance was destroyed "
        "and a new one created - bind_all was likely registered more than once for the same interpreter"
    )


def test_refresh_chrome_keeps_canvas_borderless(root):
    """`refresh_chrome()` is what `ScrollablePopupWindow.apply_theme()` calls after a theme switch."""
    frame = ScrollableFrame(root)
    frame.canvas.configure(highlightthickness=3)

    frame.refresh_chrome()

    assert int(frame.canvas["highlightthickness"]) == 0


def _add_columns(frame: ScrollableFrame, count: int) -> list:
    labels = [widgets.Label(frame.content, text=f"tab {i:02d} xxxxxxxx", padding=(8, 4)) for i in range(count)]
    for label in labels:
        label.pack(side="left")
    return labels


def test_horizontal_rejects_unknown_orient(root):
    with pytest.raises(ValueError):
        ScrollableFrame(root, orient="diagonal")


def test_horizontal_content_keeps_requested_width_and_scrollbar_appears_on_overflow(root):
    frame = ScrollableFrame(root, orient="horizontal")
    frame.pack(fill="x")
    _add_columns(frame, 12)
    root.update()

    assert frame.content.winfo_width() == frame.content.winfo_reqwidth() > frame.canvas.winfo_width()
    assert frame._scrollbar.winfo_ismapped()
    assert int(frame.canvas["height"]) == frame.content.winfo_reqheight()


def test_horizontal_frame_shrink_wraps_content_and_hides_scrollbar_when_it_fits(root):
    frame = ScrollableFrame(root, orient="horizontal")
    frame.pack(fill="x")
    _add_columns(frame, 2)
    root.update()

    assert frame.canvas.winfo_width() == frame.content.winfo_reqwidth() < frame.winfo_width()
    assert not frame._scrollbar.winfo_ismapped()


def test_horizontal_mousewheel_scrolls_x_only_while_overflowing(root):
    frame = ScrollableFrame(root, orient="horizontal")
    frame.pack(fill="x")
    labels = _add_columns(frame, 12)
    root.update()

    before = frame.canvas.xview()[0]
    frame.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert frame.canvas.xview()[0] > before

    for label in labels[2:]:
        label.destroy()
    root.update()
    assert frame.canvas.xview() == (0.0, 1.0)
    frame.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert frame.canvas.xview() == (0.0, 1.0)


def test_horizontal_see_x_range_scrolls_only_when_needed(root):
    frame = ScrollableFrame(root, orient="horizontal")
    frame.pack(fill="x")
    labels = _add_columns(frame, 12)
    root.update()

    last = labels[-1]
    left, right = last.winfo_x(), last.winfo_x() + last.winfo_width()
    assert right > frame.canvas.winfo_width()

    frame.see_x_range(left, right)
    root.update()
    view_left = frame.canvas.canvasx(0)
    assert view_left + frame.canvas.winfo_width() >= right - 1

    settled = frame.canvas.xview()[0]
    frame.see_x_range(left, right)
    root.update()
    assert frame.canvas.xview()[0] == settled

    first = labels[0]
    frame.see_x_range(first.winfo_x(), first.winfo_x() + first.winfo_width())
    root.update()
    assert frame.canvas.canvasx(0) <= first.winfo_x()


def test_see_x_range_is_rejected_for_vertical_orientation(root):
    frame = ScrollableFrame(root)
    with pytest.raises(RuntimeError):
        frame.see_x_range(0, 10)
