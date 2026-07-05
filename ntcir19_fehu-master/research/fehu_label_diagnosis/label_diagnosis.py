#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_label_diagnosis/label_diagnosis.py

Research-grade diagnostic analysis for FEHU Task-1 predictions.
Analyzes recall/precision per label class (frequent → rare) as requested
by the professor before any augmentation work.

Run from project root:
    python research/fehu_label_diagnosis/label_diagnosis.py

Output: output/research_label_diagnosis/YYYYMMDD_HHMMSS/
"""

from __future__ import annotations

import csv
import json
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── matplotlib (optional but expected) ──────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    warnings.warn("matplotlib not found — figures will be skipped.")

# ── ensure project root is on sys.path so evaluation.py can be imported ─────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import (  # noqa: E402
    parse_task1a,
    parse_task1b,
    evaluate,
    l2_universe,
    l1_dir_universe,
    direction_reverse_rate_gold_excl,
    safe_div,
)

# ============================================================
# PATHS
# ============================================================

GOLD_TRAIN = PROJECT_ROOT / "dataset/gold_labels/train/train_human_values.json"
GOLD_DEV   = PROJECT_ROOT / "dataset/gold_labels/dev/dev_human_values.json"
DEV_EVENTS = PROJECT_ROOT / "dataset/dev/dev_event_base.json"

L1_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level1_values.json"
L2_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_PATH  = PROJECT_ROOT / "dataset/hv_categories/level_1_to_level_2.json"

# direction semantics per direction_mapping.json: "1"=aligned, "0"=contradictory
DIR_NAME = {"1": "aligned", "0": "contradictory"}

# All result folders to try, in display order
CANDIDATE_METHODS = [
    {"name": "Prompt_OAI",         "dir": "output/task1_prompt"},
    {"name": "Prompt_DS_Flash",    "dir": "output/task1_prompt_deepseek_v4_flash"},
    {"name": "DeBERTa_only",       "dir": "output/task1_deberta"},
    {"name": "Hybrid_v1",          "dir": "output/task1_hybrid"},
    {"name": "Hybrid_v2_DS_Pro",   "dir": "output/task1_hybrid_v2_deepseek_deepseek_v4_pro"},
    {"name": "Hybrid_v2_DS_Flash", "dir": "output/task1_hybrid_v2_deepseek_deepseek_v4_flash"},
    # Optional old methods
    {"name": "Hybrid_v2_OAI_old",  "dir": "output/task1_hybrid_v2"},
    {"name": "Hybrid_v2_OAI_mini", "dir": "output/task1_hybrid_v2_openai_gpt_4o_mini"},
]

# ============================================================
# UTILITY
# ============================================================

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_csv(rows: List[Dict], path: Path, fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def f1_score(p: float, r: float) -> float:
    return 0.0 if (p + r) == 0.0 else 2.0 * p * r / (p + r)


# ============================================================
# LOAD TAXONOMY
# ============================================================

def load_level_mappings() -> Tuple[Dict, Dict, Dict]:
    """
    Returns:
        l1_id_to_name : {str_id -> name}  (54 entries)
        l2_id_to_name : {str_id -> name}  (20 entries)
        l1_id_to_l2_id: {str_l1_id -> str_l2_id}
    """
    l1_raw = load_json(L1_VALUES_PATH)   # {"name": "id", ...}
    l2_raw = load_json(L2_VALUES_PATH)   # {"name": "id", ...}
    l1_to_l2_raw = load_json(L1_TO_L2_PATH)  # {"level_1_to_level_2": {"l1name": "l2name"}}

    l1_name_to_id: Dict[str, str] = {k: str(v) for k, v in l1_raw.items()}
    l2_name_to_id: Dict[str, str] = {k: str(v) for k, v in l2_raw.items()}
    l1_id_to_name: Dict[str, str] = {str(v): k for k, v in l1_raw.items()}
    l2_id_to_name: Dict[str, str] = {str(v): k for k, v in l2_raw.items()}

    l1_to_l2_map: Dict[str, str] = l1_to_l2_raw["level_1_to_level_2"]
    l1_id_to_l2_id: Dict[str, str] = {}
    for l1_name, l2_name in l1_to_l2_map.items():
        l1_id = l1_name_to_id.get(l1_name)
        l2_id = l2_name_to_id.get(l2_name)
        if l1_id is not None and l2_id is not None:
            l1_id_to_l2_id[l1_id] = l2_id

    return l1_id_to_name, l2_id_to_name, l1_id_to_l2_id


# ============================================================
# LOAD GOLD / PREDICTION ITEMS AS FLAT TUPLES
# ============================================================

def load_gold_items(gold_path: Path) -> List[Tuple[str, str, str, str]]:
    """Load article-level gold labels as (guid, actor, l1_value_id, direction)."""
    data = load_json(gold_path)
    items: List[Tuple[str, str, str, str]] = []
    for article in data:
        guid = str(article["guid"])
        for hv in article.get("article_human_values", []):
            items.append((
                guid,
                str(hv["actor"]),
                str(hv["l1_value"]),
                str(hv["direction"]),
            ))
    return items


def load_prediction_items_1b(pred_path: Path) -> List[Tuple[str, str, str, str]]:
    """Load pred_task1b.json as (guid, actor, l1_value_id, direction)."""
    data = load_json(pred_path)
    items: List[Tuple[str, str, str, str]] = []
    for article in data:
        guid = str(article["guid"])
        for hv in article.get("article_human_values", []):
            try:
                items.append((
                    guid,
                    str(hv["actor"]),
                    str(hv["l1_value"]),
                    str(hv["direction"]),
                ))
            except KeyError:
                pass  # skip malformed entries
    return items


# ============================================================
# PART 1: METHOD INVENTORY
# ============================================================

def build_method_inventory(
    skipped_out: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """
    Discovers valid full-dev methods and builds an inventory CSV.

    Returns:
        valid_methods : list of method info dicts (for analysis)
        inventory_rows: all rows for method_inventory.csv
    """
    inventory: List[Dict] = []
    valid_methods: List[Dict] = []

    for spec in CANDIDATE_METHODS:
        name = spec["name"]
        d = PROJECT_ROOT / spec["dir"]

        row: Dict = {
            "method_name": name,
            "output_dir": str(d),
            "pred_task1a_exists": False,
            "pred_task1b_exists": False,
            "run_config_exists": False,
            "detected_provider": "unknown",
            "detected_model": "unknown",
            "detected_version": "unknown",
            "detected_mode": "unknown",
            "detected_limit": "unknown",
            "is_full_dev_likely": False,
            "notes": "",
        }

        if not d.exists():
            row["notes"] = "Directory does not exist — skipped"
            inventory.append(row)
            skipped_out.append({"method": name, "reason": "directory does not exist"})
            continue

        p1a = d / "pred_task1a.json"
        p1b = d / "pred_task1b.json"
        row["pred_task1a_exists"] = p1a.exists()
        row["pred_task1b_exists"] = p1b.exists()

        rc_path = d / "run_config.json"
        rc: Dict = {}
        if rc_path.exists():
            row["run_config_exists"] = True
            rc = load_json(rc_path)
            row["detected_provider"] = str(rc.get("provider", rc.get("llm_provider", "unknown")))
            row["detected_model"] = str(rc.get("model", rc.get("llm_model", "unknown")))
            row["detected_version"] = str(rc.get("version", name))
            row["detected_mode"] = str(rc.get("mode", "unknown"))
            row["detected_limit"] = str(rc.get("limit", "null"))
        else:
            row["detected_version"] = name

        # Determine if full-dev (limit=None or limit >= 177)
        limit_str = row["detected_limit"]
        is_limited = limit_str not in ("null", "None", "unknown", "")
        if is_limited:
            try:
                lv = int(limit_str)
                if lv < 177:
                    row["is_full_dev_likely"] = False
                    row["notes"] = f"limit={lv} — not full-dev, excluded from main comparison"
                    inventory.append(row)
                    skipped_out.append({"method": name, "reason": f"limit={lv}, not full-dev"})
                    continue
            except (ValueError, TypeError):
                pass

        if not (p1a.exists() and p1b.exists()):
            row["notes"] = (
                f"Incomplete prediction files: "
                f"task1a={p1a.exists()}, task1b={p1b.exists()} — skipped"
            )
            inventory.append(row)
            skipped_out.append({"method": name, "reason": "missing prediction files"})
            continue

        row["is_full_dev_likely"] = True
        row["notes"] = "Valid full-dev method"
        inventory.append(row)
        valid_methods.append({
            "name": name,
            "dir": d,
            "pred_task1a": p1a,
            "pred_task1b": p1b,
            "run_config": rc,
        })

    return valid_methods, inventory


# ============================================================
# PART 2: OVERALL OFFICIAL METRICS
# ============================================================

def compute_overall_metrics(
    valid_methods: List[Dict],
    gold_dev_path: Path,
) -> List[Dict]:
    """Compute official Task-1a and Task-1b metrics for every valid method."""
    gold_1a = parse_task1a(str(gold_dev_path))
    gold_1b = parse_task1b(str(gold_dev_path))
    universe_1a = l2_universe()
    universe_1b = l1_dir_universe()
    # Number of unique articles in dev gold
    n_articles = len({k[0] for k in gold_1b.keys()})

    results: List[Dict] = []
    for method in valid_methods:
        name = method["name"]
        pred_1a = parse_task1a(str(method["pred_task1a"]))
        pred_1b = parse_task1b(str(method["pred_task1b"]))

        res_1a = evaluate(gold_1a, pred_1a, universe_1a)
        res_1b = evaluate(gold_1b, pred_1b, universe_1b)
        drr, rev_cnt, drr_denom, amb_cnt = direction_reverse_rate_gold_excl(gold_1b, pred_1b)

        total_pred_1a = sum(len(v) for v in pred_1a.values())
        total_pred_1b = sum(len(v) for v in pred_1b.values())

        results.append({
            "method": name,
            "task1a_micro_f1":   round(res_1a["micro_f1"], 4),
            "task1a_macro_f1":   round(res_1a["macro_f1"], 4),
            "task1a_precision":  round(res_1a["micro_precision"], 4),
            "task1a_recall":     round(res_1a["micro_recall"], 4),
            "task1b_micro_f1":   round(res_1b["micro_f1"], 4),
            "task1b_macro_f1":   round(res_1b["macro_f1"], 4),
            "task1b_precision":  round(res_1b["micro_precision"], 4),
            "task1b_recall":     round(res_1b["micro_recall"], 4),
            "drr":               round(drr, 4),
            "reverse_count":     rev_cnt,
            "drr_denominator":   drr_denom,
            "ambiguous_count":   amb_cnt,
            "total_pred_1a":     total_pred_1a,
            "total_pred_1b":     total_pred_1b,
            "avg_pred_1a_per_article": round(total_pred_1a / max(n_articles, 1), 2),
            "avg_pred_1b_per_article": round(total_pred_1b / max(n_articles, 1), 2),
        })
    return results


def format_overall_comparison_table(rows: List[Dict]) -> str:
    header = (
        f"{'Method':<30} "
        f"{'1a µF1':>7} {'1a MaF1':>8} {'1a P':>6} {'1a R':>6}  "
        f"{'1b µF1':>7} {'1b MaF1':>8} {'1b P':>6} {'1b R':>6}  "
        f"{'DRR':>6} {'RevCnt':>7} {'Denom':>6}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"{r['method']:<30} "
            f"{r['task1a_micro_f1']:>7.4f} {r['task1a_macro_f1']:>8.4f} "
            f"{r['task1a_precision']:>6.4f} {r['task1a_recall']:>6.4f}  "
            f"{r['task1b_micro_f1']:>7.4f} {r['task1b_macro_f1']:>8.4f} "
            f"{r['task1b_precision']:>6.4f} {r['task1b_recall']:>6.4f}  "
            f"{r['drr']:>6.4f} {r['reverse_count']:>7} {r['drr_denominator']:>6}"
        )
    return "\n".join(lines)


# ============================================================
# PART 3: LABEL FREQUENCY ANALYSIS
# ============================================================

def compute_label_frequency(
    train_items: List[Tuple],
    dev_items: List[Tuple],
    l1_id_to_name: Dict,
    l2_id_to_name: Dict,
    l1_id_to_l2_id: Dict,
) -> List[Dict]:
    """
    Compute per-L1-label train/dev gold counts and assign frequency groups.
    Returns rows sorted by train_gold_count_l1 descending.
    """
    train_total: Counter = Counter()
    train_aligned: Counter = Counter()
    train_contra: Counter = Counter()
    for _, _, l1, d in train_items:
        train_total[l1] += 1
        (train_aligned if d == "1" else train_contra)[l1] += 1

    dev_total: Counter = Counter()
    dev_aligned: Counter = Counter()
    dev_contra: Counter = Counter()
    for _, _, l1, d in dev_items:
        dev_total[l1] += 1
        (dev_aligned if d == "1" else dev_contra)[l1] += 1

    rows: List[Dict] = []
    for l1_id in [str(i) for i in range(54)]:
        l2_id = l1_id_to_l2_id.get(l1_id, "?")
        rows.append({
            "l1_value_id":                 l1_id,
            "l1_value_name":               l1_id_to_name.get(l1_id, f"L1_{l1_id}"),
            "l2_value_id":                 l2_id,
            "l2_value_name":               l2_id_to_name.get(l2_id, "?"),
            "train_gold_count_l1":         train_total.get(l1_id, 0),
            "train_gold_count_aligned":    train_aligned.get(l1_id, 0),
            "train_gold_count_contradictory": train_contra.get(l1_id, 0),
            "train_total_direction_count": (
                train_aligned.get(l1_id, 0) + train_contra.get(l1_id, 0)
            ),
            "dev_gold_count_l1":           dev_total.get(l1_id, 0),
            "dev_gold_count_aligned":      dev_aligned.get(l1_id, 0),
            "dev_gold_count_contradictory": dev_contra.get(l1_id, 0),
        })

    rows.sort(key=lambda x: -x["train_gold_count_l1"])

    for rank, row in enumerate(rows, start=1):
        row["rank_by_train_frequency"] = rank

    # Tertile groups: top-18 / middle-18 / bottom-18
    for i, row in enumerate(rows):
        if i < 18:
            row["tertile_group"] = "frequent"
        elif i < 36:
            row["tertile_group"] = "medium"
        else:
            row["tertile_group"] = "rare"

    # Threshold groups
    def _thresh(count: int) -> str:
        if count == 0:      return "zero_train"
        if count <= 5:      return "very_rare"
        if count <= 15:     return "rare"
        if count <= 40:     return "medium"
        return "frequent"

    for row in rows:
        row["threshold_group"] = _thresh(row["train_gold_count_l1"])

    return rows


# ============================================================
# PART 4: PER-LABEL METRICS (TASK-1B STYLE)
# ============================================================

def _build_per_label_index(
    items: List[Tuple[str, str, str, str]],
) -> Tuple[Dict, Dict, Dict]:
    """
    Build three lookup structures from a flat list of (guid, actor, l1, direction):

    ga_dirs[l1][(guid,actor)] = set of directions
    val_set[l1]               = set of (guid, actor)
    dir_set[l1]               = set of (guid, actor, direction)
    """
    ga_dirs: Dict[str, Dict] = defaultdict(lambda: defaultdict(set))
    val_set: Dict[str, Set]  = defaultdict(set)
    dir_set: Dict[str, Set]  = defaultdict(set)
    for guid, actor, l1, d in items:
        ga_dirs[l1][(guid, actor)].add(d)
        val_set[l1].add((guid, actor))
        dir_set[l1].add((guid, actor, d))
    return ga_dirs, val_set, dir_set


def compute_per_label_metrics(
    valid_methods: List[Dict],
    dev_gold_items: List[Tuple],
    label_freq_rows: List[Dict],
) -> List[Dict]:
    """
    For each method and each L1 label: value-level and direction-aware
    precision/recall/F1, plus direction reversal count.
    """
    freq_info: Dict[str, Dict] = {r["l1_value_id"]: r for r in label_freq_rows}
    all_l1_ids = [str(i) for i in range(54)]

    gold_ga_dirs, gold_val, gold_dir = _build_per_label_index(dev_gold_items)

    result_rows: List[Dict] = []

    for method in valid_methods:
        mname = method["name"]
        pred_items = load_prediction_items_1b(method["pred_task1b"])
        pred_ga_dirs, pred_val, pred_dir = _build_per_label_index(pred_items)

        for l1_id in all_l1_ids:
            g_val = gold_val.get(l1_id, set())
            p_val = pred_val.get(l1_id, set())
            g_dir = gold_dir.get(l1_id, set())
            p_dir = pred_dir.get(l1_id, set())

            # Value-level (ignoring direction)
            tp_v = len(g_val & p_val)
            fp_v = len(p_val - g_val)
            fn_v = len(g_val - p_val)
            pr_v = safe_div(tp_v, tp_v + fp_v)
            rc_v = safe_div(tp_v, tp_v + fn_v)
            f1_v = f1_score(pr_v, rc_v)

            # Direction-aware
            tp_d = len(g_dir & p_dir)
            fp_d = len(p_dir - g_dir)
            fn_d = len(g_dir - p_dir)
            pr_d = safe_div(tp_d, tp_d + fp_d)
            rc_d = safe_div(tp_d, tp_d + fn_d)
            f1_d = f1_score(pr_d, rc_d)

            # Direction reversal: for each unambiguous gold (guid,actor) instance,
            # count cases where prediction uses the opposite direction
            rev_count = 0
            for (ga_key), g_dirs in gold_ga_dirs.get(l1_id, {}).items():
                if len(g_dirs) == 1:   # unambiguous
                    g_d = next(iter(g_dirs))
                    opp = "0" if g_d == "1" else "1"
                    if opp in pred_ga_dirs.get(l1_id, {}).get(ga_key, set()):
                        rev_count += 1

            fi = freq_info.get(l1_id, {})
            dev_gold_count = fi.get("dev_gold_count_l1", 0)

            result_rows.append({
                "method":                      mname,
                "l1_value_id":                 l1_id,
                "l1_value_name":               fi.get("l1_value_name", f"L1_{l1_id}"),
                "l2_value_id":                 fi.get("l2_value_id", "?"),
                "l2_value_name":               fi.get("l2_value_name", "?"),
                "rank_by_train_frequency":     fi.get("rank_by_train_frequency", 99),
                "tertile_group":               fi.get("tertile_group", "unknown"),
                "threshold_group":             fi.get("threshold_group", "unknown"),
                "train_gold_count_l1":         fi.get("train_gold_count_l1", 0),
                "dev_gold_count_l1":           dev_gold_count,
                "pred_count_value":            len(p_val),
                "TP_value":                    tp_v,
                "FP_value":                    fp_v,
                "FN_value":                    fn_v,
                "precision_value":             round(pr_v, 4),
                "recall_value":                round(rc_v, 4),
                "f1_value":                    round(f1_v, 4),
                "pred_count_dir":              len(p_dir),
                "TP_dir":                      tp_d,
                "FP_dir":                      fp_d,
                "FN_dir":                      fn_d,
                "precision_dir":               round(pr_d, 4),
                "recall_dir":                  round(rc_d, 4),
                "f1_dir":                      round(f1_d, 4),
                "direction_reverse_count":     rev_count,
                "direction_reverse_rate_label": round(
                    safe_div(rev_count, max(dev_gold_count, 1)), 4
                ),
            })

    result_rows.sort(key=lambda x: (x["method"], x["rank_by_train_frequency"]))
    return result_rows


# ============================================================
# PART 5: 108-CLASS METRICS
# ============================================================

def compute_108_class_metrics(
    valid_methods: List[Dict],
    dev_gold_items: List[Tuple],
    train_gold_items: List[Tuple],
    l1_id_to_name: Dict,
    l2_id_to_name: Dict,
    l1_id_to_l2_id: Dict,
) -> List[Dict]:
    """
    Per-class metrics for all 108 classes: (l1_value × direction).
    """
    train_class: Counter = Counter()
    for _, _, l1, d in train_gold_items:
        train_class[(l1, d)] += 1

    dev_class: Counter = Counter()
    gold_cls_set: Dict[Tuple, Set] = defaultdict(set)
    for guid, actor, l1, d in dev_gold_items:
        dev_class[(l1, d)] += 1
        gold_cls_set[(l1, d)].add((guid, actor))

    result_rows: List[Dict] = []
    for method in valid_methods:
        mname = method["name"]
        pred_items = load_prediction_items_1b(method["pred_task1b"])

        pred_cls_count: Counter = Counter()
        pred_cls_set: Dict[Tuple, Set] = defaultdict(set)
        for guid, actor, l1, d in pred_items:
            pred_cls_count[(l1, d)] += 1
            pred_cls_set[(l1, d)].add((guid, actor))

        for l1_id in [str(i) for i in range(54)]:
            for direction in ("0", "1"):
                cls = (l1_id, direction)
                g_set = gold_cls_set.get(cls, set())
                p_set = pred_cls_set.get(cls, set())
                tp = len(g_set & p_set)
                fp = len(p_set - g_set)
                fn = len(g_set - p_set)
                pr = safe_div(tp, tp + fp)
                rc = safe_div(tp, tp + fn)
                f1 = f1_score(pr, rc)
                l2_id = l1_id_to_l2_id.get(l1_id, "?")
                result_rows.append({
                    "method":                mname,
                    "l1_value_id":           l1_id,
                    "l1_value_name":         l1_id_to_name.get(l1_id, f"L1_{l1_id}"),
                    "direction":             direction,
                    "direction_name":        DIR_NAME.get(direction, direction),
                    "l2_value_id":           l2_id,
                    "l2_value_name":         l2_id_to_name.get(l2_id, "?"),
                    "train_gold_count_class": train_class.get(cls, 0),
                    "dev_gold_count_class":  dev_class.get(cls, 0),
                    "pred_count_class":      pred_cls_count.get(cls, 0),
                    "TP":  tp,
                    "FP":  fp,
                    "FN":  fn,
                    "precision": round(pr, 4),
                    "recall":    round(rc, 4),
                    "f1":        round(f1, 4),
                })

    result_rows.sort(key=lambda x: (x["method"], -x["train_gold_count_class"]))
    return result_rows


# ============================================================
# PART 6: FREQUENCY-GROUP SUMMARY
# ============================================================

def compute_frequency_group_summary(
    per_label_rows: List[Dict],
    valid_method_names: List[str],
) -> List[Dict]:
    """Summarize metrics by frequency group (both tertile and threshold)."""
    result_rows: List[Dict] = []

    for mname in valid_method_names:
        method_rows = [r for r in per_label_rows if r["method"] == mname]

        for group_key in ("tertile_group", "threshold_group"):
            group_vals = sorted(set(r[group_key] for r in method_rows))
            for gval in group_vals:
                subset = [r for r in method_rows if r[group_key] == gval]
                if not subset:
                    continue

                # Labels with any dev gold instances
                nonempty = [r for r in subset if r["dev_gold_count_l1"] > 0]

                # Micro value-level
                tp_v  = sum(r["TP_value"] for r in subset)
                fp_v  = sum(r["FP_value"] for r in subset)
                fn_v  = sum(r["FN_value"] for r in subset)
                mpr_v = safe_div(tp_v, tp_v + fp_v)
                mrc_v = safe_div(tp_v, tp_v + fn_v)
                mf1_v = f1_score(mpr_v, mrc_v)

                # Macro value-level (over labels with dev gold > 0)
                n_ne = max(len(nonempty), 1)
                macro_pr_v  = sum(r["precision_value"] for r in nonempty) / n_ne
                macro_rc_v  = sum(r["recall_value"]    for r in nonempty) / n_ne
                macro_f1_v  = sum(r["f1_value"]        for r in nonempty) / n_ne

                # Micro direction-aware
                tp_d  = sum(r["TP_dir"] for r in subset)
                fp_d  = sum(r["FP_dir"] for r in subset)
                fn_d  = sum(r["FN_dir"] for r in subset)
                mpr_d = safe_div(tp_d, tp_d + fp_d)
                mrc_d = safe_div(tp_d, tp_d + fn_d)
                mf1_d = f1_score(mpr_d, mrc_d)

                # Macro direction-aware
                macro_pr_d  = sum(r["precision_dir"] for r in nonempty) / n_ne
                macro_rc_d  = sum(r["recall_dir"]    for r in nonempty) / n_ne
                macro_f1_d  = sum(r["f1_dir"]        for r in nonempty) / n_ne

                total_rev = sum(r["direction_reverse_count"]       for r in subset)
                avg_drr   = sum(r["direction_reverse_rate_label"]  for r in subset) / max(len(subset), 1)

                result_rows.append({
                    "method":                    mname,
                    "group_type":                group_key,
                    "group_value":               gval,
                    "number_of_labels":          len(subset),
                    "total_train_gold_count":    sum(r["train_gold_count_l1"] for r in subset),
                    "total_dev_gold_count":      sum(r["dev_gold_count_l1"]   for r in subset),
                    "total_predictions_value":   sum(r["pred_count_value"]    for r in subset),
                    "total_predictions_dir":     sum(r["pred_count_dir"]      for r in subset),
                    "micro_precision_value":     round(mpr_v,    4),
                    "micro_recall_value":        round(mrc_v,    4),
                    "micro_f1_value":            round(mf1_v,    4),
                    "macro_precision_value":     round(macro_pr_v, 4),
                    "macro_recall_value":        round(macro_rc_v, 4),
                    "macro_f1_value":            round(macro_f1_v, 4),
                    "micro_precision_dir":       round(mpr_d,    4),
                    "micro_recall_dir":          round(mrc_d,    4),
                    "micro_f1_dir":              round(mf1_d,    4),
                    "macro_precision_dir":       round(macro_pr_d, 4),
                    "macro_recall_dir":          round(macro_rc_d, 4),
                    "macro_f1_dir":              round(macro_f1_d, 4),
                    "total_direction_reverse_count": total_rev,
                    "avg_direction_reverse_rate":    round(avg_drr, 4),
                })

    return result_rows


# ============================================================
# PART 7: DIAGNOSTIC TABLES
# ============================================================

def _suggest_action(row: Dict) -> str:
    if row["direction_reverse_rate_label"] > 0.3:
        return "direction_contrastive_augmentation"
    if row["train_gold_count_l1"] == 0:
        return "inspect_label_definition"
    if row["recall_value"] < 0.10 and row["dev_gold_count_l1"] > 0:
        return "rare_positive_augmentation"
    if row["FP_value"] > row["TP_value"] + 3:
        return "hard_negative_needed"
    return "paraphrase_existing_samples"


def create_diagnostic_tables(
    per_label_rows: List[Dict],
    valid_method_names: List[str],
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """
    Returns:
        rare_low_recall_rows
        high_fp_rows
        high_dir_error_rows
        method_gap_rows
    """
    # 1. Rare + low recall
    rare_low_recall: List[Dict] = []
    for r in per_label_rows:
        is_rare = (
            r["threshold_group"] in ("very_rare", "rare", "zero_train")
            or r["tertile_group"] == "rare"
        )
        low_recall = (r["recall_dir"] < 0.30 or r["recall_value"] < 0.30)
        has_dev = r["dev_gold_count_l1"] > 0
        if is_rare and low_recall and has_dev:
            rare_low_recall.append({
                "method":                r["method"],
                "l1_value_id":           r["l1_value_id"],
                "l1_value_name":         r["l1_value_name"],
                "train_gold_count_l1":   r["train_gold_count_l1"],
                "dev_gold_count_l1":     r["dev_gold_count_l1"],
                "precision_value":       r["precision_value"],
                "recall_value":          r["recall_value"],
                "f1_value":              r["f1_value"],
                "precision_dir":         r["precision_dir"],
                "recall_dir":            r["recall_dir"],
                "f1_dir":                r["f1_dir"],
                "suggested_future_action": _suggest_action(r),
            })

    # 2. High false positives
    high_fp: List[Dict] = []
    for r in per_label_rows:
        if r["FP_value"] >= 5 and r["precision_value"] < 0.30 and r["pred_count_value"] >= 5:
            high_fp.append({
                "method":              r["method"],
                "l1_value_id":         r["l1_value_id"],
                "l1_value_name":       r["l1_value_name"],
                "train_gold_count_l1": r["train_gold_count_l1"],
                "dev_gold_count_l1":   r["dev_gold_count_l1"],
                "pred_count_value":    r["pred_count_value"],
                "TP_value":            r["TP_value"],
                "FP_value":            r["FP_value"],
                "FN_value":            r["FN_value"],
                "precision_value":     r["precision_value"],
                "recall_value":        r["recall_value"],
                "f1_value":            r["f1_value"],
            })

    # 3. High direction errors
    high_dir_error: List[Dict] = []
    for r in per_label_rows:
        if r["direction_reverse_count"] > 0:
            high_dir_error.append({
                "method":                       r["method"],
                "l1_value_id":                  r["l1_value_id"],
                "l1_value_name":                r["l1_value_name"],
                "train_gold_count_l1":          r["train_gold_count_l1"],
                "dev_gold_count_l1":            r["dev_gold_count_l1"],
                "direction_reverse_count":      r["direction_reverse_count"],
                "direction_reverse_rate_label": r["direction_reverse_rate_label"],
                "precision_dir":                r["precision_dir"],
                "recall_dir":                   r["recall_dir"],
                "f1_dir":                       r["f1_dir"],
            })
    high_dir_error.sort(key=lambda x: (-x["direction_reverse_rate_label"], x["method"]))

    # 4. Method gap analysis (per L1 label, across methods)
    lookup: Dict[Tuple, Dict] = {
        (r["method"], r["l1_value_id"]): r for r in per_label_rows
    }
    KEY = {
        "oai":   "Prompt_OAI",
        "flash": "Prompt_DS_Flash",
        "deb":   "DeBERTa_only",
        "pro":   "Hybrid_v2_DS_Pro",
    }

    # Only include keys whose method is actually present
    present_key = {k: v for k, v in KEY.items() if v in valid_method_names}

    method_gap: List[Dict] = []
    # use label_freq order from per_label_rows (first method, sorted by rank)
    seen_l1: List[str] = []
    seen_set: Set[str] = set()
    for r in per_label_rows:
        if r["l1_value_id"] not in seen_set:
            seen_l1.append(r["l1_value_id"])
            seen_set.add(r["l1_value_id"])

    for l1_id in seen_l1:
        # pick any row to get label metadata
        ref = next(
            (r for r in per_label_rows if r["l1_value_id"] == l1_id), None
        )
        if ref is None:
            continue

        gap_row: Dict = {
            "l1_value_id":         l1_id,
            "l1_value_name":       ref["l1_value_name"],
            "rank_by_train_freq":  ref["rank_by_train_frequency"],
            "train_gold_count_l1": ref["train_gold_count_l1"],
            "dev_gold_count_l1":   ref["dev_gold_count_l1"],
        }

        for k, mname in present_key.items():
            r = lookup.get((mname, l1_id))
            gap_row[f"recall_dir_{k}"]   = r["recall_dir"]    if r else None
            gap_row[f"precision_dir_{k}"] = r["precision_dir"] if r else None

        # Gain: Flash over OAI
        if "oai" in present_key and "flash" in present_key:
            r_oai   = lookup.get((present_key["oai"],   l1_id))
            r_flash = lookup.get((present_key["flash"], l1_id))
            if r_oai and r_flash:
                gap_row["recall_gain_flash_over_oai"] = round(
                    r_flash["recall_dir"] - r_oai["recall_dir"], 4)

        # Gain: Hybrid v2 Pro over DeBERTa
        if "deb" in present_key and "pro" in present_key:
            r_deb = lookup.get((present_key["deb"], l1_id))
            r_pro = lookup.get((present_key["pro"], l1_id))
            if r_deb and r_pro:
                gap_row["recall_gain_hybrid_v2_pro_over_deberta"]    = round(
                    r_pro["recall_dir"]    - r_deb["recall_dir"],    4)
                gap_row["precision_gain_hybrid_v2_pro_over_deberta"] = round(
                    r_pro["precision_dir"] - r_deb["precision_dir"], 4)
                # DeBERTa high recall but low precision flag
                gap_row["deberta_high_recall_low_precision"] = bool(
                    r_deb["recall_dir"] > 0.5 and r_deb["precision_dir"] < 0.4)

        # Overall failure
        all_recalls = [
            lookup.get((mname, l1_id), {}).get("recall_dir", 0.0) or 0.0
            for mname in valid_method_names
        ]
        max_recall = max(all_recalls) if all_recalls else 0.0
        gap_row["all_methods_recall_dir_max"] = round(max_recall, 4)
        gap_row["all_methods_fail"] = (
            max_recall < 0.10 and ref["dev_gold_count_l1"] > 0
        )

        method_gap.append(gap_row)

    # Keep original frequency order (already sorted by rank)
    return rare_low_recall, high_fp, high_dir_error, method_gap


# ============================================================
# PART 8: FIGURES
# ============================================================

def create_figures(
    label_freq_rows: List[Dict],
    per_label_rows: List[Dict],
    freq_group_rows: List[Dict],
    overall_metrics: List[Dict],
    valid_method_names: List[str],
    fig_dir: Path,
) -> None:
    if not HAS_MPL:
        print("  [WARNING] matplotlib unavailable — figures skipped.")
        return

    fig_dir.mkdir(parents=True, exist_ok=True)

    # Assign consistent colors to methods
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    method_color = {m: color_cycle[i % len(color_cycle)] for i, m in enumerate(valid_method_names)}

    sorted_names  = [r["l1_value_name"] for r in label_freq_rows]
    sorted_ids    = [r["l1_value_id"]   for r in label_freq_rows]
    sorted_counts = [r["train_gold_count_l1"] for r in label_freq_rows]
    n_labels = len(sorted_ids)

    # per-label lookup
    lk = {(r["method"], r["l1_value_id"]): r for r in per_label_rows}
    # freq-group lookup
    fglk = {(r["method"], r["group_type"], r["group_value"]): r for r in freq_group_rows}

    # ── 1. Label frequency distribution ─────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(range(n_labels), sorted_counts, color="steelblue", alpha=0.75)
    ax.set_xticks(range(n_labels))
    ax.set_xticklabels(sorted_names, rotation=90, fontsize=5.5)
    ax.set_xlabel("L1 Value (sorted by train frequency)")
    ax.set_ylabel("Train Gold Count")
    ax.set_title("Label Frequency Distribution (L1 Values, sorted by train count)")
    ax.axvline(x=17.5, color="tomato", linestyle="--", linewidth=0.8)
    ax.axvline(x=35.5, color="tomato", linestyle="--", linewidth=0.8)
    plt.tight_layout()
    plt.savefig(fig_dir / "label_frequency_distribution.png", dpi=150)
    plt.close()
    print("    label_frequency_distribution.png")

    # ── 2. Recall by label frequency (direction-aware) ───────────────────────
    fig, ax = plt.subplots(figsize=(14, 5))
    for mname in valid_method_names:
        vals = [lk.get((mname, lid), {}).get("recall_dir", float("nan")) for lid in sorted_ids]
        ax.plot(range(n_labels), vals, label=mname, color=method_color[mname],
                linewidth=1.2, alpha=0.8)
    ax.set_xticks(range(n_labels))
    ax.set_xticklabels(sorted_names, rotation=90, fontsize=5.5)
    ax.set_xlabel("L1 Value (sorted by train frequency)")
    ax.set_ylabel("Direction-aware Recall")
    ax.set_title("Recall by Label (frequent → rare), Task-1b")
    ax.legend(fontsize=7, loc="upper right")
    ax.axvline(x=17.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.axvline(x=35.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.text(9,  -0.12, "Frequent", ha="center", fontsize=8, color="gray",
            transform=ax.get_xaxis_transform())
    ax.text(26.5, -0.12, "Medium",  ha="center", fontsize=8, color="gray",
            transform=ax.get_xaxis_transform())
    ax.text(44.5, -0.12, "Rare",   ha="center", fontsize=8, color="gray",
            transform=ax.get_xaxis_transform())
    plt.tight_layout()
    plt.savefig(fig_dir / "recall_by_label_frequency_task1b.png", dpi=150)
    plt.close()
    print("    recall_by_label_frequency_task1b.png")

    # ── 3. Precision by label frequency (direction-aware) ────────────────────
    fig, ax = plt.subplots(figsize=(14, 5))
    for mname in valid_method_names:
        vals = [lk.get((mname, lid), {}).get("precision_dir", float("nan")) for lid in sorted_ids]
        ax.plot(range(n_labels), vals, label=mname, color=method_color[mname],
                linewidth=1.2, alpha=0.8)
    ax.set_xticks(range(n_labels))
    ax.set_xticklabels(sorted_names, rotation=90, fontsize=5.5)
    ax.set_xlabel("L1 Value (sorted by train frequency)")
    ax.set_ylabel("Direction-aware Precision")
    ax.set_title("Precision by Label (frequent → rare), Task-1b")
    ax.legend(fontsize=7, loc="upper right")
    ax.axvline(x=17.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.axvline(x=35.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    plt.tight_layout()
    plt.savefig(fig_dir / "precision_by_label_frequency_task1b.png", dpi=150)
    plt.close()
    print("    precision_by_label_frequency_task1b.png")

    # ── 4 & 5. Frequency-group bar charts ────────────────────────────────────
    tertile_order = ["frequent", "medium", "rare"]
    n_methods = len(valid_method_names)
    bar_w = 0.8 / max(n_methods, 1)

    for metric_key, ylabel, fname in [
        ("micro_recall_dir",    "Direction-aware Recall",    "frequency_group_recall_bar.png"),
        ("micro_precision_dir", "Direction-aware Precision", "frequency_group_precision_bar.png"),
    ]:
        fig, ax = plt.subplots(figsize=(10, 5))
        for i, mname in enumerate(valid_method_names):
            heights = [
                fglk.get((mname, "tertile_group", g), {}).get(metric_key, 0.0)
                for g in tertile_order
            ]
            offsets = [(j + (i - n_methods / 2 + 0.5) * bar_w) for j in range(len(tertile_order))]
            ax.bar(offsets, heights, bar_w * 0.92, label=mname,
                   color=method_color[mname], alpha=0.8)
        ax.set_xticks(range(len(tertile_order)))
        ax.set_xticklabels(tertile_order)
        ax.set_xlabel("Frequency Group (tertile)")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} by Frequency Group")
        ax.legend(fontsize=7)
        ax.set_ylim(0, 1.0)
        plt.tight_layout()
        plt.savefig(fig_dir / fname, dpi=150)
        plt.close()
        print(f"    {fname}")

    # ── 6. Task-1b precision–recall scatter ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 6))
    for r in overall_metrics:
        ax.scatter(r["task1b_recall"], r["task1b_precision"],
                   s=120, color=method_color.get(r["method"], "gray"), zorder=5)
        ax.annotate(r["method"],
                    (r["task1b_recall"], r["task1b_precision"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=7)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Task-1b Recall (micro)")
    ax.set_ylabel("Task-1b Precision (micro)")
    ax.set_title("Task-1b Precision vs Recall per Method")
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.5, alpha=0.3)
    plt.tight_layout()
    plt.savefig(fig_dir / "task1b_precision_recall_scatter.png", dpi=150)
    plt.close()
    print("    task1b_precision_recall_scatter.png")

    # ── 7. DRR by method ─────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    names = [r["method"] for r in overall_metrics]
    drrs  = [r["drr"]    for r in overall_metrics]
    colors = [method_color.get(n, "gray") for n in names]
    ax.bar(range(len(names)), drrs, color=colors, alpha=0.8)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Direction Reverse Rate (DRR)")
    ax.set_title("DRR by Method  (lower = better)")
    for i, v in enumerate(drrs):
        ax.text(i, v + 0.003, f"{v:.4f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.savefig(fig_dir / "drr_by_method.png", dpi=150)
    plt.close()
    print("    drr_by_method.png")

    # ── 8. Rare-label recall comparison ──────────────────────────────────────
    rare_ids   = [r["l1_value_id"]   for r in label_freq_rows if r["tertile_group"] == "rare"]
    rare_names = [r["l1_value_name"] for r in label_freq_rows if r["tertile_group"] == "rare"]
    key_rare_methods = [
        "Prompt_OAI", "Prompt_DS_Flash", "DeBERTa_only",
        "Hybrid_v2_DS_Pro", "Hybrid_v2_DS_Flash",
    ]
    present_rare = [m for m in key_rare_methods if m in valid_method_names]

    if present_rare and rare_ids:
        fig, ax = plt.subplots(figsize=(14, 5))
        for mname in present_rare:
            vals = [lk.get((mname, lid), {}).get("recall_dir", float("nan")) for lid in rare_ids]
            ax.plot(range(len(rare_ids)), vals, label=mname,
                    color=method_color.get(mname, "gray"),
                    linewidth=1.3, alpha=0.85, marker="o", markersize=4)
        ax.set_xticks(range(len(rare_ids)))
        ax.set_xticklabels(rare_names, rotation=90, fontsize=6.5)
        ax.set_xlabel("Rare L1 Value")
        ax.set_ylabel("Direction-aware Recall")
        ax.set_title("Rare Label Recall Comparison (key methods)")
        ax.legend(fontsize=8)
        ax.set_ylim(0, 1.05)
        plt.tight_layout()
        plt.savefig(fig_dir / "rare_label_recall_comparison.png", dpi=150)
        plt.close()
        print("    rare_label_recall_comparison.png")


# ============================================================
# PART 9: RESEARCH REPORT
# ============================================================

def write_report(
    overall_metrics: List[Dict],
    label_freq_rows: List[Dict],
    per_label_rows: List[Dict],
    freq_group_rows: List[Dict],
    rare_low_recall: List[Dict],
    high_fp: List[Dict],
    high_dir_error: List[Dict],
    valid_method_names: List[str],
    skipped_methods: List[Dict],
    output_dir: Path,
    timestamp: str,
) -> str:
    # ── Summary stats ────────────────────────────────────────────────────────
    def count_group(key: str, val: str) -> int:
        return sum(1 for r in label_freq_rows if r[key] == val)

    n_freq = count_group("tertile_group", "frequent")
    n_med  = count_group("tertile_group", "medium")
    n_rare = count_group("tertile_group", "rare")

    thresh_counts = {
        "zero_train": count_group("threshold_group", "zero_train"),
        "very_rare":  count_group("threshold_group", "very_rare"),
        "rare":       count_group("threshold_group", "rare"),
        "medium":     count_group("threshold_group", "medium"),
        "frequent":   count_group("threshold_group", "frequent"),
    }

    best_1b = max(overall_metrics, key=lambda x: x["task1b_micro_f1"]) if overall_metrics else {}
    best_drr = min(overall_metrics, key=lambda x: x["drr"]) if overall_metrics else {}

    # Avg rare-label direction recall per method
    rare_avg: Dict[str, float] = {}
    for mname in valid_method_names:
        rows = [r for r in per_label_rows
                if r["method"] == mname
                and r["tertile_group"] == "rare"
                and r["dev_gold_count_l1"] > 0]
        rare_avg[mname] = (sum(r["recall_dir"] for r in rows) / len(rows)) if rows else 0.0
    best_rare_m = max(rare_avg, key=rare_avg.get) if rare_avg else "—"
    best_rare_v = rare_avg.get(best_rare_m, 0.0)

    # ── Helper: markdown table from overall_metrics ──────────────────────────
    def overall_md_table() -> str:
        cols = ["Method", "1a µF1", "1a MaF1", "1a P", "1a R",
                "1b µF1", "1b MaF1", "1b P", "1b R", "DRR", "RevCnt"]
        sep  = "|" + "|".join(["---"] * len(cols)) + "|"
        hdr  = "| " + " | ".join(cols) + " |"
        rows_md = [hdr, sep]
        for r in overall_metrics:
            rows_md.append(
                f"| {r['method']} "
                f"| {r['task1a_micro_f1']:.4f} | {r['task1a_macro_f1']:.4f} "
                f"| {r['task1a_precision']:.4f} | {r['task1a_recall']:.4f} "
                f"| {r['task1b_micro_f1']:.4f} | {r['task1b_macro_f1']:.4f} "
                f"| {r['task1b_precision']:.4f} | {r['task1b_recall']:.4f} "
                f"| {r['drr']:.4f} | {r['reverse_count']} |"
            )
        return "\n".join(rows_md)

    # ── First method for sample per-label tables ─────────────────────────────
    fm = valid_method_names[0] if valid_method_names else ""
    fm_rows = [r for r in per_label_rows if r["method"] == fm and r["dev_gold_count_l1"] > 0]
    top_recall   = sorted(fm_rows, key=lambda x: -x["recall_dir"])[:5]
    low_recall   = sorted(fm_rows, key=lambda x:  x["recall_dir"])[:5]
    top_rare_rr  = sorted(
        [r for r in rare_low_recall if r["method"] == fm],
        key=lambda x: x["recall_dir"]
    )[:10]

    # ── Build the report string ───────────────────────────────────────────────
    L = []
    L += [
        "# FEHU Label Diagnosis Report",
        "",
        f"**Generated:** {timestamp}  ",
        "**Project:** NTCIR-19 FEHU — Task-1 Diagnostic Analysis  ",
        "",
        "---",
        "",
        "## 1. Purpose",
        "",
        "This analysis responds to the professor's suggestions for a recall-focused and label-wise",
        "diagnostic evaluation **before** any data augmentation work.",
        "",
        "Key questions addressed:",
        "",
        "- Which labels are frequent vs. rare?",
        "- Which labels have low recall / low precision per method?",
        "- Which labels have high direction reversal errors (high DRR)?",
        "- Are methods behaving as recall-focused or precision-focused?",
        "- Recall/precision from frequent to rare labels (the professor's main ask)?",
        "",
        "> **Constraint**: This report is purely diagnostic. No augmentation, no training, no API calls.",
        "",
        "---",
        "",
        "## 2. Data and Methods",
        "",
        "**Gold labels used:**",
        "- `dataset/gold_labels/train/train_human_values.json` — for label frequency analysis",
        "- `dataset/gold_labels/dev/dev_human_values.json`   — for metric evaluation",
        "",
        f"**Methods analyzed ({len(valid_method_names)}):**",
    ]
    for m in valid_method_names:
        L.append(f"- `{m}`")
    L += [
        "",
        f"**Methods skipped ({len(skipped_methods)}):**",
    ]
    for s in skipped_methods:
        L.append(f"- `{s['method']}`: {s['reason']}")
    L += [
        "",
        "---",
        "",
        "## 3. Overall Results",
        "",
        overall_md_table(),
        "",
        "> `µF1` = micro-F1, `MaF1` = macro-F1 (gold-supported), `P` = micro-precision, `R` = micro-recall.  ",
        "> `DRR` = Direction Reverse Rate (lower is better). `RevCnt` = raw direction reversals.",
        "",
    ]
    if best_1b:
        L.append(f"**Best Task-1b Micro-F1:** `{best_1b['method']}` = {best_1b['task1b_micro_f1']:.4f}  ")
    if best_drr:
        L.append(f"**Lowest DRR (best direction accuracy):** `{best_drr['method']}` = {best_drr['drr']:.4f}  ")
    L.append(f"**Best rare-label avg direction-recall:** `{best_rare_m}` = {best_rare_v:.4f}")
    L += [
        "",
        "---",
        "",
        "## 4. Label Frequency Distribution",
        "",
        f"Total L1 label classes: **54**  ",
        f"Total L1 × direction classes: **108**  ",
        "",
        "**Tertile groups (18 labels each, by train gold count):**",
        f"- Frequent (top-18):   {n_freq} labels",
        f"- Medium (middle-18):  {n_med}  labels",
        f"- Rare (bottom-18):    {n_rare} labels",
        "",
        "**Threshold groups (by raw count):**",
        f"- `zero_train` (0):     {thresh_counts['zero_train']} labels",
        f"- `very_rare`  (1–5):   {thresh_counts['very_rare']} labels",
        f"- `rare`       (6–15):  {thresh_counts['rare']} labels",
        f"- `medium`     (16–40): {thresh_counts['medium']} labels",
        f"- `frequent`   (>40):   {thresh_counts['frequent']} labels",
        "",
        "The distribution is **strongly long-tailed**: a handful of labels dominate training data,",
        "while many rare labels receive very limited supervision.",
        "",
        "---",
        "",
        "## 5. Per-Label Precision/Recall Findings",
        "",
        f"*(Sample for method `{fm}`; see `per_label_l1_metrics.csv` for all methods.)*",
        "",
        "### High-Recall Labels",
        "",
        "| L1 Value | Rec (dir) | Prec (dir) | F1 (dir) | Train Count |",
        "|---|---|---|---|---|",
    ]
    for r in top_recall:
        L.append(
            f"| {r['l1_value_name']} "
            f"| {r['recall_dir']:.4f} | {r['precision_dir']:.4f} | {r['f1_dir']:.4f} "
            f"| {r['train_gold_count_l1']} |"
        )
    L += [
        "",
        "### Low-Recall Labels (with dev gold > 0)",
        "",
        "| L1 Value | Rec (dir) | Prec (dir) | F1 (dir) | Train | Dev |",
        "|---|---|---|---|---|---|",
    ]
    for r in low_recall:
        L.append(
            f"| {r['l1_value_name']} "
            f"| {r['recall_dir']:.4f} | {r['precision_dir']:.4f} | {r['f1_dir']:.4f} "
            f"| {r['train_gold_count_l1']} | {r['dev_gold_count_l1']} |"
        )
    L += [
        "",
        "### Rare + Low-Recall Labels (top-10, suggested for augmentation)",
        "",
        f"*(method: `{fm}`)*",
        "",
        "| L1 Value | Rec (dir) | Train | Dev | Suggested Action |",
        "|---|---|---|---|---|",
    ]
    for r in top_rare_rr:
        L.append(
            f"| {r['l1_value_name']} "
            f"| {r['recall_dir']:.4f} "
            f"| {r['train_gold_count_l1']} | {r['dev_gold_count_l1']} "
            f"| `{r['suggested_future_action']}` |"
        )
    L += [
        "",
        "---",
        "",
        "## 6. Method-Level Interpretation",
        "",
        "### Prompt-only Models",
        "",
        "Check `task1b_precision` vs `task1b_recall` in the overall table.",
        "Models with recall > precision are in 'recall-focused' mode; the opposite indicates conservatism.",
        "LLM model choice (OAI vs. DeepSeek Flash) may shift the recall–precision balance on rare labels.",
        "",
        "### DeBERTa-only",
        "",
        "DeBERTa is trained on actual gold labels with binary classifiers.",
        "Its behavior on frequent labels may differ significantly from rare/zero-train labels.",
        "Check `frequency_group_summary.csv` group-level `micro_recall_dir` and `micro_precision_dir`.",
        "High recall on frequent labels combined with low recall on rare labels would confirm class-imbalance effects.",
        "",
        "### Hybrid Methods (v1, v2 DS Pro, v2 DS Flash)",
        "",
        "Hybrid methods use DeBERTa for candidate generation and an LLM for verification.",
        "They should reduce direction errors (lower DRR) vs. prompt-only methods.",
        "Compare `drr` column across methods. If Hybrid DRR < Prompt DRR, direction modeling improves.",
        "v2 methods have the most complete run configs; v1 uses GPT-4o-mini as verifier.",
        "",
        "### DeepSeek vs. OpenAI",
        "",
        "If `Prompt_DS_Flash` shows higher recall than `Prompt_OAI` on rare labels,",
        "this suggests LLM model choice meaningfully affects rare-class recall —",
        "a key input for deciding which backbone to use in the augmentation pipeline.",
        "",
        "---",
        "",
        "## 7. Research Implications",
        "",
        "Based on this diagnostic analysis, the following augmentation strategies are indicated:",
        "",
        "### (a) Recall-focused Thresholding",
        "",
        "If DeBERTa-only shows high precision but low recall on rare labels,",
        "lowering the classification threshold per-group can recover recall.",
        "Target: labels in `rare` / `very_rare` / `zero_train` threshold groups.",
        "",
        "### (b) Traditional Paraphrase Augmentation",
        "",
        "Labels with 1–15 train examples (`very_rare`, `rare`) are strong candidates",
        "for synonym replacement and back-translation augmentation.",
        "See `rare_low_recall_labels.csv` for a pre-filtered candidate list.",
        "",
        "### (c) LLM-Generated Rare-Class Positives",
        "",
        "Labels where **all methods** fail (recall < 0.10) need synthetic positives.",
        "Use an LLM to generate news-style sentences that express the target value.",
        "See `method_gap_analysis.csv` column `all_methods_fail`.",
        "",
        "### (d) Hard Negatives for Over-Predicted Labels",
        "",
        "Labels with high FP counts and low precision (see `high_false_positive_labels.csv`)",
        "need hard negative training examples — articles that are topically similar but",
        "do **not** express the target value.",
        "",
        "### (e) Direction-Contrastive Samples",
        "",
        "Labels with high direction-reversal rates (see `high_direction_error_labels.csv`)",
        "need contrastive pairs: one aligned example and one contradictory example for the same value.",
        "This is especially important if `drr` is high across methods.",
        "",
        "---",
        "",
        "## 8. Important Constraint",
        "",
        "> **This report is ONLY diagnostic analysis. No augmentation has been performed.**  ",
        "> No models were trained. No APIs were called. No existing files were modified.  ",
        "> All analysis uses local prediction files and gold labels only.",
        "",
        "---",
        "",
        "## Output Files",
        "",
        f"All outputs saved to: `{output_dir}`",
        "",
        "| File | Description |",
        "|---|---|",
        "| `method_inventory.csv` | Validation table for all candidate result sets |",
        "| `overall_metrics.json/.csv` | Official Task-1a/1b metrics per method |",
        "| `overall_comparison_table.txt` | Plain-text aligned metrics table |",
        "| `label_frequency_l1.csv/.json` | L1 label frequency + tertile/threshold groups |",
        "| `per_label_l1_metrics.csv/.json` | Per-label P/R/F1 per method (54 labels × N methods) |",
        "| `per_class_108_metrics.csv/.json` | Per-class metrics (108 = 54 L1 × 2 directions) |",
        "| `frequency_group_summary.csv/.json` | Group-level micro/macro P/R/F1 |",
        "| `rare_low_recall_labels.csv` | Rare labels with low recall — augmentation candidates |",
        "| `high_false_positive_labels.csv` | Over-predicted labels — hard-negative candidates |",
        "| `high_direction_error_labels.csv` | High direction-reversal labels |",
        "| `method_gap_analysis.csv` | Label-wise method comparison (gains, failure flags) |",
        "| `figures/` | All PNG diagnostic figures |",
        "| `diagnosis_report.md` | This report |",
        "| `diagnosis_run_config.json` | Run metadata |",
        "",
    ]
    return "\n".join(L)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "output" / "research_label_diagnosis" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = output_dir / "figures"

    print("=" * 68)
    print("FEHU Label Diagnosis")
    print("=" * 68)
    print(f"Timestamp : {timestamp}")
    print(f"Output dir: {output_dir}")
    print()

    # ── [1] Taxonomy ─────────────────────────────────────────────────────────
    print("[1/10] Loading taxonomy mappings ...")
    l1_id_to_name, l2_id_to_name, l1_id_to_l2_id = load_level_mappings()
    print(f"       L1 values: {len(l1_id_to_name)}, L2 values: {len(l2_id_to_name)}")

    # ── [2] Method inventory ─────────────────────────────────────────────────
    print("[2/10] Building method inventory ...")
    skipped: List[Dict] = []
    valid_methods, inventory_rows = build_method_inventory(skipped)
    valid_names = [m["name"] for m in valid_methods]
    print(f"       Valid full-dev methods : {len(valid_methods)}")
    for m in valid_methods:
        print(f"         + {m['name']}")
    print(f"       Skipped methods        : {len(skipped)}")
    for s in skipped:
        print(f"         - {s['method']}: {s['reason']}")
    save_csv(inventory_rows, output_dir / "method_inventory.csv")
    print("       Saved: method_inventory.csv")

    if not valid_methods:
        print("[ERROR] No valid full-dev methods found. Exiting.")
        sys.exit(1)

    # ── [3] Gold labels ──────────────────────────────────────────────────────
    print("[3/10] Loading gold labels ...")
    train_items = load_gold_items(GOLD_TRAIN)
    dev_items   = load_gold_items(GOLD_DEV)
    print(f"       Train gold items: {len(train_items)}")
    print(f"       Dev   gold items: {len(dev_items)}")

    # ── [4] Overall metrics ──────────────────────────────────────────────────
    print("[4/10] Computing overall official metrics ...")
    overall = compute_overall_metrics(valid_methods, GOLD_DEV)
    save_json(overall, output_dir / "overall_metrics.json")
    save_csv(overall,  output_dir / "overall_metrics.csv")
    table_txt = format_overall_comparison_table(overall)
    (output_dir / "overall_comparison_table.txt").write_text(table_txt, encoding="utf-8")
    print("       Saved: overall_metrics.json/.csv, overall_comparison_table.txt")

    # ── [5] Label frequency ──────────────────────────────────────────────────
    print("[5/10] Computing label frequency analysis ...")
    label_freq = compute_label_frequency(
        train_items, dev_items, l1_id_to_name, l2_id_to_name, l1_id_to_l2_id
    )
    save_csv(label_freq,  output_dir / "label_frequency_l1.csv")
    save_json(label_freq, output_dir / "label_frequency_l1.json")
    print("       Saved: label_frequency_l1.csv/.json")

    # ── [6] Per-label metrics ────────────────────────────────────────────────
    print("[6/10] Computing per-label Task-1b style metrics ...")
    per_label = compute_per_label_metrics(valid_methods, dev_items, label_freq)
    save_csv(per_label,  output_dir / "per_label_l1_metrics.csv")
    save_json(per_label, output_dir / "per_label_l1_metrics.json")
    print(f"       Saved: per_label_l1_metrics.csv/.json  ({len(per_label)} rows)")

    # ── [7] 108-class metrics ────────────────────────────────────────────────
    print("[7/10] Computing 108-class metrics ...")
    cls_108 = compute_108_class_metrics(
        valid_methods, dev_items, train_items,
        l1_id_to_name, l2_id_to_name, l1_id_to_l2_id,
    )
    save_csv(cls_108,  output_dir / "per_class_108_metrics.csv")
    save_json(cls_108, output_dir / "per_class_108_metrics.json")
    print(f"       Saved: per_class_108_metrics.csv/.json  ({len(cls_108)} rows)")

    # ── [8] Frequency-group summary ──────────────────────────────────────────
    print("[8/10] Computing frequency-group summary ...")
    fg_summary = compute_frequency_group_summary(per_label, valid_names)
    save_csv(fg_summary,  output_dir / "frequency_group_summary.csv")
    save_json(fg_summary, output_dir / "frequency_group_summary.json")
    print("       Saved: frequency_group_summary.csv/.json")

    # ── [9] Diagnostic tables ────────────────────────────────────────────────
    print("[9/10] Creating diagnostic tables ...")
    rare_lr, high_fp, high_de, meth_gap = create_diagnostic_tables(per_label, valid_names)
    save_csv(rare_lr,  output_dir / "rare_low_recall_labels.csv")
    save_csv(high_fp,  output_dir / "high_false_positive_labels.csv")
    save_csv(high_de,  output_dir / "high_direction_error_labels.csv")
    save_csv(meth_gap, output_dir / "method_gap_analysis.csv")
    print(
        f"       Saved: diagnostic tables  "
        f"(rare_lr={len(rare_lr)}, high_fp={len(high_fp)}, "
        f"high_de={len(high_de)}, gap={len(meth_gap)})"
    )

    # ── [10] Figures ─────────────────────────────────────────────────────────
    print("[10/10] Generating figures ...")
    create_figures(label_freq, per_label, fg_summary, overall, valid_names, fig_dir)

    # ── Report + run config ──────────────────────────────────────────────────
    print("[Report] Writing diagnosis_report.md ...")
    report = write_report(
        overall, label_freq, per_label, fg_summary,
        rare_lr, high_fp, high_de,
        valid_names, skipped, output_dir, timestamp,
    )
    (output_dir / "diagnosis_report.md").write_text(report, encoding="utf-8")

    run_config = {
        "timestamp":   timestamp,
        "script_path": str(Path(__file__).resolve()),
        "project_root": str(PROJECT_ROOT),
        "train_gold_path": str(GOLD_TRAIN),
        "dev_gold_path":   str(GOLD_DEV),
        "analyzed_methods": valid_names,
        "skipped_methods":  skipped,
        "output_dir": str(output_dir),
        "frequency_group_definition": {
            "tertile":   "top-18 / middle-18 / bottom-18 labels by train gold count",
            "threshold": {
                "zero_train": "count == 0",
                "very_rare":  "1 ≤ count ≤ 5",
                "rare":       "6 ≤ count ≤ 15",
                "medium":     "16 ≤ count ≤ 40",
                "frequent":   "count > 40",
            },
        },
        "notes": (
            "Diagnostic analysis only. No augmentation, training, or API calls performed. "
            "Responds to professor's request for recall/precision per label class."
        ),
    }
    save_json(run_config, output_dir / "diagnosis_run_config.json")
    print("       Saved: diagnosis_run_config.json")

    # ── Final print summary ──────────────────────────────────────────────────
    print()
    print("=" * 68)
    print("OVERALL COMPARISON TABLE")
    print("=" * 68)
    print(table_txt)

    fm = valid_names[0] if valid_names else ""

    print()
    print(f"=== TOP 10 RARE LOW-RECALL LABELS  (method: {fm}) ===")
    top_rare = sorted(
        [r for r in rare_lr if r["method"] == fm],
        key=lambda x: x["recall_dir"],
    )[:10]
    if top_rare:
        print(f"{'L1 Value':<38} {'Train':>6} {'Dev':>5} {'RecDir':>7} {'PrecDir':>8}  Action")
        print("-" * 88)
        for r in top_rare:
            print(
                f"{r['l1_value_name']:<38} {r['train_gold_count_l1']:>6} "
                f"{r['dev_gold_count_l1']:>5} {r['recall_dir']:>7.4f} "
                f"{r['precision_dir']:>8.4f}  {r['suggested_future_action']}"
            )
    else:
        print("  (none meeting criteria for this method)")

    print()
    print(f"=== TOP 10 HIGH FALSE-POSITIVE LABELS  (method: {fm}) ===")
    top_fp = sorted(
        [r for r in high_fp if r["method"] == fm],
        key=lambda x: -x["FP_value"],
    )[:10]
    if top_fp:
        print(f"{'L1 Value':<38} {'Train':>6} {'Dev':>5} {'Pred':>6} {'TP':>4} {'FP':>4} {'Prec':>7}")
        print("-" * 80)
        for r in top_fp:
            print(
                f"{r['l1_value_name']:<38} {r['train_gold_count_l1']:>6} "
                f"{r['dev_gold_count_l1']:>5} {r['pred_count_value']:>6} "
                f"{r['TP_value']:>4} {r['FP_value']:>4} {r['precision_value']:>7.4f}"
            )
    else:
        print("  (none meeting criteria for this method)")

    print()
    print(f"=== TOP 10 HIGH DIRECTION-ERROR LABELS  (method: {fm}) ===")
    top_de = sorted(
        [r for r in high_de if r["method"] == fm],
        key=lambda x: -x["direction_reverse_rate_label"],
    )[:10]
    if top_de:
        print(f"{'L1 Value':<38} {'Train':>6} {'Dev':>5} {'RevCnt':>7} {'DRR_label':>10}")
        print("-" * 72)
        for r in top_de:
            print(
                f"{r['l1_value_name']:<38} {r['train_gold_count_l1']:>6} "
                f"{r['dev_gold_count_l1']:>5} {r['direction_reverse_count']:>7} "
                f"{r['direction_reverse_rate_label']:>10.4f}"
            )
    else:
        print("  (none found for this method)")

    print()
    print(f"Output directory: {output_dir}")
    print("=" * 68)


if __name__ == "__main__":
    main()
