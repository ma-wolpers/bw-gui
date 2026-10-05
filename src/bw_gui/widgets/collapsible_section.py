"""Collapsible frame with a title row (▾/▸) - the bw-gui building block for panels that need to save space.

`CollapsibleSection` is a genuine `ttk.LabelFrame` subclass (just as
`ScrollableFrame` is a genuine `ttk.Frame` subclass): it can be packed or
gridded anywhere a `LabelFrame` could. Content belongs exclusively in
`self.content`, never directly in the instance - the instance only holds the
internally managed header widget.

Contract (modelled on `docs/TOGGLE_CONTRACT.md`, Switch = immediate effect):

* ``collapsed`` is **read-only**. ``set_collapsed(value)`` changes the state
  programmatically - without calling the callback. ``toggle()`` behaves like
  a user click.
* ``on_toggle(requested_collapsed)`` runs only on user interaction (click on
  arrow or title) or ``toggle()``. If the callback raises, the *widget state*
  (arrow, visibility of ``content``) is rolled back and the exception is
  re-raised (it ends up in Tk's ``report_callback_exception``). Side effects
  the callback already caused (e.g. persistence) cannot be rolled back by
  the widget.
* Persistence is the consumer's job; bw-gui stores nothing.
* ``labelwidget`` and ``text`` belong to the widget: passing them to the
  constructor, ``configure``/``config`` or ``widget[key] = ...`` raises
  ``TypeError``.
* Appearance comes exclusively from bw-gui styles (``SecondaryAction.TButton``
  for the arrow); consumers do no colour work.
"""

from __future__ import annotations

from collections.abc import Callable

from bw_gui.runtime import widgets

ToggleCallback = Callable[[bool], None]

ARROW_EXPANDED = "▾"
ARROW_COLLAPSED = "▸"
_RESERVED_OPTIONS = frozenset({"labelwidget", "text"})


def _reject_reserved(options: dict) -> None:
    """Raise ``TypeError`` if *options* contains an option the section owns itself."""
    reserved = _RESERVED_OPTIONS.intersection(options)
    if reserved:
        raise TypeError(
            f"option(s) {sorted(reserved)} are managed by CollapsibleSection; pass the title as "
            "`title` and build content into `.content`"
        )


class CollapsibleSection(widgets.LabelFrame):
    """`LabelFrame` whose content can be collapsed/expanded via an arrow in its title row.

    Example::

        section = CollapsibleSection(parent, "Diagnostics", collapsed=saved, on_toggle=save_state)
        section.pack(fill="x")
        widgets.Label(section.content, text="...").pack()
    """

    def __init__(
        self,
        parent,
        title: str,
        *,
        collapsed: bool = False,
        on_toggle: ToggleCallback | None = None,
        **frame_kwargs,
    ) -> None:
        """Create the section.

        Args:
            parent:         Parent widget.
            title:          Text of the title row.
            collapsed:      Initial state (``True`` = collapsed).
            on_toggle:      Optional; receives the *requested* state on user interaction.
                            Raise to reject (the widget state is rolled back).
            **frame_kwargs: Further ``ttk.LabelFrame`` options (``padding``, ``style``, ...);
                            ``labelwidget``/``text`` are reserved.

        Raises:
            TypeError: for reserved options.
        """
        _reject_reserved(frame_kwargs)
        super().__init__(parent, **frame_kwargs)
        self._on_toggle = on_toggle
        self._collapsed = bool(collapsed)

        header = widgets.Frame(self)
        self._arrow = widgets.Button(
            header,
            text=ARROW_EXPANDED,
            width=2,
            style="SecondaryAction.TButton",
            command=self.toggle,
        )
        self._arrow.pack(side="left")
        self._title = widgets.Label(header, text=str(title))
        self._title.pack(side="left", padx=(4, 0))
        self._title.bind("<Button-1>", lambda _event: self.toggle())
        super().configure(labelwidget=header)
        self._header = header

        self.content = widgets.Frame(self)
        """Target frame for the consumer's content."""
        # Tk does not shrink a master when its *last* slave is pack_forget()-ten: it
        # keeps the previously requested size. A zero-height placeholder packed while
        # collapsed makes the frame recompute its size down to the title row.
        self._collapsed_placeholder = widgets.Frame(self, height=0)
        self._render()

    # -- public API -----------------------------------------------------------------

    @property
    def collapsed(self) -> bool:
        """Whether the content is currently collapsed (read-only; use ``set_collapsed``)."""
        return self._collapsed

    @property
    def title(self) -> str:
        """Text of the title row."""
        return str(self._title.cget("text"))

    def set_collapsed(self, value: bool) -> None:
        """Set the state programmatically - **without** calling ``on_toggle``."""
        self._collapsed = bool(value)
        self._render()

    def toggle(self) -> None:
        """Flip the state like a user click (calls ``on_toggle``, rolls back if it raises)."""
        previous = self._collapsed
        requested = not previous
        self._collapsed = requested
        self._render()
        if self._on_toggle is None:
            return
        try:
            self._on_toggle(requested)
        except BaseException:
            self._collapsed = previous
            self._render()
            raise

    def configure(self, cnf=None, **options):
        """``ttk.LabelFrame.configure`` minus the reserved options."""
        _reject_reserved({**(cnf or {}), **options})
        return super().configure(cnf, **options)

    config = configure

    def __setitem__(self, key: str, value) -> None:
        """``widget[key] = value`` with the same reserved-option check as ``configure``."""
        _reject_reserved({key: value})
        super().__setitem__(key, value)

    # -- internals ------------------------------------------------------------------

    def _render(self) -> None:
        """Align the arrow, the visibility of ``content`` and the frame height with ``_collapsed``.

        Collapsed means the section only takes the height of its title row (the
        placeholder swap forces Tk to recompute the requested size).
        """
        self._arrow.configure(text=ARROW_COLLAPSED if self._collapsed else ARROW_EXPANDED)
        if self._collapsed:
            self.content.pack_forget()
            if not self._collapsed_placeholder.winfo_manager():
                self._collapsed_placeholder.pack(fill="x")
        else:
            self._collapsed_placeholder.pack_forget()
            if not self.content.winfo_manager():
                self.content.pack(fill="both", expand=True)
