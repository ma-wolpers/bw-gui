"""Create a real Tk root for a test, skipping only for environmental reasons (consumer test helper).

Tests with a real Tk interpreter hit two failures that say nothing about the code
under test:

* **No display** (headless CI runners, SSH sessions): Tk raises ``TclError``
  "no display name and no $DISPLAY environment variable" or "couldn't connect to
  display". The test cannot run, so it is skipped.
* **Tcl init race** (Windows): creating several interpreters in one process
  intermittently fails with "Can't find a usable init.tcl" / "invalid command
  name tcl_findLibrary". That is retried; if it persists, the test is skipped.

Every other ``TclError`` is a real failure and propagates unchanged -- a
blanket ``except TclError: skip`` would hide a broken widget setup as "skipped".
"""

from __future__ import annotations

import tkinter
from typing import Callable, TypeVar

__all__ = ["create_tk_root", "is_missing_display", "is_tcl_init_race"]

T = TypeVar("T")

_DISPLAY_MARKERS = ("no display name", "couldn't connect to display")
_INIT_RACE_MARKERS = ("usable", "tcl_findLibrary", "init.tcl", "tk.tcl")


def is_missing_display(error: BaseException) -> bool:
    """Return whether *error* means that Tk found no display to connect to.

    Args:
        error: The exception raised while creating the interpreter.
    """
    return isinstance(error, tkinter.TclError) and any(m in str(error) for m in _DISPLAY_MARKERS)


def is_tcl_init_race(error: BaseException) -> bool:
    """Return whether *error* is the known, retryable Tcl init race on Windows.

    Args:
        error: The exception raised while creating the interpreter.
    """
    return isinstance(error, tkinter.TclError) and any(m in str(error) for m in _INIT_RACE_MARKERS)


def create_tk_root(factory: Callable[[], T] = tkinter.Tk, *, attempts: int = 3) -> T:
    """Call *factory* to create a Tk root; retry the init race, skip without a display.

    Args:
        factory: Creates the root, e.g. ``tkinter.Tk``, ``bw_gui.runtime.create_root``
            or a whole app class whose constructor creates its own root.
        attempts: How often the known init race is retried before the test is skipped.

    Returns:
        Whatever *factory* returned.

    Raises:
        pytest.skip.Exception: No display is available, or the init race persisted.
        tkinter.TclError: Any other Tk error (a real failure of the code under test).
    """
    import pytest  # only needed inside a test run; keeps the module importable without pytest

    for attempt in range(attempts):
        try:
            return factory()
        except tkinter.TclError as error:
            if is_missing_display(error):
                pytest.skip(f"no Tk display available: {error}")
            if not is_tcl_init_race(error):
                raise
            if attempt == attempts - 1:
                pytest.skip(f"Tcl init race persisted after {attempts} attempts: {error}")
    raise AssertionError("attempts must be at least 1")
