# Expeditionary Force Portraits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone ComfyUI queue script that generates painted sci-fi book-cover, full-body portraits for 14 Expeditionary Force characters (8 human crew + 6 alien species), 3 seeds each.

**Architecture:** Clone of the `pipelines/comfyui/queue_npc_realistic_v1.py` pattern: a character-data list, a prompt template, a `build_workflow()` that emits a raw ComfyUI API graph, and a `queue()` that POSTs it to the local server. No shared code, no new dependencies (stdlib only).

**Tech Stack:** Python 3 stdlib (`json`, `urllib`), ComfyUI HTTP API on `127.0.0.1:8188`, SDXL checkpoint `juggernautXL_v9.safetensors`.

## Global Constraints

- Checkpoint: `juggernautXL_v9.safetensors` (exact filename)
- Resolution 832x1216, 30 steps, CFG 6.5, sampler `dpmpp_2m`, scheduler `karras`
- Seeds: `[1001, 2002, 3003]` (3 candidates per character; 42 images total)
- Output prefix: `characters/exforce/<id>/<id>_cover`
- Painted style: photo/photoreal terms go in the NEGATIVE prompt, never the positive
- Alien (creature) entries must NOT get the human-anatomy negative terms (`extra limbs, extra fingers, bad hands...`)
- Git workflow: commit directly on `master` (repo convention), no branches/PRs

---

### Task 1: queue_exforce_crew_v1.py

**Files:**
- Create: `pipelines/comfyui/queue_exforce_crew_v1.py`

**Interfaces:**
- Consumes: nothing from this repo (standalone; talks to the ComfyUI server over HTTP)
- Produces: `build_workflow(char: dict, seed: int) -> dict` and `queue(workflow: dict) -> str` (same shape as `queue_npc_realistic_v1.py`, used only within the script)

- [ ] **Step 1: Write the script**

Create `pipelines/comfyui/queue_exforce_crew_v1.py` with exactly this content:

