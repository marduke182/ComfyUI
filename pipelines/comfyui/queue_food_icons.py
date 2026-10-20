#!/usr/bin/env python3
"""
queue_food_icons.py — batch-generate flat vector-style food icons for the Brinco
app from a CSV of names, via the ComfyUI /prompt API.

CSV columns: icon,label_en,label_es,category,tint_hex
Output:      out/food-icons/<icon>.png  (1024x1024), one per row.

Styles (--style):
  flat  (default)  juggernautXL_v9, 25 steps, cfg 6, dpmpp_2m/karras  ~24 s/img, true flat fills
  fast             dreamshaperXL_lightning, 6 steps, cfg 1.8, dpmpp_sde/karras  ~3 s/img, glossier
Any of --checkpoint/--steps/--cfg/--sampler/--scheduler overrides the preset.

Behaviour:
  * rows whose PNG already exists are skipped (use --force to regenerate)
  * each icon gets a fixed seed derived from sha256(icon) so reruns reproduce
  * one job at a time: queue -> poll /history -> fetch via /view -> write PNG
  * every PNG is re-encoded with Pillow so no ComfyUI prompt/workflow text chunks
    survive, then verified; --verify-clean DIR / --strip-dir DIR work on any folder
  * one automatic retry per icon on any failure
  * prints a per-icon timing line and a final summary; exit code 1 if any failed

Workflow template: pipelines/comfyui/workflows/food_icon_sdxl.json
(plain SDXL txt2img; the script patches prompts, seed, sampler and prefix).

Usage (ComfyUI server up on :8188):
  python pipelines/comfyui/queue_food_icons.py                       # sample CSV, flat style
  python pipelines/comfyui/queue_food_icons.py --csv path/to/icons.csv
  python pipelines/comfyui/queue_food_icons.py --style fast --only apple --force
  python pipelines/comfyui/queue_food_icons.py --dry-run             # print prompts + seeds only
"""
import argparse
import colorsys
import csv
import hashlib
import json
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

SERVER = "http://127.0.0.1:8188"
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
WORKFLOW_PATH = HERE / "workflows" / "food_icon_sdxl.json"
DEFAULT_CSV = HERE / "samples" / "food_icons_sample.csv"
DEFAULT_OUT = REPO / "out" / "food-icons"

# Node ids inside food_icon_sdxl.json
N_CKPT, N_POS, N_NEG, N_LATENT, N_SAMPLER, N_SAVE = "4", "6", "7", "5", "3", "9"

STYLES = {
    "flat": dict(checkpoint="juggernautXL_v9.safetensors",
                 steps=25, cfg=6.0, sampler="dpmpp_2m", scheduler="karras"),
    "fast": dict(checkpoint="dreamshaperXL_lightningDPMSDE.safetensors",
                 steps=6, cfg=1.8, sampler="dpmpp_sde", scheduler="karras"),
}
DEFAULT_STYLE = "flat"
DEFAULT_SIZE = 1024

POS_TEMPLATE = (
    "flat vector illustration of {label_en}, vector art, flat design, cartoon icon, "
    "solid flat colors, single object, "
    "centered, fills 70% of the frame, front three-quarter view, "
    "simple geometric shapes, soft rounded shapes, 3 flat colors plus one darker shade, "
    "friendly cute food icon, clean edges, no outline strokes, "
    "plain {tint_name} background, isolated, "
    "no text, no shadow, no gradient, minimal, app icon"
)
PALETTE_HINT = "limited palette of coral, teal, sunflower yellow, violet and cream"
NEG_PROMPT = (
    "photo, photorealistic, 3d render, text, letters, watermark, logo, "
    "multiple objects, table, hands, people, blurry, noisy, gradient, shadow, "
    "complex background, pattern, frame, border, "
    "plate, dish, circle, badge, decal, sticker, gloss, highlight, reflection, "
    "two straws, multiple items, "
    "realistic, photograph, photography, detailed texture, realistic lighting, sliced, cut open"
)

# Brand palette (hue in degrees) used to turn tint_hex into a word SDXL understands.
PALETTE = {
    "coral": "#FF6B6B",
    "teal": "#2EC4B6",
    "sunflower yellow": "#FFD166",
    "violet": "#7B61FF",
    "cream": "#FFF8EE",
}

POLL_INTERVAL = 0.5
JOB_TIMEOUT = 300  # seconds per image before we give up and retry


# ----------------------------------------------------------------------------- helpers
def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad hex colour {h!r}")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def tint_name(tint_hex: str) -> str:
    """Nearest brand-palette name for a (usually pastel) hex tint, e.g. '#FFE3E3' -> 'coral pink'."""
    try:
        r, g, b = hex_to_rgb(tint_hex)
    except ValueError:
        return "cream"
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.25 or light > 0.97:
        return "cream"
    hue_deg = hue * 360
    best, best_d = "cream", 999.0
    for name, phex in PALETTE.items():
        if name == "cream":
            continue
        ph = colorsys.rgb_to_hls(*hex_to_rgb(phex))[0] * 360
        d = min(abs(hue_deg - ph), 360 - abs(hue_deg - ph))
        if d < best_d:
            best, best_d = name, d
    # pastel tints read better with a softening word
    return {"coral": "pastel coral pink", "sunflower yellow": "pastel butter yellow",
            "violet": "pastel lavender", "teal": "pastel mint teal"}.get(best, best)


