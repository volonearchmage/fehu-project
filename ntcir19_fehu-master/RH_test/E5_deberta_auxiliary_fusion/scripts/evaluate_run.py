#!/usr/bin/env python3
"""E5 evaluation — official scorer plus the diagnostics the official
evaluator lacks (macro-P/R, target-18 / non-target-90 group metrics,
per-class table, delta vs the frozen E1 baseline).

Usage:
  python evaluate_run.py --run_dir <dir with pred_task1a/1b.json> \
      [--gold_1b dataset/gold_labels/dev/dev_human_values.json]

Writes <run_dir>/metrics.json and <run_dir>/per_class_metrics.csv.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from evaluation import (  # noqa: E402  (official scorer)
    parse_task1a, parse_task1b, evaluate, l1_dir_universe, l2_universe,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr,
)

E1_RUN = ROOT / "RH_test/E1_fewshot_repair/runs/20260722_152456"
TARGETS_JSON = (ROOT / "output/research_label_aware_low_frequency_augmentation_v2/"
                "20260713_163751/02_selected_targets_and_allocation.json")
ALL_108 = sorted(l1_dir_universe(), key=lambda s: (int(s.split(":")[1]), s))


def per_label_counts(gold, pred, labels):
    counts = {lab: {"tp": 0, "fp": 0, "fn": 0} for lab in labels}
    for iid in set(gold) | set(pred):
        g = gold.get(iid, set())
        p = pred.get(iid, set())
        for lab in g & p:
            counts[lab]["tp"] += 1
        for lab in p - g:
            counts[lab]["fp"] += 1
        for lab in g - p:
            counts[lab]["fn"] += 1
    return counts


def macro_prf_gold_supported(counts, gold):
    sup = defaultdict(int)
    for labs in gold.values():
        for lab in labs:
            sup[lab] += 1
    ps, rs, f1s = [], [], []
    for lab, c in counts.items():
        if sup.get(lab, 0) == 0:
            continue
        p = safe_div(c["tp"], c["tp"] + c["fp"])
        r = safe_div(c["tp"], c["tp"] + c["fn"])
        ps.append(p)
        rs.append(r)
        f1s.append(f1_from_pr(p, r))
    n = len(f1s)
    return {"macro_precision": sum(ps) / n, "macro_recall": sum(rs) / n,
            "macro_f1": sum(f1s) / n, "n_gold_supported_labels": n}


def group_micro(counts, labels):
    tp = sum(counts[l]["tp"] for l in labels)
    fp = sum(counts[l]["fp"] for l in labels)
    fn = sum(counts[l]["fn"] for l in labels)
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn,
            "micro_precision": p, "micro_recall": r,
            "micro_f1": f1_from_pr(p, r)}


def full_report(gold_1b, gold_1a, pred_1b, pred_1a, t18):
    r1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    r1a = evaluate(gold_1a, pred_1a, l2_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(gold_1b, pred_1b)
    counts = per_label_counts(gold_1b, pred_1b, ALL_108)
    nt90 = [l for l in ALL_108 if l not in t18]
    return {
        "task1b": dict(r1b, **macro_prf_gold_supported(counts, gold_1b)),
        "task1a": r1a,
        "drr": {"drr": drr, "reversals": rev, "denominator": den,
                "ambiguous_gold": amb},
        "target18": group_micro(counts, sorted(t18)),
        "nontarget90": group_micro(counts, nt90),
    }, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", type=Path, required=True)
    ap.add_argument("--gold_1b", type=Path,
                    default=ROOT / "dataset/gold_labels/dev/dev_human_values.json")
    args = ap.parse_args()

    p1b = args.run_dir / "pred_task1b.json"
    p1a = args.run_dir / "pred_task1a.json"
    for p in (p1b, p1a, args.gold_1b):
        if not p.is_file():
            sys.exit(f"ABORT: missing {p}")

    gold_1b = parse_task1b(str(args.gold_1b))
    gold_1a = parse_task1a(str(args.gold_1b))
    t18 = {f"{t['direction']}:{t['l1_value_id']}"
           for t in json.load(open(TARGETS_JSON))["targets"]}

    report, counts = full_report(gold_1b, gold_1a,
                                 parse_task1b(str(p1b)),
                                 parse_task1a(str(p1a)), t18)
    base_report, _ = full_report(gold_1b, gold_1a,
                                 parse_task1b(str(E1_RUN / "pred_task1b.json")),
                                 parse_task1a(str(E1_RUN / "pred_task1a.json")),
                                 t18)
    report["baseline_e1"] = {
        "run": str(E1_RUN),
        "task1b_micro_f1": base_report["task1b"]["micro_f1"],
        "task1b_macro_f1": base_report["task1b"]["macro_f1"],
        "task1a_micro_f1": base_report["task1a"]["micro_f1"],
        "drr": base_report["drr"]["drr"],
    }
    report["delta_vs_e1"] = {
        "task1b_micro_f1": report["task1b"]["micro_f1"]
        - base_report["task1b"]["micro_f1"],
        "task1b_macro_f1": report["task1b"]["macro_f1"]
        - base_report["task1b"]["macro_f1"],
        "task1a_micro_f1": report["task1a"]["micro_f1"]
        - base_report["task1a"]["micro_f1"],
        "drr": report["drr"]["drr"] - base_report["drr"]["drr"],
        "target18_micro_f1": report["target18"]["micro_f1"]
        - base_report["target18"]["micro_f1"],
        "nontarget90_micro_f1": report["nontarget90"]["micro_f1"]
        - base_report["nontarget90"]["micro_f1"],
    }

    (args.run_dir / "metrics.json").write_text(json.dumps(report, indent=2))

    sup = defaultdict(int)
    for labs in gold_1b.values():
        for lab in labs:
            sup[lab] += 1
    with open(args.run_dir / "per_class_metrics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "gold_support", "is_target18",
                    "tp", "fp", "fn", "precision", "recall", "f1"])
        for lab in ALL_108:
            c = counts[lab]
            p = safe_div(c["tp"], c["tp"] + c["fp"])
            r = safe_div(c["tp"], c["tp"] + c["fn"])
            w.writerow([lab, sup.get(lab, 0), lab in t18, c["tp"], c["fp"],
                        c["fn"], round(p, 4), round(r, 4),
                        round(f1_from_pr(p, r), 4)])

    t = report["task1b"]
    print(f"1b micro {t['micro_f1']:.4f} (P {t['micro_precision']:.4f} "
          f"R {t['micro_recall']:.4f})  macro {t['macro_f1']:.4f} "
          f"(P {t['macro_precision']:.4f} R {t['macro_recall']:.4f})")
    print(f"1a micro {report['task1a']['micro_f1']:.4f}  "
          f"DRR {report['drr']['drr']:.4f}")
    print(f"t18 micro {report['target18']['micro_f1']:.4f}  "
          f"nt90 micro {report['nontarget90']['micro_f1']:.4f}")
    d = report["delta_vs_e1"]
    print("delta vs E1: " + "  ".join(
        f"{k} {v:+.4f}" for k, v in d.items()))


if __name__ == "__main__":
    main()
