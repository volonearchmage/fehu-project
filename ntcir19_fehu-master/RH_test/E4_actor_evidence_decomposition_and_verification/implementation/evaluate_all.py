#!/usr/bin/env python3
"""Uniform re-evaluation of every method on the FULL 177-article dev set.

Reuses the official evaluation.py parsers and metrics so all numbers are
directly comparable. Adds macro Precision/Recall (gold-supported, same label
set the official macro-F1 averages over), labels-per-actor, and predicted
class coverage, which the official CLI does not print.

Emits <out>/e4_dev_comparison.json and <out>/e4_dev_comparison.md.

Usage:
  python3 evaluate_all.py --out <dir>            # evaluate all known methods
Nothing here calls any API; it only reads existing prediction files + gold.
"""

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
E4_DIR = os.path.dirname(HERE)
BASE = os.path.dirname(os.path.dirname(E4_DIR))
sys.path.insert(0, BASE)

from evaluation import (  # noqa: E402
    parse_task1a, parse_task1b, evaluate, l2_universe, l1_dir_universe,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr)

DEV_GOLD = os.path.join(BASE, "dataset", "gold_labels", "dev",
                        "dev_human_values.json")

# (name, task1a_path, task1b_path). Liu label-aware ensemble (0.5657) is
# reported-only: its artifacts are absent locally (documented BLOCKED), so it
# cannot be recomputed and is injected as an external number in the report.
RUNS = "runs"
E1 = os.path.join(BASE, "RH_test", "E1_fewshot_repair", "runs",
                  "20260722_152456")
E2 = os.path.join(BASE, "RH_test", "E2_prompt_bias_control", "runs",
                  "20260723_000019")
E3 = os.path.join(BASE, "RH_test", "E3_subevent_decomposition", "runs",
                  "20260723_162944")
E3A = os.path.join(BASE, "RH_test", "E3a_task1_only_subevent", "runs",
                   "20260723_141123")
LIU = os.path.join(BASE, "output", "task1", "runs",
                   "dev_deepseek_deepseek-v4-flash_targeted_more_shot_"
                   "balanced_temp0p1_max8000")
E4RUN = os.path.join(E4_DIR, "runs", "dev_20260723_full")


def method_dirs():
    return [
        ("Liu single-prompt (frozen)", LIU),
        ("E1 few-shot repair", E1),
        ("E2 bias control", E2),
        ("E3 subevent union", E3),
        ("E3a task1-only subevent", E3A),
        ("E4a evidence scaffold", os.path.join(E4RUN, "e4a_pred")),
        ("E4b dual-view union", os.path.join(E4RUN, "e4b_pred")),
        ("E4c verifier + aggregation", os.path.join(E4RUN, "e4c_pred")),
    ]


def macro_pr_gold_supported(gold, pred, label_universe):
    """Macro Precision/Recall over gold-supported labels (matches the
    official macro-F1 label set: labels with >=1 gold positive)."""
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    instances = set(gold) | set(pred)
    for iid in instances:
        g = gold.get(iid, set())
        p = pred.get(iid, set())
        for lab in (g & p):
            tp[lab] += 1
        for lab in (p - g):
            fp[lab] += 1
        for lab in (g - p):
            fn[lab] += 1
    labels = [lab for lab in label_universe if (tp[lab] + fn[lab]) > 0]
    if not labels:
        return 0.0, 0.0, 0
    ps = [safe_div(tp[l], tp[l] + fp[l]) for l in labels]
    rs = [safe_div(tp[l], tp[l] + fn[l]) for l in labels]
    return sum(ps) / len(ps), sum(rs) / len(rs), len(labels)


def coverage(pred, universe):
    seen = set()
    for labs in pred.values():
        seen |= labs
    return len(seen & universe), len(universe)


