# SPDX-License-Identifier: 0BSD
"""Procedural artwork generation and its deterministic export palette."""
import json
from pathlib import Path
from .design import generate


def load(root, finish_path=None):
    root = Path(root)
    finish = json.loads(Path(finish_path or root / "source/finish.json").read_text())
    width = height = 64
    design = generate(root)
    palette = [bytes.fromhex(c.lstrip("#")) for c in finish["source_palette"]]
    lookup = {color: i for i, color in enumerate(palette)}
    try:
        indices = [lookup[design[i : i + 4]] for i in range(0, len(design), 4)]
    except KeyError as error:
        raise ValueError("Artwork color is missing from the export lookup") from error
    export = [bytes.fromhex(c.lstrip("#")) for c in finish["palette"]]
    remap = finish["map"]
    if (
        len(remap) != len(palette)
        or any(not 0 <= i < len(export) for i in remap)
        or any(len(c) != 4 for c in export)
    ):
        raise ValueError("Invalid export palette mapping")
    final_indices = bytes(remap[i] for i in indices)
    return {
        "name": "Lumi",
        "model": "slim",
        "width": width,
        "height": height,
        "design": design,
        "rgba": b"".join(export[i] for i in final_indices),
        "indices": final_indices,
        "palette": export,
        "filters": finish["filters"],
        "finish": finish,
    }
