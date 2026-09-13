from __future__ import annotations

import re
from collections.abc import Callable

from bw_gui.runtime import ui
from bw_gui.theming import theme_widget_border


class RegexEntryField:
    """Text entry that compiles its content as a Python regex on every keystroke.

    Wraps a raw ``tk.Entry`` (not ``ttk``) because ``theme_widget_border``
    only reliably restyles classic ``tk`` widgets, matching the existing
    convention for themed border feedback elsewhere in this codebase.
    Compilation uses plain ``re.compile`` (case-sensitive, no implicit
    flags) -- consumers wanting different semantics compile their own
    pattern from :meth:`get_text` instead of relying on this widget.

    An invalid pattern turns the border red and makes
    :meth:`get_compiled_pattern` return ``None`` -- there is deliberately
    no silent fallback to substring matching. Consumers decide what "no
    valid pattern" means for their own feature (ignore the change, keep
    the previous result, etc.).
    """

    def __getattr__(self, name: str):
        """Delegate unknown widget attributes to the composed frame container."""
        return getattr(self._container, name)

    def __init__(
        self,
        master,
        *,
        initial: str = "",
        on_change: Callable[[str, re.Pattern[str] | None], None] | None = None,
    ):
        self._container = ui.Frame(master)
        self._var = ui.StringVar(value=initial)
        self.entry = ui.Entry(self._container, textvariable=self._var)
        self.entry.pack(fill="x", expand=True)
        self._compiled: re.Pattern[str] | None = None
        self._on_change = on_change
        self._var.trace_add("write", lambda *_args: self._recompile())
        self._recompile()

    def _recompile(self) -> None:
        text = self._var.get()
        if not text:
            self._compiled = None
            theme_widget_border(self.entry, color_token="border")
        else:
            try:
                self._compiled = re.compile(text)
            except re.error:
                self._compiled = None
                theme_widget_border(self.entry, color_token="danger")
            else:
                theme_widget_border(self.entry, color_token="border")
        if self._on_change is not None:
            self._on_change(text, self._compiled)

    def get_text(self) -> str:
        """Return the raw, uncompiled entry text."""
        return self._var.get()

    def get_compiled_pattern(self) -> re.Pattern[str] | None:
        """Return the last successfully compiled pattern, or ``None`` if the text is empty/invalid."""
        return self._compiled

    def set_text(self, value: str) -> None:
        """Replace the entry content, re-triggering compilation."""
        self._var.set(value)

    def focus_set(self) -> None:
        """Move keyboard focus to the inner entry, not the wrapping frame."""
        self.entry.focus_set()

    def bind(self, sequence: str, func, add: str | None = None):  # type: ignore[override]
        """Forward event bindings to the internal entry widget."""
        return self.entry.bind(sequence, func, add=add)
