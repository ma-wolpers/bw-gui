"""Toggle contract for menu surfaces: custom menu items and native-menu helpers."""

from __future__ import annotations

import pytest

from bw_gui.menu import CustomMenuBar, MenuItem, add_menu_checkbox, add_menu_switch
from bw_gui.menu._toggle_glyphs import menu_item_command
from bw_gui.runtime import ui
from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import DEFAULT_THEME
from bw_gui.theming._toggle_styles import toggle_image


@pytest.fixture
def root(_shared_tk_root, monkeypatch):
    configure_ttk_theme(_shared_tk_root, DEFAULT_THEME)
    reported: list[BaseException] = []
    monkeypatch.setattr(_shared_tk_root, "report_callback_exception",
                        lambda exc_type, exc, tb: reported.append(exc))
    _shared_tk_root.reported = reported
    yield _shared_tk_root
    for child in _shared_tk_root.winfo_children():
        child.destroy()


# --- custom menu items -----------------------------------------------------------------

@pytest.mark.parametrize("item_type, checked, mixed, target, expected", [
    ("switch", False, False, None, True),
    ("switch", True, False, None, False),
    ("switch", True, True, None, False),     # mixed -> default target False
    ("checkbox", False, True, None, True),   # mixed -> default target True
    ("switch", False, True, True, True),     # explicit target
])
def test_menu_item_click_delivers_requested_value(item_type, checked, mixed, target, expected) -> None:
    received: list[bool] = []
    item = MenuItem(type=item_type, label="x", checked=checked, mixed=mixed,
                    mixed_click_target=target, on_toggle=received.append)
    menu_item_command(item)()
    assert received == [expected]


def test_legacy_checkbox_item_keeps_its_command() -> None:
    calls: list[str] = []
    item = MenuItem(type="checkbox", label="x", checked=True, command=lambda: calls.append("legacy"))
    menu_item_command(item)()
    assert calls == ["legacy"]


def test_custom_menu_renders_shared_glyphs(root) -> None:
    bar = CustomMenuBar(root, (), theme_key=DEFAULT_THEME)
    anchor = ui.Label(root, text="anchor")
    anchor.pack()
    items = (
        MenuItem(type="switch", label="Grid", checked=True, on_toggle=lambda _: None),
        MenuItem(type="checkbox", label="Partly", mixed=True, on_toggle=lambda _: None),
    )
    bar.open_popup(anchor, items, 0, "view")
    rows = [row for row, _item in bar._popup_stack[0]._bw_menu_navigable_rows]
    assert rows[0].cget("image") == str(toggle_image(root, "switch", "on-rest"))
    assert rows[1].cget("image") == str(toggle_image(root, "checkbox", "mixed-rest"))
    assert rows[0].cget("text") == "Grid"
    bar.close_all_popups()


# --- native menus ----------------------------------------------------------------------

def test_native_switch_invoke_delivers_requested_value(root) -> None:
    menu = ui.Menu(root, tearoff=0)
    var = ui.BooleanVar(master=root, value=False)
    received: list[bool] = []
    entry = add_menu_switch(menu, label="Grid", variable=var, on_change=received.append)
    menu.invoke(entry.index)
    assert received == [True] and var.get() is True
    assert menu.entrycget(entry.index, "image") == str(toggle_image(root, "switch", "on-rest"))


def test_native_programmatic_changes_fire_no_callback(root) -> None:
    menu = ui.Menu(root, tearoff=0)
    var = ui.BooleanVar(master=root, value=False)
    received: list[bool] = []
    entry = add_menu_switch(menu, label="Grid", variable=var, on_change=received.append)
    var.set(True)
    entry.set_mixed(True)
    assert received == []
    assert menu.entrycget(entry.index, "image") == str(toggle_image(root, "switch", "mixed-rest"))
    entry.set_mixed(False)
    assert var.get() is True


def test_native_mixed_click_and_checkbox_default_target(root) -> None:
    menu = ui.Menu(root, tearoff=0)
    var = ui.BooleanVar(master=root, value=False)
    received: list[bool] = []
    entry = add_menu_checkbox(menu, label="All", variable=var, on_select=received.append, mixed=True)
    menu.invoke(entry.index)
    assert received == [True] and not entry.is_mixed()


def test_native_reentrant_click_is_ignored(root) -> None:
    menu = ui.Menu(root, tearoff=0)
    var = ui.BooleanVar(master=root, value=False)
    calls: list[bool] = []

    def on_change(requested: bool) -> None:
        calls.append(requested)
        before = var.get()
        menu.invoke(entry.index)
        assert var.get() == before

    entry = add_menu_switch(menu, label="Grid", variable=var, on_change=on_change)
    menu.invoke(entry.index)
    assert calls == [True] and root.reported == []


def test_native_exception_rolls_back(root) -> None:
    menu = ui.Menu(root, tearoff=0)
    var = ui.BooleanVar(master=root, value=False)

    def failing(_requested: bool) -> None:
        raise RuntimeError("effect failed")

    entry = add_menu_switch(menu, label="Grid", variable=var, on_change=failing, mixed=True, mixed_click_target=True)
    menu.invoke(entry.index)
    assert [type(exc) for exc in root.reported] == [RuntimeError]
    assert var.get() is False and entry.is_mixed()


def test_native_switch_requires_on_change(root) -> None:
    menu = ui.Menu(root, tearoff=0)
    with pytest.raises(TypeError):
        add_menu_switch(menu, label="x", variable=ui.BooleanVar(master=root), on_change=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        add_menu_checkbox(menu, label="x", variable=ui.IntVar(master=root))
