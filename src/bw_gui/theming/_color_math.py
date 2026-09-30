"""Color math for the theme system (private, pure functions, no state).

Split out of ``_theme_manager`` (file-size rule). ``_theme_manager`` re-exports every
name here, so ``from ._theme_manager import _mix`` etc. keep working.
"""

from __future__ import annotations


# ── Private color helpers ────────────────────────────────────────────────────

def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse a ``"#RRGGBB"`` string into an (R, G, B) int tuple.

    Strips leading ``#`` and whitespace.  Returns ``(0, 0, 0)`` for any input
    that is not exactly 6 hex digits after stripping.
    """
    text = color.strip().lstrip("#")
    if len(text) != 6:
        return (0, 0, 0)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _mix(color_a: str, color_b: str, ratio: float) -> str:
    """Linearly interpolate between two ``"#RRGGBB"`` hex colors.

    ``ratio=0.0`` returns *color_a* unchanged; ``ratio=1.0`` returns *color_b*.
    Values outside [0, 1] are clamped.  Returns a ``"#RRGGBB"`` string.
    """
    ax, ay, az = _hex_to_rgb(color_a)
    bx, by, bz = _hex_to_rgb(color_b)
    w = max(0.0, min(1.0, ratio))
    return (
        f"#{round(ax + (bx - ax) * w):02X}"
        f"{round(ay + (by - ay) * w):02X}"
        f"{round(az + (bz - az) * w):02X}"
    )


def _is_dark(color: str) -> bool:
    """Return True if *color* is perceptually dark using a fast luminance check.

    Uses weighted-average luminance (the W3C fast approximation) against a
    threshold of 0.45.  Not the full WCAG linearized calculation — use
    ``relative_luminance()`` when WCAG contrast ratios matter.
    """
    r, g, b = _hex_to_rgb(color)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return luminance < 0.45


# ── Public color utilities ───────────────────────────────────────────────────

def mix_hex(base: str, target: str, ratio: float) -> str:
    """Mix two ``"#RRGGBB"`` hex colors and return the result.

    Thin public alias for the internal ``_mix()`` helper.

    Args:
        base:   Starting color (``ratio=0`` returns this unchanged).
        target: Ending color (``ratio=1`` returns this unchanged).
        ratio:  Blend weight in [0, 1]; values outside that range are clamped.

    Returns:
        A ``"#RRGGBB"`` hex string for the blended color.

    Example — tint ``bg_surface`` with ``accent`` at 20%::

        tinted = mix_hex(theme["bg_surface"], theme["accent"], 0.20)
    """
    return _mix(base, target, ratio)


def relative_luminance(hex_color: str) -> float:
    """Compute the WCAG 2.1 relative luminance of a ``"#RRGGBB"`` hex color.

    Returns a value in [0.0, 1.0], where 0.0 is absolute black and 1.0 is
    absolute white.  Uses the full IEC 61966-2-1 sRGB linearization rather
    than the fast approximation used by ``_is_dark()``.

    Returns 0.0 for any unparseable input rather than raising.
    """
    color = hex_color.strip().lstrip("#")
    if len(color) != 6:
        return 0.0
    try:
        r = int(color[0:2], 16) / 255.0
        g = int(color[2:4], 16) / 255.0
        b = int(color[4:6], 16) / 255.0
    except ValueError:
        return 0.0

    def _srgb(c: float) -> float:
        """Linearise a single sRGB channel component to linear light."""
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast_text_color(bg_hex: str) -> str:
    """Return the highest-contrast text color (dark or white) for a given background.

    Uses ``relative_luminance()`` against a threshold of 0.38.  Returns
    ``"#111111"`` for light backgrounds and ``"#FFFFFF"`` for dark ones.

    Useful when computing foreground color for a dynamically-generated button
    background, e.g. inside ``configure_tinted_button_style()``.
    """
    return "#111111" if relative_luminance(bg_hex) >= 0.38 else "#FFFFFF"


def is_dark_color(color: str) -> bool:
    """Return True if *color* is perceptually dark.

    Public alias for ``_is_dark()``.  Use this to decide whether to apply a
    dark or light window chrome (title bar) via ``apply_window_chrome_theme()``.
    """
    return _is_dark(color)
