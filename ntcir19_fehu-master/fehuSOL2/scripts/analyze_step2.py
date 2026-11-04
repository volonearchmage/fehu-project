#!/usr/bin/env python3
"""Compare SOL2 Step 2 single-actor predictions with the frozen Pro T=0 baseline."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = PROJECT / "Mathematical_optimization/temperature_ablation/t0.0"
DEFAULT_STEP2 = PROJECT / "fehuSOL2/runs/step2_single_actor_pro_t0"
DEV_GOLD = PROJECT / "dataset/gold_labels/dev/dev_human_values.json"
DEV_ARTICLES = PROJECT / "dataset/dev/dev_event_base.json"

Atom = tuple[str, str, str]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atom_map(path: Path) -> dict[str, set[Atom]]:
    result = {}
    for row in load(path):
        result[str(row["guid"])] = {
            (str(v["actor"]), str(v["l1_value"]), str(v["direction"]))
            for v in row.get("article_human_values", [])
        }
    return result


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def slice_counts(pred, gold, guids: set[str]) -> dict:
    tp = fp = fn = 0
    for guid in guids:
        p, g = pred[guid], gold[guid]
        tp += len(p & g)
        fp += len(p - g)
        fn += len(g - p)
    return prf(tp, fp, fn)


def attribution_like_fp(pred: dict[str, set[Atom]], gold: dict[str, set[Atom]]) -> int:
    count = 0
    for guid, atoms in pred.items():
        gold_atoms = gold[guid]
        gold_by_label = defaultdict(set)
        for actor, l1, direction in gold_atoms:
            gold_by_label[(l1, direction)].add(actor)
        for actor, l1, direction in atoms - gold_atoms:
            if gold_by_label[(l1, direction)] and actor not in gold_by_label[(l1, direction)]:
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--step2-dir", type=Path, default=DEFAULT_STEP2)
    args = parser.parse_args()

    required = [
        args.base_dir / "pred_task1b.json", args.base_dir / "metrics.json",
        args.step2_dir / "pred_task1b.json", args.step2_dir / "metrics.json",
        DEV_GOLD, DEV_ARTICLES,
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    base, step2, gold = map(atom_map, [
        args.base_dir / "pred_task1b.json",
        args.step2_dir / "pred_task1b.json",
        DEV_GOLD,
    ])
    if set(base) != set(step2) or set(base) != set(gold):
        raise ValueError("GUID sets differ")

    additions = []
    removals = []
    for guid in base:
        for atom in sorted(step2[guid] - base[guid], key=lambda x: (x[0], int(x[1]), x[2])):
            additions.append({"guid": guid, "actor": atom[0], "l1_value": atom[1], "direction": atom[2], "is_gold": atom in gold[guid]})
        for atom in sorted(base[guid] - step2[guid], key=lambda x: (x[0], int(x[1]), x[2])):
            removals.append({"guid": guid, "actor": atom[0], "l1_value": atom[1], "direction": atom[2], "is_gold": atom in gold[guid]})

    add_tp = sum(row["is_gold"] for row in additions)
    rem_tp = sum(row["is_gold"] for row in removals)
    add_stats = {
        "n": len(additions), "tp": add_tp, "fp": len(additions) - add_tp,
        "precision": round(add_tp / len(additions), 4) if additions else 0.0,
    }
    removal_stats = {
        "n": len(removals), "removed_tp": rem_tp, "removed_fp": len(removals) - rem_tp,
        "removed_group_precision": round(rem_tp / len(removals), 4) if removals else 0.0,
    }

    article_rows = load(DEV_ARTICLES)
    actor_counts = {str(row["guid"]): len(row.get("actors", [])) for row in article_rows}
    slices = {
        "one_actor": {g for g, n in actor_counts.items() if n == 1},
        "two_to_three_actors": {g for g, n in actor_counts.items() if 2 <= n <= 3},
        "four_plus_actors": {g for g, n in actor_counts.items() if n >= 4},
    }
    slice_metrics = {
        name: {
            "n_articles": len(guids),
            "base": slice_counts(base, gold, guids),
            "step2": slice_counts(step2, gold, guids),
        }
        for name, guids in slices.items()
    }

    base_metrics = load(args.base_dir / "metrics.json")
    step2_metrics = load(args.step2_dir / "metrics.json")
    b, s = base_metrics["task1b"], step2_metrics["task1b"]
    delta = {
        key: round(s[key] - b[key], 4)
        for key in ("micro_precision", "micro_recall", "micro_f1", "macro_f1", "drr")
    }
    delta["task1a_micro_f1"] = round(step2_metrics["task1a"]["micro_f1"] - base_metrics["task1a"]["micro_f1"], 4)
    delta["task1a_macro_f1"] = round(step2_metrics["task1a"]["macro_f1_official"] - base_metrics["task1a"]["macro_f1_official"], 4)

    if s["micro_f1"] > b["micro_f1"] and s["macro_f1"] >= b["macro_f1"]:
        decision = "PROMOTE_STEP2"
        next_action = "Step 2 becomes the champion; Step 3 should target its largest remaining error."
    elif s["micro_recall"] > b["micro_recall"] and add_stats["tp"] > 0:
        decision = "RESIDUAL_ONLY"
        next_action = "Do not promote standalone Step 2; Step 3 may verify only Step2-minus-baseline additions."
    else:
        decision = "REJECT_STEP2"
        next_action = "Discard the single-actor view; Step 3 should only consider direction repair on T=0."

    analysis = {
        "base_task1b": b,
        "step2_task1b": s,
        "delta": delta,
        "unique_additions": add_stats,
        "unique_removals": removal_stats,
        "attribution_like_fp": {
            "base": attribution_like_fp(base, gold),
            "step2": attribution_like_fp(step2, gold),
        },
        "actor_count_slices": slice_metrics,
        "decision": decision,
        "next_action": next_action,
    }
    (args.step2_dir / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.step2_dir / "unique_additions.json").write_text(json.dumps(additions, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.step2_dir / "unique_removals.json").write_text(json.dumps(removals, indent=2, ensure_ascii=False), encoding="utf-8")

    report = f"""# SOL2 Step 2 — 单 Actor Prompt 实验报告

