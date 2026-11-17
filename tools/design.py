# SPDX-License-Identifier: 0BSD
"""Lumi's procedural drawing stages and one deliberate pixel-detail pass."""
import json
import math
from pathlib import Path

RIG = {
    "head": (8, 8, 8, (0, 0), (32, 0)),
    "body": (8, 12, 4, (16, 16), (16, 32)),
    "rarm": (3, 12, 4, (40, 16), (40, 32)),
    "larm": (3, 12, 4, (32, 48), (48, 48)),
    "rleg": (4, 12, 4, (0, 16), (0, 32)),
    "lleg": (4, 12, 4, (16, 48), (0, 48)),
}


class Canvas:
    def __init__(self):
        self.raw = bytearray(64 * 64 * 4)

    def get(self, x, y):
        i = (y * 64 + x) * 4
        return self.raw[i : i + 4]

    def put(self, x, y, color):
        if color is None:
            color = bytes(4)
        elif isinstance(color, str):
            color = bytes.fromhex(color.lstrip("#"))
        else:
            color = bytes(color)
        if len(color) == 3:
            color += b"\xff"
        if len(color) != 4 or not (0 <= x < 64 and 0 <= y < 64):
            raise ValueError("Invalid drawing pixel")
        i = (y * 64 + x) * 4
        self.raw[i : i + 4] = color


def faces(part, outer=False):
    w, h, d, base, over = RIG[part]
    u, v = over if outer else base
    return [
        ("front", u + d, v + d, w, h),
        ("back", u + 2 * d + w, v + d, w, h),
        ("right", u, v + d, d, h),
        ("left", u + d + w, v + d, d, h),
        ("top", u + d, v, w, d),
        ("bottom", u + d + w, v, w, d),
    ]


def shift(color, amount):
    return tuple(max(0, min(255, round(v + amount))) for v in color[:3])


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gaussian(x, sigma):
    return math.exp(-0.5 * (x / sigma) ** 2)


def foundation(c, features):
    for x, y, color in features["face"]:
        c.put(x, y, color)
    for y, row in enumerate(features["head_underside"]):
        for x, color in enumerate(row):
            c.put(16 + x, y, color)
    for face, u, v, w, h in faces("body"):
        for y in range(h):
            for x in range(w):
                if face == "top":
                    color = "d493ae"
                elif face == "bottom":
                    color = "d08ea0"
                else:
                    delta = {"front": 0, "back": -1, "right": -2, "left": -1}[face]
                    base = (210, 143, 161) if y < 11 else (216, 154, 172)
                    color = shift(base, delta + round(math.sin((x + 0.25) * 1.3) * 2.5))
                c.put(u + x, v + y, color)
    c.put(20, 16, "d696b0")
    for x in (23, 24):
        c.put(x, 18, "ffede9")
        c.put(x, 19, "fffef2")
    for y, row in enumerate(features["bodice"]):
        for x, color in enumerate(row):
            c.put(22 + x, 20 + y, color)
    for face, u, v, w, h in faces("body"):
        if face in features["hems"]:
            for x, color in enumerate(features["hems"][face]):
                c.put(u + x, v + 11, color)
    for side, x in [("right", 17), ("left", 29)]:
        for y, row in enumerate(features["side_fabric"][side]):
            for xx, color in enumerate(row):
                c.put(x + xx, 20 + y, color)


