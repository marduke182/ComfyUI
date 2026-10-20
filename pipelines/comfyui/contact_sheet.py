#!/usr/bin/env python3
"""
contact_sheet.py — tile every PNG in a folder into one labelled grid.

Usage:
  python pipelines/comfyui/contact_sheet.py SRC_DIR OUT.png [--cols 8] [--cell 256] [--only a b c]
Labels are the file stems, drawn under each tile. Output is a clean PNG (no metadata).
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LABEL_H = 24


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--cell", type=int, default=256, help="tile size in px")
    ap.add_argument("--only", nargs="*", default=None, help="file stems to include, in this order")
    a = ap.parse_args()

    files = sorted(p for p in a.src.glob("*.png") if p.resolve() != a.out.resolve())
    if a.only:
        by_stem = {p.stem: p for p in files}
        files = [by_stem[s] for s in a.only if s in by_stem]
    if not files:
        raise SystemExit(f"no PNGs in {a.src}")

    cols = min(a.cols, len(files))
    rows = (len(files) + cols - 1) // cols
    cell, lh = a.cell, LABEL_H
    sheet = Image.new("RGB", (cols * cell, rows * (cell + lh)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    for i, p in enumerate(files):
        x, y = (i % cols) * cell, (i // cols) * (cell + lh)
        with Image.open(p) as im:
            sheet.paste(im.convert("RGB").resize((cell, cell), Image.LANCZOS), (x, y))
        draw.text((x + 6, y + cell + 4), p.stem, fill="black", font=font)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out, "PNG", optimize=True)
    print(f"{len(files)} tiles -> {a.out} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
