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

# Tk test windows hand the OS foreground straight back to the developer's window
# (no stolen keystrokes while the suite runs); disabled with TK_FOCUS_TESTS=1.
from bw_gui.testing.background_windows import pytest_configure, pytest_unconfigure  # noqa: F401

from bw_gui.runtime import ui


@pytest.fixture(scope="session")
def _shared_tk_root():
    window = ui.Tk()
    window.geometry("400x300+0+0")
    window.deiconify()
    window.update()
    yield window
    window.destroy()


def create_extra_tk(attempts: int = 3):
    """Create an additional real Tk interpreter, retrying only the known Tcl init race.

    Some tests need their own interpreter (e.g. to observe what is on the ``all``
    bindtag at router installation). Creating one next to the shared root
    intermittently fails on this Windows setup with ``init.tcl``/``tcl_findLibrary``
    errors (see the module docstring); only those are retried.
    """
    for attempt in range(attempts):
        try:
            return ui.Tk()
        except ui.TclError as exc:
            if attempt == attempts - 1 or not any(m in str(exc) for m in ("tcl_findLibrary", "init.tcl", "tk.tcl")):
                raise
    raise AssertionError("unreachable")
