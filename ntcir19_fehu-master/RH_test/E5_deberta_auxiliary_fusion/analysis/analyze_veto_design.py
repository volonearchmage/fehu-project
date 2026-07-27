#!/usr/bin/env python3
"""E5 — second-stage analysis: design space for the conservative
negative-evidence veto and the empty-actor backfill.

Questions answered (all on dev, read-only):
  1. Veto criterion: exact-label prob vs value-level prob (max over the two
     directions). The value-level form is immune to v2's direction noise
     (v2 DRR 0.288).
  2. Seed unanimity: does requiring v2 AND all three Phase-3 Fp seeds to be
     below tau improve the FP:TP ratio of removals?
  3. Protections: how many removals hit target-18 classes / would empty an
     actor entirely?
  4. Projected micro/macro F1 for each veto variant (upper-bound estimate,
     since this IS the dev set — treated as design evidence, not a result).
  5. Empty-actor backfill: for gold actors with no E1 labels, precision of
     adding v2's top-k labels.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from evaluation import (  # noqa: E402
    parse_task1b, evaluate, l1_dir_universe,
    direction_reverse_rate_gold_excl, safe_div, split_dir_l1,
)
from analyze_complementarity import (  # noqa: E402
    load_probs, label_index, AnalysisError,
    GOLD_1B, E1_RUN, V2_PROBS, FP_RUNS, TARGETS_JSON, OUT,
)


def value_score(p, v: str) -> float:
    return max(p[int(v) * 2], p[int(v) * 2 + 1])


def main():
    gold = parse_task1b(str(GOLD_1B))
    e1 = parse_task1b(str(E1_RUN / "pred_task1b.json"))
    sources = {}
    probs = load_probs(V2_PROBS, sources)
    fp_probs = {s: load_probs(p) for s, p in FP_RUNS.items()}
    targets = json.load(open(TARGETS_JSON))["targets"]
    t18 = {f"{t['direction']}:{t['l1_value_id']}" for t in targets}

    report = {}

    # ---------------- veto sweep --------------------------------------
    # A removal candidate is an E1-predicted (iid, label) cell.
    variants = []
    for crit in ("exact", "value"):
        for unanimity in (False, True):
            for tau in (0.02, 0.05, 0.10, 0.15):
                removed = []
                for iid, plabs in e1.items():
                    pr = probs.get(iid)
                    if pr is None:
                        raise AnalysisError(f"no prob row for {iid}")
                    for lab in plabs:
                        d, v = split_dir_l1(lab)
                        s = (pr[label_index(lab)] if crit == "exact"
                             else value_score(pr, v))
                        if s >= tau:
                            continue
                        if unanimity:
                            ok = True
                            for sd in fp_probs.values():
                                q = sd.get(iid)
                                if q is None:
                                    ok = False  # cannot confirm -> no veto
                                    break
                                qs = (q[label_index(lab)] if crit == "exact"
                                      else value_score(q, v))
                                if qs >= tau:
                                    ok = False
                                    break
                            if not ok:
                                continue
                        removed.append((iid, lab))

                rm_tp = sum(1 for iid, lab in removed
                            if lab in gold.get(iid, set()))
                rm_fp = len(removed) - rm_tp
                rm_t18 = sum(1 for _, lab in removed if lab in t18)
                # how many vetoes would empty an actor
                per_iid = defaultdict(int)
                for iid, _ in removed:
                    per_iid[iid] += 1
                emptied = sum(1 for iid, n in per_iid.items()
                              if n == len(e1[iid]))

                # projected metrics after applying this veto (no protections)
                fused = {iid: set(labs) for iid, labs in e1.items()}
                for iid, lab in removed:
                    fused[iid].discard(lab)
                fused = {k: v for k, v in fused.items() if v}
                r = evaluate(gold, fused, l1_dir_universe())
                drr, *_ = direction_reverse_rate_gold_excl(gold, fused)
                variants.append({
                    "criterion": crit, "unanimity": unanimity, "tau": tau,
                    "removed": len(removed), "removed_tp": rm_tp,
                    "removed_fp": rm_fp,
                    "fp_per_tp": round(safe_div(rm_fp, rm_tp), 2) if rm_tp else None,
                    "removed_on_t18": rm_t18, "actors_emptied": emptied,
                    "proj_micro_f1": round(r["micro_f1"], 4),
                    "proj_macro_f1": round(r["macro_f1"], 4),
                    "proj_micro_p": round(r["micro_precision"], 4),
                    "proj_micro_r": round(r["micro_recall"], 4),
                    "proj_drr": round(drr, 4),
                })
    report["veto_sweep"] = variants

    # ---------------- empty-actor backfill ----------------------------
    # gold actors that E1 assigns no labels at all
    missing = [iid for iid in gold if iid not in e1]
    backfill = {"n_gold_actors_without_e1_labels": len(missing), "topk": []}
    for k in (1, 2, 3):
        added = tp = 0
        for iid in missing:
            pr = probs.get(iid)
            if pr is None:
                continue
            top = sorted(range(108), key=lambda i: -pr[i])[:k]
            for idx in top:
                lab = f"{idx % 2}:{idx // 2}"
                added += 1
                tp += lab in gold.get(iid, set())
        backfill["topk"].append({
            "k": k, "added": added, "tp": tp,
            "precision": round(safe_div(tp, added), 4)})
    # value-level top-k (direction chosen by argmax of the pair)
    for k in (1, 2, 3):
        added = tp = 0
        for iid in missing:
            pr = probs.get(iid)
            if pr is None:
                continue
            vals = sorted(range(54), key=lambda v: -value_score(pr, str(v)))[:k]
            for v in vals:
                d = "1" if pr[v * 2 + 1] >= pr[v * 2] else "0"
                lab = f"{d}:{v}"
                added += 1
                tp += lab in gold.get(iid, set())
        backfill["topk"].append({
            "k": f"value_{k}", "added": added, "tp": tp,
            "precision": round(safe_div(tp, added), 4)})
    report["backfill"] = backfill

    # ---------------- per-class effect of the leading veto -------------
    # leading candidate from the sweep: value criterion, unanimity, tau=0.05
    lead = {"criterion": "value", "unanimity": True, "tau": 0.05}
    per_class = defaultdict(lambda: {"removed_tp": 0, "removed_fp": 0})
    for iid, plabs in e1.items():
        pr = probs[iid]
        for lab in plabs:
            d, v = split_dir_l1(lab)
            if value_score(pr, v) >= lead["tau"]:
                continue
            if not all(iid in fp_probs[s]
                       and value_score(fp_probs[s][iid], v) < lead["tau"]
                       for s in fp_probs):
                continue
            key = "removed_tp" if lab in gold.get(iid, set()) else "removed_fp"
            per_class[lab][key] += 1
    report["lead_veto_per_class"] = {
        lab: dict(c, is_t18=lab in t18)
        for lab, c in sorted(per_class.items(),
                             key=lambda kv: -(kv[1]["removed_tp"]
                                              + kv[1]["removed_fp"]))}

    with open(OUT / "veto_design.json", "w") as f:
        json.dump(report, f, indent=2)

    # console summary
    print(f"gold actors without E1 labels: {len(missing)}")
    for row in backfill["topk"]:
        print(f"  backfill top-{row['k']}: +{row['added']} "
              f"tp {row['tp']} prec {row['precision']}")
    print("\nveto sweep (E1 base micro 0.5480 / macro 0.3719):")
    for v in variants:
        print(f"  {v['criterion']:5s} unan={str(v['unanimity']):5s} "
              f"tau={v['tau']:.2f}: -{v['removed']:4d} "
              f"(TP {v['removed_tp']:3d} FP {v['removed_fp']:3d} "
              f"ratio {v['fp_per_tp']}) t18hit {v['removed_on_t18']:2d} "
              f"emptied {v['actors_emptied']} -> micro {v['proj_micro_f1']:.4f} "
              f"macro {v['proj_macro_f1']:.4f} P {v['proj_micro_p']:.4f} "
              f"R {v['proj_micro_r']:.4f}")


if __name__ == "__main__":
    main()
