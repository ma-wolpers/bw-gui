"""Progress ring chart widget for drawing themed multi-segment ring charts.

Provides ``draw_ring_chart`` — a drawing function that paints a multi-segment
ring chart onto any ``tk.Canvas`` with full automatic dark/light theme
adaptation.  The consumer supplies per-segment data including both color
variants; bw_gui picks the correct variant for the active theme internally.

No color value or theme decision reaches consumer code::

    from bw_gui.widgets.ring_chart import draw_ring_chart, RingSegment

    draw_ring_chart(
        self._ring_canvas,
        [
            RingSegment(light_color="#2563EB", dark_color="#60A5FA", fraction=0.4),
            RingSegment(light_color="#16A34A", dark_color="#4ADE80", fraction=0.3),
            RingSegment(light_color="#CA8A04", dark_color="#FDE047", fraction=0.3),
        ],
    )

Call ``draw_ring_chart`` again whenever the canvas needs repainting (on theme
switch, on data change, or after the canvas is first realized).  The function
always reads the current global theme — no ``theme_key`` argument.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from ..theming.theme_manager import _is_dark, get_theme


@dataclass
class RingSegment:
    """Data for one segment of a ring chart.

    The consumer owns the domain color values and passes both light and dark
    variants; bw_gui picks the correct one based on the active theme so
    consumer code never performs a dark/light check.

    Attributes:
        light_color: ``"#RRGGBB"`` hex used when the active theme is light.
        dark_color:  ``"#RRGGBB"`` hex used when the active theme is dark.
        fraction:    Share of the full ring in [0, 1].  Segments are drawn
                     clockwise starting from 12 o'clock.  If the fractions of
                     all segments sum to less than 1.0, the remainder of the
                     ring shows the track background color.
    """

    light_color: str
    dark_color: str
    fraction: float


def draw_ring_chart(
    canvas: tk.Canvas,
    segments: list[RingSegment],
    *,
    center_bg_token: str = "bg_surface",
    ring_bg_token: str = "border",
) -> None:
    """Draw a multi-segment ring chart on *canvas* using the current theme.

    Clears *canvas* and repaints a ring (donut) chart built from *segments*.
    The dark/light theme adaptation is entirely internal — the consumer never
    calls ``is_dark_theme()`` or reads any hex value.

    Rendering model:
      1. A filled disk at ``ring_bg_token`` color forms the ring track.
      2. Each segment is drawn as a pie slice from its domain color (light or
         dark variant chosen by bw_gui).  Segments are laid out clockwise
         starting from the 12 o'clock position.
      3. A smaller filled disk at ``center_bg_token`` color covers the center,
         creating the donut (ring) effect.

    Sizing is taken from the canvas widget's current realized dimensions
    (``winfo_width`` / ``winfo_height``); if the canvas has not yet been
    mapped, the configured ``width`` / ``height`` options are used as fallback.
    Call ``draw_ring_chart`` from within a ``<Configure>`` binding or after the
    window is realized to ensure accurate sizing.

    Args:
        canvas:          The ``tk.Canvas`` to draw on.  Caller is responsible
                         for creating and placing the canvas; this function
                         manages only its contents.
        segments:        Ordered list of ``RingSegment`` instances.  Drawn
                         clockwise from 12 o'clock.
        center_bg_token: Contract token for the center hole background.
                         Defaults to ``"bg_surface"`` so the hole blends into
                         the card/surface the ring sits on.
        ring_bg_token:   Contract token for the ring track background (the
                         unfilled arc).  Defaults to ``"border"``.
    """
    canvas.delete("all")

    w = canvas.winfo_width() or int(canvas.cget("width") or 100)
    h = canvas.winfo_height() or int(canvas.cget("height") or 100)
    cx, cy = w // 2, h // 2

    theme = get_theme()
    dark = _is_dark(theme["bg_main"])
    center_bg = theme[center_bg_token]
    ring_bg = theme[ring_bg_token]

    outer = int(min(w, h) * 0.46)
    inner = int(outer * 0.58)

    # Ring track background (full disk)
    canvas.create_oval(
        cx - outer, cy - outer, cx + outer, cy + outer,
        fill=ring_bg, outline="",
    )

    # Segments (pie slices, clockwise from 12 o'clock)
    # Tk's arc angles: 0 = 3 o'clock, positive = counter-clockwise.
    # We start at 90 (12 o'clock) and subtract extent for clockwise motion.
    tk_start = 90.0
    for seg in segments:
        if seg.fraction <= 0:
            continue
        color = seg.dark_color if dark else seg.light_color
        extent = seg.fraction * 360.0
        canvas.create_arc(
            cx - outer, cy - outer, cx + outer, cy + outer,
            start=tk_start, extent=-extent,
            fill=color, outline="", style="pieslice",
        )
        tk_start -= extent

    # Center hole (drawn last to create the donut effect)
    canvas.create_oval(
        cx - inner, cy - inner, cx + inner, cy + inner,
        fill=center_bg, outline="",
    )
