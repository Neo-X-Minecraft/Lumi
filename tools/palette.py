# SPDX-License-Identifier: 0BSD
"""Refine an export palette while keeping its pixel assignments and byte layout."""
import collections
import copy
from . import artwork
from .color import lab, delta_e


def refine(root, passes=6):
    art = artwork.load(root)
    finish = copy.deepcopy(art["finish"])
    palette = [tuple(bytes.fromhex(c.lstrip("#"))) for c in finish["palette"]]
    fixed = {bytes.fromhex(c) for c in finish["fixed_colors"]}
    weights = [1.0] * (art["width"] * art["height"])
    for entry in finish["weights"].values():
        if "rect" in entry:
            x, y, w, h = entry["rect"]
            points = ((xx, yy) for yy in range(y, y + h) for xx in range(x, x + w))
        else:
            points = entry["pixels"]
        for x, y in points:
            weights[y * art["width"] + x] = entry["weight"]
    groups = [collections.Counter() for _ in palette]
    for i, index in enumerate(art["indices"]):
        groups[index][art["design"][i * 4 : i * 4 + 3]] += weights[i]
    for index, color in enumerate(palette):
        if not color[3] or bytes(color[:3]) in fixed or not groups[index]:
            continue
        points = [(tuple(c), lab(c), w) for c, w in groups[index].items()]

        def cost(rgb):
            target = lab(rgb)
            return sum(w * delta_e(c, target) ** 2 for _, c, w in points)

        center, score = tuple(color[:3]), cost(color)
        for _ in range(passes):
            winner, value = center, score
            for dr in (-1, 0, 1):
                for dg in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        trial = tuple(
                            max(0, min(255, v + d))
                            for v, d in zip(center, (dr, dg, db))
                        )
                        if any(
                            max(abs(a - b) for a, b in zip(c, trial)) > 14
                            for c, _, _ in points
                        ):
                            continue
                        if any(
                            trial == p[:3] for j, p in enumerate(palette) if j != index
                        ):
                            continue
                        loss = cost(trial)
                        if loss < value - 1e-9:
                            winner, value = trial, loss
            if winner == center:
                break
            center, score = winner, value
        palette[index] = center + (color[3],)
    finish["palette"] = ["#" + bytes(c).hex() for c in palette]
    return finish
