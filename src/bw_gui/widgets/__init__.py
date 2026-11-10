"""Shared widget primitives."""

from .collapsible_section import CollapsibleSection
from .doc_text_events import CodeBlockEvent, DocEvent, HeadingEvent, ListItemEvent, ParagraphEvent, TextRun, html_to_events
from .doc_text_view import configure_doc_text_tags, configure_doc_text_theme, render_events_into_text
from .drag_drop import DragDropController
from .grid_span import GridSpanSegment, compute_contiguous_spans
from .hover_tooltip import HoverTooltip
from .radio_group import RadioGroup
from .regex_entry_field import RegexEntryField
from .resizable_side_overlay import ResizableSideOverlay
from .ring_chart import RingSegment, draw_ring_chart
from .scrollable_frame import ScrollableFrame
from .scrollable_image_preview import ScrollableImagePreview
from .toggles import Checkbox, Switch
from .wrapped_text_field import WrappedTextField
from .zoomable_doc_text import ZoomableDocText

__all__ = [
    "Checkbox",
    "CollapsibleSection",
    "CodeBlockEvent",
    "DocEvent",
    "DragDropController",
    "GridSpanSegment",
    "HeadingEvent",
    "HoverTooltip",
    "ListItemEvent",
    "ParagraphEvent",
    "RadioGroup",
    "RegexEntryField",
    "ResizableSideOverlay",
    "RingSegment",
    "ScrollableFrame",
    "ScrollableImagePreview",
    "Switch",
    "TextRun",
    "WrappedTextField",
    "ZoomableDocText",
    "compute_contiguous_spans",
    "configure_doc_text_tags",
    "configure_doc_text_theme",
    "draw_ring_chart",
    "html_to_events",
    "render_events_into_text",
]