def limbs(c):
    front = ((252, 230, 227), (255, 235, 231), (252, 230, 227))
    back = ((249, 226, 222), (252, 231, 227), (249, 226, 222))
    depth = [mix(back[0], front[0], z / 3) for z in range(4)]
    for part in ("rarm", "larm"):
        _, _, _, (u, v), (ou, ov) = RIG[part]
        for y in range(4):
            for x in range(3):
                c.put(
                    u + 4 + x,
                    v + y,
                    shift(
                        (208, 151, 173), round(4 - 4 * abs(x - 1) - 1.5 * abs(y - 1.5))
                    ),
                )
                c.put(u + 7 + x, v + y, mix(back[x], front[x], y / 3))
        for face, du, w, colors in [
            ("right", 0, 4, depth),
            ("front", 4, 3, front),
            ("left", 7, 4, depth[::-1]),
            ("back", 11, 3, back),
        ]:
            delta = {"front": 0, "back": -2, "right": -3, "left": -1}[face]
            for y in range(12):
                for x in range(w):
                    fold = round(5 * (1 - abs(x - (w - 1) / 2) / max(1, (w - 1) / 2)))
                    if y < 2:
                        color = shift(
                            (201, 139, 162), fold + delta - (2 if y == 1 else 0)
                        )
                    elif y == 2:
                        color = shift((217, 167, 185), fold + delta + 3)
                    else:
                        color = colors[x]
                    if (
                        y == 1
                        and x in (1, 2)
                        and face == ("left" if part == "rarm" else "right")
                    ):
                        color = colors[x]
                    c.put(u + du + x, v + 4 + y, color)
                    if y == 2:
                        c.put(ou + du + x, ov + 4 + y, color)
    skin, sock, shorts, shoe, sole = (
        (255, 235, 231),
        (255, 245, 239),
        (229, 181, 196),
        (224, 180, 193),
        (209, 164, 179),
    )
    for part in ("rleg", "lleg"):
        for face, u, v, w, h in faces(part):
            delta = {
                "front": 0,
                "back": -1,
                "right": -2,
                "left": -1,
                "top": 1,
                "bottom": -4,
            }[face]
            for y in range(h):
                for x in range(w):
                    edge = -2 if x not in (1, 2) else 0
                    if face == "top":
                        color = shift(shorts, delta - 2)
                    elif face == "bottom":
                        color = shift(sole, delta - 1)
                    elif y == 0:
                        color = shift(
                            shorts, delta + (2 if x == 1 else -2 if x == w - 1 else 0)
                        )
                    elif y <= 4:
                        color = shift(skin, delta + edge)
                    elif y == 5:
                        color = shift(mix(skin, sock, 0.28), delta + edge)
                    elif y == 6:
                        color = shift(mix(skin, sock, 0.62), delta + edge)
                    elif y in (7, 8):
                        color = shift(sock, delta + (1 if x == 1 else edge))
                    elif y == 9:
                        color = shift(sock if x in (1, 2) else shoe, delta + edge)
                    elif y == 10:
                        color = shift(
                            shoe, delta + (4 if x == 1 else -2 if x == w - 1 else 1)
                        )
                    else:
                        color = shift(sole, delta + (1 if x == 1 else 0))
                    c.put(u + x, v + y, color)


