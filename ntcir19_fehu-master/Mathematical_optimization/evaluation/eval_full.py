#!/usr/bin/env python3
"""
DS Comprehensive Evaluation Script
===================================
Evaluates predictions against gold labels with FULL metrics:
  Task-1a: micro P/R/F1, macro P/R/F1 (gold-supported)
  Task-1b: micro P/R/F1, macro P/R/F1 (gold-supported), DRR
  Target-18 group: micro/macro P/R/F1, TP/FP/FN
  Non-target-90 group: micro/macro P/R/F1
  Per-class details: support, TP, FP, FN, P, R, F1

Accepts predictions in the standard FEHU submission format.

Usage:
    python evaluation/eval_full.py \
        --pred_1a path/to/pred_task1a.json \
        --pred_1b path/to/pred_task1b.json \
        --output path/to/metrics.json
"""

from __future__ import annotations

import json
import argparse
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
sys.path.insert(0, str(BASE))

from evaluation import (
    parse_task1a, parse_task1b, evaluate,
    l2_universe, l1_dir_universe,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr,
)

DEV_LABELS = BASE / "dataset" / "gold_labels" / "dev" / "dev_human_values.json"

# Frozen 18 target labels from Phase 0
TARGETS_18 = [
    "0:31", "0:48", "0:53", "1:31", "0:16", "1:10",
    "0:19", "0:20", "1:49", "0:13", "0:37", "0:29",
    "1:4",  "0:2",  "0:33", "0:32", "0:40", "0:28",
]

ALL_108 = [f"{d}:{v}" for v in range(54) for d in ("0", "1")]


def fmt(x: float, precision: int = 4) -> float:
    return round(x, precision)


def compute_all_metrics(pred_1a_path: str, pred_1b_path: str) -> dict:
    """Compute all metrics for a prediction pair."""
    gold_1a = parse_task1a(str(DEV_LABELS))
    gold_1b = parse_task1b(str(DEV_LABELS))
    pred_1a = parse_task1a(pred_1a_path)
    pred_1b = parse_task1b(pred_1b_path)

    # ── Per-class counts ──────────────────────────────────────────────
    counts = {}
    instances = set(gold_1b) | set(pred_1b)
    for iid in instances:
        g = gold_1b.get(iid, set())
        p = pred_1b.get(iid, set())
        for lab in g & p:
            counts.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1
        for lab in p - g:
            counts.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
        for lab in g - p:
            counts.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
    for lab in ALL_108:
        if lab not in counts:
            counts[lab] = {"tp": 0, "fp": 0, "fn": 0}

    # ── Task-1a official metrics ──────────────────────────────────────
    r1a = evaluate(gold_1a, pred_1a, l2_universe())

    # ── Task-1b official metrics ──────────────────────────────────────
    r1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    drr, rev, denom, ambig = direction_reverse_rate_gold_excl(gold_1b, pred_1b)

    # ── Macro P/R/F1 (gold-supported, Task-1b) ──────────────────────
    gsup = set()
    for iid, labels in gold_1b.items():
        gsup.update(labels)
    mb_p, mb_r, mb_f1 = macro_prf_from_counts(counts, gsup)

    # ── Group metrics ─────────────────────────────────────────────────
    nontarget = [l for l in ALL_108 if l not in set(TARGETS_18)]
    g_t18 = group_prf(counts, TARGETS_18, gsup)
    g_nt90 = group_prf(counts, nontarget, gsup)

    # ── Distinct classes ──────────────────────────────────────────────
    distinct = sum(1 for l in ALL_108
                   if counts[l]["tp"] + counts[l]["fp"] > 0)

    # ── Per-class details ─────────────────────────────────────────────
    per_class = {}
    for lab in sorted(ALL_108):
        c = counts[lab]
        support = c["tp"] + c["fn"]
        p = safe_div(c["tp"], c["tp"] + c["fp"])
        r = safe_div(c["tp"], support)
        f1 = f1_from_pr(p, r)
        per_class[lab] = {
            "support": support,
            "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
            "precision": fmt(p), "recall": fmt(r), "f1": fmt(f1),
        }

    n_pred_1b = sum(len(v) for v in pred_1b.values())
    n_actors = len(pred_1b)
    tp_all = sum(counts[l]["tp"] for l in ALL_108)
    fp_all = sum(counts[l]["fp"] for l in ALL_108)
    fn_all = sum(counts[l]["fn"] for l in ALL_108)

    return {
        "task1a": {
            "micro_precision":  fmt(r1a["micro_precision"]),
            "micro_recall":     fmt(r1a["micro_recall"]),
            "micro_f1":         fmt(r1a["micro_f1"]),
            "macro_f1_official": fmt(r1a["macro_f1"]),
        },
        "task1b": {
            "micro_precision":  fmt(r1b["micro_precision"]),
            "micro_recall":     fmt(r1b["micro_recall"]),
            "micro_f1":         fmt(r1b["micro_f1"]),
            "macro_precision":  fmt(mb_p),
            "macro_recall":     fmt(mb_r),
            "macro_f1":         fmt(mb_f1),
            "macro_f1_official": fmt(r1b["macro_f1"]),
            "drr":              fmt(drr),
            "drr_reversals":    rev,
            "drr_denom":        denom,
            "drr_ambiguous":    ambig,
            "tp":               tp_all,
            "fp":               fp_all,
            "fn":               fn_all,
            "pred_labels":      n_pred_1b,
            "labels_per_actor": fmt(n_pred_1b / max(n_actors, 1)),
            "distinct_classes": distinct,
        },
        "target_18": {
            "micro_precision":  fmt(g_t18["micro_precision"]),
            "micro_recall":     fmt(g_t18["micro_recall"]),
            "micro_f1":         fmt(g_t18["micro_f1"]),
            "macro_precision":  fmt(g_t18["macro_precision"]),
            "macro_recall":     fmt(g_t18["macro_recall"]),
            "macro_f1":         fmt(g_t18["macro_f1"]),
            "tp":               g_t18["tp"],
            "fp":               g_t18["fp"],
            "fn":               g_t18["fn"],
        },
        "nontarget_90": {
            "micro_precision":  fmt(g_nt90["micro_precision"]),
            "micro_recall":     fmt(g_nt90["micro_recall"]),
            "micro_f1":         fmt(g_nt90["micro_f1"]),
            "macro_precision":  fmt(g_nt90["macro_precision"]),
            "macro_recall":     fmt(g_nt90["macro_recall"]),
            "macro_f1":         fmt(g_nt90["macro_f1"]),
        },
        "per_class": per_class,
    }


