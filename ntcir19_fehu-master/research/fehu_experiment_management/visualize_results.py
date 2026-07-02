#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_experiment_management/visualize_results.py

Build a presentation-ready dashboard from an existing label-diagnosis output.
Reads CSVs only; recomputes nothing; calls no API.

Run from project root:
    python research/fehu_experiment_management/visualize_results.py \
        --diagnosis_dir output/research_label_diagnosis/20260613_145847

Output: output/research_visualization_dashboard/YYYYMMDD_HHMMSS/
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================
# IO
# ============================================================

def read_csv(p: Path) -> List[Dict]:
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def as_int(s, default=0):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


# ============================================================
# FIGURES
# ============================================================

def fig_task1b_micro_f1(overall: List[Dict], out: Path) -> None:
    overall_sorted = sorted(overall, key=lambda r: -as_float(r["task1b_micro_f1"]))
    names = [r["method"] for r in overall_sorted]
    vals  = [as_float(r["task1b_micro_f1"]) for r in overall_sorted]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(names)), vals, alpha=0.85)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.005, f"{v:.4f}",
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Task-1b micro-F1")
    ax.set_title("Task-1b Micro-F1 by Method")
    ax.set_ylim(0, max(vals) * 1.15 if vals else 1.0)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close()


def fig_pr_scatter(overall: List[Dict], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    for r in overall:
        x = as_float(r["task1b_recall"])
        y = as_float(r["task1b_precision"])
        ax.scatter(x, y, s=110, alpha=0.85, zorder=5)
        ax.annotate(r["method"], (x, y),
                    textcoords="offset points", xytext=(6, 4), fontsize=8)
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.5, alpha=0.3)
    ax.set_xlim(0, 1.0); ax.set_ylim(0, 1.0)
    ax.set_xlabel("Task-1b Recall (micro)")
    ax.set_ylabel("Task-1b Precision (micro)")
    ax.set_title("Task-1b Precision vs Recall per Method")
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()


def fig_drr(overall: List[Dict], out: Path) -> None:
    overall_sorted = sorted(overall, key=lambda r: as_float(r["drr"]))
    names = [r["method"] for r in overall_sorted]
    drrs  = [as_float(r["drr"]) for r in overall_sorted]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(names)), drrs, alpha=0.85)
    for b, v in zip(bars, drrs):
        ax.text(b.get_x() + b.get_width()/2, v + 0.003,
                f"{v:.4f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Direction Reverse Rate (DRR)")
    ax.set_title("DRR by Method  (lower is better)")
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()


def fig_rare_recall(freq_group: List[Dict], out: Path) -> None:
    """Rare-tertile micro_recall_dir per method (bar)."""
    rare = [r for r in freq_group
            if r["group_type"] == "tertile_group" and r["group_value"] == "rare"]
    rare_sorted = sorted(rare, key=lambda r: -as_float(r["micro_recall_dir"]))
    names = [r["method"] for r in rare_sorted]
    vals  = [as_float(r["micro_recall_dir"]) for r in rare_sorted]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(names)), vals, alpha=0.85)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.005,
                f"{v:.4f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Rare-label micro-recall (direction-aware)")
    ax.set_title("Rare-label Recall by Method")
    ymax = max(vals + [0.05])
    ax.set_ylim(0, ymax * 1.3)
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()


