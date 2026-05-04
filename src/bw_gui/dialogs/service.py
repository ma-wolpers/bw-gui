from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog


ModalCallback = Callable[[], Any]


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
        return _run_modal(parent, title, lambda: simpledialog.askstring(title, prompt, **kwargs))


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
