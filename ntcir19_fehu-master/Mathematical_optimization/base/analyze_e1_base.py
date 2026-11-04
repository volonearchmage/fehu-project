#!/usr/bin/env python3
"""E1 analysis — compare the E1 run against the frozen Liu baseline with the
unchanged official evaluator plus the Phase-0 group/target machinery.

Usage: python analyze_e1.py <run_ts>
Reads:  RH_test/E1_fewshot_repair/runs/<run_ts>/pred_task1{a,b}.json
        output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000/  (frozen baseline)
Writes: outputs into the same run dir (comparison CSV/JSON). Stdlib only.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
sys.path.insert(0, str(BASE / "new_check" / "phase0" / "scripts"))

from phase0_lib import (  # noqa: E402
    ALL_108, fmt, gold_support, group_metrics, per_label_counts,
    reversals_by_gold_class, write_csv,
)
from evaluation import (  # noqa: E402
    parse_task1a, parse_task1b, evaluate, l2_universe, l1_dir_universe,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr,
)

BASELINE_DIR = (BASE / "output" / "task1" / "runs" /
                "dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000")
GOLD = BASE / "dataset" / "gold_labels" / "dev" / "dev_human_values.json"
TARGETS = json.loads((BASE / "new_check" / "phase0" / "outputs"
                      / "run_manifest.json").read_text())["targets_18"]
EXPECTED_BASELINE_1B_MICRO = 0.5347


def macro_prf(gold, pred, universe):
    """gold-supported macro P/R/F1 for an arbitrary label universe."""
    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    for iid in set(gold) | set(pred):
        g = gold.get(iid, set()); p = pred.get(iid, set())
        for lab in g & p: tp[lab] += 1
        for lab in p - g: fp[lab] += 1
        for lab in g - p: fn[lab] += 1
    labels = [l for l in universe if tp[l] + fn[l] > 0]
    ps, rs, f1s = [], [], []
    for l in labels:
        p = safe_div(tp[l], tp[l] + fp[l]); r = safe_div(tp[l], tp[l] + fn[l])
        ps.append(p); rs.append(r); f1s.append(f1_from_pr(p, r))
    n = len(labels)
    return sum(ps) / n, sum(rs) / n, sum(f1s) / n


def system_row(name, dir_1a, dir_1b, gold_1a, gold_1b, gsup):
    p1a = parse_task1a(str(dir_1a))
    p1b = parse_task1b(str(dir_1b))
    r1a = evaluate(gold_1a, p1a, l2_universe())
    r1b = evaluate(gold_1b, p1b, l1_dir_universe())
    ma_p, ma_r, ma_f = macro_prf(gold_1a, p1a, l2_universe())
    mb_p, mb_r, mb_f = macro_prf(gold_1b, p1b, l1_dir_universe())
    drr, rev, denom, _ = direction_reverse_rate_gold_excl(gold_1b, p1b)
    counts = per_label_counts(gold_1b, p1b)
    nont = [l for l in ALL_108 if l not in set(TARGETS)]
    g_t = group_metrics(counts, TARGETS, gsup)
    g_n = group_metrics(counts, nont, gsup)
    rev_cls, _ = reversals_by_gold_class(gold_1b, p1b)
    n_pred = sum(len(v) for v in p1b.values())
    n_actors_with_pred = len(p1b)
    tp = sum(counts[l]["tp"] for l in ALL_108)
    fpn = sum(counts[l]["fp"] for l in ALL_108)
    fnn = sum(counts[l]["fn"] for l in ALL_108)
    return {
        "system": name,
        "1a_micro_p": fmt(r1a["micro_precision"]), "1a_micro_r": fmt(r1a["micro_recall"]),
        "1a_micro_f1": fmt(r1a["micro_f1"]),
        "1a_macro_p": fmt(ma_p), "1a_macro_r": fmt(ma_r), "1a_macro_f1": fmt(ma_f),
        "1a_macro_f1_official": fmt(r1a["macro_f1"]),
        "1b_micro_p": fmt(r1b["micro_precision"]), "1b_micro_r": fmt(r1b["micro_recall"]),
        "1b_micro_f1": fmt(r1b["micro_f1"]),
        "1b_macro_p": fmt(mb_p), "1b_macro_r": fmt(mb_r), "1b_macro_f1": fmt(mb_f),
        "drr": fmt(drr), "reversals": rev, "drr_denom": denom,
        "tp": tp, "fp": fpn, "fn": fnn,
        "pred_1b_labels": n_pred,
        "labels_per_actor": fmt(n_pred / max(n_actors_with_pred, 1)),
        "distinct_1b_classes": sum(1 for l in ALL_108
                                   if counts[l]["tp"] + counts[l]["fp"] > 0),
        "t18_micro_p": fmt(g_t["micro_precision"]), "t18_micro_r": fmt(g_t["micro_recall"]),
        "t18_micro_f1": fmt(g_t["micro_f1"]),
        "t18_macro_p": fmt(g_t["macro_precision_gold_supported"]),
        "t18_macro_r": fmt(g_t["macro_recall_gold_supported"]),
        "t18_macro_f1": fmt(g_t["macro_f1_gold_supported"]),
        "t18_tp": g_t["sum_tp"], "t18_fp": g_t["sum_fp"], "t18_fn": g_t["sum_fn"],
        "t18_reversals": sum(rev_cls.get(c, 0) for c in TARGETS),
        "nt90_micro_f1": fmt(g_n["micro_f1"]),
        "nt90_macro_p": fmt(g_n["macro_precision_gold_supported"]),
        "nt90_macro_r": fmt(g_n["macro_recall_gold_supported"]),
        "nt90_macro_f1": fmt(g_n["macro_f1_gold_supported"]),
    }, counts


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: analyze_e1.py <run_ts>")
    run = HERE.parent / "runs" / sys.argv[1]
    for f in ("pred_task1a.json", "pred_task1b.json"):
        if not (run / f).is_file():
            sys.exit(f"ABORT: missing {run / f}")

    gold_1a = parse_task1a(str(GOLD))
    gold_1b = parse_task1b(str(GOLD))
    gsup = gold_support(gold_1b)

    base_row, base_counts = system_row(
        "liu_baseline_frozen", BASELINE_DIR / "pred_task1a.json",
        BASELINE_DIR / "pred_task1b.json", gold_1a, gold_1b, gsup)
    if abs(base_row["1b_micro_f1"] - EXPECTED_BASELINE_1B_MICRO) > 0.001:
        sys.exit(f"ABORT: frozen baseline re-eval {base_row['1b_micro_f1']} "
                 f"!= documented {EXPECTED_BASELINE_1B_MICRO}")
    e1_row, e1_counts = system_row(
        "E1_fewshot_repair", run / "pred_task1a.json",
        run / "pred_task1b.json", gold_1a, gold_1b, gsup)

    delta = {"system": "delta_E1_minus_baseline"}
    for k in base_row:
        if k == "system":
            continue
        if isinstance(base_row[k], (int, float)):
            delta[k] = round(e1_row[k] - base_row[k], 4)
    rows = [base_row, e1_row, delta]
    write_csv(run / "comparison_vs_baseline.csv", rows, list(base_row.keys()))

    per_target = []
    for cls in TARGETS:
        b, e = base_counts[cls], e1_counts[cls]
        per_target.append({
            "class_key": cls, "support": gsup.get(cls, 0),
            "base_tp": b["tp"], "base_fp": b["fp"],
            "e1_tp": e["tp"], "e1_fp": e["fp"],
            "delta_tp": e["tp"] - b["tp"],
        })
    write_csv(run / "per_target_18_comparison.csv", per_target,
              list(per_target[0].keys()))

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
