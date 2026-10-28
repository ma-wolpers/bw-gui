"""Count the real Tcl/Tk calls of an action (shared by bw-gui tests and consumer benchmarks).

Every Tkinter widget call ends up in ``_tkinter.tkapp.call``; cProfile counts
those calls exactly without patching Tkinter. Deterministic, hence suitable
for call-budget tests (unlike wall-clock timings), e.g. "moving the cursor
costs the same number of Tcl calls with 10 or 80 columns".
"""

from __future__ import annotations

import cProfile
import pstats
from typing import Callable

__all__ = ["count_tcl_calls"]

_TKAPP_CALL = "<method 'call' of '_tkinter.tkapp' objects>"


def count_tcl_calls(action: Callable[[], object]) -> int:
    """Run *action* and return how many Tcl calls it issued.

    Args:
        action: Parameterless action, e.g. one navigation step plus ``update()``.
    """
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        action()
    finally:
        profiler.disable()
    stats = pstats.Stats(profiler)
    return sum(entry[1] for key, entry in stats.stats.items() if key[2] == _TKAPP_CALL)
