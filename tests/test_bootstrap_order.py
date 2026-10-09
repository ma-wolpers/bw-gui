"""Step 2-0 invariant: Tk() -> router installed -> first consumer code, nothing in between."""

from __future__ import annotations

import tkinter

import pytest

import bw_gui.runtime.key_router as key_router
from bw_gui.runtime.root_host import TkRootHost


@pytest.fixture
def spy(monkeypatch):
    events: list[str] = []
    real_init = tkinter.Tk.__init__
    real_install = key_router.install_router

    def _tk_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        events.append("Tk()")

    def _install(root):
        events.append("router")
        return real_install(root)

    monkeypatch.setattr(tkinter.Tk, "__init__", _tk_init)
    monkeypatch.setattr(key_router, "install_router", _install)
    return events


def test_create_runs_build_only_after_router(spy):
    seen: dict[str, object] = {}

    def build(root):
        spy.append("build")
        router = key_router.router_for(root)
        seen["unwrapped"] = router.verify()
        seen["children"] = list(root.children)
        seen["defaults"] = dict(router.originals)
        return root

    # Creating an additional Tk interpreter intermittently fails on this Windows setup
    # with a Tcl init race (see tests/conftest.py); retry only that environment error.
    for attempt in range(3):
        try:
            root = TkRootHost.create(build=build)
            break
        except tkinter.TclError as exc:
            if attempt == 2 or not any(m in str(exc) for m in ("tcl_findLibrary", "init.tcl", "tk.tcl")):
                raise
            spy.clear()
    try:
        assert spy == ["Tk()", "router", "build"]
        assert seen["unwrapped"] == [] and seen["children"] == []
        assert "<<NextWindow>>" in seen["defaults"]  # Tk defaults were captured before consumer code
    finally:
        root.destroy()
