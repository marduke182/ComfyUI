# Expeditionary Force crew & alien portraits — design

Date: 2026-07-24
Status: approved pending user review

## Goal

Generate painted sci-fi book-cover-style, full-body character portraits for the core
crew and iconic alien species of Craig Alanson's *Expeditionary Force* series (fan
art, personal use), using the existing ComfyUI queue-script pattern.

## Approach

Clone-and-adapt `pipelines/comfyui/queue_npc_realistic_v1.py` into a new standalone
script. No shared refactor; matches the repo convention of self-contained,
versioned queue scripts.

## Deliverable

`pipelines/comfyui/queue_exforce_crew_v1.py`

- Checkpoint: `juggernautXL_v9.safetensors` (same as realistic_v1)
- 832x1216, 30 steps, CFG 6.5, dpmpp_2m / karras
- Seeds: `[1001, 2002, 3003]` — 3 candidates per character
- Queues via HTTP to the ComfyUI server at `127.0.0.1:8188`
- Output: `characters/exforce/<id>/<id>_cover_*` (lands in the usual
  `H:\ComfyUI-Output` tree, separate from Watchman assets)

## Prompt recipe

Positive template (painted, not photoreal):

> epic digital painting, military science fiction book cover art, {name},
> {description}, wearing/of {clothing-or-body}, {setting}, {demeanor},
> dramatic rim lighting, cold starlight and warm console glow, detailed
> concept art, painterly brushwork, cinematic composition, dark background

Negative: photo, photograph, photorealistic, 35mm, film grain move INTO the
negative; keep pixel art, cartoon, anime, deformed/extra-limbs, text/watermark
terms from realistic_v1. For alien entries, drop the human-anatomy bias terms
where they'd fight the design (e.g. keep "extra fingers" out of the negative for
the Rindhalu).

## Roster

### Human crew (8)

| id | Character | Key visual notes |
|---|---|---|
| joe-bishop | Joe Bishop | Tall US Army officer from rural Maine, 20s–30s, brown hair, easygoing but tired command presence, combat uniform |
| skippy | Skippy the Magnificent | Chrome beer-can-sized cylinder, faint blue glow, hovering, lit like a holy relic |
| margaret-adams | Margaret Adams | US Marine gunnery sergeant, Black woman, athletic, composed and formidable |
| jeremy-smythe | Jeremy Smythe | British SAS lieutenant colonel, lean, older, aristocratic-hard |
| jennifer-simms | Jennifer Simms | US Army logistics officer / XO, practical, steady |
| kong-chang | Kong Chang | Chinese army officer, disciplined second-in-command |
| priya-desai | Priya Desai | Indian pilot, flight suit, confident |
| hans-chotek | Hans Chotek | Older Austrian UN bureaucrat, civilian suit among soldiers |

### Iconic aliens (6)

| id | Species | Key visual notes |
|---|---|---|
| kristang-warrior | Kristang | 7-foot reptilian humanoid warrior, dull green-brown scales, sharp teeth, warrior-caste powered armor, cruel bearing |
| ruhar-soldier | Ruhar | Humanoid soldier with soft hamster-like fur and features, large dark eyes, practical military fatigues and rifle — cute face, professional soldier |
| thuranin-cyborg | Thuranin | Small pale-green dwarfish humanoid, hairless, visible cybernetic implants on skull and hands, cold clinical stare |
| jeraptha-officer | Jeraptha | Large beetle-like insectoid, glossy wing cases, expressive antennae, naval officer's harness, roguish gambler energy |
| maxolhx-warrior | Maxolhx | Sleek apex-predator biped, black-and-copper armored exoskeleton look, feline-reptilian grace, radiating arrogance |
| rindhalu-elder | Rindhalu | Ancient many-limbed spider-like being, iridescent dark carapace, unsettling and vast, half in shadow |

Total queue: 14 characters x 3 seeds = 42 images.

## Notes / constraints

- The books give sparse physical descriptions; appearance fields are
  interpretation from context. Iteration happens by seed-picking and prompt
  tweaks, as with the Elias Crane portraits.
- Alien setting lines vary per species (Kristang war camp, Jeraptha ship
  wardroom, etc.) instead of one shared human-starship setting.
- Requires the ComfyUI server up on :8188 before running.

## Error handling / testing

Same as realistic_v1: per-queue try/except printing FAILED on URLError; the
script is verified by queueing and eyeballing outputs (no automated tests —
generation quality is judged visually).