def hair(c):
    garment = bytes(c.raw)
    hair_pixels = set()

    def sample(x, y):
        i = (y * 64 + x) * 4
        return garment[i : i + 4]

    def base(x, y, color):
        c.put(x, y, color)
        hair_pixels.add((x, y))

    def shade(t):
        return mix((208, 146, 173), (246, 210, 224), max(0.18, min(0.95, t)))

    def wave(x, y, side=False):
        left = 1.65 + 0.9 * math.sin((y - 1) * 0.72)
        right = 5.5 + 0.8 * math.sin((y + 2) * 0.66)
        curl = max(gaussian(x - left, 0.90), gaussian(x - right, 0.95))
        light = 0.76 + 0.24 * math.sin(y * 0.56 + x * 0.37)
        crease = min(gaussian(x - left - 1.25, 0.55), gaussian(x - right + 1.2, 0.55))
        edge = math.exp(-min(x, 7 - x) / 0.7)
        return shade(
            0.49
            + 0.31 * curl * light
            - 0.13 * crease
            - 0.055 * edge
            - (0.025 if side else 0)
        )

    protected = {
        (50, 9),
        (49, 10),
        (50, 10),
        (51, 10),
        (50, 11),
        (53, 11),
        (52, 12),
        (53, 12),
        (54, 12),
        (53, 13),
        (52, 11),
    }

    def layer(bu, bv, ou, ov, mask, colors=None, protect=()):
        for y, row in enumerate(mask):
            for x, symbol in enumerate(row):
                if (ou + x, ov + y) in protect:
                    continue
                if symbol == "#":
                    color = colors(x, y) if colors else c.get(bu + x, bv + y)
                    if (bu + x, bv + y) in hair_pixels:
                        c.put(bu + x, bv + y, shift(color, -4))
                    c.put(ou + x, ov + y, shift(color, 2))
                else:
                    c.put(ou + x, ov + y, None)

    for y in range(8):
        for x in range(8):
            base(24 + x, 8 + y, wave(x, y))
    for y in range(9):
        for x in range(8):
            base(32 + x, 20 + y, wave(x, 8 + y))
    for y, mask in [(9, ".###.##."), (10, "..#..#..")]:
        for x, symbol in enumerate(mask):
            if symbol == "#":
                base(32 + x, 20 + y, wave(x, 8 + y))
            else:
                c.put(32 + x, 20 + y, shift(sample(32 + x, 31), 2))
    colors = {"s": "dba4be", "m": "e5b3c8", "a": "eabdd0", "h": "f0c8d8", "l": "f5d1df"}
    for y, row in enumerate(("smhhmams", "mhlmhamm", "hlhmahhm")):
        for x, symbol in enumerate(row):
            base(8 + x, 8 + y, colors[symbol])
    for x, symbol in [(0, "s"), (1, "h"), (2, "m"), (5, "m"), (6, "h"), (7, "s")]:
        base(8 + x, 11, colors[symbol])
    for y in range(4, 8):
        for x in (0, 7):
            base(8 + x, 8 + y, wave(x, y))
    for x in (1, 6):
        base(8 + x, 12, colors["a"])
        base(8 + x, 15, colors["s"])
    for u, mirrored in [(0, False), (16, True)]:
        for y in range(8):
            for x in range(8):
                base(u + x, 8 + y, wave(7 - x if mirrored else x, y, True))
        for y in range(8):
            if mirrored:
                base(16, 8 + y, c.get(15, 8 + y))
                base(23, 8 + y, c.get(24, 8 + y))
            else:
                base(7, 8 + y, c.get(8, 8 + y))
                base(0, 8 + y, c.get(31, 8 + y))
    for y in range(8):
        for x in range(8):
            curl = gaussian(
                x - (2.2 + 0.85 * math.sin(y * 0.7)), 1.05
            ) + 0.65 * gaussian(x - (5.6 + 0.5 * math.sin(y * 0.8 + 1)), 1)
            base(
                8 + x,
                y,
                shade(0.5 + 0.24 * min(1.3, curl) + 0.025 * math.sin(x + y * 0.6)),
            )
    for x in range(8):
        base(8 + x, 0, c.get(31 - x, 8))
        base(8 + x, 7, c.get(8 + x, 8))
    front = [
        "........",
        ".##.##..",
        ".##..##.",
        "##....##",
        "##....##",
        "#......#",
        "#......#",
        ".#....#.",
    ]
    back = [
        "........",
        "..##.##.",
        ".###..#.",
        ".##..##.",
        "##..###.",
        "##...##.",
        ".##.##..",
        "..##..#.",
    ]
    side = [
        "........",
        "..##.##.",
        ".##...##",
        ".##...##",
        "##....##",
        "##...##.",
        ".##..##.",
        "..##..#.",
    ]
    crown = [
        "........",
        "..##....",
        ".###.##.",
        "..##.##.",
        "...##...",
        "...###..",
        "..##....",
        "........",
    ]
    layer(8, 8, 40, 8, front)
    layer(24, 8, 56, 8, back, lambda x, y: wave(x, y))
    layer(0, 8, 32, 8, side, lambda x, y: wave(x, y, True))
    layer(
        16,
        8,
        48,
        8,
        [row[::-1] for row in side],
        lambda x, y: wave(7 - x, y, True),
        protected,
    )
    layer(8, 0, 40, 0, crown)
    back_locks = [
        ".##..##.",
        ".##...##",
        ".##...##",
        "..##..##",
        "..##.##.",
        "..##.##.",
        ".##.##..",
        "##..##..",
        "##..##..",
        ".##..##.",
        "..#..#..",
    ]
    layer(32, 20, 32, 36, back_locks, lambda x, y: wave(x, 8 + y))
    for y in range(9):
        for x in (0, 1, 6, 7):
            base(20 + x, 20 + y, wave(x, 8 + y))
    for y, mask in [(9, ".#....#."), (10, "..#..#..")]:
        for x in (0, 1, 2, 5, 6, 7):
            if mask[x] == "#":
                base(20 + x, 20 + y, wave(x, 8 + y))
            else:
                c.put(20 + x, 20 + y, sample(22 if x < 3 else 25, 20 + y))
    front_locks = [
        "##....##",
        ".##..##.",
        ".##..##.",
        "##....##",
        "##....##",
        ".##..##.",
        "..#..#..",
        ".##..##.",
        "##....##",
        ".#....#.",
        "..#..#..",
    ]
    layer(20, 20, 20, 36, front_locks, lambda x, y: wave(x, 8 + y))
    for y in range(11):
        for x, bx, mask, mx in [
            (31, 32, back_locks, 0),
            (16, 39, back_locks, 7),
            (19, 20, front_locks, 0),
            (28, 27, front_locks, 7),
        ]:
            c.put(x, 20 + y, c.get(bx, 20 + y))
            c.put(x, 36 + y, c.get(bx, 20 + y) if mask[y][mx] == "#" else None)
    for face, u, v, w, h in faces("body", True):
        if face not in ("top", "bottom"):
            base_chart = next(chart for chart in faces("body") if chart[0] == face)
            for x in range(w):
                c.put(u + x, v + 11, c.get(base_chart[1] + x, base_chart[2] + 11))
    for x, y in [(49, 0), (54, 0), (49, 7), (54, 7)]:
        c.put(x, y, shift(c.get(x - 32, y), 2))