def seed_for(icon: str) -> int:
    """Deterministic 32-bit seed from the icon name."""
    return int(hashlib.sha256(icon.encode("utf-8")).hexdigest()[:8], 16)


def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    required = {"icon", "label_en", "tint_hex"}
    if not rows or not required.issubset(rows[0].keys()):
        sys.exit(f"CSV {csv_path} must have columns: icon,label_en,label_es,category,tint_hex")
    return [r for r in rows if r["icon"].strip()]


def build_positive(row: dict, opts: argparse.Namespace) -> str:
    text = POS_TEMPLATE.format(label_en=row["label_en"].strip(),
                               tint_name=tint_name(row["tint_hex"]))
    if opts.palette_hint:
        text += ", " + PALETTE_HINT
    if opts.pos_extra:
        text += ", " + opts.pos_extra
    return text


def build_negative(opts: argparse.Namespace) -> str:
    return NEG_PROMPT + (", " + opts.neg_extra if opts.neg_extra else "")


def build_workflow(template: dict, row: dict, opts: argparse.Namespace) -> dict:
    wf = json.loads(json.dumps(template))  # deep copy
    icon = row["icon"].strip()
    wf[N_CKPT]["inputs"]["ckpt_name"] = opts.checkpoint
    wf[N_POS]["inputs"]["text"] = build_positive(row, opts)
    wf[N_NEG]["inputs"]["text"] = build_negative(opts)
    wf[N_LATENT]["inputs"].update(width=opts.size, height=opts.size, batch_size=1)
    wf[N_SAMPLER]["inputs"].update(seed=seed_for(icon), steps=opts.steps, cfg=opts.cfg,
                                   sampler_name=opts.sampler, scheduler=opts.scheduler,
                                   denoise=1.0)
    wf[N_SAVE]["inputs"]["filename_prefix"] = f"food-icons/{icon}"
    return wf


# ----------------------------------------------------------------------------- metadata
TEXT_CHUNKS = {b"tEXt", b"iTXt", b"zTXt", b"eXIf"}


