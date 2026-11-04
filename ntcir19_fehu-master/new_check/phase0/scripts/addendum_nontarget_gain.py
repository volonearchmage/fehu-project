#!/usr/bin/env python3
"""Addendum: decompose the baseline -> v2 per-class F1 change on NON-target
gold-supported classes by whether the class received synthetic training
positives in the v2 training set (from any source: round-1 340 or round-2
secondary labels).

Answers: "did the observed macro improvement come from classes that were
actually augmented, or is it diffuse (pointing at the loss/trajectory change
rather than targeted data)?"

Usage: python addendum_nontarget_gain.py   (after run_phase0.py)
Reads existing artifacts + Phase-0 outputs; writes
outputs/nontarget_gain_decomposition.csv and appends nothing anywhere else.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from phase0_lib import (  # noqa: E402
    ALL_108, class_index, fmt, gold_support, load_json, per_label_counts, rp,
    write_csv,
)
from evaluation import parse_task1b, safe_div, f1_from_pr  # noqa: E402

PHASE0 = HERE.parent
OUT = PHASE0 / "outputs"
CFG = json.loads((PHASE0 / "configs" / "phase0_config.json").read_text())


def per_class_f1(pred_rel: str, gold: dict) -> dict:
    counts = per_label_counts(gold, parse_task1b(str(rp(pred_rel))))
    out = {}
    for lab in ALL_108:
        c = counts[lab]
        p = safe_div(c["tp"], c["tp"] + c["fp"])
        r = safe_div(c["tp"], c["tp"] + c["fn"])
        out[lab] = dict(tp=c["tp"], fp=c["fp"], fn=c["fn"],
                        p=p, r=r, f1=f1_from_pr(p, r))
    return out


def main():
    gold = parse_task1b(str(rp(CFG["gold_dev_labels"])))
    gsup = gold_support(gold)
    targets = set(json.loads((OUT / "run_manifest.json").read_text())["targets_18"])

    # synthetic positives per class in the v2 training set
    sup_map = load_json(CFG["v2_supervision_map"])
    syn_pos = defaultdict(int)
    for item in load_json(CFG["v2_train_labels"]):
        guid = str(item["guid"])
        if guid not in sup_map:
            continue  # official article
        per_actor = defaultdict(set)
        for hv in item["article_human_values"]:
            per_actor[str(hv["actor"])].add(f"{hv['direction']}:{hv['l1_value']}")
        for pos in per_actor.values():
            for cls in pos:
                syn_pos[cls] += 1

    base = per_class_f1(CFG["systems"]["deberta_baseline"]["pred_task1b"], gold)
    v2 = per_class_f1(CFG["systems"]["augmented_v2"]["pred_task1b"], gold)

    rows = []
    for lab in ALL_108:
        if lab in targets or gsup.get(lab, 0) == 0:
            continue  # non-target gold-supported classes only
        rows.append({
            "class_key": lab,
            "dev_gold_support": gsup[lab],
            "synthetic_positives_in_v2_train": syn_pos.get(lab, 0),
            "received_synthetic": syn_pos.get(lab, 0) > 0,
            "baseline_f1": fmt(base[lab]["f1"]),
            "v2_f1": fmt(v2[lab]["f1"]),
            "delta_f1": fmt(v2[lab]["f1"] - base[lab]["f1"]),
            "baseline_tp": base[lab]["tp"], "v2_tp": v2[lab]["tp"],
            "v2_fp": v2[lab]["fp"],
        })
    rows.sort(key=lambda r: -r["delta_f1"])
    write_csv(OUT / "nontarget_gain_decomposition.csv", rows,
              list(rows[0].keys()))

    with_syn = [r for r in rows if r["received_synthetic"]]
    without = [r for r in rows if not r["received_synthetic"]]
    def mean(xs): return sum(xs) / len(xs) if xs else 0.0
    summary = {
        "n_nontarget_gold_supported": len(rows),
        "n_with_synthetic_positives": len(with_syn),
        "n_without_synthetic_positives": len(without),
        "mean_delta_f1_with_synthetic": round(mean([r["delta_f1"] for r in with_syn]), 4),
        "mean_delta_f1_without_synthetic": round(mean([r["delta_f1"] for r in without]), 4),
        "n_improved_with_synthetic": sum(1 for r in with_syn if r["delta_f1"] > 0),
        "n_improved_without_synthetic": sum(1 for r in without if r["delta_f1"] > 0),
        "note": ("single seed, confounded comparison (data + supervision policy "
                 "changed together); this decomposition is descriptive, not causal"),
    }
    (OUT / "nontarget_gain_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
