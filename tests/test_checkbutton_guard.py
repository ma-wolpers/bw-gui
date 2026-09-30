"""Tests for the consumer guard against raw Tk/ttk checkbuttons (synthetic snippets only)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bw_gui.testing.checkbutton_guard import checkbutton_lines, find_offenders


def _lines(tmp_path: Path, source: str) -> list[int]:
    path = tmp_path / "snippet.py"
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return checkbutton_lines(path)


@pytest.mark.parametrize("source, expected", [
    ("from tkinter import ttk\nttk.Checkbutton(root)\n", [2]),
    ("import tkinter as tk\ntk.Checkbutton(root)\n", [2]),
    ("import tkinter.ttk\ntkinter.ttk.Checkbutton(root)\n", [2]),
    ("import tkinter.ttk as t\nt.Checkbutton(root)\n", [2]),
    ("from bw_gui.runtime import widgets\nwidgets.Checkbutton(root)\n", [2]),
    ("from bw_gui.runtime import widgets as w\nw.Checkbutton(root)\n", [2]),
    ("from bw_gui.runtime import ui\nui.Checkbutton(root)\n", [2]),
    ("from bw_gui.runtime.primitives import widgets\nwidgets.Checkbutton(root)\n", [2]),
    ("import bw_gui\nbw_gui.runtime.widgets.Checkbutton(root)\n", [2]),
    ("from tkinter import Checkbutton\nCheckbutton(root)\n", [1, 2]),
    ("from tkinter.ttk import Checkbutton as CB\nCB(root)\n", [1, 2]),
    ("from bw_gui.runtime.primitives import Checkbutton\nCheckbutton(root)\n", [1, 2]),
    ("from bw_gui.runtime.primitives import Checkbutton as CB\nCB(root)\n", [1, 2]),
    ("from bw_gui.runtime import Checkbutton\n", [1]),
    ("from tkinter.ttk import *\nCheckbutton(root)\n", [1, 2]),
    ("from tkinter import ttk\nclass Box(ttk.Checkbutton):\n    pass\n", [2]),
    ("from bw_gui.runtime.primitives import Checkbutton as CB\nclass Box(CB):\n    pass\n", [1, 2]),
    ("menu.add_checkbutton(label='x')\n", [1]),
    ("menu.insert_checkbutton(0, label='x')\n", [1]),
    ("menu.add('checkbutton', label='x')\n", [1]),
    ("menu.insert(2, 'checkbutton', label='x')\n", [1]),
    ("root.tk.call('ttk::checkbutton', '.c')\n", [1]),
    ("def build():\n    from tkinter import ttk\n    return ttk.Checkbutton(root)\n", [3]),
])
def test_flagged_forms(tmp_path: Path, source: str, expected: list[int]) -> None:
    assert _lines(tmp_path, source) == expected


@pytest.mark.parametrize("source", [
    "from bw_gui.widgets import Checkbox, Switch\nCheckbox(root, text='x', variable=v)\n",
    "from mylib import Checkbutton\nCheckbutton(root)\n",
    "import mylib\nmylib.Checkbutton(root)\n",
    "self.widgets.Checkbutton(root)\n",
    "from tkinter import ttk\ngetattr(ttk, 'Checkbutton')(root)\n",
    "from .compat import ttk\nttk.Checkbutton(root)\n",
    "cls = factory()\ncls(root)\n",
    "menu.add('command', label='x')\n",
    "menu.add(kind, label='x')\n",
    "root.tk.call('ttk::button', '.b')\n",
    "from bw_gui.menu import add_menu_switch\nadd_menu_switch(menu, label='x', variable=v, on_change=f)\n",
])
def test_deliberately_unflagged_forms(tmp_path: Path, source: str) -> None:
    assert _lines(tmp_path, source) == []


def test_find_offenders_reports_relative_paths(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "ui").mkdir(parents=True)
    (app / "ui" / "bad.py").write_text("from tkinter import ttk\nttk.Checkbutton(None)\n", encoding="utf-8")
    (app / "ok.py").write_text("﻿x = 1\n", encoding="utf-8")  # BOM is tolerated
    assert find_offenders(app) == {str(Path("app") / "ui" / "bad.py"): [2]}


def test_bw_gui_itself_uses_no_raw_checkbutton_outside_the_toggle_widgets() -> None:
    src = Path(__file__).resolve().parents[1] / "src" / "bw_gui"
    offenders = find_offenders(src)
    # The widgets themselves are the one place that wraps ttk.Checkbutton.
    toggles = str(Path("bw_gui") / "widgets" / "toggles.py")
    assert set(offenders) == {toggles}, offenders


def test_bw_gui_widgets_is_the_widget_package_not_the_ttk_alias() -> None:
    import importlib

    import bw_gui
    import bw_gui.widgets.toggles as toggles

    package = importlib.import_module("bw_gui.widgets")
    assert bw_gui.widgets is package
    assert package.Checkbox is toggles.Checkbox
    assert not hasattr(bw_gui, "ui") and not hasattr(bw_gui, "fonts")
