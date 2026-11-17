# SPDX-License-Identifier: 0BSD
"""Alpha-aware grayscale difference masks, normalized to visible color error."""
from .color import rgba_distance
from . import png


def compare(a, b, width, height):
    if len(a) != len(b) or len(a) != width * height * 4:
        raise ValueError("Images must have matching dimensions")
    cache, errors = {}, []
    changed = visible = alpha_changed = 0
    rgb_sum = rgb_max = 0
    for i in range(width * height):
        ca, cb = a[i * 4 : i * 4 + 4], b[i * 4 : i * 4 + 4]
        key = ca, cb
        if key not in cache:
            cache[key] = rgba_distance(ca, cb)
        errors.append(cache[key])
        alpha_changed += ca[3] != cb[3]
        if ca[3] or cb[3]:
            visible += 1
            changed += ca != cb
            steps = [abs(ca[k] - cb[k]) for k in range(3)]
            rgb_sum += sum(steps)
            rgb_max = max(rgb_max, max(steps))
    maximum = max(errors, default=0)
    mask = bytes(255 - round(255 * d / maximum) if maximum else 255 for d in errors)
    report = {
        "visible_pixels": visible,
        "changed_visible_pixels": changed,
        "alpha_changes": alpha_changed,
        "mean_rgb_step": rgb_sum / (visible * 3) if visible else 0,
        "max_rgb_step": rgb_max,
        "mean_delta_e": sum(errors) / visible if visible else 0,
        "max_delta_e": maximum,
    }
    return mask, report


def images(mask, width, height, scale=12):
    enlarged = bytearray()
    for y in range(height):
        row = b"".join(bytes([v]) * scale for v in mask[y * width : (y + 1) * width])
        for _ in range(scale):
            enlarged.extend(row)
    return png.gray(width, height, mask), png.gray(
        width * scale, height * scale, enlarged
    )
