"""Semantic handler results shared by every bw-gui event contract.

Consumer handlers (shortcut binders, ``on_key``, pointer hooks, ``on_activate``,
router roles) return :class:`EventResult` instead of Tk's ``"break"`` string. Only
bw-gui translates ``HANDLED`` into Tk's propagation stop (see
``bw_gui.runtime._tk_dispatch``). Consumers never need to know Tk's convention.
"""

from __future__ import annotations

from enum import Enum


class EventResult(Enum):
    """Outcome of a semantic event handler.

    ``HANDLED`` stops further processing of the underlying Tk event;
    ``NOT_HANDLED`` lets it continue to the next bindtag.
    """

    HANDLED = "handled"
    NOT_HANDLED = "not_handled"


def coerce_result(value: object) -> EventResult:
    """Normalise a handler return value to :class:`EventResult`.

    ``None`` means ``NOT_HANDLED`` (so plain handlers keep today's propagation).

    Raises:
        TypeError: For any other type, in particular a legacy Tk ``"break"`` string;
            consumers must return ``EventResult`` instead.
    """
    if value is None:
        return EventResult.NOT_HANDLED
    if isinstance(value, EventResult):
        return value
    raise TypeError(
        f"Event handlers must return EventResult or None, got {value!r} "
        "(Tk strings like 'break' are not part of the bw-gui contract)"
    )
