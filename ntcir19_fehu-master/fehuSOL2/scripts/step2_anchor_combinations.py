#!/usr/bin/env python3
"""Offline anchor combinations between Pro T=0 and SOL2 single-actor Step 2."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT / "Mathematical_optimization/temperature_ablation/t0.0"
STEP2_DIR = PROJECT / "fehuSOL2/runs/step2_single_actor_pro_t0"
OUT_DIR = STEP2_DIR / "anchor_combinations"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, default=BASE_DIR)
    parser.add_argument("--step2-dir", type=Path, default=STEP2_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    helpers = load_module("sol2_step1_helpers", PROJECT / "fehuSOL2/scripts/step1_anchor.py")
    evaluator = helpers.load_evaluator()
    order, base = helpers.prediction_map(args.base_dir / "pred_task1b.json")
    order2, step2 = helpers.prediction_map(args.step2_dir / "pred_task1b.json")
    if order != order2:
        raise ValueError("ordered GUIDs differ")

    combinations = {}
    combinations["directed_intersection"] = {g: base[g] & step2[g] for g in order}
    combinations["union"] = {g: base[g] | step2[g] for g in order}

    value_agreement = {}
    for guid in order:
        step2_values = {(actor, l1) for actor, l1, _ in step2[guid]}
        value_agreement[guid] = {
            atom for atom in base[guid] if (atom[0], atom[1]) in step2_values
        }
    combinations["value_agreement_t0_direction"] = value_agreement

    args.output_dir.mkdir(parents=True, exist_ok=True)
    l1_to_l2 = helpers.load_l1_to_l2()
    results = {}
    for name, mapped in combinations.items():
        method_dir = args.output_dir / name
        method_dir.mkdir(parents=True, exist_ok=True)
        pred1b = method_dir / "pred_task1b.json"
        pred1a = method_dir / "pred_task1a.json"
        helpers.write_task1b(order, mapped, pred1b)
        helpers.write_task1a(order, mapped, l1_to_l2, pred1a)
        metrics = evaluator.compute_all_metrics(str(pred1a), str(pred1b))
        (method_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        results[name] = metrics

    base_metrics = json.loads((args.base_dir / "metrics.json").read_text(encoding="utf-8"))
    step2_metrics = json.loads((args.step2_dir / "metrics.json").read_text(encoding="utf-8"))
    all_metrics = {"t0_base": base_metrics, "single_actor": step2_metrics, **results}
    summary = {}
    for name, metrics in all_metrics.items():
        t1b = metrics["task1b"]
        summary[name] = {
            "micro_precision": t1b["micro_precision"],
            "micro_recall": t1b["micro_recall"],
            "micro_f1": t1b["micro_f1"],
            "macro_f1": t1b["macro_f1"],
            "drr": t1b["drr"],
            "tp": t1b["tp"], "fp": t1b["fp"], "fn": t1b["fn"],
            "pred_labels": t1b["pred_labels"],
            "task1a_micro_f1": metrics["task1a"]["micro_f1"],
            "task1a_macro_f1": metrics["task1a"]["macro_f1_official"],
        }

    best_micro = max(summary, key=lambda name: summary[name]["micro_f1"])
    report_lines = [
        "# SOL2 Step 2 — Anchor 组合离线分析", "",
        "所有组合均为零 API、Dev 诊断。`value_agreement_t0_direction` 只保留两个 view 都提出的 value，并沿用原始 T=0 direction。", "",
        "| 方法 | Micro-P | Micro-R | Micro-F1 | Macro-F1 | DRR | 预测数 | 1a Micro |", 
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, values in summary.items():
        report_lines.append(
            f"| {name} | {values['micro_precision']:.4f} | {values['micro_recall']:.4f} | "
            f"{values['micro_f1']:.4f} | {values['macro_f1']:.4f} | {values['drr']:.4f} | "
            f"{values['pred_labels']} | {values['task1a_micro_f1']:.4f} |"
        )
    report_lines.extend([
        "", f"**Micro-F1 最佳：`{best_micro}` ({summary[best_micro]['micro_f1']:.4f})。**", "",
        "注意：组合规则是看过 Dev 后的诊断结果，不能未经 TRAIN 内复现便直接冻结到 test。",
    ])
    (args.output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "best_micro": best_micro}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (args.output_dir / "ANCHOR_COMBINATIONS_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "best_micro": best_micro}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
