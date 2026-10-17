"""Tests for bw_gui.testing.tk_usage_guard (one fixture per detected pattern and per allowed case)."""

from __future__ import annotations

import pytest

from bw_gui.testing.tk_usage_guard import find_offenders, opt_outs, scan_source


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ('w.bind("<Configure>", f)', "bind"),
        ('w.bind(\n    "<FocusOut>",\n    f,\n)', "bind"),
        ('canvas.tag_bind(tag, "<Button-1>", f)', "bind"),
        ('root.bind_all("<<Paste>>", f)', "bind"),
        ('w.unbind("<Return>")', "bind"),
        ('SEQUENCES = ("<Control-z>",)', "sequence"),
        ('x = "<<ListboxSelect>>"', "sequence"),
        ("def f(e):\n    return 'break'", "break"),
        ("def f(e):\n    return e.keysym", "event-field"),
        ("def f(e):\n    return e.delta", "event-field"),
        ("def f(e):\n    return e.char", "event-field"),
        ("tree.selection_set(item)", "selection"),
        ("lb.select_set(0, 'end')", "selection"),
        ("lb.selection_clear(0, 'end')", "selection"),
        ("tree.selection_remove(*tree.selection())", "selection"),
        ("combo.current(2)", "selection"),
        ('tree.selection("set", item)', "selection"),
    ],
)
def test_detected_patterns(code, rule):
    assert [r for _line, r in scan_source(code)] == [rule]


@pytest.mark.parametrize(
    "code",
    [
        '"""Docstring with widget.bind("<Return>") inside."""',
        'html = "<td>" + "<br>" + "<b>"',
        'spec = KeySpec.char("z")',
        "entry.selection_clear()",
        "index = combo.current()",
        "items = tree.selection()",
        'w.bind("<Configure>", f)  # bw-tk: measured layout hook, see doc',
    ],
)
def test_allowed_cases(code):
    assert scan_source(code) == []


def test_find_offenders_and_opt_outs(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "good.py").write_text("x = 1\n", encoding="utf-8")
    (app / "bad.py").write_text('w.bind("<Destroy>", f)\nw.bind("<Map>", g)  # bw-tk: reason\n', encoding="utf-8")
    assert find_offenders(app) == {"app\\bad.py" if "\\" in str(app) else "app/bad.py": [(1, "bind")]}
    assert list(opt_outs(app).values()) == [[2]]
