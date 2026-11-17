# Working on Lumi

Keep the production drawing pipeline direct and deterministic. Put shape
and shading logic in `tools/design.py`, hand-drawn features in
`source/features.json`, and deliberate pixel-level finishing in
`source/details.json`.

Run the checks from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 lumi.py artwork
python3 lumi.py build
python3 lumi.py verify build/Lumi.png
```

An intentional change to the canonical skin needs a matching export
palette, compression plan, manifest, and checked-in PNG. Preserve the
sub-1000-byte budget and ensure the complete build works in isolation.

All contributions are made under the repository's 0BSD license.
