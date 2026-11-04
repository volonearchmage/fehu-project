#!/usr/bin/env python3
"""FEHU SOL2 Step 1: anchor-preserving temperature consensus.

The experiment is deliberately narrow:

    residual = (T0.1 ∩ T0.3) - T0.0
    anchor   = T0.0 ∪ residual

Intersection is direction-aware at (guid, actor, L1, direction) granularity.
The script never calls an API and never changes an existing T0.0 atom.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_T0 = PROJECT / "Mathematical_optimization/temperature_ablation/t0.0/pred_task1b.json"
DEFAULT_T01 = PROJECT / "Mathematical_optimization/temperature_ablation/t0.1/pred_task1b.json"
DEFAULT_T03 = PROJECT / "Mathematical_optimization/temperature_ablation/t0.3/pred_task1b.json"
DEFAULT_GOLD = PROJECT / "dataset/gold_labels/dev/dev_human_values.json"
DEFAULT_OUT = PROJECT / "fehuSOL2/outputs/step1_anchor"

Atom = tuple[str, str, str]  # actor, l1, direction


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prediction_map(path: Path) -> tuple[list[str], dict[str, set[Atom]]]:
    rows = load_json(path)
    order: list[str] = []
    mapped: dict[str, set[Atom]] = {}
    for row in rows:
        guid = str(row["guid"])
        if guid in mapped:
            raise ValueError(f"duplicate guid in {path}: {guid}")
        order.append(guid)
        atoms: set[Atom] = set()
        for hv in row.get("article_human_values", []):
            atom = (str(hv["actor"]), str(hv["l1_value"]), str(hv["direction"]))
            if not atom[1].isdigit() or not 0 <= int(atom[1]) <= 53:
                raise ValueError(f"invalid L1 in {path}: {guid} {atom}")
            if atom[2] not in {"0", "1"}:
                raise ValueError(f"invalid direction in {path}: {guid} {atom}")
            atoms.add(atom)
        mapped[guid] = atoms
    return order, mapped


def gold_map(path: Path) -> dict[str, set[Atom]]:
    result: dict[str, set[Atom]] = {}
    for row in load_json(path):
        result[str(row["guid"])] = {
            (str(hv["actor"]), str(hv["l1_value"]), str(hv["direction"]))
            for hv in row.get("article_human_values", [])
        }
    return result


def load_l1_to_l2() -> dict[str, str]:
    hv_dir = PROJECT / "dataset/hv_categories"
    l1_names = load_json(hv_dir / "human_value_level1_values.json")
    l2_names = load_json(hv_dir / "human_value_level2_values.json")
    raw = load_json(hv_dir / "level_1_to_level_2.json")["level_1_to_level_2"]
    return {str(l1_names[l1]): str(l2_names[l2]) for l1, l2 in raw.items()}


def write_task1b(order: Iterable[str], mapped: dict[str, set[Atom]], path: Path) -> None:
    rows = []
    for guid in order:
        values = [
            {"actor": actor, "l1_value": l1, "direction": direction}
            for actor, l1, direction in sorted(
                mapped[guid], key=lambda x: (x[0], int(x[1]), x[2])
            )
        ]
        rows.append({"guid": guid, "article_human_values": values})
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def write_task1a(
    order: Iterable[str], mapped: dict[str, set[Atom]], l1_to_l2: dict[str, str], path: Path
) -> None:
    rows = []
    for guid in order:
        value_set = {(actor, l1_to_l2[l1]) for actor, l1, _ in mapped[guid]}
        values = [
            {"actor": actor, "l2_value": l2}
            for actor, l2 in sorted(value_set, key=lambda x: (x[0], int(x[1])))
        ]
        rows.append({"guid": guid, "article_human_values": values})
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def load_evaluator():
    path = PROJECT / "Mathematical_optimization/evaluation/eval_full.py"
    spec = importlib.util.spec_from_file_location("sol2_eval_full", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metric_delta(new: dict, base: dict, section: str, key: str) -> float:
    return round(new[section][key] - base[section][key], 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t0", type=Path, default=DEFAULT_T0)
    parser.add_argument("--t01", type=Path, default=DEFAULT_T01)
    parser.add_argument("--t03", type=Path, default=DEFAULT_T03)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    for path in (args.t0, args.t01, args.t03, args.gold):
        if not path.is_file():
            raise FileNotFoundError(path)

    order0, s0 = prediction_map(args.t0)
    order01, s01 = prediction_map(args.t01)
    order03, s03 = prediction_map(args.t03)
    if order0 != order01 or order0 != order03:
        raise ValueError("temperature prediction files do not have identical ordered GUIDs")

    gold = gold_map(args.gold)
    if set(order0) != set(gold):
        raise ValueError("prediction/gold GUID sets differ")

    residual: dict[str, set[Atom]] = {}
    anchor: dict[str, set[Atom]] = {}
    conflict_rows: list[dict] = []
    residual_rows: list[dict] = []
    per_class = Counter()
    per_class_tp = Counter()

    for guid in order0:
        residual[guid] = (s01[guid] & s03[guid]) - s0[guid]
        anchor[guid] = s0[guid] | residual[guid]

        by_value01: dict[tuple[str, str], set[str]] = defaultdict(set)
        by_value03: dict[tuple[str, str], set[str]] = defaultdict(set)
        for actor, l1, direction in s01[guid]:
            by_value01[(actor, l1)].add(direction)
        for actor, l1, direction in s03[guid]:
            by_value03[(actor, l1)].add(direction)
        for key in sorted(by_value01.keys() & by_value03.keys()):
            if by_value01[key] != by_value03[key]:
                conflict_rows.append({
                    "guid": guid,
                    "actor": key[0],
                    "l1_value": key[1],
                    "t0.1_directions": sorted(by_value01[key]),
                    "t0.3_directions": sorted(by_value03[key]),
                    "t0_directions": sorted(
                        d for a, l, d in s0[guid] if (a, l) == key
                    ),
                })

        for atom in sorted(residual[guid], key=lambda x: (x[0], int(x[1]), x[2])):
            is_tp = atom in gold[guid]
            label = f"{atom[2]}:{atom[1]}"
            per_class[label] += 1
            if is_tp:
                per_class_tp[label] += 1
            residual_rows.append({
                "guid": guid,
                "actor": atom[0],
                "l1_value": atom[1],
                "direction": atom[2],
                "is_gold": is_tp,
            })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pred1b = args.output_dir / "pred_task1b_anchor.json"
    pred1a = args.output_dir / "pred_task1a_anchor.json"
    write_task1b(order0, anchor, pred1b)
    write_task1a(order0, anchor, load_l1_to_l2(), pred1a)
    (args.output_dir / "residual_atoms.json").write_text(
        json.dumps(residual_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (args.output_dir / "direction_conflicts.json").write_text(
        json.dumps(conflict_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    evaluator = load_evaluator()
    base_metrics = evaluator.compute_all_metrics(
        str(PROJECT / "Mathematical_optimization/temperature_ablation/t0.0/pred_task1a.json"),
        str(args.t0),
    )
    anchor_metrics = evaluator.compute_all_metrics(str(pred1a), str(pred1b))
    metrics = {
        "experiment": "SOL2 Step 1 anchor-preserving temperature consensus",
        "formula": "S_anchor = S0 union ((S01 intersection S03) minus S0)",
        "base": base_metrics,
        "anchor": anchor_metrics,
        "delta": {
            "task1a_micro_f1": metric_delta(anchor_metrics, base_metrics, "task1a", "micro_f1"),
            "task1a_macro_f1": metric_delta(anchor_metrics, base_metrics, "task1a", "macro_f1_official"),
            "task1b_micro_precision": metric_delta(anchor_metrics, base_metrics, "task1b", "micro_precision"),
            "task1b_micro_recall": metric_delta(anchor_metrics, base_metrics, "task1b", "micro_recall"),
            "task1b_micro_f1": metric_delta(anchor_metrics, base_metrics, "task1b", "micro_f1"),
            "task1b_macro_f1": metric_delta(anchor_metrics, base_metrics, "task1b", "macro_f1"),
            "drr": metric_delta(anchor_metrics, base_metrics, "task1b", "drr"),
        },
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    residual_n = len(residual_rows)
    residual_tp = sum(1 for row in residual_rows if row["is_gold"])
    residual_fp = residual_n - residual_tp
    residual_precision = residual_tp / residual_n if residual_n else 0.0
    threshold = base_metrics["task1b"]["micro_f1"] / 2
    criteria = {
        "micro_improved": anchor_metrics["task1b"]["micro_f1"] > base_metrics["task1b"]["micro_f1"],
        "residual_precision_above_f1_over_2": residual_precision > threshold,
        "macro_not_worse": anchor_metrics["task1b"]["macro_f1"] >= base_metrics["task1b"]["macro_f1"],
        "drr_not_worse": anchor_metrics["task1b"]["drr"] <= base_metrics["task1b"]["drr"],
    }
    go = all(criteria.values())

    class_rows = [
        {
            "label": label,
            "n": per_class[label],
            "tp": per_class_tp[label],
            "fp": per_class[label] - per_class_tp[label],
            "precision": round(per_class_tp[label] / per_class[label], 4),
        }
        for label in sorted(per_class)
    ]
    summary = {
        "residual": {
            "n": residual_n,
            "tp": residual_tp,
            "fp": residual_fp,
            "precision": round(residual_precision, 4),
            "f1_over_2_threshold": round(threshold, 4),
            "distinct_classes": len(per_class),
            "per_class": class_rows,
        },
        "direction_conflicts": len(conflict_rows),
        "decision_criteria": criteria,
        "decision": "GO" if go else "NO_GO",
        "next_baseline": "S_anchor" if go else "S0",
    }
    (args.output_dir / "analysis.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    manifest = {
        "inputs": {
            "t0": {"path": str(args.t0.relative_to(PROJECT)), "sha256": sha256(args.t0)},
            "t01": {"path": str(args.t01.relative_to(PROJECT)), "sha256": sha256(args.t01)},
            "t03": {"path": str(args.t03.relative_to(PROJECT)), "sha256": sha256(args.t03)},
            "gold": {"path": str(args.gold.relative_to(PROJECT)), "sha256": sha256(args.gold)},
        },
        "model_identity": {
            "model": "deepseek-v4-pro",
            "thinking": "disabled",
            "temperatures": [0.0, 0.1, 0.3],
        },
        "n_articles": len(order0),
        "script_sha256": sha256(Path(__file__)),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    b = base_metrics["task1b"]
    a = anchor_metrics["task1b"]
    report = f"""# SOL2 Step 1 — Anchor 结合实验报告

