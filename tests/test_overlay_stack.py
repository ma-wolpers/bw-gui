"""Overlay stack: categories, presets, native modal invocations, lifecycle, diagnostics."""

from __future__ import annotations

import pytest

from bw_gui.contracts.popup import POPUP_KIND_MODAL, PopupPolicy
from bw_gui.dialogs.scrollable_popup import ScrollablePopupWindow
from bw_gui.dialogs.service import _run_modal
from bw_gui.runtime import ui
from bw_gui.runtime.overlay_stack import (
    OverlayCategory,
    blocking,
    modal_affecting_mode,
    overlay_state,
    register_overlay,
    unregistered_visible_toplevels,
)


@pytest.fixture
def root(_shared_tk_root):
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        if isinstance(child, ui.Toplevel):
            child.destroy()


def test_categories_and_presets(root):
    menu_top, tool_top = ui.Toplevel(root), ui.Toplevel(root)
    register_overlay(root, OverlayCategory.MENU, toplevel=menu_top)
    register_overlay(root, OverlayCategory.NON_MODAL_POPUP, toplevel=tool_top)
    tip = ui.Toplevel(root)
    register_overlay(root, OverlayCategory.TRANSIENT, toplevel=tip)
    state = overlay_state(root)
    assert state.menu_open and state.non_modal_popups == 1 and not state.modal_dialog
    assert blocking(root)() is False
    assert blocking(root, include_menus=True)() is True
    assert blocking(root, include_non_modal=True)() is True
    menu_top.destroy()
    tool_top.destroy()
    assert blocking(root, include_menus=True, include_non_modal=True)() is False  # transient never counts


def test_modal_affecting_mode_preset(root):
    top = ui.Toplevel(root)
    sub = register_overlay(root, OverlayCategory.MODAL_DIALOG, toplevel=top, policy=PopupPolicy("p", affects_mode=False))
    assert overlay_state(root).modal_dialog and not modal_affecting_mode(root)()
    sub.remove()
    register_overlay(root, OverlayCategory.MODAL_DIALOG, toplevel=top, policy=PopupPolicy("q", kind=POPUP_KIND_MODAL))
    assert modal_affecting_mode(root)()


def test_native_modal_invocation_without_toplevel(root):
    seen = []
    _run_modal(root, "Titel", lambda: seen.append(blocking(root)()))
    assert seen == [True] and not overlay_state(root).modal_dialog
    with pytest.raises(ZeroDivisionError):
        _run_modal(root, "Titel", lambda: 1 / 0)
    assert not overlay_state(root).modal_dialog  # removed also on exception


def test_toplevel_none_only_for_modal(root):
    with pytest.raises(ValueError):
        register_overlay(root, OverlayCategory.MENU, toplevel=None)


def test_scrollable_popup_registers_and_unregisters(root):
    popup = ScrollablePopupWindow(root, title="x", geometry="200x100", minsize=(100, 50))
    assert ScrollablePopupWindow.active_popup() is popup and overlay_state(root).modal_dialog
    popup.destroy()
    assert ScrollablePopupWindow.active_popup() is None and not overlay_state(root).modal_dialog


def test_diagnostics_reports_unregistered_visible_toplevel(root):
    stray = ui.Toplevel(root)
    stray.geometry("50x50+0+0")
    root.update()
    assert stray in unregistered_visible_toplevels(root)
    register_overlay(root, OverlayCategory.NON_MODAL_POPUP, toplevel=stray)
    assert stray not in unregistered_visible_toplevels(root)
