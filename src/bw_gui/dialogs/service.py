from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import simpledialog as _tk_simpledialog


ModalCallback = Callable[[], Any]


class _EscapeSafeQueryString(_tk_simpledialog._QueryString):
    """Wie ``simpledialog._QueryString``, aber ``cancel()`` stoppt die Ereigniskette.

    Der Stdlib-``Dialog.cancel`` gibt ``None`` statt ``"break"`` zurueck, wodurch ein
    Escape-Tastendruck nicht am Dialog-Toplevel stoppt, sondern bis zu darunterliegenden
    Fenstern (z. B. einem globalen ``bind_all("<Escape>")``-Handler) weiterlaeuft.
    """

    def cancel(self, event=None):
        """Close the dialog like the base class, additionally stopping event propagation."""
        super().cancel(event)
        return "break"


def _resolve_parent(parent: object | None) -> object | None:
    if parent is not None:
        return parent
    return tk._default_root


def _run_modal(parent: object | None, title: str, callback: ModalCallback) -> Any:
    resolved_parent = _resolve_parent(parent)
    if resolved_parent is not None and hasattr(resolved_parent, "_run_modal_dialog_call"):
        return resolved_parent._run_modal_dialog_call(title, callback)
    return callback()


class MessageDialogService:
    """Wrapper for messagebox calls that keeps popup policy tracking intact."""

    def showerror(self, title: str, message: str, **kwargs: Any) -> str:
        parent = kwargs.get("parent")
        return _run_modal(parent, title, lambda: messagebox.showerror(title, message, **kwargs))

    def showwarning(self, title: str, message: str, **kwargs: Any) -> str:
        parent = kwargs.get("parent")
        return _run_modal(parent, title, lambda: messagebox.showwarning(title, message, **kwargs))

    def showinfo(self, title: str, message: str, **kwargs: Any) -> str:
        parent = kwargs.get("parent")
        return _run_modal(parent, title, lambda: messagebox.showinfo(title, message, **kwargs))

    def askyesno(self, title: str, message: str, **kwargs: Any) -> bool:
        parent = kwargs.get("parent")
        return bool(_run_modal(parent, title, lambda: messagebox.askyesno(title, message, **kwargs)))

    def askyesnocancel(self, title: str, message: str, **kwargs: Any) -> bool | None:
        parent = kwargs.get("parent")
        return _run_modal(parent, title, lambda: messagebox.askyesnocancel(title, message, **kwargs))

    def askretrycancel(self, title: str, message: str, **kwargs: Any) -> bool:
        parent = kwargs.get("parent")
        return bool(_run_modal(parent, title, lambda: messagebox.askretrycancel(title, message, **kwargs)))


class TextPromptDialogService:
    """Wrapper for simpledialog text prompts with popup policy tracking."""

    def askstring(self, title: str, prompt: str, **kwargs: Any) -> str | None:
        parent = kwargs.get("parent")

        def _show() -> str | None:
            dialog = _EscapeSafeQueryString(title, prompt, **kwargs)
            return dialog.result

        return _run_modal(parent, title, _show)


@dataclass(frozen=True)
class ChoiceOption:
    """One answer offered by :meth:`ChoiceDialogService.askchoice`.

    Attributes:
        key: Stable, non-empty identifier returned when this option is chosen.
            Unique within one ``askchoice`` call.
        label: Button text shown to the user.
        description: Optional muted explanation shown directly below the button.
    """

    key: str
    label: str
    description: str = ""


def _validate_choice_options(options: Sequence[ChoiceOption]) -> tuple[ChoiceOption, ...]:
    """Return ``options`` as a tuple, rejecting invalid input before anything is shown.

    Raises:
        ValueError: No options, an entry that is not a :class:`ChoiceOption`, an
            empty key, or a key that occurs twice.
    """
    normalized = tuple(options)
    if not normalized:
        raise ValueError("askchoice needs at least one option.")
    seen: set[str] = set()
    for option in normalized:
        if not isinstance(option, ChoiceOption):
            raise ValueError(f"askchoice options must be ChoiceOption instances, got {option!r}.")
        if not option.key:
            raise ValueError("askchoice option keys must not be empty.")
        if option.key in seen:
            raise ValueError(f"askchoice option key {option.key!r} is used twice.")
        seen.add(option.key)
    return normalized


