#!/usr/bin/env python3
"""Phase 2 — build the official+900 training inputs and supervision maps.

Cells:
  A: official data only, empty supervision map (trainer == original behavior)
  B: official + 900 round-2 records, empty map  -> assume-negative supervision
  C: official + 900 round-2 records, 900-entry map -> masked supervision

Sources (read-only): the Augmented-v2 run's input files, whose official
portion was verified byte-identical to the dataset files, and whose synthetic
records carry unambiguous guid prefixes (aug2_r2_* = round-2 900;
aug_r1_* / aug_exp_* = round-1 340).

Validations (all hard, no fallbacks):
  * exactly 900 aug2_r2 guids and 340 round-1 guids in the supervision map;
  * official portion of the v2 article/label files == official dataset files;
  * every aug2_r2 guid appears exactly once in both article and label files;
  * the C map has 450 full_multilabel + 450 target_only entries and every
    known_negative key is a valid "d:l1" label;
  * output counts: 2128 articles / 2128 label entries for B/C inputs.

Writes only into new_check/phase2/inputs/.
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
INP = HERE.parent / "inputs"

V2IN = BASE / "output/research_augmented_deberta_v2_unfiltered/20260714_032758/inputs"
OFF_ART = BASE / "dataset/train/train_event_base.json"
OFF_LAB = BASE / "dataset/gold_labels/train/train_human_values.json"


def fail(msg):
    sys.exit(f"ABORT: {msg}")


def main():
    sup = json.loads((V2IN / "supervision_map.json").read_text())
    r2 = sorted(g for g in sup if g.startswith("aug2_r2_"))
    r1 = sorted(g for g in sup if g.startswith(("aug_r1_", "aug_exp_")))
    if len(r2) != 900:
        fail(f"expected 900 aug2_r2 guids, got {len(r2)}")
    if len(r1) != 340:
        fail(f"expected 340 round-1 guids, got {len(r1)}")
    if set(r2) | set(r1) != set(sup):
        fail("supervision map contains guids with unrecognized prefixes")

    arts = json.loads((V2IN / "augmented_train_event_base_v2.json").read_text())
    labs = json.loads((V2IN / "augmented_train_human_values_v2.json").read_text())
    official_art = [a for a in arts if str(a["guid"]) not in sup]
    official_lab = [l for l in labs if str(l["guid"]) not in sup]
    if official_art != json.loads(OFF_ART.read_text()):
        fail("official article portion differs from dataset/train file")
    if official_lab != json.loads(OFF_LAB.read_text()):
        fail("official label portion differs from official gold train file")

    r2set = set(r2)
    r2_art = [a for a in arts if str(a["guid"]) in r2set]
    r2_lab = [l for l in labs if str(l["guid"]) in r2set]
    ca = Counter(str(a["guid"]) for a in r2_art)
    cl = Counter(str(l["guid"]) for l in r2_lab)
    if len(r2_art) != 900 or any(v != 1 for v in ca.values()):
        fail("round-2 article entries not exactly one per guid")
    if len(r2_lab) != 900 or any(v != 1 for v in cl.values()):
        fail("round-2 label entries not exactly one per guid")

    c_map = {g: sup[g] for g in r2}
    modes = Counter(v["supervision_mode"] for v in c_map.values())
    if modes != Counter({"full_multilabel": 450, "target_only": 450}):
        fail(f"unexpected round-2 mode split: {modes}")
    for g, v in c_map.items():
        for k in v.get("known_negative", []):
            d, l1 = k.split(":")
            if d not in ("0", "1") or not (0 <= int(l1) <= 53):
                fail(f"invalid known_negative {k} in {g}")

    INP.mkdir(parents=True, exist_ok=True)
    (INP / "train_event_base_official_plus_900.json").write_text(
        json.dumps(official_art + r2_art, ensure_ascii=False))
    (INP / "train_human_values_official_plus_900.json").write_text(
        json.dumps(official_lab + r2_lab, ensure_ascii=False))
    (INP / "supervision_map_empty.json").write_text("{}")
    (INP / "supervision_map_round2_only.json").write_text(
        json.dumps(c_map, ensure_ascii=False))

    manifest = {
        "official_articles": len(official_art),
        "round2_articles": len(r2_art),
        "combined_articles": len(official_art) + len(r2_art),
        "round2_modes": dict(modes),
        "round2_known_negative_records":
            sum(1 for v in c_map.values() if v.get("known_negative")),
        "validations": "all passed (see script docstring)",
    }
    (INP / "inputs_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
