"""Build the role-mask PNGs for bw-gui's Checkbox and Switch indicators (dev tool).

Run from the repo root whenever the indicator geometry changes::

    python tools/build_toggle_assets.py

The output is committed under ``src/bw_gui/assets/toggles/``; the runtime never runs
this script and never rasterises shapes itself (see ``docs/TOGGLE_CONTRACT.md``).

Each PNG is a *role mask*, not a picture: the four channels hold anti-aliased
coverage (0..255) for one role each and are coloured by the theme at runtime::

    R = fill      (checkbox box interior / switch track interior)
    G = outline   (inner border band of the box / track)
    B = mark      (check mark or dash / switch knob)
    A = ring      (focus ring outside the box / track)

Anti-aliasing uses signed distance fields sampled at pixel centres
(coverage = clamp(0.5 - distance, 0, 1)), which needs only the standard library.
One file per control, shape and density: ``{control}_{shape}_{density%}.png``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bw_gui.theming._png_codec import encode_rgba  # noqa: E402

OUT_DIR = ROOT / "src" / "bw_gui" / "assets" / "toggles"
DENSITIES = (1.0, 1.25, 1.5, 1.75, 2.0)
SHAPES = ("off", "on", "mixed")

# Geometry in 96-DPI pixels, relative to the canvas centre.
CHECKBOX = {"canvas": (22, 22), "half": (8.0, 8.0), "radius": 4.0, "outline": 1.5}
CHECK_MARK = [(-4.2, 0.2), (-1.3, 3.1), (4.3, -3.2)]
DASH = [(-4.0, 0.0), (4.0, 0.0)]
MARK_HALF_WIDTH = 1.1
SWITCH = {"canvas": (40, 24), "half": (17.0, 9.0), "radius": 9.0, "outline": 1.25}
KNOB_RADIUS = 6.5
KNOB_OFFSET = {"off": -8.0, "on": 8.0, "mixed": 0.0}
RING_GAP, RING_WIDTH = 1.0, 1.5

Sdf = Callable[[float, float], float]


def rounded_box(half_x: float, half_y: float, radius: float) -> Sdf:
    """Signed distance to a centred rounded rectangle (negative inside)."""
    def sdf(x: float, y: float) -> float:
        qx, qy = abs(x) - half_x + radius, abs(y) - half_y + radius
        outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
        return outside + min(max(qx, qy), 0.0) - radius
    return sdf


def circle(cx: float, cy: float, radius: float) -> Sdf:
    """Signed distance to a circle (negative inside)."""
    return lambda x, y: math.hypot(x - cx, y - cy) - radius


def polyline(points: list[tuple[float, float]], half_width: float) -> Sdf:
    """Signed distance to a round-capped stroke along *points* (negative inside)."""
    segments = list(zip(points, points[1:]))

    def segment_distance(x: float, y: float, a: tuple[float, float], b: tuple[float, float]) -> float:
        abx, aby = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((x - a[0]) * abx + (y - a[1]) * aby) / (abx * abx + aby * aby)))
        return math.hypot(x - a[0] - t * abx, y - a[1] - t * aby)

    return lambda x, y: min(segment_distance(x, y, a, b) for a, b in segments) - half_width


def coverage(distance: float) -> float:
    """Pixel coverage for a signed distance measured at the pixel centre."""
    return max(0.0, min(1.0, 0.5 - distance))


def render(canvas: tuple[int, int], density: float, body: Sdf, outline_width: float,
           mark: Sdf | None) -> tuple[int, int, bytearray]:
    """Rasterise the four role channels for one shape at one density.

    Args:
        canvas:        Canvas size in 96-DPI pixels.
        density:       Density factor (1.0 = 96 DPI).
        body:          SDF of the box/track in 96-DPI units.
        outline_width: Width of the inner border band in 96-DPI units.
        mark:          SDF of the check mark/dash/knob, or ``None`` for no mark.

    Returns:
        ``(width, height, rgba_pixels)`` of the role mask.
    """
    width, height = round(canvas[0] * density), round(canvas[1] * density)
    pixels = bytearray(width * height * 4)
    for py in range(height):
        for px in range(width):
            # Pixel centre, converted back to 96-DPI units around the canvas centre.
            x = (px + 0.5 - width / 2) / density
            y = (py + 0.5 - height / 2) / density
            d = body(x, y) * density
            fill = coverage(d)
            outline = fill - coverage(d + outline_width * density)
            ring = coverage(d - (RING_GAP + RING_WIDTH) * density) - coverage(d - RING_GAP * density)
            knob = coverage(mark(x, y) * density) if mark is not None else 0.0
            i = (py * width + px) * 4
            pixels[i:i + 4] = bytes(round(v * 255) for v in (fill, outline, knob, ring))
    return width, height, pixels


def build() -> list[Path]:
    """Render every control/shape/density combination into ``OUT_DIR``."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    box = rounded_box(*CHECKBOX["half"], CHECKBOX["radius"])
    track = rounded_box(*SWITCH["half"], SWITCH["radius"])
    marks = {"off": None, "on": polyline(CHECK_MARK, MARK_HALF_WIDTH), "mixed": polyline(DASH, MARK_HALF_WIDTH)}
    written = []
    for density in DENSITIES:
        for shape in SHAPES:
            jobs = {
                "checkbox": (CHECKBOX["canvas"], box, CHECKBOX["outline"], marks[shape]),
                "switch": (SWITCH["canvas"], track, SWITCH["outline"], circle(KNOB_OFFSET[shape], 0.0, KNOB_RADIUS)),
            }
            for control, (canvas, body, outline_width, mark) in jobs.items():
                width, height, pixels = render(canvas, density, body, outline_width, mark)
                path = OUT_DIR / f"{control}_{shape}_{round(density * 100)}.png"
                path.write_bytes(encode_rgba(width, height, pixels))
                written.append(path)
    return written


if __name__ == "__main__":
    for written_path in build():
        print(written_path.relative_to(ROOT))
