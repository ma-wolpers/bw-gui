"""Classic Tk widgets never keep Tk's system colours (``theming._classic_widgets``).

The classes under test are discovered from ``tkinter`` itself, so a class the
table does not cover fails here instead of showing system grey in a dark theme.
Uses the session's shared Tk root; created Toplevels are withdrawn at once.
"""

from __future__ import annotations

import sys
import tkinter as tk

import pytest

from bw_gui.theming import configure_ttk_theme, theme_text
from bw_gui.theming._classic_widgets import CLASSIC_WIDGET_CONSTANTS, CLASSIC_WIDGET_TOKENS
from bw_gui.theming._theme_manager import get_theme

_DARK, _LIGHT = "mono_night", "mono_day"


def _classic_classes() -> list[type]:
    """Every classic widget class of ``tkinter`` (``OptionMenu`` is a ``Menubutton``)."""
    return [
        value for value in vars(tk).values()
        if isinstance(value, type) and issubclass(value, tk.BaseWidget)
        and value not in (tk.BaseWidget, tk.Widget, tk.OptionMenu)
    ]


@pytest.fixture
def root(_shared_tk_root):
    created: list[tk.Misc] = []

    def make(cls: type, **options) -> tk.Misc:
        widget = cls(_shared_tk_root, **options)
        if isinstance(widget, tk.Toplevel):
            widget.withdraw()
        created.append(widget)
        return widget

    _shared_tk_root.make = make
    yield _shared_tk_root
    for widget in created:
        widget.destroy()
    configure_ttk_theme(_shared_tk_root, _LIGHT)


def _color_options(widget: tk.Misc):
    """``(option, current value)`` of every colour option of *widget*."""
    for name, entry in widget.configure().items():
        if len(entry) == 5 and any(part in str(entry[1]).lower() for part in ("ground", "color")):
            yield name, str(entry[4])


def test_table_covers_every_classic_widget_class(root):
    tk_classes = {root.make(cls).winfo_class() for cls in _classic_classes()}
    assert tk_classes == set(CLASSIC_WIDGET_TOKENS)


@pytest.mark.parametrize("cls", _classic_classes(), ids=lambda cls: cls.__name__)
def test_new_widgets_start_in_theme_colours(root, cls):
    configure_ttk_theme(root, _DARK)
    widget = root.make(cls)
    theme = get_theme(_DARK)
    for option, token in CLASSIC_WIDGET_TOKENS[widget.winfo_class()].items():
        assert str(widget.cget(option.lower())) == theme[token], option
    for option, value in CLASSIC_WIDGET_CONSTANTS.get(widget.winfo_class(), {}).items():
        assert str(widget.cget(option.lower())) == value, option
    if sys.platform == "win32":
        leftovers = {name: value for name, value in _color_options(widget) if value.startswith("System")}
        assert leftovers == {}


def test_switch_rethemes_existing_widgets_but_keeps_explicit_colours(root):
    configure_ttk_theme(root, _LIGHT)
    paned = root.make(tk.PanedWindow)
    custom = root.make(tk.Label, background="#123456")
    configure_ttk_theme(root, _DARK)
    assert str(paned.cget("background")) == get_theme(_DARK)["bg_main"]
    assert str(paned.cget("sashrelief")) == "flat"
    assert str(custom.cget("background")) == "#123456"
    configure_ttk_theme(root, _LIGHT)
    assert str(paned.cget("background")) == get_theme(_LIGHT)["bg_main"]


def test_root_follows_the_theme(root):
    configure_ttk_theme(root, _DARK)
    assert str(root.cget("background")) == get_theme(_DARK)["bg_main"]


def test_theme_text_token_overrides_still_apply(root):
    configure_ttk_theme(root, _DARK)
    text = root.make(tk.Text)
    theme_text(text, bg_token="warning_soft", fg_token="fg_muted")
    theme = get_theme(_DARK)
    assert (str(text.cget("background")), str(text.cget("insertbackground"))) == (theme["warning_soft"], theme["fg_muted"])
    assert str(text.cget("selectbackground")) == theme["selection_bg"]
