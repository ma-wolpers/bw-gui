"""Real-Tk tests for ``ResizableSideOverlay``, ``ZoomableDocText`` and ``configure_doc_text_theme``.

Overlay: show/hide/close, width clamping to ``[min_width, parent*max_ratio]``
(also after a parent resize) and the grip drag lifecycle (live width, final
``on_width_changed``). Doc view: rendering replaces content read-only,
Ctrl+wheel zooms within the range and reports it, the plain wheel stays
unhandled (native ``Text`` scrolling), theme switches re-colour. Uses the
session-scoped real Tk root (``conftest.py``); events via ``event_generate``.
"""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import get_theme
from bw_gui.widgets import (
    HeadingEvent,
    ParagraphEvent,
    ResizableSideOverlay,
    TextRun,
    ZoomableDocText,
    configure_doc_text_theme,
)

CTRL = 0x0004


@pytest.fixture
def parent(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    _shared_tk_root.geometry("800x400+0+0")
    frame = ui.Frame(_shared_tk_root)
    frame.pack(fill="both", expand=True)
    _shared_tk_root.update()
    yield frame
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _overlay(parent, **kwargs):
    defaults = {"title": "Vorschau", "width": 300, "min_width": 200, "max_ratio": 0.5}
    defaults.update(kwargs)
    overlay = ResizableSideOverlay(parent, **defaults)
    overlay.show()
    parent.update()
    return overlay


def test_show_places_right_edge_full_height_and_hide_forgets(parent):
    overlay = _overlay(parent)
    assert overlay.is_visible
    assert overlay.winfo_width() == 300
    assert overlay.winfo_height() == parent.winfo_height()
    assert overlay.winfo_x() + overlay.winfo_width() == parent.winfo_width()
    overlay.hide()
    parent.update()
    assert not overlay.is_visible
    assert not overlay.winfo_ismapped()


def test_close_button_hides_and_reports(parent):
    closed = []
    overlay = _overlay(parent, on_close=lambda: closed.append(True))
    overlay.close_button.invoke()
    assert closed == [True]
    assert not overlay.is_visible


def test_width_is_clamped_to_parent_ratio_and_minimum(parent):
    assert _overlay(parent, width=10_000).effective_width() == 400
    assert _overlay(parent, width=50).effective_width() == 200


def test_parent_shrink_reclamps_visible_overlay(parent):
    overlay = _overlay(parent, width=380)
    parent.winfo_toplevel().geometry("600x400")
    parent.update()
    assert overlay.winfo_width() == 300


def test_grip_drag_resizes_live_and_reports_final_width(parent):
    widths = []
    overlay = _overlay(parent, on_width_changed=widths.append)
    grip = overlay._grip
    grip.event_generate("<ButtonPress-1>", x=1, y=5, rootx=500, rooty=50)
    grip.event_generate("<B1-Motion>", x=1, y=5, rootx=450, rooty=50, state=0x100)
    parent.update()
    assert overlay.winfo_width() == 350
    grip.event_generate("<ButtonRelease-1>", x=1, y=5, rootx=420, rooty=50)
    parent.update()
    assert widths == [380]
    assert overlay.width == 380


def _doc(parent, **kwargs):
    view = ZoomableDocText(parent, **kwargs)
    view.pack(fill="both", expand=True)
    parent.update()
    return view


def test_render_replaces_content_and_stays_read_only(parent):
    view = _doc(parent)
    view.render([HeadingEvent(level=1, runs=(TextRun("Titel"),)), ParagraphEvent(runs=(TextRun("Text"),))])
    view.render([ParagraphEvent(runs=(TextRun("Neu"),))])
    assert view.text.get("1.0", "end").strip() == "Neu"
    assert str(view.text.cget("state")) == "disabled"


def test_ctrl_wheel_zooms_within_range_and_reports(parent):
    sizes = []
    view = _doc(parent, base_size=10, min_size=9, max_size=11, on_zoom_changed=sizes.append)
    for _ in range(3):
        view.text.event_generate("<MouseWheel>", delta=120, state=CTRL)
    assert view.base_size == 11
    view.text.event_generate("<MouseWheel>", delta=-240, state=CTRL)
    assert view.base_size == 9
    assert sizes == [11, 9]
    assert view.text.tag_cget("body", "font").endswith("9")


def test_plain_wheel_is_left_to_native_scrolling(parent):
    view = _doc(parent, base_size=10)
    view.render([ParagraphEvent(runs=(TextRun("Zeile\n" * 200),))])
    parent.update()
    view.text.event_generate("<MouseWheel>", delta=-120)
    parent.update()
    assert view.base_size == 10
    assert view.text.yview()[0] > 0.0


def test_theme_switch_recolours_doc_view(parent):
    view = _doc(parent)
    configure_ttk_theme(parent.winfo_toplevel(), "porcelain")
    try:
        assert view.text.tag_cget("body", "foreground") == get_theme("porcelain")["fg_primary"]
    finally:
        configure_ttk_theme(parent.winfo_toplevel(), None)


def test_configure_doc_text_theme_sets_fonts_and_colours(parent):
    text = ui.Text(parent)
    configure_doc_text_theme(text, "mono_day", base_size=12)
    assert str(text.cget("background")) == get_theme("mono_day")["bg_surface"]
    assert text.tag_cget("h1", "font").endswith("20 bold")