**模型：** DeepSeek V4 Pro，non-thinking (`thinking=disabled`)  
**温度：** 0.0  
**唯一 Prompt 改动：** 每次调用只判断一个 target actor；全文和完整 actor 列表保留。  
**基线：** 原始 Pro non-thinking T=0（Step 1 判定 NO-GO 后未采用温度 residual）。

## 总体结果

| 系统 | Micro-P | Micro-R | Micro-F1 | Macro-F1 | DRR | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 原始 T=0 | {b['micro_precision']:.4f} | {b['micro_recall']:.4f} | {b['micro_f1']:.4f} | {b['macro_f1']:.4f} | {b['drr']:.4f} | {b['tp']} | {b['fp']} | {b['fn']} |
| 单 Actor | {s['micro_precision']:.4f} | {s['micro_recall']:.4f} | {s['micro_f1']:.4f} | {s['macro_f1']:.4f} | {s['drr']:.4f} | {s['tp']} | {s['fp']} | {s['fn']} |

## 增量

- Δ Micro-F1：**{delta['micro_f1']:+.4f}**
- Δ Macro-F1：**{delta['macro_f1']:+.4f}**
- Δ Precision：**{delta['micro_precision']:+.4f}**
- Δ Recall：**{delta['micro_recall']:+.4f}**
- Δ DRR：**{delta['drr']:+.4f}**
- Δ Task-1a Micro-F1：**{delta['task1a_micro_f1']:+.4f}**

## 互补性

- Step2-only：**{add_stats['n']}**，TP/FP = **{add_stats['tp']}/{add_stats['fp']}**，precision = **{add_stats['precision']:.4f}**
- Baseline-only：**{removal_stats['n']}**，其中被移除 TP/FP = **{removal_stats['removed_tp']}/{removal_stats['removed_fp']}**
- attribution-like FP：baseline **{analysis['attribution_like_fp']['base']}** → Step2 **{analysis['attribution_like_fp']['step2']}**

## 决策

**{decision}**

{next_action}
"""
    (args.step2_dir / "STEP2_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
