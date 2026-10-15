"""Widget-event contract, Tk side: lifecycle hooks (``docs/WIDGET_EVENTS_CONTRACT.md``).

``on_resize``, ``on_focus_change``, ``on_visibility``, ``on_destroy``,
``on_text_modified`` and ``on_tab_changed`` replace raw ``widget.bind("<Configure>")``,
``<FocusIn>``/``<FocusOut>``, ``<Map>``/``<Unmap>``, ``<Destroy>``, ``<<Modified>>`` and
``<<NotebookTabChanged>>`` bindings in consumer code. Every hook returns a
:class:`Subscription` (``remove()`` idempotent; invalidated when the widget is
destroyed). Handlers get semantic values from ``bw_gui.contracts.widget_events``, never
Tk event objects; their return value is ignored (lifecycle events are never consumed).

Scope: hooks bind on the widget's own bw-gui tag (``bwkeys:<path>``), so they see the
widget's **own** events. ``within=True`` (``on_resize``, ``on_focus_change``; toplevels
only) also reports events of every descendant -- the semantics of a former binding on
the toplevel's path tag, which Tk puts into the bindtags of all its descendants.
"""

from __future__ import annotations

from typing import Any, Callable

from bw_gui.contracts.subscription import CompositeSubscription, Subscription
from bw_gui.contracts.widget_events import FocusChange, ResizeEvent, TabChange

from .pointer import _bind, _track

__all__ = [
    "on_destroy",
    "on_focus_change",
    "on_resize",
    "on_tab_changed",
    "on_text_modified",
    "on_visibility",
    "reset_text_modified",
]


def _is_toplevel(widget: Any) -> bool:
    return str(widget.winfo_toplevel()) == str(widget)


def _bind_scope(widget: Any, sequence: str, func: Callable[[Any], None], *, within: bool) -> Subscription:
    """Bind on the widget's bw tag, or (``within``) on the toplevel's path tag for all descendants."""
    if not within:
        return _track(widget, _bind(widget, sequence, func))
    if not _is_toplevel(widget):
        raise ValueError("within=True is only supported for toplevel windows")
    tag = str(widget)
    funcid = widget.bind(sequence, func, add="+")

    def _remove() -> None:
        try:
            script = widget.tk.call("bind", tag, sequence)
            widget.tk.call("bind", tag, sequence, "\n".join(l for l in str(script).split("\n") if funcid not in l))
            widget.deletecommand(funcid)
        except Exception:
            pass

    return _track(widget, Subscription(_remove))


def on_resize(widget: Any, handler: Callable[[ResizeEvent], object], *, within: bool = False) -> Subscription:
    """Report geometry changes of *widget* (Tk ``<Configure>``) as :class:`ResizeEvent`.

    Fires after every size change; for a toplevel also after it was moved (its
    ``x``/``y`` are screen coordinates). With ``within=True`` (toplevels only) it also
    fires when any descendant's geometry changes; ``ResizeEvent.widget`` is then the
    changed widget.
    """
    path = str(widget)

    def _on_configure(event: Any) -> None:
        if not within and str(event.widget) != path:
            return
        handler(ResizeEvent(int(event.width), int(event.height), int(event.x), int(event.y), event.widget))

    return _bind_scope(widget, "<Configure>", _on_configure, within=within)


def on_focus_change(
    widget: Any,
    *,
    on_gained: Callable[[FocusChange], object] | None = None,
    on_lost: Callable[[FocusChange], object] | None = None,
    within: bool = False,
) -> Subscription:
    """Report keyboard focus gained/lost by *widget* (Tk ``<FocusIn>``/``<FocusOut>``).

    Every Tk focus event is reported, whatever its notify detail (1:1 to a former raw
    binding). With ``within=True`` (toplevels only) focus changes of every descendant
    are reported too, ``FocusChange.widget`` being the widget whose focus changed.
    """
    if on_gained is None and on_lost is None:
        raise ValueError("on_focus_change needs on_gained and/or on_lost")
    path = str(widget)
    subs: list[Subscription] = []
    for sequence, callback, gained in (("<FocusIn>", on_gained, True), ("<FocusOut>", on_lost, False)):
        if callback is None:
            continue

        def _on_focus(event: Any, *, _callback=callback, _gained=gained) -> None:
            if not within and str(event.widget) != path:
                return
            _callback(FocusChange(_gained, event.widget))

        subs.append(_bind_scope(widget, sequence, _on_focus, within=within))
    return subs[0] if len(subs) == 1 else _track(widget, CompositeSubscription(subs))


