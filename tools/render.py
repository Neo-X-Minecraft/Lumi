# SPDX-License-Identifier: 0BSD
"""Minecraft UV previews with slim-arm geometry and both texture layers."""
import math
from .png import rgba as png


def front(raw, scale=10, back=False, arm_width=3):
    out = bytearray(18 * 32 * 4)
    segs = [
        (8, 8, 8, 8, 5, 0),
        (20, 20, 8, 12, 5, 8),
        (44, 20, arm_width, 12, 5 - arm_width, 8),
        (36, 52, arm_width, 12, 13, 8),
        (4, 20, 4, 12, 5, 20),
        (20, 52, 4, 12, 9, 20),
        (40, 8, 8, 8, 5, 0),
        (20, 36, 8, 12, 5, 8),
        (44, 36, arm_width, 12, 5 - arm_width, 8),
        (52, 52, arm_width, 12, 13, 8),
        (4, 36, 4, 12, 5, 20),
        (4, 52, 4, 12, 9, 20),
    ]
    if back:
        segs = [
            (
                (
                    sx + 12
                    if w == 8 and h == 12
                    else sx + 16 if h == 8 else sx + 7 if w == 3 else sx + 8
                ),
                sy,
                w,
                h,
                dx,
                dy,
            )
            for sx, sy, w, h, dx, dy in segs
        ]
    for sx, sy, w, h, dx, dy in segs:
        for y in range(h):
            for x in range(w):
                i = ((sy + y) * 64 + sx + x) * 4
                j = ((dy + y) * 18 + dx + x) * 4
                if raw[i + 3]:
                    out[j : j + 4] = raw[i : i + 4]
    result = bytearray()
    for y in range(32):
        row = b"".join(
            (out[(y * 18 + x) * 4 : (y * 18 + x) * 4 + 4] * scale for x in range(18))
        )
        for _ in range(scale):
            result.extend(row)
    return png(18 * scale, 32 * scale, result)


def preview(raw, yaw=-0.38, pitch=-0.13, arm_width=3):
    W, H, S = (320, 500, 11.5)
    out = bytearray([27, 33, 29, 255] * (W * H))
    depth = [-float('inf')] * (W * H)
    translucent = []
    cy, sy, cp, sp = (math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch))

    def rotate(p):
        x, y, z = p
        X = x * cy + z * sy
        Z = -x * sy + z * cy
        return (X, y * cp - Z * sp, y * sp + Z * cp)

    def project(p):
        X, Y, Z = rotate([p[0], p[1] - 16, p[2]])
        return (W / 2 + X * S, H * 0.48 + Y * S, Z)

    parts = [
        (-4, 0, -4, 8, 8, 8, (0, 0), (32, 0), 0.5),
        (-4, 8, -2, 8, 12, 4, (16, 16), (16, 32), 0.25),
        (-4 - arm_width, 8, -2, arm_width, 12, 4, (40, 16), (40, 32), 0.25),
        (4, 8, -2, arm_width, 12, 4, (32, 48), (48, 48), 0.25),
        (-4, 20, -2, 4, 12, 4, (0, 16), (0, 32), 0.25),
        (0, 20, -2, 4, 12, 4, (16, 48), (0, 48), 0.25),
    ]
    faces = []
    for x, y, z, w, h, d, base, over, exp in parts:
        for outer in [False, True]:
            e = exp if outer else 0
            X, Y, Z = (x - e, y - e, z - e)
            ww, hh, dd = (w + e * 2, h + e * 2, d + e * 2)
            u, v = over if outer else base
            fs = [
                (
                    [X, Y, Z + dd],
                    [X + ww, Y, Z + dd],
                    [X, Y + hh, Z + dd],
                    (u + d, v + d, w, h),
                    (0, 0, 1),
                    1,
                ),
                (
                    [X + ww, Y, Z],
                    [X, Y, Z],
                    [X + ww, Y + hh, Z],
                    (u + 2 * d + w, v + d, w, h),
                    (0, 0, -1),
                    0.88,
                ),
                (
                    [X, Y, Z],
                    [X, Y, Z + dd],
                    [X, Y + hh, Z],
                    (u, v + d, d, h),
                    (-1, 0, 0),
                    0.84,
                ),
                (
                    [X + ww, Y, Z + dd],
                    [X + ww, Y, Z],
                    [X + ww, Y + hh, Z + dd],
                    (u + d + w, v + d, d, h),
                    (1, 0, 0),
                    0.88,
                ),
                (
                    [X, Y, Z],
                    [X + ww, Y, Z],
                    [X, Y, Z + dd],
                    (u + d, v, w, d),
                    (0, -1, 0),
                    1.03,
                ),
                (
                    [X, Y + hh, Z],
                    [X + ww, Y + hh, Z],
                    [X, Y + hh, Z + dd],
                    (u + d + w, v, w, d),
                    (0, 1, 0),
                    0.8,
                ),
            ]
            for a, b, c, uv, n, light in fs:
                if rotate(n)[2] <= 0:
                    continue
                A, B, C = (project(a), project(b), project(c))
                faces.append(((B[2] + C[2]) / 2, A, B, C, uv, light, outer))
    for _, A, B, C, uv, light, outer in sorted(faces, key=lambda f: f[0]):
        u, v, fw, fh = uv
        ax, ay = (B[0] - A[0], B[1] - A[1])
        bx, by = (C[0] - A[0], C[1] - A[1])
        det = ax * by - ay * bx
        if abs(det) < 1e-06:
            continue
        D = [B[0] + C[0] - A[0], B[1] + C[1] - A[1]]
        for yy in range(
            max(0, int(min(A[1], B[1], C[1], D[1]))),
            min(H, math.ceil(max(A[1], B[1], C[1], D[1]))),
        ):
            for xx in range(
                max(0, int(min(A[0], B[0], C[0], D[0]))),
                min(W, math.ceil(max(A[0], B[0], C[0], D[0]))),
            ):
                dx, dy = (xx + 0.5 - A[0], yy + 0.5 - A[1])
                a, b = ((dx * by - dy * bx) / det, (ax * dy - ay * dx) / det)
                if not (0 <= a < 1 and 0 <= b < 1):
                    continue
                i = (
                    (v + min(fh - 1, int(b * fh))) * 64 + u + min(fw - 1, int(a * fw))
                ) * 4
                j = (yy * W + xx) * 4
                alpha = raw[i + 3] / 255
                if not alpha:
                    continue
                z = A[2] + a * (B[2] - A[2]) + b * (C[2] - A[2])
                rgb = [min(255, raw[i + k] * light) for k in range(3)]
                if alpha < 1:
                    translucent.append((z, j, rgb, alpha))
                    continue
                if z <= depth[j // 4]:
                    continue
                depth[j // 4] = z
                for k in range(3):
                    out[j + k] = round(rgb[k])
    for z, j, rgb, alpha in sorted(translucent, key=lambda item: item[0]):
        if z < depth[j // 4]:
            continue
        for k in range(3):
            out[j + k] = round(rgb[k] * alpha + out[j + k] * (1 - alpha))
    return png(W, H, out)
