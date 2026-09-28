"""Themed image data for the Checkbox and Switch indicators (private).

Turns the committed role masks (``bw_gui/assets/toggles``, built by
``tools/build_toggle_assets.py``) into ready-to-use PNG data for one theme:
each mask channel is a coverage map for one role (R fill, G outline, B mark/knob,
A focus ring); this module assigns a theme colour to every role and composites the
roles into straight-alpha RGBA.

Boundary: this renderer serves exactly the two toggle primitives and their menu
glyphs. It recolours fixed pixels and never rasterises shapes; it is not a general
graphics helper for bw-gui (see ``docs/TOGGLE_CONTRACT.md``).

Data contract (verified on Tk 8.6.15): RGBA -> PNG bytes -> base64 ASCII ->
``PhotoImage(format="png", data=...)``.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ._png_codec import decode_rgba, encode_rgba
from ._theme_manager import _mix, contrast_text_color, relative_luminance

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "toggles"
CONTROLS = ("checkbox", "switch")
SHAPES = ("off", "on", "mixed")
OVERLAYS = ("rest", "hover", "focus", "hover_focus")
DENSITIES = (1.0, 1.25, 1.5, 1.75, 2.0)
_BASE_TK_SCALING = 96 / 72
MIN_CONTRAST = 3.0  # WCAG 1.4.11 non-text contrast for state-bearing indicator parts


@dataclass(frozen=True)
class RoleColors:
    """Theme colours for the four mask roles; ``None`` leaves a role transparent."""

    fill: str
    outline: str
    mark: str | None
    ring: str | None


def density_for_scaling(tk_scaling: float) -> float:
    """Map Tk's ``tk scaling`` (pixels per point) to a supported asset density.

    The factor relative to 96 DPI is clamped to ``[1.0, 2.0]`` and rounded to the
    nearest supported density; ties round up (1.125 -> 1.25, 1.375 -> 1.5).

    Args:
        tk_scaling: Value of ``tk scaling`` (1.333... at 96 DPI).

    Returns:
        One of ``DENSITIES``.
    """
    factor = min(max(tk_scaling / _BASE_TK_SCALING, DENSITIES[0]), DENSITIES[-1])
    # Tie -> larger density: compare distances, preferring the later entry on equality.
    return min(reversed(DENSITIES), key=lambda density: abs(density - factor))


def contrast_ratio(color_a: str, color_b: str) -> float:
    """WCAG 2.1 contrast ratio between two ``#rrggbb`` colours (1.0 .. 21.0)."""
    high, low = sorted((relative_luminance(color_a), relative_luminance(color_b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _guarded(color: str, backgrounds: tuple[str, ...], toward: str) -> str:
    """Shift *color* towards *toward* until it reaches ``MIN_CONTRAST`` on all backgrounds.

    The contrast guard keeps the toggle state recognisable at low theme
    intensities ("dezent", "mittel"), where the accent colour alone falls below 3:1.
    Colours that already pass are returned unchanged, so the default intensity
    looks exactly like the theme; the shift is the smallest 5 % step that passes.

    Args:
        color:       Candidate colour.
        backgrounds: Colours it is drawn on or next to.
        toward:      High-contrast target to mix towards (e.g. ``fg_primary``).
    """
    for step in range(21):
        candidate = _mix(color, toward, step / 20)
        if all(contrast_ratio(candidate, background) >= MIN_CONTRAST for background in backgrounds):
            return candidate
    return toward


def image_keys() -> tuple[str, ...]:
    """All image keys per control: 3 shapes x 4 overlays plus 3 muted (disabled)."""
    keys = [f"{shape}-{overlay}" for shape in SHAPES for overlay in OVERLAYS]
    return tuple(keys + [f"{shape}-muted" for shape in SHAPES])


def role_colors(theme: dict[str, str], control: str, image_key: str) -> RoleColors:
    """Assign theme colours to the mask roles for one control state image.

    Colour rules (the shape itself carries the state; colour only reinforces it):

    * off: surface-coloured fill, ``fg_muted`` border (checkbox) / knob (switch);
      hover turns the border ``accent``.
    * on: ``accent`` fill (``accent_hover`` on hover), ``fg_on_accent`` mark/knob.
    * mixed: checkbox like on with a dash; switch ``accent_soft`` track with an
      ``accent`` knob in the centre.
    * muted (disabled): the rest colours mixed 55 % towards ``bg_main``, no ring.
    * focus: ``focus_ring`` ring around the indicator.
    * contrast guard (all non-muted states): fill/border/knob reach 3:1 against
      ``bg_main`` and ``bg_surface`` (shifted towards ``fg_primary``), the mark/knob
      reaches 3:1 against its fill (shifted towards black or white). Disabled states
      are exempt, as in WCAG.

    Args:
        theme:     Resolved theme dict (``get_theme``).
        control:   ``"checkbox"`` or ``"switch"``.
        image_key: ``"<shape>-<overlay>"`` from ``image_keys()``.

    Returns:
        The colours for fill, outline, mark and ring.
    """
    shape, overlay = image_key.split("-", 1)
    hover = overlay in ("hover", "hover_focus")
    ring = theme["focus_ring"] if overlay in ("focus", "hover_focus") else None
    backgrounds = (theme["bg_main"], theme["bg_surface"])
    guard = (lambda color: _guarded(color, backgrounds, theme["fg_primary"])) if overlay != "muted" else (lambda c: c)
    accent = guard(theme["accent_hover"] if hover else theme["accent"])
    if shape == "off":
        colors = RoleColors(
            fill=theme["bg_surface"],
            outline=guard(theme["accent"]) if hover else guard(theme["fg_muted"]),
            mark=guard(theme["fg_muted"]) if control == "switch" else None,
            ring=ring,
        )
    elif shape == "mixed" and control == "switch":
        knob = accent if overlay == "muted" else _guarded(accent, (theme["accent_soft"],), theme["fg_primary"])
        colors = RoleColors(fill=theme["accent_soft"], outline=accent, mark=knob, ring=ring)
    else:
        mark = theme["fg_on_accent"]
        if overlay != "muted":
            mark = _guarded(mark, (accent,), contrast_text_color(accent))
        colors = RoleColors(fill=accent, outline=accent, mark=mark, ring=ring)
    if overlay != "muted":
        return colors
    fade = lambda color: None if color is None else _mix(color, theme["bg_main"], 0.55)  # noqa: E731
    return RoleColors(fill=fade(colors.fill), outline=fade(colors.outline), mark=fade(colors.mark), ring=None)


@lru_cache(maxsize=None)
def _mask(control: str, shape: str, density: float) -> tuple[int, int, bytes]:
    """Decoded role mask for one control/shape/density (cached for the process)."""
    path = ASSET_DIR / f"{control}_{shape}_{round(density * 100)}.png"
    width, height, pixels = decode_rgba(path.read_bytes())
    return width, height, bytes(pixels)


def _rgb(color: str) -> tuple[int, int, int]:
    """``#rrggbb`` -> RGB tuple."""
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def compose(width: int, height: int, mask: bytes, colors: RoleColors) -> bytearray:
    """Composite the four roles (fill, outline, mark, ring - in that order) into RGBA.

    Every role is painted "over" the result so far with its mask coverage as alpha;
    the output keeps straight (non-premultiplied) alpha so Tk can blend it onto any
    widget background.

    Args:
        width:  Mask width.
        height: Mask height.
        mask:   Flat RGBA role mask (``_mask``).
        colors: Role colours; ``None`` roles are skipped.

    Returns:
        Flat straight-alpha RGBA pixels.
    """
    layers = [(channel, _rgb(color)) for channel, color in enumerate(
        (colors.fill, colors.outline, colors.mark, colors.ring)) if color is not None]
    out = bytearray(width * height * 4)
    for i in range(0, len(mask), 4):
        red = green = blue = alpha = 0.0  # premultiplied accumulator
        for channel, (r, g, b) in layers:
            coverage = mask[i + channel] / 255
            if coverage:
                red = r * coverage + red * (1 - coverage)
                green = g * coverage + green * (1 - coverage)
                blue = b * coverage + blue * (1 - coverage)
                alpha = coverage + alpha * (1 - coverage)
        if alpha:
            out[i:i + 4] = bytes((round(red / alpha), round(green / alpha), round(blue / alpha), round(alpha * 255)))
    return out


@lru_cache(maxsize=None)
def _encoded(control: str, image_key: str, density: float, colors: RoleColors) -> str:
    """Base64 PNG data for one image; cache key = (control, image, density, colours)."""
    shape = image_key.split("-", 1)[0]
    width, height, mask = _mask(control, shape, density)
    png = encode_rgba(width, height, compose(width, height, mask, colors))
    return base64.b64encode(png).decode("ascii")


def image_data(theme: dict[str, str], control: str, image_key: str, density: float) -> str:
    """Base64 PNG data for ``PhotoImage(format="png", data=...)``.

    Cached by the *resolved* role colours rather than the theme key, so theme
    intensity changes and re-registered themes can never serve stale data.

    Args:
        theme:     Resolved theme dict.
        control:   ``"checkbox"`` or ``"switch"``.
        image_key: Key from ``image_keys()``.
        density:   One of ``DENSITIES``.
    """
    return _encoded(control, image_key, density, role_colors(theme, control, image_key))
