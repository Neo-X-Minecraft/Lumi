# SPDX-License-Identifier: 0BSD
"""Small, strict PNG utilities for 8-bit skin textures and grayscale masks."""
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk(kind, data):
    return (
        struct.pack("!I", len(data))
        + kind
        + data
        + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def chunks(blob):
    if not blob.startswith(SIGNATURE):
        raise ValueError("Not a PNG")
    pos, result = 8, []
    while pos < len(blob):
        if pos + 12 > len(blob):
            raise ValueError("Truncated PNG chunk")
        n = struct.unpack("!I", blob[pos : pos + 4])[0]
        kind, data = blob[pos + 4 : pos + 8], blob[pos + 8 : pos + 8 + n]
        if (
            pos + 12 + n > len(blob)
            or zlib.crc32(kind + data) & 0xFFFFFFFF
            != struct.unpack("!I", blob[pos + 8 + n : pos + 12 + n])[0]
        ):
            raise ValueError("Invalid PNG chunk checksum")
        result.append((kind, data))
        pos += n + 12
        if kind == b"IEND":
            break
    if pos != len(blob) or not result or result[-1] != (b"IEND", b""):
        raise ValueError("Invalid PNG ending")
    return result


def paeth(a, b, c):
    p = a + b - c
    dist = (abs(p - a), abs(p - b), abs(p - c))
    return (a, b, c)[dist.index(min(dist))]


def filter_rows(raw, width, height, bpp, filters):
    stride = width * bpp
    if len(raw) != stride * height or len(filters) != height:
        raise ValueError("Image dimensions do not match pixels")
    out = bytearray()
    for y, kind in enumerate(filters):
        if not 0 <= kind <= 4:
            raise ValueError("Unknown PNG filter")
        out.append(kind)
        for x in range(stride):
            i = y * stride + x
            a = raw[i - bpp] if x >= bpp else 0
            b = raw[i - stride] if y else 0
            c = raw[i - stride - bpp] if y and x >= bpp else 0
            out.append((raw[i] - (0, a, b, (a + b) // 2, paeth(a, b, c))[kind]) & 255)
    return bytes(out)


def indexed(width, height, palette, stream):
    if not 1 <= len(palette) <= 256:
        raise ValueError("Palette must contain 1 to 256 colors")
    return (
        SIGNATURE
        + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 3, 0, 0, 0))
        + chunk(b"PLTE", b"".join(bytes(c[:3]) for c in palette))
        + chunk(b"tRNS", bytes(c[3] for c in palette).rstrip(b"\xff"))
        + chunk(b"IDAT", stream)
        + chunk(b"IEND", b"")
    )


def rgba(width, height, raw):
    return (
        SIGNATURE
        + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0))
        + chunk(
            b"IDAT", zlib.compress(filter_rows(raw, width, height, 4, [0] * height), 9)
        )
        + chunk(b"IEND", b"")
    )


def gray(width, height, raw):
    return (
        SIGNATURE
        + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 0, 0, 0, 0))
        + chunk(
            b"IDAT", zlib.compress(filter_rows(raw, width, height, 1, [0] * height), 9)
        )
        + chunk(b"IEND", b"")
    )


def decode(blob):
    parts = chunks(blob)
    fields = dict(parts)
    w, h, depth, kind, compression, filtering, interlace = struct.unpack(
        "!2I5B", fields[b"IHDR"]
    )
    if (
        depth != 8
        or kind not in (0, 2, 3, 4, 6)
        or compression
        or filtering
        or interlace
    ):
        raise ValueError("Expected a non-interlaced 8-bit PNG")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[kind]
    stride = w * bpp
    packed = zlib.decompress(b"".join(data for tag, data in parts if tag == b"IDAT"))
    if len(packed) != (stride + 1) * h:
        raise ValueError("Unexpected PNG pixel length")
    pixels = bytearray()
    pos = 0
    for y in range(h):
        f = packed[pos]
        pos += 1
        if f > 4:
            raise ValueError("Unknown PNG filter")
        row = bytearray(packed[pos : pos + stride])
        pos += stride
        for x in range(stride):
            a = row[x - bpp] if x >= bpp else 0
            b = pixels[(y - 1) * stride + x] if y else 0
            c = pixels[(y - 1) * stride + x - bpp] if y and x >= bpp else 0
            row[x] = (row[x] + (0, a, b, (a + b) // 2, paeth(a, b, c))[f]) & 255
        pixels.extend(row)
    out = bytearray()
    palette = fields.get(b"PLTE", b"")
    alpha = fields.get(b"tRNS", b"")
    for i in range(0, len(pixels), bpp):
        p = pixels[i : i + bpp]
        if kind == 6:
            out.extend(p)
        elif kind == 2:
            out.extend(p + b"\xff")
        elif kind == 0:
            out.extend(bytes([p[0], p[0], p[0], 255]))
        elif kind == 4:
            out.extend(bytes([p[0], p[0], p[0], p[1]]))
        else:
            k = p[0]
            if k * 3 + 3 > len(palette):
                raise ValueError("Palette index out of range")
            out.extend(
                palette[k * 3 : k * 3 + 3]
                + bytes([alpha[k] if k < len(alpha) else 255])
            )
    return w, h, bytes(out)