```python
#!/usr/bin/env python3
"""
queue_exforce_crew_v1.py — painted sci-fi book-cover portraits for the core crew
and iconic alien species of Craig Alanson's Expeditionary Force (fan art).

Full-body figures, painterly military-SF cover style (NOT photoreal — photo terms
live in the negative prompt). Pure txt2img on juggernautXL, 832x1216, 3 seeds per
character. Spec: docs/superpowers/specs/2026-07-24-exforce-portraits-design.md

Output: H:\\ComfyUI-Output\\characters\\exforce\\<id>\\<id>_cover_*
Run with the ComfyUI server up on :8188.
"""
import json
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8188"
CHECKPOINT = "juggernautXL_v9.safetensors"
WIDTH, HEIGHT = 832, 1216
STEPS = 30
CFG = 6.5
SAMPLER = "dpmpp_2m"
SCHEDULER = "karras"
SEEDS = [1001, 2002, 3003]   # 3 cover candidates per character

FULL_FIGURE = "full body portrait, full figure from head to boots"

# Each: id, framing, subject (name + look + attire/body), setting, demeanor,
# creature (True skips human-anatomy negatives), negative_extra (appended if set).
CHARACTERS = [
    # ---- human crew ----
    {"id": "joe-bishop", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Joe Bishop, a tall broad-shouldered US Army colonel in his late twenties, "
                "short brown hair, friendly open face worn tired by command, wry half-smile, "
                "modern digital-camo combat uniform with a skull-and-crossbones pirate shoulder patch, rifle slung",
     "setting": "standing on the dim bridge of a captured alien starship, starfield viewscreen behind him",
     "demeanor": "easygoing but burdened command presence"},
    {"id": "skippy", "framing": "centered hero shot", "creature": True,
     "negative_extra": "humanoid, robot, arms, legs, face, eyes, label, sticker",
     "subject": "Skippy the Magnificent, a flawless mirror-polished chrome cylinder the size of a beer can, "
                "hovering motionless in mid-air above a black pedestal, faint cold blue glow around it",
     "setting": "dark starship compartment, single shaft of light from above, lit like a holy relic, volumetric light",
     "demeanor": "an absurd object radiating smug cosmic grandeur"},
    {"id": "margaret-adams", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Margaret Adams, a US Marine gunnery sergeant, athletic African-American woman in her early thirties, "
                "close-cropped dark hair, composed formidable face, "
                "modern combat fatigues with sergeant chevrons, rifle held at low ready",
     "setting": "standing in a starship corridor lined with glowing alien technology panels",
     "demeanor": "calm, tough, utterly professional"},
    {"id": "jeremy-smythe", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Jeremy Smythe, a British SAS lieutenant colonel in his late forties, lean and hard, "
                "short silver-grey hair, sharp aristocratic weathered face, "
                "British special forces combat gear with a winged-dagger patch, suppressed carbine",
     "setting": "standing in a dropship bay beside racked weapons, cold overhead light",
     "demeanor": "quiet lethal composure"},
    {"id": "jennifer-simms", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Jennifer Simms, a US Army logistics officer in her mid thirties, "
                "brown hair in a regulation bun, steady practical face, "
                "army combat uniform with captain bars, datapad in hand",
     "setting": "standing in a starship cargo bay stacked with strapped-down supply crates",
     "demeanor": "grounded, no-nonsense, quietly indispensable"},
    {"id": "kong-chang", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Kong Chang, a Chinese People's Liberation Army officer in his mid thirties, "
                "short black hair, disciplined thoughtful face, "
                "PLA combat uniform with subdued rank insignia, hands clasped behind his back",
     "setting": "standing in a starship command center, tactical holograms glowing",
     "demeanor": "disciplined, loyal, quietly capable"},
    {"id": "priya-desai", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Priya Desai, an Indian air force pilot in her early thirties, "
                "dark hair tied back, confident sharp-eyed face, "
                "olive flight suit covered in mission patches, flight helmet under one arm",
     "setting": "standing in a hangar bay beside a sleek angular alien dropship",
     "demeanor": "cocky competent fighter-pilot grin"},
    {"id": "hans-chotek", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
     "subject": "Hans Chotek, an Austrian United Nations diplomat in his late fifties, "
                "silver hair immaculately combed, precise disapproving face, "
                "tailored dark three-piece civilian suit, leather folio under one arm",
     "setting": "standing stiffly in a starship conference room among soldiers' stowed combat gear",
     "demeanor": "prim, bureaucratic, conspicuously out of place"},
    # ---- iconic aliens ----
    {"id": "kristang-warrior", "framing": FULL_FIGURE, "creature": True, "negative_extra": "",
     "subject": "a Kristang warrior, seven foot tall reptilian humanoid alien, dull green-brown scales, "
                "yellow slit-pupil eyes, mouth of needle teeth, spiked powered combat armor with warrior-caste crest",
     "setting": "striding through a burning war camp at night, torn alien banners behind it",
     "demeanor": "cruel arrogant menace"},
    {"id": "ruhar-soldier", "framing": FULL_FIGURE, "creature": True, "negative_extra": "",
     "subject": "a Ruhar soldier, humanoid alien with soft tan hamster-like fur, round face, "
                "large dark eyes, small rounded ears, practical military fatigues and body armor, rifle at patrol carry",
     "setting": "standing in tall grass on a colony world under a violet alien sky, distant farm domes",
     "demeanor": "alert and professional, deceptively cute"},
    {"id": "thuranin-cyborg", "framing": FULL_FIGURE, "creature": True, "negative_extra": "",
     "subject": "a Thuranin, a small pale green hairless dwarfish humanoid alien, "
                "cybernetic implants studding its skull and hands, one glowing ocular implant, sleek silver-grey skinsuit",
     "setting": "standing in a sterile white starship laboratory, cold clinical light, surgical machinery",
     "demeanor": "cold clinical contempt"},
    {"id": "jeraptha-officer", "framing": FULL_FIGURE, "creature": True, "negative_extra": "",
     "subject": "a Jeraptha naval officer, large upright beetle-like insectoid alien, "
                "glossy dark wing cases with iridescent sheen, expressive antennae, "
                "officer's harness with rank insignia across its thorax",
     "setting": "in a starship wardroom, a glowing holographic wagering board behind it",
     "demeanor": "roguish gambler swagger"},
    {"id": "maxolhx-warrior", "framing": FULL_FIGURE, "creature": True, "negative_extra": "",
     "subject": "a Maxolhx, a sleek apex-predator alien biped, black and copper armored exoskeleton, "
                "feline-reptilian grace, narrow luminous eyes, long clawed limbs",
     "setting": "standing on the gleaming obsidian bridge of a warship, red tactical light",
     "demeanor": "radiating ancient effortless arrogance"},
    {"id": "rindhalu-elder", "framing": "full figure emerging from shadow", "creature": True, "negative_extra": "",
     "subject": "a Rindhalu, an ancient vast many-limbed spider-like alien, iridescent dark carapace, "
                "clusters of small star-like eyes, long articulated limbs, half veiled in drifting haze",
     "setting": "within a dim crystalline living starship, faint blue bioluminescence",
     "demeanor": "patient unknowable menace"},
]

POS_TEMPLATE = (
    "epic digital painting, military science fiction book cover art, {framing}, "
    "{subject}, {setting}, {demeanor}, "
    "dramatic rim lighting, cold starlight and warm console glow, detailed concept art, "
    "painterly brushwork, cinematic composition, dark background"
)

NEG_BASE = (
    "photo, photograph, photorealistic, 35mm film, film grain, "
    "pixel art, cartoon, anime, chibi, 3d render, video game screenshot, "
    "cropped, out of frame, cut off, close up, headshot, "
    "text, watermark, signature, logo, book title, author name, "
    "blurry, low quality, jpeg artifacts"
)
NEG_HUMAN_ANATOMY = "deformed, extra limbs, extra fingers, bad hands, mutated, disfigured"


def build_negative(char: dict) -> str:
    parts = [NEG_BASE]
    if not char["creature"]:
        parts.append(NEG_HUMAN_ANATOMY)
    if char["negative_extra"]:
        parts.append(char["negative_extra"])
    return ", ".join(parts)


def build_workflow(char: dict, seed: int) -> dict:
    positive = POS_TEMPLATE.format(**char)
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": build_negative(char), "clip": ["4", 1]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "3": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": STEPS, "cfg": CFG,
                         "sampler_name": SAMPLER, "scheduler": SCHEDULER, "denoise": 1.0,
                         "model": ["4", 0], "positive": ["6", 0],
                         "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": f"characters/exforce/{char['id']}/{char['id']}_cover",
                         "images": ["8", 0]}},
    }


def queue(workflow: dict) -> str:
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{SERVER}/prompt", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["prompt_id"]


def main() -> None:
    total = len(CHARACTERS) * len(SEEDS)
    print(f"Queueing {total} cover images ({len(CHARACTERS)} characters x {len(SEEDS)} seeds), {WIDTH}x{HEIGHT}")
    for char in CHARACTERS:
        for seed in SEEDS:
            try:
                pid = queue(build_workflow(char, seed))
                print(f"  {char['id']:<18} seed {seed:>4}  queued  {pid}")
            except urllib.error.URLError as e:
                print(f"  {char['id']:<18} seed {seed:>4}  FAILED  {e}")
    print("Done. Results -> H:\\ComfyUI-Output\\characters\\exforce\\<id>\\<id>_cover_*")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it compiles and the graph builds correctly (dry run, no server)**

Run:

```bash
python3 -m py_compile pipelines/comfyui/queue_exforce_crew_v1.py && python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('q', 'pipelines/comfyui/queue_exforce_crew_v1.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert len(m.CHARACTERS) == 14, len(m.CHARACTERS)
assert len(m.CHARACTERS) * len(m.SEEDS) == 42
for c in m.CHARACTERS:
    wf = m.build_workflow(c, 1001)
    pos = wf['6']['inputs']['text']; neg = wf['7']['inputs']['text']
    assert 'photo' not in pos and 'digital painting' in pos, c['id']
    assert 'photorealistic' in neg, c['id']
    assert ('extra fingers' in neg) != c['creature'], c['id']
    assert wf['9']['inputs']['filename_prefix'] == f\"characters/exforce/{c['id']}/{c['id']}_cover\"
print('dry run OK: 14 characters, 42 images, prompts and paths valid')
"
```

Expected output: `dry run OK: 14 characters, 42 images, prompts and paths valid`

(Note: `exec_module` only defines the module; `main()` is guarded by `__name__ == "__main__"`, so nothing is queued.)

- [ ] **Step 3: Commit**

```bash
git add pipelines/comfyui/queue_exforce_crew_v1.py docs/superpowers/plans/2026-07-24-exforce-portraits.md
git commit -m "Add ExForce painted-cover portrait queue script (14 chars x 3 seeds)"
```

### Task 2: Queue the batch (requires live ComfyUI server)

**Files:**
- Create: none (runs Task 1's script)

**Interfaces:**
- Consumes: `queue_exforce_crew_v1.py` from Task 1; ComfyUI server on `127.0.0.1:8188`
- Produces: 42 images under `H:\ComfyUI-Output\characters\exforce\<id>\`

- [ ] **Step 1: Check the server is up**

Run: `curl -s http://127.0.0.1:8188/system_stats | head -c 200`
Expected: JSON beginning with `{"system": ...`. If connection refused, start ComfyUI first (`./start.sh`) or report to the user that the server is down — do not mark this task complete.

- [ ] **Step 2: Run the queue script**

Run: `python3 pipelines/comfyui/queue_exforce_crew_v1.py`
Expected: 42 lines ending in `queued <prompt_id>`, then the `Done.` line. Any `FAILED` line means the server rejected a graph — stop and investigate before continuing.

- [ ] **Step 3: Report**

Tell the user generation is queued and where outputs land. Image quality review is manual/visual (per spec, no automated checks).
