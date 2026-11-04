#!/usr/bin/env python3
"""SOL2 Step 3: Direction QA fix using Flash as direction oracle.

Strategy (per fehuSOL2.md §3.2):
  - Keep value set unchanged
  - Only fix direction for:
    1. (actor, L1) where T=0 and single-actor disagree on direction
    2. High-DRR classes identified from T=0 baseline on dev
  - Use Flash predictions as direction oracle (zero API for dev analysis)
"""

from __future__ import annotations
import json, os
from collections import defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT / "fehuSOL2/outputs/step3_direction_fix"
T0_PRED = PROJECT / "Mathematical_optimization/temperature_ablation/t0.0/pred_task1b.json"
SA_PRED = PROJECT / "fehuSOL2/runs/step2_single_actor_pro_t0/pred_task1b.json"
FLASH_PRED = PROJECT / "Mathematical_optimization/runs/20260724_160254/pred_task1b.json"
DEV_GOLD = PROJECT / "dataset/gold_labels/dev/dev_human_values.json"

Atom = tuple[str, str, str, str]  # (guid, actor, l1, direction)

def load_atoms(path: Path) -> dict[str, set[Atom]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for art in data:
        guid = str(art["guid"])
        atoms = set()
        for hv in art.get("article_human_values", []):
            atoms.add((guid, str(hv["actor"]), str(hv["l1_value"]), str(hv.get("direction","1"))))
        result[guid] = atoms
    return result

def load_flash_map(path: Path) -> dict[tuple[str,str,str], str]:
    """(guid, actor, l1) -> Flash's direction"""
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for art in data:
        guid = str(art["guid"])
        for hv in art.get("article_human_values", []):
            result[(guid, str(hv["actor"]), str(hv["l1_value"]))] = str(hv.get("direction","1"))
    return result

# Load
t0 = load_atoms(T0_PRED)
sa = load_atoms(SA_PRED)
flash_dir = load_flash_map(FLASH_PRED)
gold_data = json.loads(DEV_GOLD.read_text(encoding="utf-8"))
gold = {}
for item in gold_data:
    guid = str(item["guid"])
    atoms = set()
    for hv in item.get("article_human_values", []):
        atoms.add((guid, str(hv["actor"]), str(hv["l1_value"]), str(hv["direction"])))
    gold[guid] = atoms

print("=" * 60)
print("SOL2 Step 3: Direction QA Fix (Flash Oracle)")
print("=" * 60)

# ── 1. Find direction conflicts between T=0 and single-actor ──
conflicts = []
for guid in t0:
    if guid not in sa:
        continue
    t0_vals = {(a, l1, d) for (g, a, l1, d) in t0[guid] if g == guid}
    sa_vals = {(a, l1, d) for (g, a, l1, d) in sa.get(guid, set()) if g == guid}
    
    # Find (actor, l1) pairs predicted by both but with different direction
    t0_map = {(a, l1): d for (a, l1, d) in t0_vals}
    sa_map = {(a, l1): d for (a, l1, d) in sa_vals}
    
    for (a, l1) in set(t0_map) & set(sa_map):
        if t0_map[(a,l1)] != sa_map[(a,l1)]:
            conflicts.append((guid, a, l1, t0_map[(a,l1)], sa_map[(a,l1)]))

print(f"\n1. Direction conflicts (T=0 vs single-actor): {len(conflicts)}")
for g, a, l1, d0, d1 in conflicts[:5]:
    print(f"   {g} actor={a} L1={l1}: T0={d0} vs SA={d1}")

# ── 2. Identify high-DRR classes from T=0 baseline ──
# Compute per-class DRR
class_reversals = defaultdict(int)
class_total = defaultdict(int)
for guid in t0:
    if guid not in gold:
        continue
    t0_atoms = t0[guid]
    g_atoms = gold[guid]
    for (g, a, l1, d_pred) in t0_atoms:
        # Find matching gold
        gold_match = {(gg, aa, ll, dd) for (gg, aa, ll, dd) in g_atoms if gg==g and aa==a and ll==l1}
        for (_, _, _, d_gold) in gold_match:
            key = f"{d_gold}:{l1}"
            class_total[key] += 1
            if d_pred != d_gold:
                class_reversals[key] += 1

high_drr = []
for cls in class_total:
    if class_total[cls] >= 5:  # minimum support
        drr = class_reversals[cls] / class_total[cls]
        high_drr.append((cls, drr, class_reversals[cls], class_total[cls]))
high_drr.sort(key=lambda x: -x[1])

print(f"\n2. Top-10 high-DRR classes:")
for cls, drr, rev, total in high_drr[:10]:
    print(f"   {cls}: DRR={drr:.3f} ({rev}/{total})")

# ── 3. Apply Flash direction fix ──
S_fixed = {}
n_flipped = 0
n_kept = 0

for guid in t0:
    fixed_atoms = set()
    for (g, a, l1, d_t0) in t0[guid]:
        flash_d = flash_dir.get((guid, a, l1))
        if flash_d is not None and flash_d != d_t0:
            fixed_atoms.add((guid, a, l1, flash_d))
            n_flipped += 1
        else:
            fixed_atoms.add((guid, a, l1, d_t0))
            n_kept += 1
    S_fixed[guid] = fixed_atoms

print(f"\n3. Flash direction fix:")
print(f"   Flipped: {n_flipped} directions")
print(f"   Kept:    {n_kept} directions")

# ── 4. Quick evaluation ──
def evaluate(pred, gold, name):
    tp = fp = fn = 0
    for guid in pred:
        if guid not in gold:
            continue
        p = pred[guid]
        g = gold[guid]
        # Filter to gold-exclusive denominator for DRR
        tp += len(p & g)
        fp += len(p - g)
        fn += len(g - p)
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * p * r / (p + r) if p + r else 0
    print(f"\n{name}:")
    print(f"   TP={tp} FP={fp} FN={fn}")
    print(f"   P={p:.4f} R={r:.4f} F1={f1:.4f}")
    return tp, fp, fn, p, r, f1

evaluate(t0, gold, "T=0 baseline")
evaluate(S_fixed, gold, "T=0 + Flash dir fix")

# ── 5. Save predictions ──
os.makedirs(OUT_DIR, exist_ok=True)

output_1b = []
for guid, atoms in S_fixed.items():
    hvs = []
    for (g, a, l1, d) in atoms:
        hvs.append({"actor": a, "l1_value": l1, "direction": d})
    output_1b.append({"guid": guid, "article_human_values": hvs})

json.dump(output_1b, open(OUT_DIR / "pred_task1b.json", "w"), indent=2, ensure_ascii=False)

# Derive 1a
l1_to_l2_data = json.load(open(PROJECT / "dataset/hv_categories/level_1_to_level_2.json"))
l1n = json.load(open(PROJECT / "dataset/hv_categories/human_value_level1_values.json"))
l2n = json.load(open(PROJECT / "dataset/hv_categories/human_value_level2_values.json"))
l1_to_l2 = {l1n[k]: l2n[v] for k, v in l1_to_l2_data["level_1_to_level_2"].items()}

output_1a = []
for art in output_1b:
    seen = set()
    vals = []
    for hv in art["article_human_values"]:
        l2 = l1_to_l2.get(str(hv["l1_value"]))
        if l2:
            k = (str(hv["actor"]), l2)
            if k not in seen:
                seen.add(k)
                vals.append({"actor": hv["actor"], "l2_value": l2})
    output_1a.append({"guid": art["guid"], "article_human_values": vals})

json.dump(output_1a, open(OUT_DIR / "pred_task1a.json", "w"), indent=2, ensure_ascii=False)

n_1a = sum(len(a["article_human_values"]) for a in output_1a)
n_1b = sum(len(a["article_human_values"]) for a in output_1b)
print(f"\nSaved: {n_1b} 1b predictions, {n_1a} 1a predictions")
print(f"Output: {OUT_DIR}")

# Save analysis
analysis = {
    "direction_conflicts": len(conflicts),
    "conflict_samples": [(g, a, l1, d0, d1) for g, a, l1, d0, d1 in conflicts[:10]],
    "high_drr_classes": [{"class": c, "drr": round(d,4), "reversals": r, "total": t} for c, d, r, t in high_drr[:20]],
    "flash_flipped": n_flipped,
    "flash_kept": n_kept,
}
json.dump(analysis, open(OUT_DIR / "analysis.json", "w"), indent=2, ensure_ascii=False)
print(f"Analysis saved to {OUT_DIR}/analysis.json")
