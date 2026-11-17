# Source format

## Drawing

`tools/design.py` creates an empty 64 × 64 RGBA canvas. Minecraft UV charts
are defined in `RIG` and `faces()`. Hair, fabric, sleeves, hands, socks, and
footwear are computed directly by the drawing functions.

`features.json` contains compact facial and fabric feature tables. Colors
are hexadecimal RGBA values. Flower recipes list the upper, left, right,
lower, and center colors in that order. `hair_glazes` adds soft value strokes
only where hair is already painted; `curl_shades` groups selected existing
crest and valley pixels into six deliberate shades. Neither changes the curl
silhouettes or their transparent outer-layer gaps.

`details.json` is a list of `[x, y, RGBA]` entries applied once at the end of
the drawing stage. There are 25 entries.

## Export

`finish.json` contains:

- `source_palette`: the artwork's complete RGBA color domain, without a 256-color limit;
- `palette`: the ordered export RGBA palette;
- `map`: one export index for each source color;
- `filters`: one PNG filter number per row;
- `budget`: the maximum file size in bytes;
- `fixed_colors` and `weights`: color-refinement constraints.

Index zero is fully transparent. All other entries are opaque. The same
source color always maps to the same export color, preserving equal colors
at touching arm, torso, and cuff pixels.

## Compression

`deflate.json` describes the exact standard DEFLATE bit layout. Each block
has its final flag, block type, Huffman-tree description, and tokens.

An integer token is a run of literal bytes read from the generated pixel
stream. A three-item token is `[length, distance, length_symbol]`. Match
contents are checked against the generated stream during encoding.

Literal pixel values are supplied by the drawing pipeline. The plan stores
compression decisions. It supports stored, fixed-tree, and dynamic-tree
DEFLATE blocks, with canonical Huffman coding and explicit padding.

`manifest.json` locks the output dimensions, pixel hash, file hash, palette
size, and 999-byte file size. `verify` checks these properties independently
of the drawing stage.

The manifest also records the unrestricted artwork color count and opaque texel
count. Alpha masks stay identical through the export mapping. Flower colors and
the centered sleeve-fold highlight are protected during palette refinement.