def macro_prf_from_counts(counts, gsup):
    """Compute gold-supported macro P/R/F1 from per-class counts."""
    ps, rs, f1s = [], [], []
    for lab in gsup:
        c = counts.get(lab, {"tp": 0, "fp": 0, "fn": 0})
        p = safe_div(c["tp"], c["tp"] + c["fp"])
        r = safe_div(c["tp"], c["tp"] + c["fn"])
        ps.append(p)
        rs.append(r)
        f1s.append(f1_from_pr(p, r))
    n = len(gsup)
    return sum(ps) / n, sum(rs) / n, sum(f1s) / n


def group_prf(counts, label_group, gsup):
    """Compute micro and gold-supported macro P/R/F1 for a group of labels."""
    tp = sum(counts[l]["tp"] for l in label_group)
    fp = sum(counts[l]["fp"] for l in label_group)
    fn = sum(counts[l]["fn"] for l in label_group)
    micro_p = safe_div(tp, tp + fp)
    micro_r = safe_div(tp, tp + fn)
    micro_f1 = f1_from_pr(micro_p, micro_r)

    gsup_group = gsup & set(label_group)
    macro_p, macro_r, macro_f1 = macro_prf_from_counts(
        {l: counts[l] for l in label_group}, gsup_group)

    return {
        "micro_precision": micro_p, "micro_recall": micro_r,
        "micro_f1": micro_f1,
        "macro_precision": macro_p, "macro_recall": macro_r,
        "macro_f1": macro_f1,
        "tp": tp, "fp": fp, "fn": fn,
    }


def main():
    parser = argparse.ArgumentParser(description="DS Full Evaluation")
    parser.add_argument("--pred_1a", type=str, required=True)
    parser.add_argument("--pred_1b", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--label", type=str, default=None,
                        help="Human-readable label for this run")
    args = parser.parse_args()

    print(f"Evaluating: {args.label or 'unnamed'}")
    metrics = compute_all_metrics(args.pred_1a, args.pred_1b)

    if args.label:
        metrics["label"] = args.label

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    # Print summary
    print(f"\n{'='*50}")
    print(f"Task-1a: micro-F1 {metrics['task1a']['micro_f1']:.4f}  "
          f"macro-F1 {metrics['task1a']['macro_f1_official']:.4f}")
    print(f"Task-1b: micro-F1 {metrics['task1b']['micro_f1']:.4f}  "
          f"macro-F1 {metrics['task1b']['macro_f1']:.4f}  "
          f"DRR {metrics['task1b']['drr']:.4f}")
    print(f"  micro-P {metrics['task1b']['micro_precision']:.4f}  "
          f"micro-R {metrics['task1b']['micro_recall']:.4f}")
    print(f"  macro-P {metrics['task1b']['macro_precision']:.4f}  "
          f"macro-R {metrics['task1b']['macro_recall']:.4f}")
    print(f"  TP={metrics['task1b']['tp']} FP={metrics['task1b']['fp']} "
          f"FN={metrics['task1b']['fn']}  "
          f"distinct={metrics['task1b']['distinct_classes']}")
    print(f"Target-18: micro-F1 {metrics['target_18']['micro_f1']:.4f}  "
          f"macro-F1 {metrics['target_18']['macro_f1']:.4f}  "
          f"TP={metrics['target_18']['tp']}")
    print(f"Full metrics → {out_path}")


if __name__ == "__main__":
    main()
