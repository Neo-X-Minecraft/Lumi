# SPDX-License-Identifier: 0BSD
"""sRGB/D65 perceptual color measurements."""
import math


def lab(rgb):
    linear = [
        v / 255 / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4
        for v in rgb[:3]
    ]
    r, g, b = linear
    xyz = (
        (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047,
        r * 0.2126729 + g * 0.7151522 + b * 0.0721750,
        (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883,
    )
    f = [v ** (1 / 3) if v > 216 / 24389 else (24389 / 27 * v + 16) / 116 for v in xyz]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def delta_e(a, b):
    l1, a1, b1 = a
    l2, a2, b2 = b
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    c = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c**7 / (c**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1, h2 = (
        math.degrees(math.atan2(b1, a1p)) % 360,
        math.degrees(math.atan2(b2, a2p)) % 360,
    )
    dl, dc, dh = l2 - l1, c2p - c1p, h2 - h1
    if c1p * c2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    d_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh) / 2)
    lp, cp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp = h1 + h2
    elif abs(h1 - h2) <= 180:
        hp = (h1 + h2) / 2
    elif h1 + h2 < 360:
        hp = (h1 + h2 + 360) / 2
    else:
        hp = (h1 + h2 - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(hp - 30))
        + 0.24 * math.cos(math.radians(2 * hp))
        + 0.32 * math.cos(math.radians(3 * hp + 6))
        - 0.20 * math.cos(math.radians(4 * hp - 63))
    )
    sl = 1 + 0.015 * (lp - 50) ** 2 / math.sqrt(20 + (lp - 50) ** 2)
    sc, sh = 1 + 0.045 * cp, 1 + 0.015 * cp * t
    rt = (
        -2
        * math.sqrt(cp**7 / (cp**7 + 25**7))
        * math.sin(math.radians(60 * math.exp(-(((hp - 275) / 25) ** 2))))
    )
    return math.sqrt(
        max(
            0,
            (dl / sl) ** 2
            + (dc / sc) ** 2
            + (d_h / sh) ** 2
            + rt * (dc / sc) * (d_h / sh),
        )
    )


def rgba_distance(a, b):
    if a == b or a[3] == b[3] == 0:
        return 0.0
    if a[3] == b[3] == 255:
        return delta_e(lab(a), lab(b))

    def composite(c, bg):
        return [c[k] * c[3] / 255 + bg * (1 - c[3] / 255) for k in range(3)]

    return max(delta_e(lab(composite(a, bg)), lab(composite(b, bg))) for bg in (0, 255))
