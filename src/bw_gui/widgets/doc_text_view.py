"""Thin Tk rendering layer for ``bw_gui.widgets.doc_text_events`` output.

Deliberately kept minimal (event -> widget insertion only, no HTML parsing)
so the only thing that needs a running Tk root to exercise is this file --
the actual HTML-to-event translation lives in ``doc_text_events.py`` and is
covered by plain unit tests instead.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from bw_gui.theming._color_math import mix_hex
from bw_gui.theming._theme_manager import get_theme

from .doc_text_events import CodeBlockEvent, DocEvent, HeadingEvent, ListItemEvent, ParagraphEvent, TextRun

_HEADING_SIZE_DELTA = {1: 8, 2: 5, 3: 2}

DOC_FONT_FAMILY = "Segoe UI"
"""Body font of every themed doc view (``configure_doc_text_theme``)."""
DOC_MONO_FONT_FAMILY = "Consolas"
"""Code font of every themed doc view."""
DEFAULT_DOC_BASE_SIZE = 10
"""Body point size of a doc view at zoom 100 %."""
_CODE_BG_BORDER_RATIO = 0.35
"""Share of the ``border`` token mixed into ``bg_surface`` for code backgrounds."""


def configure_doc_text_theme(
    text: tk.Text, theme_key: str | None = None, *, base_size: int = DEFAULT_DOC_BASE_SIZE
) -> None:
    """Configures the doc tags of ``text`` from the theme -- the one theme-to-doc-style mapping.

    Consumers never see hex values: colours come from the theme contract
    (``fg_primary``, ``bg_surface``, code background mixed from ``border``),
    fonts from ``DOC_FONT_FAMILY``/``DOC_MONO_FONT_FAMILY``. Call it again with
    another ``base_size`` to zoom (only tag fonts change, no re-render) and
    after a theme switch to re-colour. ``theme_key=None`` uses the current theme.
    """
    theme = get_theme(theme_key)
    configure_doc_text_tags(
        text,
        {
            "fg_primary": theme["fg_primary"],
            "bg_surface": theme["bg_surface"],
            "bg_code": mix_hex(theme["border"], theme["bg_surface"], _CODE_BG_BORDER_RATIO),
            "font_family": DOC_FONT_FAMILY,
            "mono_font_family": DOC_MONO_FONT_FAMILY,
            "base_size": base_size,
        },
    )


def configure_doc_text_tags(text: tk.Text, style: dict) -> None:
    """Configures the Text tags used by ``render_events_into_text`` from a plain style dict.

    Required ``style`` keys: ``fg_primary``, ``bg_surface``, ``bg_code``,
    ``font_family``, ``mono_font_family``, ``base_size``. Callers own theme
    lookup -- this module has no theme/color knowledge of its own.
    """
    base_family = style["font_family"]
    mono_family = style["mono_font_family"]
    base_size = int(style["base_size"])
    fg = style["fg_primary"]

    text.configure(background=style["bg_surface"], foreground=fg)

    # Block-level tags configured first so the inline emphasis tags below win
    # the (per-attribute) tag-priority race for `font` specifically, while
    # still inheriting margins/spacing from these block tags.
    text.tag_configure("body", font=(base_family, base_size), foreground=fg)
    text.tag_configure("list_item", font=(base_family, base_size), foreground=fg, lmargin1=18, lmargin2=32)
    for level, delta in _HEADING_SIZE_DELTA.items():
        text.tag_configure(
            f"h{level}",
            font=(base_family, base_size + delta, "bold"),
            foreground=fg,
            spacing3=6,
        )

    text.tag_configure("bold", font=(base_family, base_size, "bold"))
    text.tag_configure("italic", font=(base_family, base_size, "italic"))
    text.tag_configure("bold_italic", font=(base_family, base_size, "bold italic"))
    text.tag_configure("code_inline", font=(mono_family, base_size), background=style["bg_code"], foreground=fg)
    text.tag_configure(
        "code_block",
        font=(mono_family, base_size),
        background=style["bg_code"],
        foreground=fg,
        lmargin1=16,
        lmargin2=16,
        spacing1=4,
        spacing3=4,
    )


def render_events_into_text(
    text: tk.Text,
    events: list[DocEvent],
    *,
    on_copy: Callable[[str], None],
) -> None:
    """Inserts ``events`` into ``text`` from the current insert position onward.

    Every ``CodeBlockEvent`` gets its own small "Kopieren" button embedded via
    ``window_create`` immediately above the block, invoking ``on_copy`` with
    that block's raw text -- deliberately without exceptions, per the v1 rule
    that every code block is treated as copy-worthy.
    """
    for event in events:
        if isinstance(event, HeadingEvent):
            _insert_runs(text, event.runs, block_tag=f"h{event.level}")
            text.insert("end", "\n\n")
        elif isinstance(event, ParagraphEvent):
            _insert_runs(text, event.runs, block_tag="body")
            text.insert("end", "\n\n")
        elif isinstance(event, ListItemEvent):
            text.insert("end", "• ", ("list_item",))
            _insert_runs(text, event.runs, block_tag="list_item")
            text.insert("end", "\n")
        elif isinstance(event, CodeBlockEvent):
            _insert_code_block(text, event.text, on_copy)


def _emphasis_tag(run: TextRun) -> str | None:
    if run.code:
        return "code_inline"
    if run.bold and run.italic:
        return "bold_italic"
    if run.bold:
        return "bold"
    if run.italic:
        return "italic"
    return None


def _insert_runs(text: tk.Text, runs: tuple[TextRun, ...], *, block_tag: str) -> None:
    for run in runs:
        tags = [block_tag]
        emphasis = _emphasis_tag(run)
        if emphasis is not None:
            tags.append(emphasis)
        text.insert("end", run.text, tuple(tags))


def _insert_code_block(text: tk.Text, code: str, on_copy: Callable[[str], None]) -> None:
    button = ttk.Button(text, text="Kopieren", command=lambda: on_copy(code))
    text.window_create("end", window=button)
    text.insert("end", "\n")
    text.insert("end", code, ("code_block",))
    text.insert("end", "\n\n")
