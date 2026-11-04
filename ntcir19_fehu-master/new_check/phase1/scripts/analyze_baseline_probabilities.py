#!/usr/bin/env python3
"""Phase 1 — threshold / per-target / separation analysis for the baseline
probabilities, mirroring the Phase-0 v2 analysis exactly, plus a
baseline-vs-v2 per-target separation comparison (AUC, gold-score quantiles,
oracle thresholds).

Inputs: Phase-1 export (baseline_actor_probabilities.jsonl), the v2
probabilities JSONL used in Phase 0, dev gold, the frozen 18-target list
from the Phase-0 manifest. Stdlib only; no GPU, no network.

Usage: python analyze_baseline_probabilities.py   (any python >= 3.8)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE0_SCRIPTS = HERE.parents[1] / "phase0" / "scripts"
sys.path.insert(0, str(PHASE0_SCRIPTS))

from phase0_lib import (  # noqa: E402
    ALL_108, Phase0InputError, class_index, fmt, gold_support,
    group_metrics, per_label_counts, rp, write_csv,
)
from evaluation import (  # noqa: E402
    parse_task1b, direction_reverse_rate_gold_excl, safe_div, f1_from_pr,
)

PHASE0_OUT = HERE.parents[1] / "phase0" / "outputs"
OUT = HERE.parent / "outputs"
CFG = json.loads((HERE.parents[1] / "phase0" / "configs"
                  / "phase0_config.json").read_text())

GLOBAL_THRESHOLDS = CFG["global_thresholds"]
OG = CFG["oracle_threshold_grid"]
GRID = [round(OG["start"] + i * OG["step"], 4)
        for i in range(int(round((OG["stop"] - OG["start"]) / OG["step"])) + 1)]


def load_probs(path: Path, gold_iids: set):
    rows = [json.loads(l) for l in open(path)]
    kept = [((str(r["guid"]), str(r["actor_id"])), r["probabilities_108"])
            for r in rows
            if (str(r["guid"]), str(r["actor_id"])) in gold_iids]
    if len(kept) != len(gold_iids):
        raise Phase0InputError(
            f"{path}: expected probabilities for all {len(gold_iids)} gold "
            f"instances, found {len(kept)}")
    return kept


def sweep(kept, gold, gsup, targets):
    rows = []
    for th in GLOBAL_THRESHOLDS:
        pred = {}
        for iid, probs in kept:
            labs = {f"{i % 2}:{i // 2}" for i, p in enumerate(probs) if p >= th}
            if labs:
                pred[iid] = labs
        counts = per_label_counts(gold, pred)
        g_t = group_metrics(counts, targets, gsup)
        g_all = group_metrics(counts, ALL_108, gsup)
        drr, rev, _, _ = direction_reverse_rate_gold_excl(gold, pred)
        rows.append({
            "threshold": th,
            "all108_micro_p": fmt(g_all["micro_precision"]),
            "all108_micro_r": fmt(g_all["micro_recall"]),
            "all108_micro_f1": fmt(g_all["micro_f1"]),
            "all108_macro_f1_gold": fmt(g_all["macro_f1_gold_supported"]),
            "target18_micro_p": fmt(g_t["micro_precision"]),
            "target18_micro_r": fmt(g_t["micro_recall"]),
            "target18_micro_f1": fmt(g_t["micro_f1"]),
            "target18_macro_p_gold": fmt(g_t["macro_precision_gold_supported"]),
            "target18_macro_r_gold": fmt(g_t["macro_recall_gold_supported"]),
            "target18_macro_f1_gold": fmt(g_t["macro_f1_gold_supported"]),
            "distinct_pred_classes": sum(
                1 for l in ALL_108 if counts[l]["tp"] + counts[l]["fp"] > 0),
            "drr": fmt(drr), "reversals": rev,
        })
    return rows


def per_target_stats(kept, gold, cls):
    """oracle threshold + separation statistics for one directed class."""
    ci = class_index(cls)
    pos_scores, neg_scores = [], []
    for iid, probs in kept:
        (pos_scores if cls in gold.get(iid, set()) else neg_scores).append(
            probs[ci])
    # rank-based AUC = P(score_pos > score_neg) (+0.5 ties)
    gt = eq = 0
    for p in pos_scores:
        for n in neg_scores:
            if p > n:
                gt += 1
            elif p == n:
                eq += 1
    auc = (gt + 0.5 * eq) / (len(pos_scores) * len(neg_scores))
    best = None
    for th in GRID:
        tp = sum(1 for p in pos_scores if p >= th)
        fp = sum(1 for n in neg_scores if n >= th)
        fn = len(pos_scores) - tp
        p = safe_div(tp, tp + fp)
        r = safe_div(tp, tp + fn)
        f1 = f1_from_pr(p, r)
        if best is None or f1 > best["oracle_f1"]:
            best = dict(oracle_threshold=th, oracle_precision=fmt(p),
                        oracle_recall=fmt(r), oracle_f1=fmt(f1),
                        tp=tp, fp=fp, fn=fn)
    pos_sorted = sorted(pos_scores, reverse=True)
    return {
        "n_gold": len(pos_scores),
        "auc": fmt(auc),
        "max_prob_gold": fmt(pos_sorted[0]),
        "median_prob_gold": fmt(pos_sorted[len(pos_sorted) // 2]),
        "recall_at_0.05": fmt(sum(1 for p in pos_scores if p >= 0.05)
                              / len(pos_scores)),
        **best,
    }


def main():
    gold = parse_task1b(str(rp(CFG["gold_dev_labels"])))
    gsup = gold_support(gold)
    targets = json.loads(
        (PHASE0_OUT / "run_manifest.json").read_text())["targets_18"]

    base_kept = load_probs(OUT / "baseline_actor_probabilities.jsonl",
                           set(gold))
    v2_kept = load_probs(rp(CFG["v2_probabilities_jsonl"]), set(gold))

    # sanity: baseline sweep at 0.30 must match Phase-0 frozen baseline metrics
    base_sweep = sweep(base_kept, gold, gsup, targets)
    row30 = next(r for r in base_sweep if r["threshold"] == 0.3)
    if abs(row30["all108_micro_f1"] - 0.3023) > 0.001:
        raise Phase0InputError(
            f"baseline sweep@0.30 micro-F1 {row30['all108_micro_f1']} does "
            f"not match the frozen 0.3023")
    write_csv(OUT / "threshold_sensitivity_baseline.csv", base_sweep,
              list(base_sweep[0].keys()))

    oracle_rows, comparison_rows = [], []
    for cls in targets:
        b = per_target_stats(base_kept, gold, cls)
        v = per_target_stats(v2_kept, gold, cls)
        oracle_rows.append({
            "class_key": cls,
            **{k: b[k] for k in ("oracle_threshold", "oracle_precision",
                                 "oracle_recall", "oracle_f1",
                                 "tp", "fp", "fn")},
            "flag": "DEV_TUNED_ORACLE_NOT_A_PERFORMANCE_CLAIM",
            "max_prob_on_gold_instances": b["max_prob_gold"],
            "median_prob_on_gold_instances": b["median_prob_gold"],
        })
        comparison_rows.append({
            "class_key": cls, "dev_gold_support": b["n_gold"],
            "baseline_auc": b["auc"], "v2_auc": v["auc"],
            "delta_auc": fmt(v["auc"] - b["auc"]),
            "baseline_median_prob_gold": b["median_prob_gold"],
            "v2_median_prob_gold": v["median_prob_gold"],
            "baseline_max_prob_gold": b["max_prob_gold"],
            "v2_max_prob_gold": v["max_prob_gold"],
            "baseline_recall_at_0.05": b["recall_at_0.05"],
            "v2_recall_at_0.05": v["recall_at_0.05"],
            "baseline_oracle_f1": b["oracle_f1"],
            "v2_oracle_f1": v["oracle_f1"],
            "baseline_oracle_threshold": b["oracle_threshold"],
            "v2_oracle_threshold": v["oracle_threshold"],
        })
    write_csv(OUT / "per_target_oracle_thresholds_baseline.csv", oracle_rows,
              list(oracle_rows[0].keys()))
    write_csv(OUT / "baseline_vs_v2_target_separation.csv", comparison_rows,
              list(comparison_rows[0].keys()))

    n = len(comparison_rows)
    summary = {
        "mean_baseline_auc": round(sum(r["baseline_auc"]
                                       for r in comparison_rows) / n, 4),
        "mean_v2_auc": round(sum(r["v2_auc"] for r in comparison_rows) / n, 4),
        "targets_with_auc_improved": sum(1 for r in comparison_rows
                                         if r["delta_auc"] > 0),
        "mean_baseline_oracle_f1": round(sum(r["baseline_oracle_f1"]
                                             for r in comparison_rows) / n, 4),
        "mean_v2_oracle_f1": round(sum(r["v2_oracle_f1"]
                                       for r in comparison_rows) / n, 4),
        "targets_with_oracle_f1_improved": sum(
            1 for r in comparison_rows
            if r["v2_oracle_f1"] > r["baseline_oracle_f1"]),
        "baseline_target18_recall_at_0.05": next(
            r["target18_micro_r"] for r in base_sweep
            if r["threshold"] == 0.05),
        "note": "single seed each; v2 differs from baseline in data AND "
                "supervision policy; separation deltas are descriptive",
    }
    (OUT / "separation_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
