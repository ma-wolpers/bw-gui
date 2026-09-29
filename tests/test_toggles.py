"""Contract tests for Checkbox and Switch (docs/TOGGLE_CONTRACT.md, section "API")."""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui
from bw_gui.theming import configure_ttk_theme
from bw_gui.theming._theme_manager import DEFAULT_THEME
from bw_gui.widgets import Checkbox, Switch


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


def _display(widget) -> bool:
    return bool(widget._display.get())


def _alternate(widget) -> bool:
    return widget.instate(["alternate"])


# --- constructor ----------------------------------------------------------------------

def test_switch_requires_on_change(root) -> None:
    var = ui.BooleanVar(master=root)
    with pytest.raises(TypeError):
        Switch(root, text="x", variable=var)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Switch(root, text="x", variable=var, on_change=None)  # type: ignore[arg-type]


@pytest.mark.parametrize("option", ["command", "style", "onvalue", "offvalue"])
def test_reserved_options_are_rejected(root, option: str) -> None:
    var = ui.BooleanVar(master=root)
    with pytest.raises(TypeError):
        Checkbox(root, text="x", variable=var, **{option: "a"})
    box = Checkbox(root, text="x", variable=var)
    with pytest.raises(TypeError):
        box.configure(**{option: "a"})
    with pytest.raises(TypeError):
        box[option] = "a"


def test_variable_must_be_booleanvar_and_text_non_empty(root) -> None:
    with pytest.raises(TypeError):
        Checkbox(root, text="x", variable=ui.IntVar(master=root))
    with pytest.raises(ValueError):
        Checkbox(root, text="  ", variable=ui.BooleanVar(master=root))


# --- click sequence -------------------------------------------------------------------

def test_click_sequence_trace_sees_only_requested_and_mixed_is_cleared(root) -> None:
    var = ui.BooleanVar(master=root, value=False)
    seen_by_trace: list[bool] = []
    var.trace_add("write", lambda *_: seen_by_trace.append(var.get()))
    inside: list[tuple[bool, bool, bool]] = []
    switch = Switch(root, text="x", variable=var,
                    on_change=lambda requested: inside.append((requested, var.get(), switch.is_mixed())))
    switch.invoke()
    assert inside == [(True, True, False)]
    assert seen_by_trace == [True]
    assert _display(switch) is True and var.get() is True


@pytest.mark.parametrize("cls, target", [(Switch, False), (Checkbox, True)])
def test_click_while_mixed_resolves_to_default_target(root, cls, target: bool) -> None:
    for start in (False, True):
        var = ui.BooleanVar(master=root, value=start)
        received: list[bool] = []
        kwargs = {"on_change": received.append} if cls is Switch else {"on_select": received.append}
        widget = cls(root, text="x", variable=var, mixed=True, **kwargs)
        widget.invoke()
        assert received == [target]
        assert var.get() is target and _display(widget) is target
        assert not widget.is_mixed() and not _alternate(widget)


def test_custom_mixed_click_target(root) -> None:
    var = ui.BooleanVar(master=root, value=False)
    received: list[bool] = []
    switch = Switch(root, text="x", variable=var, on_change=received.append, mixed=True, mixed_click_target=True)
    switch.invoke()
    assert received == [True]


def test_checkbox_without_on_select_still_toggles(root) -> None:
    var = ui.BooleanVar(master=root, value=False)
    box = Checkbox(root, text="x", variable=var)
    box.invoke()
    assert var.get() is True and _display(box) is True


# --- programmatic changes -------------------------------------------------------------

@pytest.mark.parametrize("mixed", [False, True])
def test_variable_set_fires_no_widget_callback_but_external_traces(root, mixed: bool) -> None:
    var = ui.BooleanVar(master=root, value=False)
    received: list[bool] = []
    external: list[bool] = []
    var.trace_add("write", lambda *_: external.append(var.get()))
    switch = Switch(root, text="x", variable=var, on_change=received.append, mixed=mixed)
    var.set(True)
    switch.set_mixed(not mixed)
    switch.set_mixed(mixed)
    assert received == []
    assert external == [True]
    assert _display(switch) is True