**模型身份：** DeepSeek V4 Pro，non-thinking (`thinking=disabled`)  
**数据：** Dev 177 篇  
**API 调用：** 0  
**规则：** `S_anchor = S0 ∪ ((S0.1 ∩ S0.3) - S0)`，交集为 direction-aware 原子。

## 结果

| 系统 | Micro-P | Micro-R | Micro-F1 | Macro-F1 | DRR | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T=0 anchor | {b['micro_precision']:.4f} | {b['micro_recall']:.4f} | {b['micro_f1']:.4f} | {b['macro_f1']:.4f} | {b['drr']:.4f} | {b['tp']} | {b['fp']} | {b['fn']} |
| Anchor + consensus residual | {a['micro_precision']:.4f} | {a['micro_recall']:.4f} | {a['micro_f1']:.4f} | {a['macro_f1']:.4f} | {a['drr']:.4f} | {a['tp']} | {a['fp']} | {a['fn']} |

## Residual 质量

- 候选：**{residual_n}**
- TP / FP：**{residual_tp} / {residual_fp}**
- Precision：**{residual_precision:.4f}**
- `F1/2` 理论线：**{threshold:.4f}**
- 涉及 directed classes：**{len(per_class)}**
- T=0.1/T=0.3 value-level direction conflicts：**{len(conflict_rows)}**

