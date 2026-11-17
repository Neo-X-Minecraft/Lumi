# ✿ Lumi

A small, offline workbench for creating **Lumi**, a soft pink Minecraft skin.

<img src="docs/preview.png" width="320" alt="Lumi, with fluffy pink hair and three pastel flowers">

| Texture | Model | Export palette | PNG size | License |
| --- | --- | --- | --- | --- |
| 64 × 64 | Slim, 3-pixel arms | 50 entries, including transparency | **999 bytes** | [0BSD](LICENSE) |

## Make Lumi

Use Python 3.9 or newer. The build uses only its standard library.

```sh
python3 lumi.py build
python3 lumi.py verify build/Lumi.png
```

This generates `build/Lumi.png`. The checked-in [Lumi.png](Lumi.png) is the
canonical export. Both have this SHA-256:

```text
abea3475884e40ab9f72a50f3bc80be0018b53086c4c304499625a576463cd32
```

To generate the full-color artwork itself:

```sh
python3 lumi.py artwork
```

The result is `build/Lumi-artwork.png`, drawn from an empty texture by the
same pipeline used for the compact export.

## The drawing pipeline

The production build has six fixed drawing stages:

1. **Foundation:** face features, chin, neckline, plain fabric, and quiet folds.
2. **Limbs:** short cap sleeves, continuous cuffs, hand shading, shorts, and
   smooth skin-to-sock gradients.
3. **Hair:** analytic S-curves and Gaussian lobes create the soft waves,
   reflections, recessed bends, rounded ends, and selective outer-layer locks.
   Hair edges wrap around adjoining UV faces.
4. **Footwear:** matching base and outer sole boundaries create raised heels,
   rounded forefeet, and recessed arches.
5. **Flowers:** three final pastel flower recipes and their small leaf details.
6. **Detail finish:** 20 explicit pixel corrections refine silhouettes and lights.

The completed artwork then passes through the export palette and PNG encoder.
The drawing code, feature tables, and detail pass are all editable source.

## Exact, offline packing

The export uses 8-bit indexed PNG. `source/finish.json` defines its palette,
color mapping, and row filters. `source/deflate.json` defines the final LZ77
match layout and Huffman trees.

The encoder reads literal pixel values from the freshly generated artwork,
validates every match, and writes a standard zlib-wrapped DEFLATE stream.
It calculates the PNG checksums and Adler-32 during each build. This makes
the complete 999-byte output deterministic with Python alone.

See [the source format](docs/FORMAT.md) for the drawing and packing data.

## Toolbench

```sh
# Render the finished skin.
python3 lumi.py preview

# Compare any two 8-bit PNGs.
python3 lumi.py diff image-a.png image-b.png

# Refine export RGB values while keeping the pixel layout fixed.
python3 lumi.py palette

# Run the full test suite.
python3 -m unittest discover -s tests -v
```

Diff masks use white for unchanged pixels and black for the largest visible
perceptual difference. Hidden RGB values in fully transparent pixels are ignored.

Packing-plan regeneration is optional. With a local `zopfli` executable:

```sh
python3 lumi.py plan --output build/deflate.json
python3 lumi.py build --plan build/deflate.json
```

The plan command can also import a zlib stream with `--stream FILE`.
Normal artwork generation, builds, previews, diffs, and verification need no
external programs or Python packages.

## Inside

```text
lumi.py                 command line
Lumi.png                canonical 999-byte skin
source/features.json    hand-drawn facial and fabric details
source/details.json     final pixel corrections
source/finish.json      export palette and lookup
source/deflate.json     deterministic packing plan
source/manifest.json    expected hashes and dimensions
tools/design.py         procedural artwork generator
tools/                  PNG, DEFLATE, palette, diff, and rendering tools
tests/                  isolated rebuild and format tests
```

## License

All code, artwork, and source data in this repository are released under
the [0BSD license](LICENSE).
