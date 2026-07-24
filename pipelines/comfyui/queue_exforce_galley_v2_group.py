#!/usr/bin/env python3
"""
queue_exforce_galley_v2_group.py — ExForce group scene: the whole crew together
in the Flying Dutchman galley, Skippy hovering over the table. Landscape canvas.

v2 notes: v1's "Merry Band of Pirates / pirate patch" wording made the model draw
literal pirate hats — all pirate-costume language removed from the positive and
banned in the negative. Same painted book-cover recipe, imported from
queue_exforce_crew_v1.py with the canvas flipped to 1216x832 for the group shot.

Output: H:\\ComfyUI-Output\\characters\\exforce\\galley-group\\galley-group_cover_*
Run with the ComfyUI server up on :8188.
"""
import urllib.error

import queue_exforce_crew_v1 as base

# Landscape canvas for the group scene (build_workflow reads these globals).
base.WIDTH, base.HEIGHT = 1216, 832

GROUP = {
    "id": "galley-group", "framing": "wide shot, group scene", "creature": False,
    "negative_extra": "pirate hat, tricorn hat, pirate costume, eyepatch, bandana, skull flag",
    "subject": "the crew of the starship Flying Dutchman gathered around a steel mess table: "
               "a tall young US Army colonel with short brown hair laughing over a mug of coffee, "
               "a composed athletic African-American female Marine sergeant, "
               "a lean silver-haired British special forces officer, "
               "a disciplined Chinese army officer, "
               "an Indian woman pilot in an olive flight suit, "
               "a practical brown-haired female army officer, "
               "and a small gleaming chrome cylinder the size of a beer can hovering above the table",
    "setting": "inside the cramped galley of the starship, brushed-steel counters, a battered coffee urn, "
               "stacked ration containers, netted supplies overhead, "
               "warm interior light against cold alien metal walls",
    "demeanor": "warm off-duty camaraderie, mid-laughter",
}


def main() -> None:
    print(f"Queueing {len(base.SEEDS)} galley group covers, {base.WIDTH}x{base.HEIGHT}")
    for seed in base.SEEDS:
        try:
            pid = base.queue(base.build_workflow(GROUP, seed))
            print(f"  {GROUP['id']:<18} seed {seed:>4}  queued  {pid}")
        except urllib.error.URLError as e:
            print(f"  {GROUP['id']:<18} seed {seed:>4}  FAILED  {e}")
    print("Done. Results -> H:\\ComfyUI-Output\\characters\\exforce\\galley-group\\")


if __name__ == "__main__":
    main()
