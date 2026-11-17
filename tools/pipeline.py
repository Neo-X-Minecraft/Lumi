# SPDX-License-Identifier: 0BSD
"""Reproducible asset building and canonical output verification."""
import hashlib
import json
from pathlib import Path
from . import artwork, deflate, png


def build(root, finish_path=None, plan_path=None):
    root = Path(root)
    art = artwork.load(root, finish_path)
    plan = json.loads(Path(plan_path or root / "source/deflate.json").read_text())
    rows = png.filter_rows(
        art["indices"], art["width"], art["height"], 1, art["filters"]
    )
    stream = deflate.encode(rows, plan)
    blob = png.indexed(art["width"], art["height"], art["palette"], stream)
    if png.decode(blob) != (art["width"], art["height"], art["rgba"]):
        raise ValueError("PNG pixels do not match the artwork")
    return blob


def verify(root, blob):
    root = Path(root)
    spec = json.loads((root / "source/manifest.json").read_text())
    art = artwork.load(root)
    digest = hashlib.sha256(blob).hexdigest()
    if len(blob) != spec["bytes"] or digest != spec["sha256"]:
        raise ValueError("PNG does not match the canonical Lumi build")
    width, height, pixels = png.decode(blob)
    if (width, height) != (64, 64) or pixels != art["rgba"]:
        raise ValueError("Unexpected skin pixels")
    if hashlib.sha256(art["design"]).hexdigest() != spec["artwork_sha256"]:
        raise ValueError("Generated artwork does not match its manifest")
    if (
        len(set(pixels[i : i + 4] for i in range(0, len(pixels), 4)))
        != spec["palette_entries"]
    ):
        raise ValueError("Unexpected color count")
    if hashlib.sha256(pixels).hexdigest() != spec["rgba_sha256"]:
        raise ValueError("Unexpected pixel checksum")
    return {
        "name": "Lumi",
        "bytes": len(blob),
        "width": width,
        "height": height,
        "palette_entries": spec["palette_entries"],
        "model": art["model"],
        "sha256": digest,
    }
