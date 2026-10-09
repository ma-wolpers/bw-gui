"""Tk side of screen placement (see ``docs/SCREEN_PLACEMENT_CONTRACT.md``).

The geometry itself is pure (``bw_gui.contracts.screen_geometry``). This module
holds the only Tk accesses of the placement contract:

* :func:`get_monitor_info` resolves the responsible monitor (Win32 via
  ``_win_monitors``; Tk-screen fallback elsewhere or on failure).
* :func:`measure_overlay` reads a window's requested size.
* :func:`apply_window_position` writes ``+x+y`` (never the size).
* :func:`place_overlay_now` is the documented composition
  measure -> monitor -> calculate -> (limit size -> re-measure -> re-calculate) -> apply.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable

from bw_gui.contracts.screen_geometry import (
    MonitorInfo,
    MonitorSource,
    Placement,
    Point,
    Rect,
    Side,
    Size,
    calculate_overlay_placement,
    select_monitor,
)
from bw_gui.runtime import _win_monitors

_LOG = logging.getLogger(__name__)
_fallback_warned = False


class MonitorQueryError(RuntimeError):
    """Raised when not even the Tk-screen fallback can be computed (dead interpreter)."""


def _tk_screen_info(tk_context: tk.Misc, source: MonitorSource) -> MonitorInfo:
    """Return the Tk screen (primary monitor on Windows) as bounds and work area."""
    try:
        width = max(1, int(tk_context.winfo_screenwidth()))
        height = max(1, int(tk_context.winfo_screenheight()))
    except tk.TclError as exc:
        raise MonitorQueryError(f"Tk screen not available: {exc}") from exc
    rect = Rect(0, 0, width, height)
    return MonitorInfo(bounds=rect, work_area=rect, source=source, primary=True)


def _target_rect(target: Point | Rect | tk.Misc) -> Rect:
    """Turn a ``Point``, ``Rect`` or mapped widget into the rectangle used for monitor selection."""
    if isinstance(target, Rect):
        return target
    if isinstance(target, Point):
        return Rect(target.x, target.y, target.x + 1, target.y + 1)
    toplevel = target.winfo_toplevel()
    if _win_monitors.is_available():
        return _win_monitors.root_window_rect(int(toplevel.winfo_id()))
    return Rect(
        int(toplevel.winfo_rootx()),
        int(toplevel.winfo_rooty()),
        int(toplevel.winfo_rootx()) + max(1, int(toplevel.winfo_width())),
        int(toplevel.winfo_rooty()) + max(1, int(toplevel.winfo_height())),
    )


def get_monitor_info(target: Point | Rect | tk.Misc, *, tk_context: tk.Misc) -> MonitorInfo:
    """Return bounds and work area of the monitor responsible for *target*.

    Args:
        target: A ``Point``, a ``Rect`` or a mapped widget (resolved to its toplevel's
            native frame rectangle).
        tk_context: Any live widget of the Tk interpreter; it provides the
            Tk-screen fallback and the DPI context. Mandatory, also for points.

    Returns:
        ``source=WIN32`` on Windows; ``TK_SCREEN`` on other backends (under X11
        usually all monitors); ``FALLBACK`` when the Win32 query failed (one
        warning per process). In both fallbacks ``work_area == bounds``.

    Raises:
        ValueError: If *target* is a widget that is not mapped.
        MonitorQueryError: If even the Tk screen fallback is impossible.
    """
    global _fallback_warned
    if isinstance(target, tk.Misc) and not bool(target.winfo_ismapped()):
        raise ValueError("get_monitor_info needs a mapped widget as target")
    if not _win_monitors.is_available():
        return _tk_screen_info(tk_context, MonitorSource.TK_SCREEN)
    try:
        return select_monitor(_win_monitors.enumerate_monitors(), _target_rect(target))
    except _win_monitors.Win32MonitorError as exc:
        if not _fallback_warned:
            _fallback_warned = True
            _LOG.warning("Win32 monitor query failed, using Tk screen fallback: %s", exc)
        return _tk_screen_info(tk_context, MonitorSource.FALLBACK)


def measure_overlay(window: tk.Misc) -> Size:
    """Return the requested size of *window* after processing pending geometry."""
    window.update_idletasks()
    return Size(max(1, int(window.winfo_reqwidth())), max(1, int(window.winfo_reqheight())))


def apply_window_position(window: tk.Misc, position: Point) -> None:
    """Move *window* to *position* (``+x+y`` only, size untouched).

    Call before making the window visible to avoid flicker; calling it on a visible
    window is allowed and moves it.

    Raises:
        ValueError: If *window* has already been destroyed (programming error).
    """
    try:
        exists = bool(window.winfo_exists())
    except tk.TclError:
        exists = False
    if not exists:
        raise ValueError("apply_window_position: window has been destroyed")
    window.geometry(f"{position.x:+d}{position.y:+d}")


def widget_rect(widget: tk.Misc) -> Rect:
    """Return the on-screen rectangle of *widget* (convenience anchor for overlays)."""
    widget.update_idletasks()
    x, y = int(widget.winfo_rootx()), int(widget.winfo_rooty())
    return Rect(x, y, x + max(1, int(widget.winfo_width())), y + max(1, int(widget.winfo_height())))


def place_overlay_now(
    window: tk.Misc,
    *,
    anchor: Rect,
    placement: tuple[Side, ...],
    tk_context: tk.Misc | None = None,
    gap: int = 0,
    margin: int = 8,
    max_size_policy: Callable[[Size], None] | None = None,
) -> Placement:
    """Measure, place and position *window* next to *anchor* (documented composition).

    Steps: measure the natural size -> resolve the monitor of the anchor ->
    ``calculate_overlay_placement``. If the overlay overflows and *max_size_policy*
    is given, it is called with the maximum allowed size (work area minus
    ``2*margin``) to limit the window (e.g. cap a menu's height and make it
    scrollable); the window is then re-measured and the placement recomputed with
    the same monitor. Finally the position is applied. A placement is only ever
    applied for the size it was computed for.

    Raises:
        RuntimeError: If the window's size changed between calculation and application.
    """
    context = tk_context if tk_context is not None else window
    size = measure_overlay(window)
    monitor = get_monitor_info(anchor, tk_context=context)
    result = calculate_overlay_placement(
        anchor=anchor, size=size, monitor=monitor, placement=placement, gap=gap, margin=margin
    )
    if not result.fits and max_size_policy is not None and result.overflow != Size(0, 0):
        work = monitor.work_area
        max_size_policy(Size(max(1, work.width - 2 * margin), max(1, work.height - 2 * margin)))
        size = measure_overlay(window)
        result = calculate_overlay_placement(
            anchor=anchor, size=size, monitor=monitor, placement=placement, gap=gap, margin=margin
        )
    if measure_overlay(window) != result.size:
        raise RuntimeError("place_overlay_now: window size changed after the placement was calculated")
    apply_window_position(window, result.position)
    return result


def place_on_pointer_monitor(
    window: tk.Misc, *, vertical_fraction: float = 0.5, margin: int = 0, size: Size | None = None
) -> Point:
    """Position a free-standing window (no anchor) on the monitor under the mouse pointer.

    For windows without a parent anchor, e.g. a startup dialog that is its own
    root: horizontally centred in the work area of the monitor the pointer is on,
    vertically at ``vertical_fraction`` of the free space (0.5 = centred, 1/3 =
    upper third), then clamped with ``calculate_clamped_position``.

    Args:
        size: The size to place; defaults to the requested size (``measure_overlay``).
            Main windows whose size was set explicitly via ``geometry("WxH")`` pass it.

    Returns:
        The applied position.
    """
    from bw_gui.contracts.screen_geometry import calculate_clamped_position

    size = size if size is not None else measure_overlay(window)
    pointer_x, pointer_y = window.winfo_pointerxy()
    work = get_monitor_info(Point(int(pointer_x), int(pointer_y)), tk_context=window).work_area
    desired = Point(
        work.left + (work.width - size.width) // 2,
        work.top + int((work.height - size.height) * vertical_fraction),
    )
    position = calculate_clamped_position(desired=desired, size=size, bounds=work, margin=margin)
    apply_window_position(window, position)
    return position


def work_area_for(widget: tk.Misc) -> Rect:
    """Return the work area of the monitor *widget* is on (mapped or not).

    A mapped widget resolves via its toplevel frame; an unmapped one via its
    current root position. Useful to cap an initial window size to the monitor
    it opens on instead of the primary screen.
    """
    if bool(widget.winfo_ismapped()):
        return get_monitor_info(widget, tk_context=widget).work_area
    return get_monitor_info(Point(int(widget.winfo_rootx()), int(widget.winfo_rooty())), tk_context=widget).work_area
