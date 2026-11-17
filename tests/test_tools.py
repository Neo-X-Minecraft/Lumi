# SPDX-License-Identifier: 0BSD
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import artwork, deflate, design, diff, palette, pipeline, png
from tools.color import delta_e, lab


class ArtworkTests(unittest.TestCase):
    def test_artwork_and_export_hashes(self):
        spec = json.loads((ROOT / "source/manifest.json").read_text())
        art = artwork.load(ROOT)
        self.assertEqual(
            hashlib.sha256(art["design"]).hexdigest(), spec["artwork_sha256"]
        )
        self.assertEqual(hashlib.sha256(art["rgba"]).hexdigest(), spec["rgba_sha256"])
        self.assertEqual(
            sum(bool(art["rgba"][i + 3]) for i in range(0, 16384, 4)), spec["opaque_pixels"]
        )

    def test_procedural_hair_and_detail_finish(self):
        features = json.loads((ROOT / "source/features.json").read_text())
        canvas = design.Canvas()
        design.foundation(canvas, features)
        design.limbs(canvas)
        foundation = bytes(canvas.raw)
        design.hair(canvas, features.get('hair_glazes', ()), features.get('curl_shades', ()))
        self.assertGreater(
            sum(
                foundation[i : i + 4] != canvas.raw[i : i + 4]
                for i in range(0, 16384, 4)
            ),
            500,
        )
        design.footwear(canvas)
        design.flowers(canvas, features["flowers"])
        details = json.loads((ROOT / "source/details.json").read_text())
        self.assertEqual(len(details), 25)
        self.assertEqual(len({(x, y) for x, y, _ in details}), 25)
        for x, y, color in details:
            canvas.put(x, y, color)
        self.assertEqual(bytes(canvas.raw), design.generate(ROOT))

    def test_joined_cuffs_and_underarms(self):
        raw = artwork.load(ROOT)["rgba"]

        def at(x, y):
            return raw[(y * 64 + x) * 4 : (y * 64 + x) * 4 + 4]

        for bu, bv, ou, ov in [(40, 16, 40, 32), (32, 48, 48, 48)]:
            for x in range(14):
                self.assertEqual(at(bu + x, bv + 6), at(ou + x, ov + 6))
        for ax, ay, bx in [(48, 21, 18), (49, 21, 17), (33, 53, 30), (34, 53, 29)]:
            self.assertEqual(at(ax, ay), at(bx, 21))

    def test_sole_footprints_and_edges(self):
        raw = artwork.load(ROOT)["rgba"]

        def at(x, y):
            return raw[(y * 64 + x) * 4 : (y * 64 + x) * 4 + 4]

        for u, v in [(0, 32), (0, 48)]:
            for y, row in enumerate(("1111", "0000", "1111", "0110")):
                for x, value in enumerate(row):
                    self.assertEqual(bool(at(u + 8 + x, v + y)[3]), value == "1")
        for u, v in [(0, 16), (0, 32), (16, 48), (0, 48)]:
            band = [at(u + x, v + 15) for x in range(16)]
            self.assertEqual(band[:4], [at(u + 8, v + z) for z in range(4)])
            self.assertEqual(band[4:8], [at(u + 8 + x, v + 3) for x in range(4)])
            self.assertEqual(band[8:12], [at(u + 11, v + z) for z in range(3, -1, -1)])
            self.assertEqual(band[12:], [at(u + 8 + x, v) for x in range(3, -1, -1)])

    def test_complete_hidden_faces_and_fitted_stocking_edges(self):
        raw = design.generate(ROOT)

        def at(x, y):
            return raw[(y * 64 + x) * 4:(y * 64 + x + 1) * 4]

        for part in design.RIG:
            for _, u, v, w, h in design.faces(part):
                for y in range(v, v + h):
                    for x in range(u, u + w):
                        self.assertEqual(at(x, y)[3], 255, (part, x, y))
        for ou, ov in [(0, 32), (0, 48)]:
            self.assertTrue(all(at(ou + x, ov + 9)[3] == 0 for x in range(16)))
        for ax, ay, bx in [(8, 26, 7), (16, 58, 20)]:
            self.assertLessEqual(max(abs(a-b) for a, b in zip(at(ax, ay), at(bx, ay))), 2)

    def test_palette_constraints(self):
        art = artwork.load(ROOT)
        tuned = palette.refine(ROOT)
        fixed = set(art["finish"]["fixed_colors"])
        self.assertEqual(len(tuned["palette"]), len(art["palette"]))
        for a, b in zip(art["finish"]["palette"], tuned["palette"]):
            if a[1:7] in fixed:
                self.assertEqual(a, b)
            self.assertEqual(a[-2:], b[-2:])

    def test_export_preserves_flowers_alpha_and_cap_folds(self):
        art = artwork.load(ROOT)
        source, compact = art["design"], art["rgba"]
        self.assertEqual(source[3::4], compact[3::4])
        features = json.loads((ROOT / "source/features.json").read_text())
        for bloom in features["flowers"]:
            x, y = bloom["center"]
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1), (0, 0)):
                i = ((y + dy) * 64 + x + dx) * 4
                self.assertEqual(source[i:i + 4], compact[i:i + 4])
        for x, y in ((45, 16), (45, 17), (45, 18), (45, 19),
                     (45, 20), (45, 21), (52, 20), (52, 21),
                     (37, 48), (37, 49), (37, 50), (37, 51),
                     (37, 52), (37, 53), (44, 52), (44, 53)):
            i = (y * 64 + x) * 4
            center, edge = compact[i:i + 3], compact[i - 4:i - 1]
            self.assertGreater(lab(center)[0] - lab(edge)[0], 0.75)
            self.assertGreaterEqual(center[1] - edge[1], 3)

    def test_artwork_can_have_more_than_256_colors(self):
        colors = [bytes(4)] + [bytes((i % 256, i // 256, 0, 255)) for i in range(257)]
        raw = b''.join(colors[i % len(colors)] for i in range(4096))
        finish = {'source_palette': [c.hex() for c in colors],
                  'palette': ['00000000', 'f8e8deff'], 'map': [0] + [1] * 257,
                  'filters': [0] * 64}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'finish.json'
            path.write_text(json.dumps(finish))
            with patch.object(artwork, 'generate', return_value=raw):
                art = artwork.load(ROOT, path)
        self.assertEqual(len(set(raw[i:i+4] for i in range(0, len(raw), 4))), 258)
        self.assertEqual(art['design'], raw)
        self.assertEqual(len(art['palette']), 2)


class BuildTests(unittest.TestCase):
    def test_canonical_png(self):
        data = pipeline.build(ROOT)
        spec = json.loads((ROOT / 'source/manifest.json').read_text())
        self.assertEqual(len(data), spec['bytes'])
        self.assertLess(len(data), 1000)
        self.assertEqual(data, (ROOT / "Lumi.png").read_bytes())
        self.assertEqual(pipeline.verify(ROOT, data)["palette_entries"], spec['palette_entries'])

    def test_relocated_cli_without_a_png_input(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "lumi"
            target.mkdir()
            shutil.copytree(ROOT / "source", target / "source")
            shutil.copytree(
                ROOT / "tools",
                target / "tools",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            shutil.copy2(ROOT / "lumi.py", target / "lumi.py")
            self.assertFalse(list(target.rglob("*.png")))
            command = [sys.executable, str(target / "lumi.py")]
            subprocess.run(
                command + ["artwork"], cwd=folder, check=True, capture_output=True
            )
            subprocess.run(
                command + ["build"], cwd=folder, check=True, capture_output=True
            )
            result = target / "build/Lumi.png"
            self.assertEqual(result.read_bytes(), (ROOT / "Lumi.png").read_bytes())
            subprocess.run(
                command + ["verify", str(result)],
                cwd=folder,
                check=True,
                capture_output=True,
            )

    def test_corrupted_export_rejected(self):
        blob = bytearray(pipeline.build(ROOT))
        blob[50] ^= 1
        with self.assertRaises(ValueError):
            pipeline.verify(ROOT, bytes(blob))


class DeflateTests(unittest.TestCase):
    def test_stored_fixed_dynamic_roundtrips(self):
        samples = (b"", b"lumi " * 900, bytes(range(256)) * 18)
        for data in samples:
            for level, strategy in [
                (0, zlib.Z_DEFAULT_STRATEGY),
                (9, zlib.Z_FIXED),
                (9, zlib.Z_DEFAULT_STRATEGY),
            ]:
                encoder = zlib.compressobj(level, zlib.DEFLATED, 15, 9, strategy)
                stream = encoder.compress(data) + encoder.flush()
                with self.subTest(length=len(data), level=level, strategy=strategy):
                    plan, decoded = deflate.extract(stream)
                    self.assertEqual(decoded, data)
                    self.assertEqual(deflate.encode(data, plan), stream)

    def test_packing_plan_roundtrip(self):
        art = artwork.load(ROOT)
        rows = png.filter_rows(art["indices"], 64, 64, 1, art["filters"])
        plan = json.loads((ROOT / "source/deflate.json").read_text())
        stream = deflate.encode(rows, plan)
        extracted, data = deflate.extract(stream)
        self.assertEqual(extracted, plan)
        self.assertEqual(data, rows)

    def test_invalid_match_rejected(self):
        art = artwork.load(ROOT)
        data = bytearray(png.filter_rows(art["indices"], 64, 64, 1, art["filters"]))
        plan = json.loads((ROOT / "source/deflate.json").read_text())
        pos = 0
        for block in plan["blocks"]:
            for token in block.get("tokens", []):
                if isinstance(token, int):
                    pos += token
                else:
                    data[pos] ^= 1
                    with self.assertRaises(ValueError):
                        deflate.encode(bytes(data), plan)
                    return
        self.fail("Expected at least one LZ77 match")


class ImageTests(unittest.TestCase):
    def test_indexed_png_filters(self):
        colors = [bytes(4), bytes.fromhex("e1b4c6ff"), bytes.fromhex("fff0ecff")]
        pixels = bytes((x + y) % 3 for y in range(5) for x in range(8))
        rows = png.filter_rows(pixels, 8, 5, 1, [0, 1, 2, 3, 4])
        blob = png.indexed(8, 5, colors, zlib.compress(rows, 9))
        self.assertEqual(png.decode(blob), (8, 5, b"".join(colors[i] for i in pixels)))

    def test_png_checksums(self):
        blob = bytearray(png.gray(2, 1, bytes([0, 255])))
        blob[-6] ^= 1
        with self.assertRaises(ValueError):
            png.decode(bytes(blob))

    def test_perceptual_color_reference(self):
        self.assertAlmostEqual(
            delta_e((50, 2.6772, -79.7751), (50, 0, -82.7485)), 2.0425, places=4
        )
        self.assertAlmostEqual(delta_e(lab((220, 180, 200)), lab((220, 180, 200))), 0)

    def test_diff_ignores_hidden_rgb(self):
        a = bytes.fromhex("00000000ffffffff")
        b = bytes.fromhex("ff008000ffffffff")
        mask, report = diff.compare(a, b, 2, 1)
        self.assertEqual(mask, b"\xff\xff")
        self.assertEqual(report["alpha_changes"], 0)

    def test_diff_mask_normalization(self):
        a = bytes.fromhex("ffffffff000000ff")
        b = bytes.fromhex("ffffffff101010ff")
        mask, _ = diff.compare(a, b, 2, 1)
        self.assertEqual(mask, b"\xff\x00")
        small, large = diff.images(mask, 2, 1)
        self.assertEqual(png.decode(small)[:2], (2, 1))
        self.assertEqual(png.decode(large)[:2], (24, 12))


if __name__ == "__main__":
    unittest.main()
