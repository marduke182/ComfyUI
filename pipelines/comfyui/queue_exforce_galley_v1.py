#!/usr/bin/env python3
"""
queue_exforce_galley_v1.py — one-off ExForce scene: a Merry Band of Pirates
crewman in the galley of the Flying Dutchman. Same painted book-cover recipe as
queue_exforce_crew_v1.py (imported from it), 3 seeds.

Output: H:\\ComfyUI-Output\\characters\\exforce\\galley-crewman\\galley-crewman_cover_*
Run with the ComfyUI server up on :8188.
"""
import urllib.error

from queue_exforce_crew_v1 import FULL_FIGURE, SEEDS, WIDTH, HEIGHT, build_workflow, queue

CREWMAN = {
    "id": "galley-crewman", "framing": FULL_FIGURE, "creature": False, "negative_extra": "",
    "subject": "a Merry Band of Pirates crewman, a young special forces soldier in worn fatigues "
               "with a skull-and-crossbones pirate shoulder patch, sleeves rolled up, "
               "holding a steaming mug of coffee",
    "setting": "inside the cramped galley of the starship Flying Dutchman, brushed-steel counters, "
               "a battered coffee urn, stacked ration containers, netted supplies overhead, "
               "warm interior light against cold alien metal walls",
    "demeanor": "relaxed off-duty moment, quiet smile",
}


def main() -> None:
    print(f"Queueing {len(SEEDS)} galley-crewman covers, {WIDTH}x{HEIGHT}")
    for seed in SEEDS:
        try:
            pid = queue(build_workflow(CREWMAN, seed))
            print(f"  {CREWMAN['id']:<18} seed {seed:>4}  queued  {pid}")
        except urllib.error.URLError as e:
            print(f"  {CREWMAN['id']:<18} seed {seed:>4}  FAILED  {e}")
    print("Done. Results -> H:\\ComfyUI-Output\\characters\\exforce\\galley-crewman\\")


if __name__ == "__main__":
    main()