def on_visibility(
    widget: Any,
    *,
    on_shown: Callable[[Any], object] | None = None,
    on_hidden: Callable[[Any], object] | None = None,
) -> Subscription:
    """Report transitions of ``winfo_viewable()`` of *widget* (not every raw ``<Map>``/``<Unmap>``).

    bw-gui observes ``<Map>``/``<Unmap>`` of the widget and of every ancestor up to its
    toplevel (iconify/deiconify included), re-evaluates ``winfo_viewable()`` and calls
    ``on_shown(widget)``/``on_hidden(widget)`` only when the state really changed.
    Registration stores the current state without a report; focus or activation
    changes of the application never report.
    """
    state = {"viewable": bool(widget.winfo_viewable())}

    def _check(_event: Any = None) -> None:
        try:
            viewable = bool(widget.winfo_viewable())
        except Exception:
            return
        if viewable == state["viewable"]:
            return
        state["viewable"] = viewable
        callback = on_shown if viewable else on_hidden
        if callback is not None:
            callback(widget)

    chain, current = [], widget
    while current is not None:
        chain.append(current)
        if _is_toplevel(current):
            break
        current = current.master
    subs = [_bind(member, sequence, _check) for member in chain for sequence in ("<Map>", "<Unmap>")]
    return _track(widget, CompositeSubscription(subs))


def on_destroy(widget: Any, handler: Callable[[Any], object]) -> Subscription:
    """Call ``handler(widget)`` once when *widget* itself is destroyed (not its descendants)."""
    path = str(widget)

    def _on_destroy(event: Any) -> None:
        if str(event.widget) == path:
            handler(widget)

    return _track(widget, _bind(widget, "<Destroy>", _on_destroy))


def on_text_modified(text: Any, handler: Callable[[Any], object]) -> Subscription:
    """Call ``handler(text)`` after the content of a ``Text`` widget changed.

    Uses Tk's modified flag: on ``<<Modified>>`` with the flag set, bw-gui resets the
    flag (``edit_modified(False)``) and reports the change; the event caused by that
    reset (flag now false) is not reported. Typing, paste, undo and programmatic
    ``insert``/``delete`` all report, like the former raw binding with its manual reset.
    Consumers never read the flag; to declare programmatic content (e.g. a document
    just loaded) as the unmodified baseline they call :func:`reset_text_modified`.
    """

    def _on_modified(_event: Any) -> None:
        try:
            if not text.edit_modified():
                return
            text.edit_modified(False)
        except Exception:
            return
        handler(text)

    return _track(text, _bind(text, "<<Modified>>", _on_modified))


def reset_text_modified(text: Any) -> None:
    """Declare the current content of *text* as unmodified (e.g. right after loading a document).

    Call it right after the programmatic ``insert``/``delete``: Tk delivers
    ``<<Modified>>`` later, and by then the flag is false, so ``on_text_modified``
    does not report the load as a change.
    """
    text.edit_modified(False)


def on_tab_changed(notebook: Any, handler: Callable[[TabChange], object]) -> Subscription:
    """Report a change of the selected tab of a ``ttk.Notebook`` (user or ``select()``) as :class:`TabChange`."""

    def _on_changed(_event: Any) -> None:
        tab_id = str(notebook.select())
        tabs = [str(tab) for tab in notebook.tabs()]
        handler(TabChange(tabs.index(tab_id) if tab_id in tabs else None, tab_id, notebook))

    return _track(notebook, _bind(notebook, "<<NotebookTabChanged>>", _on_changed))
