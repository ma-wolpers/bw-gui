"""Real-Tk tests for `CollapsibleSection` (collapsible LabelFrame with title-row arrow).

Reuses the session-scoped `_shared_tk_root` fixture (see `conftest.py`) and
tears down its children between tests, like `test_scrollable_frame.py`.
"""

from __future__ import annotations

import pytest

from bw_gui.runtime import widgets
from bw_gui.widgets import CollapsibleSection
from bw_gui.widgets.collapsible_section import ARROW_COLLAPSED, ARROW_EXPANDED


@pytest.fixture
def root(_shared_tk_root):
    for child in _shared_tk_root.winfo_children():
        child.destroy()
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


def _section(root, **kwargs):
    section = CollapsibleSection(root, "Diagnostik", **kwargs)
    section.pack(fill="x")
    widgets.Label(section.content, text="Inhalt").pack()
    root.update()
    return section


def test_expanded_by_default_and_header_is_labelwidget(root):
    section = _section(root)
    assert section.collapsed is False
    assert section._arrow.cget("text") == ARROW_EXPANDED
    assert section.content.winfo_manager() == "pack"
    assert str(section.cget("labelwidget")) == str(section._header)
    assert section.title == "Diagnostik"


def test_initially_collapsed_keeps_header_visible(root):
    section = _section(root, collapsed=True)
    assert section.content.winfo_manager() == ""
    assert section._arrow.cget("text") == ARROW_COLLAPSED
    assert section._header.winfo_ismapped()


def test_collapsed_section_shrinks_to_title_row_and_grows_back(root):
    """Regression: eingeklappt darf der Rahmen nicht die alte Höhe behalten (Tk-pack_forget-Eigenheit)."""
    section = CollapsibleSection(root, "Diagnostik")
    section.pack(fill="x")
    widgets.Frame(section.content, height=150, width=200).pack()
    root.update()
    expanded = section.winfo_height()
    header = section._header.winfo_reqheight()

    section.toggle()
    root.update()
    assert section.winfo_reqheight() <= header + 12
    assert section.winfo_height() <= header + 12 < expanded

    section.set_collapsed(False)
    root.update()
    assert section.winfo_height() == expanded


def test_initially_collapsed_section_is_small(root):
    section = CollapsibleSection(root, "Struktur", collapsed=True)
    section.pack(fill="x")
    widgets.Frame(section.content, height=150, width=200).pack()
    root.update()
    assert section.winfo_height() <= section._header.winfo_reqheight() + 12


def test_set_collapsed_does_not_call_callback(root):
    calls = []
    section = _section(root, on_toggle=calls.append)
    section.set_collapsed(True)
    section.set_collapsed(False)
    assert calls == []
    assert section.content.winfo_manager() == "pack"


def test_click_on_arrow_and_title_and_toggle_call_callback_with_requested_state(root):
    calls = []
    section = _section(root, on_toggle=calls.append)
    section._arrow.invoke()
    assert calls == [True] and section.collapsed
    section._title.event_generate("<Button-1>")
    root.update()
    assert calls == [True, False] and not section.collapsed
    section.toggle()
    assert calls == [True, False, True]


def test_callback_exception_rolls_back_widget_state_and_reraises(root):
    def reject(_requested):
        raise RuntimeError("nein")

    section = _section(root, on_toggle=reject)
    with pytest.raises(RuntimeError):
        section.toggle()
    assert section.collapsed is False
    assert section._arrow.cget("text") == ARROW_EXPANDED
    assert section.content.winfo_manager() == "pack"


def test_collapsed_is_read_only(root):
    section = _section(root)
    with pytest.raises(AttributeError):
        section.collapsed = True


@pytest.mark.parametrize("option", ["labelwidget", "text"])
def test_reserved_options_are_rejected(root, option):
    with pytest.raises(TypeError):
        CollapsibleSection(root, "X", **{option: "y"})
    section = _section(root)
    with pytest.raises(TypeError):
        section.configure(**{option: "y"})
    with pytest.raises(TypeError):
        section[option] = "y"


def test_other_frame_options_pass_through(root):
    section = _section(root, padding=4)
    assert [str(value) for value in section.cget("padding")] in (["4"], ["4", "4", "4", "4"])
