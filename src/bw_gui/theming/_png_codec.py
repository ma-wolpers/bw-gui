"""Minimal stdlib PNG codec for bw-gui's own toggle assets (private).

Scope is deliberately narrow: 8-bit RGBA, non-interlaced PNGs as produced by
``tools/build_toggle_assets.py``. This is *not* a general PNG library and must not
grow into one (see ``docs/TOGGLE_CONTRACT.md``). Anything outside that format raises
``ValueError`` instead of being half-supported.

Pixels are handled as a flat ``bytearray`` of ``width * height * 4`` bytes in RGBA
order, row-major, which is both what the decoder returns and what the encoder takes.
"""

from __future__ import annotations

import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOR_TYPE_RGBA = 6


def _chunk(tag: bytes, data: bytes) -> bytes:
    """Return one PNG chunk (length, tag, data, CRC) as bytes.

    Args:
        tag:  Four-byte chunk type, e.g. ``b"IHDR"``.
        data: Chunk payload.
    """
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def encode_rgba(width: int, height: int, pixels: bytes | bytearray) -> bytes:
    """Encode flat RGBA pixels as a PNG file (filter type 0 on every row).

    Args:
        width:  Image width in pixels (> 0).
        height: Image height in pixels (> 0).
        pixels: ``width * height * 4`` bytes, RGBA, row-major.

    Returns:
        The complete PNG file as bytes.

    Raises:
        ValueError: If the size does not match the pixel buffer.
    """
    stride = width * 4
    if width <= 0 or height <= 0 or len(pixels) != stride * height:
        raise ValueError(f"pixel buffer of {len(pixels)} bytes does not match {width}x{height} RGBA")
    raw = b"".join(b"\x00" + bytes(pixels[row * stride:(row + 1) * stride]) for row in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, _COLOR_TYPE_RGBA, 0, 0, 0)
    return _SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def _paeth(left: int, up: int, up_left: int) -> int:
    """PNG Paeth predictor for one byte."""
    estimate = left + up - up_left
    dist_left, dist_up, dist_up_left = abs(estimate - left), abs(estimate - up), abs(estimate - up_left)
    if dist_left <= dist_up and dist_left <= dist_up_left:
        return left
    return up if dist_up <= dist_up_left else up_left


def _unfilter(raw: bytes, width: int, height: int) -> bytearray:
    """Undo PNG scanline filters (types 0-4) for 4-byte RGBA pixels.

    Args:
        raw:    Decompressed IDAT stream (one filter byte per row, then the row).
        width:  Image width in pixels.
        height: Image height in pixels.

    Returns:
        Flat RGBA pixel buffer.

    Raises:
        ValueError: On an unknown filter type or a truncated stream.
    """
    stride = width * 4
    if len(raw) != (stride + 1) * height:
        raise ValueError("truncated or oversized PNG image data")
    out = bytearray(stride * height)
    previous = bytearray(stride)
    for row in range(height):
        offset = row * (stride + 1)
        filter_type = raw[offset]
        line = bytearray(raw[offset + 1:offset + 1 + stride])
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up = previous[i]
            up_left = previous[i - 4] if i >= 4 else 0
            if filter_type == 1:
                line[i] = (line[i] + left) & 0xFF
            elif filter_type == 2:
                line[i] = (line[i] + up) & 0xFF
            elif filter_type == 3:
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
            elif filter_type == 4:
                line[i] = (line[i] + _paeth(left, up, up_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter type {filter_type}")
        out[row * stride:(row + 1) * stride] = line
        previous = line
    return out


def decode_rgba(data: bytes) -> tuple[int, int, bytearray]:
    """Decode an 8-bit RGBA, non-interlaced PNG.

    Args:
        data: Complete PNG file contents.

    Returns:
        ``(width, height, pixels)`` with ``pixels`` as flat RGBA bytes.

    Raises:
        ValueError: If the file is not a PNG of exactly the supported format.
    """
    if not data.startswith(_SIGNATURE):
        raise ValueError("not a PNG file")
    pos = len(_SIGNATURE)
    width = height = 0
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, depth, color_type, _comp, _filter, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color_type != _COLOR_TYPE_RGBA or interlace != 0:
                raise ValueError("only 8-bit RGBA non-interlaced PNGs are supported")
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    if width == 0 or height == 0:
        raise ValueError("PNG without IHDR")
    return width, height, _unfilter(zlib.decompress(bytes(idat)), width, height)
