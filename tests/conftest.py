"""Shared pytest fixtures for tests that need a real (not faked/stubbed) Tk root.

`_shared_tk_root` is session-scoped: exactly one real `tk.Tk()` interpreter
is created for the entire test run, reused by every test module that needs
one (`test_scrollable_frame.py`, `test_scrollable_popup.py`). Creating and
destroying multiple real `Tk()` interpreters back-to-back within one Python
process was observed to intermittently fail on this Windows setup with a
spurious `TclError` ("Can't find a usable init.tcl" / "invalid command name
tcl_findLibrary") - a resource-timing race in the Tcl runtime itself
(plausibly antivirus file-lock contention on `init.tcl` during the
destroy/recreate window), not a bug in the code under test. Reusing one
root for the whole session avoids that churn entirely; individual test
modules get a clean slate via their own per-test child-teardown fixture.
"""

from __future__ import annotations

import pytest

from bw_gui.runtime import ui


@pytest.fixture(scope="session")
def _shared_tk_root():
    window = ui.Tk()
    window.geometry("400x300+0+0")
    window.deiconify()
    window.update()
    yield window
    window.destroy()
