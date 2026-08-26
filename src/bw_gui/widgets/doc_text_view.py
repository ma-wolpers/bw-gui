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

from .doc_text_events import CodeBlockEvent, DocEvent, HeadingEvent, ListItemEvent, ParagraphEvent, TextRun

_HEADING_SIZE_DELTA = {1: 8, 2: 5, 3: 2}


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
