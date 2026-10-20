#!/usr/bin/env python3
"""
icon_cutout.py — turn flat-icon renders (object on a plain tinted background)
into transparent RGBA cutouts, trimmed and re-centred, plus tinted previews.

For each <icon>.png in SRC:
  1. estimate the background colour from the border ring
  2. mark pixels as background when they are within --tol of that colour, or locally
     smooth (low gradient) and within --loose-tol of it: radial glows, two-tone
     gradients and soft shadows of any colour, while object colours stop at edges
  3. keep only the background region connected to the image border (flood fill),
     plus enclosed bg-coloured pockets (a bagel hole); badges/circles inside the
     drawing survive, so regenerate those with --seed-offset instead; tiny stray
     opaque islands are dropped
  4. erode the object alpha by --erode px (kills the 1-px dark fringe on light
     tints) and feather it by --feather px
  5. crop to the alpha bounding box, add --pad (fraction) padding, re-centre on a
     --size square transparent canvas  -> OUT/png/<icon>.png
  6. composite on the row's tint_hex      -> OUT/png-preview/<icon>.png
Both files are written without any metadata chunks.

Usage:
  python pipelines/comfyui/icon_cutout.py SRC_DIR OUT_DIR --csv icons.csv [--only a b] [--tol 28]
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

DEFAULT_TINT = "#FFFFFF"


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def background_mask(rgb: np.ndarray, a: argparse.Namespace, ring: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """Boolean mask of background pixels, and the estimated bg colour.

    Background = pixels close to the border colour (strict --tol), plus pixels that are
    locally smooth (low gradient after a small blur) and within --loose-tol of it,
    which covers radial glows, two-tone gradients and soft shadows of any colour.
    Only the border-connected part counts, plus enclosed pockets that are genuinely
    bg-coloured and larger than --hole-min px (a bagel hole).
    """
    border = np.concatenate([rgb[:ring].reshape(-1, 3), rgb[-ring:].reshape(-1, 3),
                             rgb[:, :ring].reshape(-1, 3), rgb[:, -ring:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=-1))
    strict = dist < a.tol

    smooth = np.stack([ndimage.gaussian_filter(rgb[..., c], a.blur) for c in range(3)], axis=-1)
    gx = np.stack([ndimage.sobel(smooth[..., c], axis=1) for c in range(3)], axis=-1)
    gy = np.stack([ndimage.sobel(smooth[..., c], axis=0) for c in range(3)], axis=-1)
    grad = np.sqrt(gx ** 2 + gy ** 2).max(axis=-1) / 8.0   # ~ per-pixel change in 0-255 units
    flat = (grad < a.grad_tol) & (dist < a.loose_tol)

    candidate = strict | flat
    labels, n = ndimage.label(candidate)
    if n == 0:
        return np.zeros(rgb.shape[:2], bool), bg
    border_ids = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    border_ids = set(border_ids[border_ids != 0].tolist())
    sizes = ndimage.sum(np.ones_like(labels), labels, index=np.arange(1, n + 1))
    mean_dist = ndimage.mean(dist, labels, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    for i in range(1, n + 1):
        if i in border_ids:
            keep[i] = True
        elif sizes[i - 1] >= a.hole_min and mean_dist[i - 1] < a.tol * 2.5:
            keep[i] = True   # enclosed pocket of plain background colour
    mask = keep[labels]

    # drop tiny opaque islands (speckles, stray dots) far from the main object
    obj_labels, m = ndimage.label(~mask)
    if m > 1:
        obj_sizes = ndimage.sum(np.ones_like(obj_labels), obj_labels, index=np.arange(1, m + 1))
        small = np.zeros(m + 1, bool)
        small[1:] = obj_sizes < a.island_min
        mask |= small[obj_labels]
    return mask, bg


def cutout(src: Path, dst: Path, preview: Path | None, tint_hex: str, a: argparse.Namespace) -> dict:
    with Image.open(src) as im:
        rgb_img = im.convert("RGB")
    rgb = np.asarray(rgb_img, dtype=np.float32)
    bg_mask, bg = background_mask(rgb, a)

    alpha = Image.fromarray(((~bg_mask) * 255).astype(np.uint8), "L")
    if a.erode > 0:
        alpha = alpha.filter(ImageFilter.MinFilter(2 * a.erode + 1))
    if a.feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(a.feather))

    rgba = rgb_img.copy().convert("RGBA")
    rgba.putalpha(alpha)
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError("nothing left after cutout (whole image treated as background)")
    obj = rgba.crop(bbox)
    bw, bh = obj.size
    span = max(bw, bh) * (1 + 2 * a.pad)
    scale = a.size / span
    new_w, new_h = max(1, round(bw * scale)), max(1, round(bh * scale))
    obj = obj.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (a.size, a.size), (0, 0, 0, 0))
    canvas.paste(obj, ((a.size - new_w) // 2, (a.size - new_h) // 2), obj)
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, "PNG", optimize=True)

    if preview is not None:
        preview.parent.mkdir(parents=True, exist_ok=True)
        base = Image.new("RGBA", (a.size, a.size), hex_to_rgb(tint_hex) + (255,))
        base.alpha_composite(canvas)
        base.convert("RGB").save(preview, "PNG", optimize=True)

    coverage = float((~bg_mask).mean())
    return {"bg": tuple(int(v) for v in bg), "bbox": bbox, "coverage": coverage,
            "scale": scale, "size": (new_w, new_h)}


def default_params(**overrides) -> argparse.Namespace:
    """Cutout parameters with the CLI defaults, for use from other scripts."""
    base = dict(tol=28, loose_tol=120, grad_tol=3.0, blur=1.2, hole_min=600, island_min=400,
                erode=1, feather=1.0, pad=0.08, size=1024)
    base.update(overrides)
    return argparse.Namespace(**base)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="folder of raw renders (<icon>.png)")
    ap.add_argument("out", type=Path, help="output root; writes OUT/png and OUT/png-preview")
    ap.add_argument("--csv", type=Path, help="icons CSV (icon,...,tint_hex) for preview tints")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--tol", type=float, default=28, help="strict RGB distance to bg colour (0-441)")
    ap.add_argument("--loose-tol", type=float, default=120, help="RGB distance cap for smooth-gradient background")
    ap.add_argument("--grad-tol", type=float, default=3.0, help="max local gradient (0-255/px) to count as smooth")
    ap.add_argument("--blur", type=float, default=1.2, help="gaussian sigma before the gradient test")
    ap.add_argument("--hole-min", type=int, default=600, help="min px for an enclosed bg pocket to be removed")
    ap.add_argument("--island-min", type=int, default=400, help="opaque islands smaller than this are dropped")
    ap.add_argument("--erode", type=int, default=1, help="alpha erosion px (removes dark fringe)")
    ap.add_argument("--feather", type=float, default=1.0, help="alpha blur radius px")
    ap.add_argument("--pad", type=float, default=0.08, help="padding fraction around the object")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--no-preview", action="store_true")
    a = ap.parse_args()

    tints: dict[str, str] = {}
    if a.csv:
        with a.csv.open(newline="", encoding="utf-8-sig") as f:
            tints = {r["icon"].strip(): r["tint_hex"].strip() for r in csv.DictReader(f)}

    files = sorted(p for p in a.src.glob("*.png"))
    if a.only:
        files = [p for p in files if p.stem in a.only]
    ok, failed, warn = 0, [], []
    for p in files:
        icon = p.stem
        tint = tints.get(icon, DEFAULT_TINT)
        try:
            info = cutout(p, a.out / "png" / f"{icon}.png",
                          None if a.no_preview else a.out / "png-preview" / f"{icon}.png", tint, a)
            flag = ""
            if info["coverage"] > 0.75:
                flag = "  WARN: >75% kept, background not detected?"
                warn.append(icon)
            elif info["coverage"] < 0.05:
                flag = "  WARN: <5% kept, object eaten?"
                warn.append(icon)
            print(f"  {icon:<24} ok  bg {info['bg']}  kept {info['coverage']:.0%}  scale {info['scale']:.2f}{flag}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed.append((icon, str(e)))
            print(f"  {icon:<24} FAILED {e}")
    print(f"\n{ok} cutouts -> {a.out / 'png'}; {len(failed)} failed; {len(warn)} warnings: {', '.join(warn)}")
    for icon, err in failed:
        print(f"  FAILED {icon}: {err}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
