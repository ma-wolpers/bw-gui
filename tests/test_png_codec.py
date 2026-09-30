"""Tests for the private stdlib PNG codec used by the toggle assets."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from bw_gui.theming._png_codec import decode_rgba, encode_rgba

ASSET_DIR = Path(__file__).resolve().parents[1] / "src" / "bw_gui" / "assets" / "toggles"


def _png_with_filtered_rows(width: int, height: int, rows: list[bytes]) -> bytes:
    """Build a PNG whose IDAT rows already carry their own filter byte."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def test_roundtrip_preserves_pixels() -> None:
    pixels = bytearray(range(3 * 2 * 4))
    width, height, decoded = decode_rgba(encode_rgba(3, 2, pixels))
    assert (width, height, decoded) == (3, 2, pixels)


def test_encode_rejects_mismatched_buffer() -> None:
    with pytest.raises(ValueError):
        encode_rgba(2, 2, bytes(15))


@pytest.mark.parametrize("filter_type", [1, 2, 3, 4])
def test_decode_undoes_every_filter_type(filter_type: int) -> None:
    # Row 0 unfiltered, row 1 uses the filter with an all-zero delta, so every
    # predictor must reproduce the value it predicts from row 0 / the left pixel.
    row0 = bytes([10, 20, 30, 40, 50, 60, 70, 80])
    data = _png_with_filtered_rows(2, 2, [b"\x00" + row0, bytes([filter_type]) + bytes(8)])
    _w, _h, pixels = decode_rgba(data)
    expected_row1 = {
        1: bytes(8),                                        # Sub: left of first pixel is 0
        2: row0,                                            # Up
        3: bytes([5, 10, 15, 20, 27, 35, 42, 50]),          # Average of left and up
        4: row0,                                            # Paeth picks up (left=0 for pixel 0)
    }[filter_type]
    assert bytes(pixels[8:]) == expected_row1


def test_decode_rejects_other_formats() -> None:
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # RGB, not RGBA
    crc = struct.pack(">I", zlib.crc32(b"IHDR" + header) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(header)) + b"IHDR" + header + crc
    with pytest.raises(ValueError):
        decode_rgba(data)
    with pytest.raises(ValueError):
        decode_rgba(b"GIF89a")


@pytest.mark.parametrize("density", [100, 125, 150, 175, 200])
@pytest.mark.parametrize("control, base", [("checkbox", (28, 22)), ("switch", (46, 24))])
@pytest.mark.parametrize("shape", ["off", "on", "mixed"])
def test_committed_assets_decode_with_expected_size(control: str, base: tuple[int, int], shape: str, density: int) -> None:
    width, height, _pixels = decode_rgba((ASSET_DIR / f"{control}_{shape}_{density}.png").read_bytes())
    assert (width, height) == (round(base[0] * density / 100), round(base[1] * density / 100))
