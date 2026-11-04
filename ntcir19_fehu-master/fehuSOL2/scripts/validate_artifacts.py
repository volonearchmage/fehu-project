#!/usr/bin/env python3
"""Validate all completed SOL2 Step 1/2 artifacts and write a compact report."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SOL2 = PROJECT / "fehuSOL2"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    step1 = load_module("sol2_validation_helpers", SOL2 / "scripts/step1_anchor.py")
    evaluator = step1.load_evaluator()
    step2_module = load_module("sol2_step2_validation", SOL2 / "scripts/step2_single_actor.py")

    checks: dict[str, bool] = {}

    # Step 1 exact formula.
    t0_order, t0 = step1.prediction_map(step1.DEFAULT_T0)
    t01_order, t01 = step1.prediction_map(step1.DEFAULT_T01)
    t03_order, t03 = step1.prediction_map(step1.DEFAULT_T03)
    anchor_order, anchor = step1.prediction_map(SOL2 / "outputs/step1_anchor/pred_task1b_anchor.json")
    checks["step1_order_identical"] = t0_order == t01_order == t03_order == anchor_order
    checks["step1_formula_exact"] = all(
        anchor[g] == t0[g] | ((t01[g] & t03[g]) - t0[g]) for g in t0_order
    )

    # Step 2 cache/input coverage and strict target isolation.
    run_dir = SOL2 / "runs/step2_single_actor_pro_t0"
    articles = json.loads(step2_module.DEV_ARTICLES.read_text(encoding="utf-8"))
    expected_keys = {
        f"{article['guid']}::{actor_id}"
        for article in articles for _, actor_id in step2_module.iter_actors(article)
    }
    cache = json.loads((run_dir / "cache.json").read_text(encoding="utf-8"))
    checks["step2_459_expected_calls"] = len(expected_keys) == 459
    checks["step2_cache_exact_coverage"] = set(cache) == expected_keys
    checks["step2_all_calls_success"] = all(v.get("status") == "success" for v in cache.values())
    checks["step2_no_extraneous_items"] = all(int(v.get("extraneous_item_count", 0)) == 0 for v in cache.values())
    checks["step2_no_malformed_items"] = all(int(v.get("malformed_item_count", 0)) == 0 for v in cache.values())
    checks["step2_all_items_match_target"] = all(
        all(str(item.get("actor_id")) == entry["actor_id"] for item in entry.get("items", []))
        for entry in cache.values()
    )
    checks["step2_no_retries"] = all(int(v.get("attempts", 1)) == 1 for v in cache.values())
    checks["step2_model_identity"] = (
        json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["model"] == "deepseek-v4-pro"
        and json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["thinking"] == "disabled"
        and json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["temperature"] == 0.0
    )

    # Metrics reproduce from predictions.
    for label, directory, pred1a, pred1b in [
        ("step1", SOL2 / "outputs/step1_anchor", "pred_task1a_anchor.json", "pred_task1b_anchor.json"),
        ("step2", run_dir, "pred_task1a.json", "pred_task1b.json"),
    ]:
        recomputed = evaluator.compute_all_metrics(str(directory / pred1a), str(directory / pred1b))
        stored = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        if label == "step1":
            stored = stored["anchor"]
        stored.pop("label", None)
        checks[f"{label}_metrics_reproduce"] = recomputed == stored

    # Combination formula and metrics.
    combo_dir = run_dir / "anchor_combinations"
    _, step2_pred = step1.prediction_map(run_dir / "pred_task1b.json")
    _, value_agree = step1.prediction_map(combo_dir / "value_agreement_t0_direction/pred_task1b.json")
    checks["value_agreement_formula_exact"] = all(
        value_agree[g] == {
            atom for atom in t0[g]
            if (atom[0], atom[1]) in {(a, l1) for a, l1, _ in step2_pred[g]}
        }
        for g in t0_order
    )
    combo_stored = json.loads((combo_dir / "value_agreement_t0_direction/metrics.json").read_text(encoding="utf-8"))
    combo_recomputed = evaluator.compute_all_metrics(
        str(combo_dir / "value_agreement_t0_direction/pred_task1a.json"),
        str(combo_dir / "value_agreement_t0_direction/pred_task1b.json"),
    )
    checks["value_agreement_metrics_reproduce"] = combo_stored == combo_recomputed

    passed = sum(checks.values())
    validation = {"checks": checks, "passed": passed, "total": len(checks), "all_passed": all(checks.values())}
    (SOL2 / "validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# SOL2 Step 1/2 Artifact Validation", ""]
    for name, ok in checks.items():
        lines.append(f"- [{'x' if ok else ' '}] `{name}`")
    lines.extend(["", f"**{passed}/{len(checks)} checks passed.**"])
    (SOL2 / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
