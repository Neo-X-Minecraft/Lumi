# SPDX-License-Identifier: 0BSD
"""Lumi's offline skin-building command line."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from . import artwork, deflate, design, diff, palette, pipeline, png, render


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def main(root):
    parser = argparse.ArgumentParser(description="Lumi: a small toolbench for Lumi.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build the indexed skin PNG")
    build.add_argument("--output", type=Path, default=root / "build/Lumi.png")
    build.add_argument("--finish", type=Path)
    build.add_argument("--plan", type=Path)
    check = commands.add_parser(
        "verify", help="Verify the canonical PNG and its exact pixels"
    )
    check.add_argument("file", type=Path, nargs="?", default=root / "Lumi.png")
    draw = commands.add_parser(
        "artwork", help="Generate the full-color artwork from a blank canvas"
    )
    draw.add_argument("--output", type=Path, default=root / "build/Lumi-artwork.png")
    preview = commands.add_parser("preview", help="Render the finished skin")
    preview.add_argument("--output", type=Path, default=root / "build/Lumi-preview.png")
    preview.add_argument("--yaw", type=float, default=-0.65)
    preview.add_argument("--pitch", type=float, default=-0.1)
    mask = commands.add_parser(
        "diff", help="Measure color error and create grayscale masks"
    )
    mask.add_argument("images", type=Path, nargs="*")
    mask.add_argument("--output", type=Path, default=root / "build/Lumi-diff-mask.png")
    tune = commands.add_parser(
        "palette", help="Refine palette RGB values without moving pixels"
    )
    tune.add_argument("--output", type=Path, default=root / "build/finish.json")
    plan = commands.add_parser("plan", help="Generate a checked packing plan")
    plan.add_argument("--output", type=Path, default=root / "build/deflate.json")
    plan.add_argument(
        "--stream",
        type=Path,
        help="Import a zlib stream containing the filtered pixels",
    )
    plan.add_argument(
        "--compressor", default="zopfli", help="Optional local compressor executable"
    )
    plan.add_argument("--iterations", type=int, default=160)
    args = parser.parse_args()
    try:
        if args.command == "build":
            blob = pipeline.build(root, args.finish, args.plan)
            art = artwork.load(root, args.finish)
            if len(blob) > art["finish"]["budget"]:
                raise ValueError("PNG exceeds the export byte budget")
            if not args.finish and not args.plan:
                pipeline.verify(root, blob)
            print(f"{write(args.output,blob)} ({len(blob)} bytes)")
        elif args.command == "verify":
            print(json.dumps(pipeline.verify(root, args.file.read_bytes()), indent=2))
        elif args.command == "artwork":
            raw = design.generate(root)
            print(write(args.output, png.rgba(64, 64, raw)))
        elif args.command == "preview":
            art = artwork.load(root)
            print(write(args.output, render.preview(art["rgba"], args.yaw, args.pitch)))
        elif args.command == "diff":
            if args.images:
                if len(args.images) != 2:
                    raise ValueError(
                        "Supply two PNGs, or no PNGs for the design/export comparison"
                    )
                wa, ha, a = png.decode(args.images[0].read_bytes())
                wb, hb, b = png.decode(args.images[1].read_bytes())
                if (wa, ha) != (wb, hb):
                    raise ValueError("Images have different dimensions")
            else:
                art = artwork.load(root)
                wa, ha, a, b = art["width"], art["height"], art["design"], art["rgba"]
            values, report = diff.compare(a, b, wa, ha)
            small, large = diff.images(values, wa, ha)
            write(args.output, small)
            write(args.output.with_name(args.output.stem + "-large.png"), large)
            write(
                args.output.with_suffix(".json"),
                (json.dumps(report, indent=2) + "\n").encode(),
            )
            print(json.dumps(report, indent=2))
        elif args.command == "palette":
            finish = palette.refine(root)
            print(write(args.output, (json.dumps(finish, indent=2) + "\n").encode()))
        elif args.command == "plan":
            art = artwork.load(root)
            rows = png.filter_rows(
                art["indices"], art["width"], art["height"], 1, art["filters"]
            )
            if args.stream:
                stream = args.stream.read_bytes()
            else:
                executable = shutil.which(args.compressor)
                if not executable:
                    raise ValueError(
                        "The optional compressor is not installed; normal builds need only Python"
                    )
                if args.iterations < 1:
                    raise ValueError("Iterations must be positive")
                with tempfile.TemporaryDirectory() as folder:
                    path = write(Path(folder) / "pixels.bin", rows)
                    result = subprocess.run(
                        [
                            executable,
                            "--zlib",
                            "--i" + str(args.iterations),
                            "-c",
                            str(path),
                        ],
                        capture_output=True,
                        check=True,
                    )
                    stream = result.stdout
            recipe, decoded = deflate.extract(stream)
            if decoded != rows:
                raise ValueError("The stream does not encode the export pixels")
            if deflate.encode(rows, recipe) != stream:
                raise ValueError("The packing plan did not reproduce its stream")
            print(write(args.output, (json.dumps(recipe, indent=2) + "\n").encode()))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"error: {error}\n")