## 增量

- Δ Micro-F1：**{anchor_metrics['task1b']['micro_f1'] - base_metrics['task1b']['micro_f1']:+.4f}**
- Δ Macro-F1：**{anchor_metrics['task1b']['macro_f1'] - base_metrics['task1b']['macro_f1']:+.4f}**
- Δ Precision：**{anchor_metrics['task1b']['micro_precision'] - base_metrics['task1b']['micro_precision']:+.4f}**
- Δ Recall：**{anchor_metrics['task1b']['micro_recall'] - base_metrics['task1b']['micro_recall']:+.4f}**
- Δ DRR：**{anchor_metrics['task1b']['drr'] - base_metrics['task1b']['drr']:+.4f}**

## 决策

```json
{json.dumps(criteria, indent=2, ensure_ascii=False)}
```

**Step 1 结论：{('GO，S_anchor 进入 Step 2。' if go else 'NO-GO，温度 residual 不作为 Step 2 基线；继续使用原始 T=0。')}**
"""
    (args.output_dir / "STEP1_REPORT.md").write_text(report, encoding="utf-8")

    print(json.dumps({
        "residual": summary["residual"],
        "direction_conflicts": len(conflict_rows),
        "base_task1b": b,
        "anchor_task1b": a,
        "decision": summary["decision"],
        "next_baseline": summary["next_baseline"],
        "output_dir": str(args.output_dir),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