def _grouped_bars(freq_group: List[Dict], metric_key: str, title: str, ylabel: str, out: Path) -> None:
    tertile_order = ["frequent", "medium", "rare"]
    # method → {group → value}
    method_vals: Dict[str, Dict[str, float]] = defaultdict(dict)
    methods_present: List[str] = []
    for r in freq_group:
        if r["group_type"] != "tertile_group":
            continue
        m = r["method"]
        g = r["group_value"]
        method_vals[m][g] = as_float(r[metric_key])
        if m not in methods_present:
            methods_present.append(m)

    n_methods = len(methods_present)
    bar_w = 0.8 / max(n_methods, 1)
    x = range(len(tertile_order))

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, m in enumerate(methods_present):
        heights = [method_vals[m].get(g, 0.0) for g in tertile_order]
        offsets = [(j + (i - n_methods / 2 + 0.5) * bar_w) for j in x]
        ax.bar(offsets, heights, bar_w * 0.92, label=m, alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(tertile_order)
    ax.set_xlabel("Frequency tertile (frequent → rare)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=7, loc="upper right")
    ax.set_ylim(0, 1.0)
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()


def fig_freq_recall(freq_group: List[Dict], out: Path) -> None:
    _grouped_bars(freq_group, "micro_recall_dir",
                  "Frequency-group Recall (direction-aware, Task-1b)",
                  "Micro-recall", out)


def fig_freq_precision(freq_group: List[Dict], out: Path) -> None:
    _grouped_bars(freq_group, "micro_precision_dir",
                  "Frequency-group Precision (direction-aware, Task-1b)",
                  "Micro-precision", out)


def fig_freq_f1(freq_group: List[Dict], out: Path) -> None:
    _grouped_bars(freq_group, "micro_f1_dir",
                  "Frequency-group F1 (direction-aware, Task-1b)",
                  "Micro-F1", out)


def fig_augmentation_need(rare_rows: List[Dict],
                          fp_rows: List[Dict],
                          de_rows: List[Dict],
                          out: Path) -> None:
    """Per L1 label, total 'augmentation need' across methods."""
    need: Dict[str, Dict[str, int]] = defaultdict(lambda: {"rare_lr": 0, "fp": 0, "dir_err": 0})
    label_name: Dict[str, str] = {}

    for r in rare_rows:
        lid = r["l1_value_id"]; label_name[lid] = r["l1_value_name"]
        need[lid]["rare_lr"] += 1
    for r in fp_rows:
        lid = r["l1_value_id"]; label_name[lid] = r["l1_value_name"]
        need[lid]["fp"] += 1
    for r in de_rows:
        lid = r["l1_value_id"]; label_name[lid] = r["l1_value_name"]
        need[lid]["dir_err"] += 1

    items = [(lid, sum(v.values()), v) for lid, v in need.items()]
    items.sort(key=lambda x: -x[1])
    top = items[:25]
    labels = [label_name.get(lid, lid) for lid, _, _ in top]
    rare_lr = [v["rare_lr"] for _, _, v in top]
    fp     = [v["fp"]      for _, _, v in top]
    direrr = [v["dir_err"] for _, _, v in top]

    fig, ax = plt.subplots(figsize=(11, 7))
    y = list(range(len(top)))
    ax.barh(y, rare_lr, label="rare + low recall", alpha=0.85)
    left2 = rare_lr
    ax.barh(y, fp, left=left2, label="high false positive", alpha=0.85)
    left3 = [a + b for a, b in zip(left2, fp)]
    ax.barh(y, direrr, left=left3, label="high direction error", alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Number of methods where this label is flagged")
    ax.set_title("Augmentation Need by Label (top 25 across methods)")
    ax.legend(fontsize=8, loc="lower right")
    plt.tight_layout(); plt.savefig(out, dpi=150); plt.close()


# ============================================================
# Summary writers
# ============================================================

def write_method_ranking(overall: List[Dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(overall, key=lambda r: -as_float(r["task1b_micro_f1"]))
    cols = ["rank", "method", "task1b_micro_f1", "task1b_macro_f1",
            "task1b_precision", "task1b_recall", "drr", "reverse_count"]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(sorted_rows, 1):
            w.writerow({
                "rank": i, "method": r["method"],
                "task1b_micro_f1":  r["task1b_micro_f1"],
                "task1b_macro_f1":  r["task1b_macro_f1"],
                "task1b_precision": r["task1b_precision"],
                "task1b_recall":    r["task1b_recall"],
                "drr":              r["drr"],
                "reverse_count":    r["reverse_count"],
            })


def write_clean_overall(overall: List[Dict], out: Path) -> None:
    cols = ["method", "task1a_micro_f1", "task1a_macro_f1",
            "task1b_micro_f1", "task1b_macro_f1",
            "task1b_precision", "task1b_recall",
            "drr", "reverse_count", "total_pred_1b"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in overall:
            w.writerow({c: r.get(c, "") for c in cols})


def write_dashboard_summary(overall: List[Dict],
                            freq_group: List[Dict],
                            rare_rows: List[Dict],
                            fp_rows: List[Dict],
                            de_rows: List[Dict],
                            ts: str,
                            diag_dir: Path,
                            out: Path) -> None:
    best = max(overall, key=lambda r: as_float(r["task1b_micro_f1"])) if overall else {}
    best_drr = min(overall, key=lambda r: as_float(r["drr"])) if overall else {}
    # Best rare-recall method from frequency_group_summary
    rare_best = sorted(
        [r for r in freq_group
         if r["group_type"] == "tertile_group" and r["group_value"] == "rare"],
        key=lambda r: -as_float(r["micro_recall_dir"])
    )
    rare_best_method = rare_best[0]["method"] if rare_best else "—"
    rare_best_val = as_float(rare_best[0]["micro_recall_dir"]) if rare_best else 0.0

    n_rare = len(rare_rows)
    n_fp   = len(fp_rows)
    n_de   = len(de_rows)

    lines = [
        "# FEHU Visualization Dashboard",
        "",
        f"**Generated:** {ts}  ",
        f"**Source diagnosis:** `{diag_dir}`  ",
        "",
        "## Headlines",
        "",
        f"- **Best Task-1b µF1:** `{best.get('method','—')}` = {as_float(best.get('task1b_micro_f1', 0)):.4f}",
        f"- **Lowest DRR:** `{best_drr.get('method','—')}` = {as_float(best_drr.get('drr', 1)):.4f}",
        f"- **Best rare-label avg recall_dir:** `{rare_best_method}` = {rare_best_val:.4f}",
        f"- **Diagnostic flags:** rare+low-recall rows = {n_rare}, high-FP rows = {n_fp}, "
        f"high-direction-error rows = {n_de}",
        "",
        "## Figures",
        "",
        "- `task1b_micro_f1_by_method.png` — overall ranking",
        "- `task1b_precision_recall_scatter.png` — P/R trade-off",
        "- `drr_by_method.png` — direction-reversal rate",
        "- `rare_recall_by_method.png` — rare-tertile micro-recall",
        "- `frequency_group_recall_task1b.png` — recall split by tertile",
        "- `frequency_group_precision_task1b.png` — precision split by tertile",
        "- `frequent_medium_rare_f1_by_method.png` — F1 split by tertile",
        "- `augmentation_need_by_label.png` — per-label flag counts",
        "",
        "## Files",
        "",
        "- `overall_metrics_clean.csv` — trimmed copy of `overall_metrics.csv`",
        "- `method_ranking_task1b.csv` — methods ranked by Task-1b micro-F1",
        "",
        "## Constraints honored",
        "",
        "This dashboard only reads existing CSVs. No predictions were recomputed; ",
        "no APIs were called; no existing files were modified.",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# Main
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Build a visualization dashboard from a diagnosis output.")
    ap.add_argument("--diagnosis_dir", type=str, required=True,
                    help="Path to an existing output/research_label_diagnosis/YYYYMMDD_HHMMSS/ folder.")
    args = ap.parse_args()

    diag_dir = Path(args.diagnosis_dir)
    if not diag_dir.is_absolute():
        diag_dir = PROJECT_ROOT / diag_dir
    if not diag_dir.exists():
        print(f"ERROR: diagnosis_dir does not exist: {diag_dir}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "output" / "research_visualization_dashboard" / ts
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Visualization Dashboard]")
    print(f"Source: {diag_dir}")
    print(f"Out:    {out_dir}")
    print()

    overall    = read_csv(diag_dir / "overall_metrics.csv")
    freq_group = read_csv(diag_dir / "frequency_group_summary.csv")
    rare_rows  = read_csv(diag_dir / "rare_low_recall_labels.csv")
    fp_rows    = read_csv(diag_dir / "high_false_positive_labels.csv")
    de_rows    = read_csv(diag_dir / "high_direction_error_labels.csv")

    if not overall:
        print(f"WARNING: overall_metrics.csv is empty or missing in {diag_dir}.")

    # Figures
    if overall:
        fig_task1b_micro_f1(overall, fig_dir / "task1b_micro_f1_by_method.png");        print("  + task1b_micro_f1_by_method.png")
        fig_pr_scatter(overall,        fig_dir / "task1b_precision_recall_scatter.png"); print("  + task1b_precision_recall_scatter.png")
        fig_drr(overall,               fig_dir / "drr_by_method.png");                   print("  + drr_by_method.png")
    if freq_group:
        fig_rare_recall(freq_group,    fig_dir / "rare_recall_by_method.png");           print("  + rare_recall_by_method.png")
        fig_freq_recall(freq_group,    fig_dir / "frequency_group_recall_task1b.png");   print("  + frequency_group_recall_task1b.png")
        fig_freq_precision(freq_group, fig_dir / "frequency_group_precision_task1b.png");print("  + frequency_group_precision_task1b.png")
        fig_freq_f1(freq_group,        fig_dir / "frequent_medium_rare_f1_by_method.png"); print("  + frequent_medium_rare_f1_by_method.png")
    if rare_rows or fp_rows or de_rows:
        fig_augmentation_need(rare_rows, fp_rows, de_rows, fig_dir / "augmentation_need_by_label.png")
        print("  + augmentation_need_by_label.png")

    # CSV outputs
    write_clean_overall(overall,         out_dir / "overall_metrics_clean.csv")
    write_method_ranking(overall,        out_dir / "method_ranking_task1b.csv")

    # Dashboard summary
    write_dashboard_summary(overall, freq_group, rare_rows, fp_rows, de_rows,
                            ts, diag_dir, out_dir / "dashboard_summary.md")

    print()
    print(f"Dashboard written to {out_dir}")


if __name__ == "__main__":
    main()
