# ComfyUI — Watchman of Dunwich Art Pipeline

This ComfyUI install at `~/apps/ComfyUI` is the AI art pipeline for **The Watchman of Dunwich**
pixel-art game. Workflow JSON templates and palettes live in the game repo at
`~/projects/watchman-of-dunwich/pipelines/comfyui/` — that is the canonical home for
source-controlled assets, not this directory.

---

## Repository Layout (Two-Remote Strategy)

This repo uses a **fork + upstream** git setup so local customizations stay separate from official
ComfyUI releases:

| Remote     | URL                                          | Purpose                              |
|------------|----------------------------------------------|--------------------------------------|
| `origin`   | `git@github.com:marduke182/ComfyUI.git`      | Your fork — push local changes here  |
| `upstream` | `https://github.com/comfyanonymous/ComfyUI.git` | Official ComfyUI — pull updates from here |

### Branch conventions

| Branch           | Tracks      | Purpose                                       |
|------------------|-------------|-----------------------------------------------|
| `master`         | upstream    | Mirrors official ComfyUI master; never commit local changes here |
| `local/watchman` | origin      | All local customizations for the Watchman pipeline |

### Typical workflow

```bash
# Pull the latest official ComfyUI release into master
git checkout master
git pull upstream master

# Merge upstream updates into your local branch
git checkout local/watchman
git merge master

# Push your local changes to your fork
git push origin local/watchman
```

---

## Storage — Everything Goes on H Drive

**Rule: no large files live on the WSL system disk.** The C/WSL disk is for code; H drive is for
binary assets and outputs.

### Models — `/mnt/h/ComfyUI-Models/`

`models/` in this directory is a symlink:

```
~/apps/ComfyUI/models -> /mnt/h/ComfyUI-Models
```

Never put model files anywhere else. To add a new model type, create the subfolder under
`/mnt/h/ComfyUI-Models/` and ComfyUI will pick it up automatically.

### Outputs — `/mnt/h/ComfyUI-Output/`

`output/` in this directory is a symlink:

```
~/apps/ComfyUI/output -> /mnt/h/ComfyUI-Output
```

All generated images and videos land on H drive. The WSL system disk is **never** written to for
generation output.

#### Reviewing and accepting outputs

ComfyUI's built-in output browser (the **Queue / History** panel in the web UI at
`http://localhost:8188`) lets you inspect every generated image alongside the workflow that
produced it. Use this as the acceptance gate:

1. Run a generation — output lands in `/mnt/h/ComfyUI-Output/`.
2. Open the History panel in ComfyUI; click an output to preview it with its metadata.
3. **Accept**: move the file from `/mnt/h/ComfyUI-Output/` into the appropriate asset folder in the
   game repo (e.g. `~/projects/watchman-of-dunwich/assets/sprites/`). You can do this from the
   ComfyUI file manager or manually in a terminal.
4. **Reject**: delete the file. The H drive is the scratch area — nothing there is precious until
   you explicitly move it into the game repo.

This keeps the game repo clean: only intentionally accepted assets ever land there.

---

## Starting the Server

```bash
cd ~/apps/ComfyUI
./venv/bin/python main.py --port 8188
```

The venv uses Python 3.14 with torch 2.11+cu128. Models resolve through the `models/` symlink; no
`extra_model_paths.yaml` needed.

---

## Custom Nodes Installed

| Directory                      | Purpose                              |
|-------------------------------|--------------------------------------|
| `ComfyUI-Manager`             | Node manager (install/update nodes)  |
| `ComfyUI-PixelArt-Detector`   | Pixel art palette detection          |
| `ComfyUI-SUPIR`               | High-res upscaling (SUPIR model)     |
| `ComfyUI-seamless-tiling`     | Seamless texture tiling              |
| `ComfyUI_IPAdapter_plus`      | IP-Adapter for style/character ref   |
| `comfy_pixelization`          | Pixelization post-processing         |
| `comfyui_controlnet_aux`      | ControlNet preprocessors             |
| `rembg-comfyui-node-better`   | Background removal (rembg)           |
| `was-node-suite-comfyui`      | WAS utility node suite               |

---

## Watchman Pipeline — Key Conventions

- **Tile size**: 16×16 px (characters: 16×32 px). The WF Cookbook mentions 32px but is stale — the
  Art & Design Reference (2026-06-21) is authoritative.
- **Perspective**: oblique top-down 3/4 view — roof visible + side depth. Never flat front
  elevation.
- **Palettes**: must be indexed (P-mode) PNGs padded to 256 entries. RGB palettes lose exact colors
  due to web-palette remapping in `Image.convert("P")`.
- **Workflow templates**: WF-1 through WF-8 in `~/projects/watchman-of-dunwich/pipelines/comfyui/`.

---

## Utility Scripts

| Script           | Usage                                   |
|------------------|-----------------------------------------|
| `dlprogress.sh`  | `watch -n 5 bash dlprogress.sh` — live download progress for large model files |
