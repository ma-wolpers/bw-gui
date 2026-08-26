"""Pure HTML-to-event translation for rendering simple docs into a Tk Text widget.

Deliberately dependency-free (stdlib ``html.parser`` only) and Tk-free, so this
layer is fully unit-testable without building any widgets. ``doc_text_view.py``
consumes the event list and does the actual (thin) Tk insertion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BOLD_TAGS = {"b", "strong"}
_ITALIC_TAGS = {"i", "em"}
_CELL_TAGS = {"td", "th"}


@dataclass(frozen=True)
class TextRun:
    """One inline run of text with the formatting active while it was parsed."""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False


@dataclass(frozen=True)
class HeadingEvent:
    level: int
    runs: tuple[TextRun, ...]


@dataclass(frozen=True)
class ParagraphEvent:
    runs: tuple[TextRun, ...]


@dataclass(frozen=True)
class ListItemEvent:
    ordered: bool
    runs: tuple[TextRun, ...]


@dataclass(frozen=True)
class CodeBlockEvent:
    """One fenced/indented code block. Every event of this type gets a copy button."""

    text: str


DocEvent = HeadingEvent | ParagraphEvent | ListItemEvent | CodeBlockEvent


@dataclass
class _OpenState:
    bold: int = 0
    italic: int = 0
    code: int = 0
    list_ordered: list[bool] = field(default_factory=list)
    in_pre: bool = False
    pre_buffer: list[str] = field(default_factory=list)
    table_row_cells: list[tuple[TextRun, ...]] | None = None


class _DocHtmlParser(HTMLParser):
    """Walks a small, known subset of HTML (as produced by ``markdown``) into events."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[DocEvent] = []
        self._runs: list[TextRun] = []
        self._state = _OpenState()

    def handle_starttag(self, tag: str, attrs) -> None:
        state = self._state
        if tag in _HEADING_TAGS or tag in ("p", "li", "pre"):
            # Discards inter-tag whitespace (e.g. the newline between "</p>"
            # and the next "<h2>") so it doesn't leak into the next block's runs.
            self._flush_runs()
        if tag == "pre":
            state.in_pre = True
            state.pre_buffer = []
            return
        if state.in_pre:
            return
        if tag in _BOLD_TAGS:
            state.bold += 1
        elif tag in _ITALIC_TAGS:
            state.italic += 1
        elif tag == "code":
            state.code += 1
        elif tag in ("ul", "ol"):
            state.list_ordered.append(tag == "ol")
        elif tag == "tr":
            state.table_row_cells = []
        elif tag in _CELL_TAGS:
            self._flush_runs()

    def handle_endtag(self, tag: str) -> None:
        state = self._state
        if tag == "pre":
            state.in_pre = False
            self.events.append(CodeBlockEvent(text="".join(state.pre_buffer).strip("\n")))
            return
        if state.in_pre:
            return
        if tag in _BOLD_TAGS:
            state.bold = max(0, state.bold - 1)
        elif tag in _ITALIC_TAGS:
            state.italic = max(0, state.italic - 1)
        elif tag == "code":
            state.code = max(0, state.code - 1)
        elif tag in _HEADING_TAGS:
            level = int(tag[1])
            self.events.append(HeadingEvent(level=level, runs=self._flush_runs()))
        elif tag == "p":
            runs = self._flush_runs()
            if runs:
                self.events.append(ParagraphEvent(runs=runs))
        elif tag == "li":
            ordered = state.list_ordered[-1] if state.list_ordered else False
            self.events.append(ListItemEvent(ordered=ordered, runs=self._flush_runs()))
        elif tag in ("ul", "ol"):
            if state.list_ordered:
                state.list_ordered.pop()
        elif tag in _CELL_TAGS:
            cell_runs = self._flush_runs()
            if state.table_row_cells is None:
                state.table_row_cells = []
            state.table_row_cells.append(cell_runs)
        elif tag == "tr":
            cells = state.table_row_cells or []
            state.table_row_cells = None
            combined: list[TextRun] = []
            for index, cell in enumerate(cells):
                if index > 0:
                    combined.append(TextRun(text="\t"))
                combined.extend(cell)
            if combined:
                self.events.append(ParagraphEvent(runs=tuple(combined)))

    def handle_data(self, data: str) -> None:
        state = self._state
        if state.in_pre:
            state.pre_buffer.append(data)
            return
        if not data:
            return
        self._runs.append(
            TextRun(text=data, bold=state.bold > 0, italic=state.italic > 0, code=state.code > 0)
        )

    def _flush_runs(self) -> tuple[TextRun, ...]:
        runs = tuple(self._runs)
        self._runs = []
        return runs


def html_to_events(html: str) -> list[DocEvent]:
    """Translates a simple HTML fragment (as produced by ``markdown.Markdown``) into events.

    Supports headings, paragraphs, bold/italic/inline code, unordered/ordered
    list items, fenced code blocks, and (flattened, tab-separated) table rows.
    Anything else is ignored rather than raising, since the input is always our
    own generated documentation HTML, not arbitrary untrusted markup.
    """

    parser = _DocHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.events