def footwear(c):
    base = [
        ["cfa3b2", "d4a9b7", "d4a9b7", "cfa3b2"],
        ["c79bab", "c198a7", "c198a7", "c79bab"],
        ["cfa5b4", "d5abba", "d5abba", "cfa5b4"],
        ["d0a7b5", "d7adbb", "d7adbb", "d0a7b5"],
    ]
    raised = [
        ["d2a6b4", "d8aebc", "d8aebc", "d2a6b4"],
        [None] * 4,
        ["d5aab8", "dfb9c5", "dfb9c5", "d5aab8"],
        [None, "d9afbd", "d9afbd", None],
    ]

    def boundary(cap):
        return (
            [cap[z][0] for z in range(4)]
            + cap[3]
            + [cap[z][3] for z in range(3, -1, -1)]
            + cap[0][::-1]
        )

    for bu, bv, ou, ov in [(0, 16, 0, 32), (16, 48, 0, 48)]:
        for z in range(4):
            for x in range(4):
                c.put(bu + 8 + x, bv + z, base[z][x])
                c.put(ou + 8 + x, ov + z, raised[z][x])
        for x, color in enumerate(boundary(base)):
            c.put(bu + x, bv + 15, color)
        for x, color in enumerate(boundary(raised)):
            c.put(ou + x, ov + 15, color)
        for x in (5, 6):
            c.put(ou + x, ov + 14, "e9c1cd")


def flowers(c, spec):
    for bloom in spec:
        x, y = bloom["center"]
        for (dx, dy), color in zip(
            ((0, -1), (-1, 0), (1, 0), (0, 1), (0, 0)), bloom["colors"]
        ):
            c.put(x + dx, y + dy, color)
    c.put(20, 11, "bcc5b5")
    c.put(21, 12, "bcc5b5")
    c.put(52, 11, None)


def generate(root):
    root = Path(root)
    features = json.loads((root / "source/features.json").read_text())
    canvas = Canvas()
    foundation(canvas, features)
    limbs(canvas)
    hair(canvas)
    footwear(canvas)
    flowers(canvas, features["flowers"])
    for x, y, color in json.loads((root / "source/details.json").read_text()):
        canvas.put(x, y, color)
    return bytes(canvas.raw)