def png_text_chunks(path: Path) -> list[str]:
    """Return the names of metadata chunks (tEXt/iTXt/zTXt/eXIf) present in a PNG."""
    found = []
    with path.open("rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return ["not-a-png"]
        while True:
            head = f.read(8)
            if len(head) < 8:
                break
            length, ctype = struct.unpack(">I4s", head)
            if ctype in TEXT_CHUNKS:
                found.append(ctype.decode("ascii"))
            f.seek(length + 4, 1)  # skip data + CRC
            if ctype == b"IEND":
                break
    return found


def strip_png(path: Path) -> None:
    """Re-encode the PNG from pixels only (no pnginfo), then verify no text chunks remain."""
    with Image.open(path) as im:
        im.load()
        clean = im.convert("RGBA")
    clean.save(path, "PNG", optimize=True)
    with Image.open(path) as im:
        leftover = getattr(im, "text", {})
    chunks = png_text_chunks(path)
    if leftover or chunks:
        raise RuntimeError(f"metadata still present in {path.name}: {chunks or list(leftover)}")


def scan_folder(folder: Path, strip: bool) -> int:
    """List PNGs carrying text chunks; optionally strip them. Returns count still dirty."""
    pngs = sorted(folder.rglob("*.png"))
    dirty = 0
    for png in pngs:
        chunks = png_text_chunks(png)
        if chunks and strip:
            strip_png(png)
            print(f"  stripped {png.relative_to(folder)}  ({', '.join(chunks)})")
        elif chunks:
            dirty += 1
            print(f"  DIRTY    {png.relative_to(folder)}  ({', '.join(chunks)})")
    print(f"{len(pngs)} PNGs in {folder}: {dirty} with text chunks"
          + (" (after stripping)" if strip else ""))
    return dirty


# ----------------------------------------------------------------------------- API
def api_json(path: str, data: dict | None = None, timeout: int = 30):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(SERVER + path, data=body,
                                 headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def queue_prompt(workflow: dict) -> str:
    return api_json("/prompt", {"prompt": workflow})["prompt_id"]


def wait_for_output(prompt_id: str) -> dict:
    """Poll /history until the job finishes; return the first output image record."""
    deadline = time.monotonic() + JOB_TIMEOUT
    while time.monotonic() < deadline:
        hist = api_json(f"/history/{prompt_id}").get(prompt_id)
        if hist:
            status = hist.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                detail = msgs[0][1].get("exception_message") if msgs else "unknown error"
                raise RuntimeError(f"ComfyUI execution error: {detail}")
            for node_out in hist.get("outputs", {}).values():
                for img in node_out.get("images", []):
                    if img.get("type") == "output":
                        return img
            if status.get("completed"):
                raise RuntimeError("job completed but produced no output image")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"no result for {prompt_id} after {JOB_TIMEOUT}s")


def fetch_image(img: dict) -> bytes:
    """Download the finished PNG from ComfyUI's output folder via /view."""
    q = urllib.parse.urlencode({"filename": img["filename"],
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")})
    with urllib.request.urlopen(f"{SERVER}/view?{q}", timeout=60) as resp:
        return resp.read()


def generate_one(template: dict, row: dict, opts: argparse.Namespace, dest: Path) -> float:
    t0 = time.monotonic()
    pid = queue_prompt(build_workflow(template, row, opts))
    img = wait_for_output(pid)
    dest.write_bytes(fetch_image(img))
    strip_png(dest)
    return time.monotonic() - t0


# ----------------------------------------------------------------------------- main
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help=f"input CSV (default: {DEFAULT_CSV.relative_to(REPO)})")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT.relative_to(REPO)})")
    p.add_argument("--style", choices=sorted(STYLES), default=DEFAULT_STYLE,
                   help=f"sampling preset (default: {DEFAULT_STYLE}); individual flags below override it")
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--cfg", type=float, default=None)
    p.add_argument("--sampler", default=None)
    p.add_argument("--scheduler", default=None)
    p.add_argument("--size", type=int, default=DEFAULT_SIZE, help="square output size in px")
    p.add_argument("--palette-hint", action="store_true",
                   help="append the brand-palette colour hint to the positive prompt (off by default: it leaks colours)")
    p.add_argument("--pos-extra", default="", help="text appended to the positive prompt")
    p.add_argument("--neg-extra", default="", help="text appended to the negative prompt")
    p.add_argument("--only", action="append", default=[], metavar="ICON", help="limit to these icon ids (repeatable)")
    p.add_argument("--limit", type=int, default=0, help="stop after N rows (0 = all)")
    p.add_argument("--force", action="store_true", help="regenerate even if the PNG exists")
    p.add_argument("--dry-run", action="store_true", help="print prompts and seeds, do not queue")
    p.add_argument("--verify-clean", type=Path, metavar="DIR",
                   help="scan DIR for PNGs still carrying text chunks and exit (no generation)")
    p.add_argument("--strip-dir", type=Path, metavar="DIR",
                   help="strip metadata from every PNG under DIR and exit (no generation)")
    opts = p.parse_args()
    for key, value in STYLES[opts.style].items():
        if getattr(opts, key) is None:
            setattr(opts, key, value)
    return opts


def main() -> None:
    opts = parse_args()
    if opts.strip_dir:
        sys.exit(1 if scan_folder(opts.strip_dir, strip=True) else 0)
    if opts.verify_clean:
        sys.exit(1 if scan_folder(opts.verify_clean, strip=False) else 0)
    template = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    rows = load_rows(opts.csv)
    if opts.only:
        rows = [r for r in rows if r["icon"].strip() in opts.only]
    if opts.limit:
        rows = rows[:opts.limit]
    opts.out.mkdir(parents=True, exist_ok=True)

    print(f"{len(rows)} icons from {opts.csv} -> {opts.out}")
    print(f"  style {opts.style}: {opts.checkpoint}  {opts.steps} steps  cfg {opts.cfg}  "
          f"{opts.sampler}/{opts.scheduler}  {opts.size}x{opts.size}")

    done, skipped, failed, times = [], [], [], []
    for row in rows:
        icon = row["icon"].strip()
        dest = opts.out / f"{icon}.png"
        if dest.exists() and not opts.force:
            skipped.append(icon)
            print(f"  {icon:<24} skip    (exists)")
            continue
        if opts.dry_run:
            print(f"  {icon:<24} seed {seed_for(icon):>10}  tint {tint_name(row['tint_hex'])!r}")
            print(f"      {build_positive(row, opts)}")
            continue

        last_err = None
        for attempt in (1, 2):
            try:
                secs = generate_one(template, row, opts, dest)
                times.append(secs)
                done.append(icon)
                print(f"  {icon:<24} ok      {secs:5.1f}s  seed {seed_for(icon)}"
                      + ("  (retry)" if attempt == 2 else ""))
                break
            except (urllib.error.URLError, RuntimeError, TimeoutError, OSError) as e:
                last_err = e
                print(f"  {icon:<24} attempt {attempt} failed: {e}")
                if attempt == 1:
                    time.sleep(2)
        else:
            failed.append((icon, str(last_err)))

    print("\nSummary")
    print(f"  generated {len(done)}  skipped {len(skipped)}  failed {len(failed)}")
    if times:
        print(f"  time per image: avg {sum(times)/len(times):.1f}s  "
              f"min {min(times):.1f}s  max {max(times):.1f}s  total {sum(times):.0f}s")
    for icon, err in failed:
        print(f"  FAILED {icon}: {err}")
    print(f"  output -> {opts.out}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