def eval_pair(path_1a, path_1b, gold_1a, gold_1b):
    pred_1a = parse_task1a(path_1a)
    pred_1b = parse_task1b(path_1b)

    r1a = evaluate(gold_1a, pred_1a, l2_universe())
    r1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    ma_p, ma_r, _ = macro_pr_gold_supported(gold_1a, pred_1a, l2_universe())
    mb_p, mb_r, _ = macro_pr_gold_supported(gold_1b, pred_1b, l1_dir_universe())
    drr, rev, denom, amb = direction_reverse_rate_gold_excl(gold_1b, pred_1b)

    n_inst = len(gold_1b)  # gold actor-instances (same actors across methods)
    n_pred_1b = sum(len(v) for v in pred_1b.values())
    n_pred_1a = sum(len(v) for v in pred_1a.values())
    cov_1b_dir = coverage(pred_1b, l1_dir_universe())
    cov_1a = coverage(pred_1a, l2_universe())
    # undirected L1 coverage (out of 54)
    l1_seen = set()
    for labs in pred_1b.values():
        for lab in labs:
            l1_seen.add(lab.split(":", 1)[1])

    return {
        "task1a": {
            "micro_p": r1a["micro_precision"], "micro_r": r1a["micro_recall"],
            "micro_f1": r1a["micro_f1"], "macro_p": ma_p, "macro_r": ma_r,
            "macro_f1": r1a["macro_f1"],
            "labels_per_actor": safe_div(n_pred_1a, n_inst),
            "pred_labels": n_pred_1a,
            "class_coverage": cov_1a,
        },
        "task1b": {
            "micro_p": r1b["micro_precision"], "micro_r": r1b["micro_recall"],
            "micro_f1": r1b["micro_f1"], "macro_p": mb_p, "macro_r": mb_r,
            "macro_f1": r1b["macro_f1"],
            "drr": drr, "reversals": rev, "drr_denom": denom,
            "ambiguous_filtered": amb,
            "labels_per_actor": safe_div(n_pred_1b, n_inst),
            "pred_labels": n_pred_1b,
            "class_coverage_dir": cov_1b_dir,
            "class_coverage_l1_undirected": (len(l1_seen), 54),
        },
        "n_gold_instances": n_inst,
    }


def fmt_row(name, m):
    a, b = m["task1a"], m["task1b"]
    return (f"| {name} | {a['micro_p']:.4f} | {a['micro_r']:.4f} | "
            f"{a['micro_f1']:.4f} | {a['macro_p']:.4f} | {a['macro_r']:.4f} | "
            f"{a['macro_f1']:.4f} | {b['micro_p']:.4f} | {b['micro_r']:.4f} | "
            f"**{b['micro_f1']:.4f}** | {b['macro_p']:.4f} | "
            f"{b['macro_r']:.4f} | {b['macro_f1']:.4f} | "
            f"{b['drr']:.4f} ({b['reversals']}) | "
            f"{b['labels_per_actor']:.2f} | "
            f"{b['class_coverage_dir'][0]}/108 |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=E4RUN)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    gold_1a = parse_task1a(DEV_GOLD)
    gold_1b = parse_task1b(DEV_GOLD)

    results = {}
    missing = []
    for name, d in method_dirs():
        p1a = os.path.join(d, "pred_task1a.json")
        p1b = os.path.join(d, "pred_task1b.json")
        if not (os.path.exists(p1a) and os.path.exists(p1b)):
            missing.append((name, d))
            continue
        results[name] = eval_pair(p1a, p1b, gold_1a, gold_1b)

    # Liu label-aware ensemble: reported-only external number (BLOCKED locally)
    results["Liu label-aware ensemble (REPORTED)"] = {
        "reported_only": True,
        "task1b": {"micro_f1": 0.5657},
        "note": "artifacts absent locally; documented BLOCKED/unreproducible; "
                "external reference number only.",
    }

    with open(os.path.join(args.out, "e4_dev_comparison.json"), "w",
              encoding="utf-8") as f:
        json.dump({"results": results, "missing": missing,
                   "gold_instances": len(gold_1b)}, f, indent=2)

    header = (
        "| Method | 1a mP | 1a mR | 1a mF1 | 1a MP | 1a MR | 1a MF1 | "
        "1b mP | 1b mR | 1b mF1 | 1b MP | 1b MR | 1b MF1 | DRR (rev) | "
        "1b lbl/actor | 1b cov |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    lines = [header]
    order = ["Liu single-prompt (frozen)", "E1 few-shot repair",
             "E2 bias control", "E3 subevent union",
             "E3a task1-only subevent", "E4a evidence scaffold",
             "E4b dual-view union", "E4c verifier + aggregation"]
    for name in order:
        if name in results:
            lines.append(fmt_row(name, results[name]))
    lines.append("")
    lines.append("Liu label-aware ensemble: **1b micro F1 0.5657 (REPORTED, "
                 "not locally reproducible — artifacts absent/BLOCKED)**.")
    md = "\n".join(lines)
    with open(os.path.join(args.out, "e4_dev_comparison.md"), "w",
              encoding="utf-8") as f:
        f.write(md + "\n")
    print(md)
    if missing:
        print("\nMISSING (not yet produced):")
        for name, d in missing:
            print(f"  {name}: {d}")


if __name__ == "__main__":
    main()