class _ChoiceDialog(_tk_simpledialog.Dialog):
    """Modal dialog with one button per :class:`ChoiceOption` plus a cancel button.

    Built on ``simpledialog.Dialog`` for the modal mechanics (transient to the
    parent, ``grab_set``, ``wait_window``), with its default OK/Cancel button
    box replaced. The result is stored in ``self.choice`` (``None`` unless an
    option was chosen).

    Attribute names carry a ``_choice_`` prefix on purpose: ``tkinter.Misc``
    already defines e.g. ``_options`` as an internal method, and shadowing it
    breaks widget construction (``TypeError: 'list' object is not callable``).

    Keyboard: initial focus is on the first option; Return activates the
    focused button (ttk buttons have no Return binding of their own); Escape
    cancels and returns ``"break"`` so a global ``bind_all("<Escape>")`` of the
    underlying window never sees it (same reason as ``_EscapeSafeQueryString``).
    """

    def __init__(
        self,
        parent: object | None,
        title: str,
        message: str,
        options: tuple[ChoiceOption, ...],
        cancel_label: str,
    ) -> None:
        """Store the content, then let ``simpledialog.Dialog`` build and run the modal window.

        Args:
            parent: Parent window (the dialog is transient to it while it is viewable).
            title: Window title.
            message: Question shown above the option buttons.
            options: Already validated options, in display order.
            cancel_label: Text of the cancel button.
        """
        self._choice_message = message
        self._choice_options = options
        self._choice_cancel_label = cancel_label
        self._choice_buttons: list[ttk.Button] = []
        self.choice: str | None = None
        super().__init__(parent, title)

    def body(self, master):
        """Show the question; returning ``None`` lets ``buttonbox`` decide the initial focus."""
        ttk.Label(master, text=self._choice_message, justify="left", wraplength=420).pack(
            anchor="w", padx=4, pady=(4, 0)
        )
        return None

    def buttonbox(self) -> None:
        """Replace the default OK/Cancel box with one button per option and a cancel button."""
        box = ttk.Frame(self, padding=(10, 4, 10, 10))
        for option in self._choice_options:
            button = ttk.Button(box, text=option.label, command=lambda key=option.key: self._choose(key))
            button.pack(fill="x", pady=(4, 0))
            self._bind_return_to_invoke(button)
            self._choice_buttons.append(button)
            if option.description:
                ttk.Label(box, text=option.description, justify="left", wraplength=400).pack(
                    anchor="w", padx=(4, 0), pady=(2, 4)
                )
        cancel_button = ttk.Button(box, text=self._choice_cancel_label, command=self.cancel)
        cancel_button.pack(fill="x", pady=(12, 0))
        self._bind_return_to_invoke(cancel_button)
        box.pack(fill="both", expand=True)
        self.bind("<Escape>", self._on_escape)
        self.initial_focus = self._choice_buttons[0]

    @staticmethod
    def _bind_return_to_invoke(button: ttk.Button) -> None:
        """Make Return activate ``button`` while it has the focus, stopping propagation."""

        def _invoke(_event=None) -> str:
            button.invoke()
            return "break"

        button.bind("<Return>", _invoke)

    def _choose(self, key: str) -> None:
        """Record ``key`` as the result and close the dialog (mirrors ``Dialog.ok``)."""
        self.choice = key
        self.withdraw()
        self.update_idletasks()
        self.cancel()

    def _on_escape(self, _event=None) -> str:
        """Cancel (result ``None``) and stop the event at the dialog toplevel."""
        self.cancel()
        return "break"


class ChoiceDialogService:
    """Modal "pick one of these answers" dialog with popup policy tracking.

    Complements ``MessageDialogService.askyesno``/``askyesnocancel`` for
    questions whose answers are not yes/no, e.g. "Ordner mit Abgaben" vs.
    "grosse PDF aufteilen". Contract:

    - Synchronous: blocks until the user answers, then returns the chosen
      option's ``key`` - or ``None`` for the cancel button, Escape, or the
      window's close button. No callbacks.
    - Invalid ``options`` raise ``ValueError`` *before* anything is shown.
    - Runs through the same modal runner as the other services, so the
      parent's popup policy tracking (``_run_modal_dialog_call``) stays intact.
    - The grab keeps the user from interacting with other windows of the app
      while it is open. It is not a general guarantee against Tk reentrancy:
      ``after()`` callbacks and already queued events still run.
    - GRENZE(theming): content uses ttk widgets; the dialog toplevel and its
      body frame come from ``simpledialog.Dialog`` (plain Tk), the same
      limitation as
      ``TextPromptDialogService.askstring``.
    """

    def askchoice(
        self,
        title: str,
        message: str,
        options: Sequence[ChoiceOption],
        *,
        parent: object | None = None,
        cancel_label: str = "Abbrechen",
    ) -> str | None:
        """Ask the user to pick one option; return its key, or ``None`` if cancelled.

        Args:
            title: Window title (also used for popup policy tracking).
            message: Question shown above the buttons.
            options: At least one :class:`ChoiceOption` with unique, non-empty keys.
            parent: Parent window; defaults to Tk's default root.
            cancel_label: Text of the cancel button.

        Example:
            >>> service.askchoice(
            ...     "Neue Klausur",
            ...     "Wie liegen die Abgaben vor?",
            ...     [ChoiceOption("folder", "Ordner mit Abgaben"), ChoiceOption("split", "Grosse PDF aufteilen")],
            ... )  # doctest: +SKIP
            'split'
        """
        validated = _validate_choice_options(options)
        resolved_parent = _resolve_parent(parent)

        def _show() -> str | None:
            dialog = _ChoiceDialog(resolved_parent, title, message, validated, cancel_label)
            return dialog.choice

        return _run_modal(resolved_parent, title, _show)


class FileDialogService:
    """Wrapper for file dialogs with popup policy tracking."""

    def askdirectory(self, **kwargs: Any) -> str:
        parent = kwargs.get("parent")
        title = str(kwargs.get("title") or "Dateidialog")
        return _run_modal(parent, title, lambda: filedialog.askdirectory(**kwargs))

    def askopenfilename(self, **kwargs: Any) -> str:
        parent = kwargs.get("parent")
        title = str(kwargs.get("title") or "Dateidialog")
        return _run_modal(parent, title, lambda: filedialog.askopenfilename(**kwargs))

    def askopenfilenames(self, **kwargs: Any) -> tuple[str, ...]:
        parent = kwargs.get("parent")
        title = str(kwargs.get("title") or "Dateidialog")
        result = _run_modal(parent, title, lambda: filedialog.askopenfilenames(**kwargs))
        if isinstance(result, tuple):
            return result
        if not result:
            return ()
        return tuple(result)

    def asksaveasfilename(self, **kwargs: Any) -> str:
        parent = kwargs.get("parent")
        title = str(kwargs.get("title") or "Dateidialog")
        return _run_modal(parent, title, lambda: filedialog.asksaveasfilename(**kwargs))
