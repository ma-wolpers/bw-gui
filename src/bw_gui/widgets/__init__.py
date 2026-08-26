"""Shared widget primitives."""

from .doc_text_events import CodeBlockEvent, DocEvent, HeadingEvent, ListItemEvent, ParagraphEvent, TextRun, html_to_events
from .doc_text_view import configure_doc_text_tags, render_events_into_text
from .grid_span import GridSpanSegment, compute_contiguous_spans
from .hover_tooltip import HoverTooltip
from .ring_chart import RingSegment, draw_ring_chart
from .wrapped_text_field import WrappedTextField

__all__ = [
    "CodeBlockEvent",
    "DocEvent",
    "GridSpanSegment",
    "HeadingEvent",
    "HoverTooltip",
    "ListItemEvent",
    "ParagraphEvent",
    "RingSegment",
    "TextRun",
    "WrappedTextField",
    "compute_contiguous_spans",
    "configure_doc_text_tags",
    "draw_ring_chart",
    "html_to_events",
    "render_events_into_text",
]