def test_callback_setting_variable_causes_no_recursion(root) -> None:
    var = ui.BooleanVar(master=root, value=False)
    calls: list[bool] = []

    def on_change(requested: bool) -> None:
        calls.append(requested)
        var.set(False)  # e.g. the effect was rejected by a domain rule

    switch = Switch(root, text="x", variable=var, on_change=on_change)
    switch.invoke()
    assert calls == [True]
    assert var.get() is False and _display(switch) is False


# --- mixed invariant ------------------------------------------------------------------

def test_mixed_and_variable_are_not_synchronised(root) -> None:
    var = ui.BooleanVar(master=root, value=True)
    switch = Switch(root, text="x", variable=var, on_change=lambda _: None, mixed=True)
    var.set(False)
    assert switch.is_mixed() and _alternate(switch)          # set keeps mixed
    var.set(True)
    switch.set_mixed(False)
    assert var.get() is True                                  # set_mixed keeps the value
    assert not _alternate(switch) and switch.instate(["selected"])


# --- re-entrancy ----------------------------------------------------------------------

@pytest.mark.parametrize("start_mixed", [False, True])
def test_reentrant_invoke_changes_nothing(root, start_mixed: bool) -> None:
    var = ui.BooleanVar(master=root, value=False)
    calls: list[bool] = []
    snapshots: list[tuple] = []

    def on_change(requested: bool) -> None:
        calls.append(requested)
        before = (_display(switch), switch.is_mixed(), _alternate(switch), var.get())
        switch.invoke()  # re-entrant
        after = (_display(switch), switch.is_mixed(), _alternate(switch), var.get())
        snapshots.append((before, after))

    switch = Switch(root, text="x", variable=var, on_change=on_change, mixed=start_mixed,
                    mixed_click_target=True)
    switch.invoke()
    assert len(calls) == 1
    before, after = snapshots[0]
    assert before == after
    assert _display(switch) == var.get()


# --- exceptions -----------------------------------------------------------------------

@pytest.mark.parametrize("start_mixed", [False, True])
def test_exception_rolls_back_value_and_mixed(root, start_mixed: bool) -> None:
    var = ui.BooleanVar(master=root, value=False)

    def failing(requested: bool) -> None:
        var.set(requested)  # changed before failing: rollback must still apply
        raise RuntimeError("effect failed")

    switch = Switch(root, text="x", variable=var, on_change=failing, mixed=start_mixed, mixed_click_target=True)
    switch.invoke()
    assert [type(exc) for exc in root.reported] == [RuntimeError]
    assert var.get() is False and _display(switch) is False
    assert switch.is_mixed() is start_mixed and _alternate(switch) is start_mixed


# --- disabled and lifecycle -----------------------------------------------------------

@pytest.mark.parametrize("mixed", [False, True])
def test_disabled_ignores_invoke(root, mixed: bool) -> None:
    var = ui.BooleanVar(master=root, value=False)
    received: list[bool] = []
    switch = Switch(root, text="x", variable=var, on_change=received.append, mixed=mixed)
    switch.state(["disabled"])
    switch.invoke()
    assert received == [] and var.get() is False
    assert switch.is_mixed() is mixed and _alternate(switch) is mixed


def test_destroy_removes_mirror_trace(root) -> None:
    var = ui.BooleanVar(master=root, value=False)
    traces_before = len(var.trace_info())
    switch = Switch(root, text="x", variable=var, on_change=lambda _: None)
    assert len(var.trace_info()) == traces_before + 1
    switch.destroy()
    assert len(var.trace_info()) == traces_before
    var.set(True)  # must not touch the destroyed widget


def test_matrix_cell_hides_text_but_keeps_label(root) -> None:
    box = Checkbox(root, text="Mathe · Verstecken", variable=ui.BooleanVar(master=root), show_text=False)
    assert box.cget("text") == ""
    assert box.label == "Mathe · Verstecken"
    with pytest.raises(ValueError):
        Checkbox(root, text="", variable=ui.BooleanVar(master=root), show_text=False)


def test_takes_keyboard_focus(root) -> None:
    switch = Switch(root, text="x", variable=ui.BooleanVar(master=root), on_change=lambda _: None)
    assert str(switch.cget("takefocus")) in ("", "ttk::takefocus")
