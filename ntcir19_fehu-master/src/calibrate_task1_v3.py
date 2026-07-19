#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V3 — label-aware policy calibration.

Learns, for every (direction, Level-1 label) pair, which ensemble stage
(variant_a / variant_b / union / intersection / verified) to trust, using
ONLY an authorized calibration run:

    python src/run_pipeline_prompt_v3.py --mode calibrate --calib_size 120
    python src/calibrate_task1_v3.py --run_dir <that run dir>

The calibration run is a deterministic TRAIN split (demonstration articles
excluded); its gold labels are TRAIN gold. This script REFUSES dev-mode run
directories unless --exploratory_dev_tuning is passed, and then permanently
marks the resulting policy as a dev-tuned exploratory artifact (results
obtained with such a policy on the same dev set are NOT unbiased).

Overfitting safeguards:
  * min positive support per label (default 5) — below it, no policy change;
  * shrinkage toward the run's default strategy — an alternative is adopted
    only when its calibration F1 beats the default's by at least min_gain
    (default 0.05);
  * deterministic tie-breaking via a fixed strategy preference order;
  * full per-label report (support, per-strategy P/R/F1, chosen strategy,
    reason) written next to the policy.

The policy file embeds the calibration provenance (dataset hash, calibration
GUID hash, prompt hashes, model, temperature, demo-set hash, schema
versions); src/run_pipeline_prompt_v3.py verifies these before applying it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))

from task1_v2_taxonomy import canonical_json, sha256_text
from task1_v3_ensemble import POLICY_VERSION, STAGE_NAMES

DEFAULT_MIN_SUPPORT = 5
DEFAULT_MIN_GAIN = 0.05

# Deterministic preference order for tie-breaking among qualifying
# alternatives (earlier wins on equal F1). The default strategy always wins
# unless an alternative clears the min_gain margin.
STRATEGY_PREFERENCE = ("verified", "intersection", "variant_a", "variant_b",
                       "union")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


# ============================================================
# Per-label scoring and policy selection (pure, unit-testable)
# ============================================================

def per_label_prf(gold: Dict[tuple, Set[str]], pred: Dict[tuple, Set[str]],
                  label: str) -> dict:
    tp = fp = fn = 0
    for iid in set(gold) | set(pred):
        g = label in gold.get(iid, set())
        p = label in pred.get(iid, set())
        if g and p:
            tp += 1
        elif p:
            fp += 1
        elif g:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4)}


def select_label_policies(
    gold: Dict[tuple, Set[str]],
    stage_preds: Dict[str, Dict[tuple, Set[str]]],
    default_strategy: str,
    min_support: int = DEFAULT_MIN_SUPPORT,
    min_gain: float = DEFAULT_MIN_GAIN,
) -> Dict[str, dict]:
    """For every label in the official Task-1b universe, choose a strategy.

    Returns label_key → {"strategy", "support", "reason", "scores"}.
    Labels never touch anything but the calibration gold/predictions passed
    in; the caller is responsible for supplying an authorized split.
    """
    if default_strategy not in STAGE_NAMES:
        raise ValueError(f"default_strategy must be one of {STAGE_NAMES}")
    from evaluation import l1_dir_universe

    available = [s for s in STRATEGY_PREFERENCE if s in stage_preds]
    if default_strategy not in stage_preds:
        raise ValueError(f"stage_preds is missing the default strategy "
                         f"{default_strategy!r}")

    out: Dict[str, dict] = {}
    for label in sorted(l1_dir_universe(),
                        key=lambda k: (int(k.split(":")[1]), k.split(":")[0])):
        support = sum(1 for labs in gold.values() if label in labs)
        scores = {s: per_label_prf(gold, stage_preds[s], label)
                  for s in available}
        default_f1 = scores[default_strategy]["f1"]

        if support < min_support:
            chosen, reason = "default", (
                f"insufficient calibration support ({support} < "
                f"{min_support}); no policy change")
        else:
            best, best_f1 = None, default_f1 + min_gain
            for s in available:      # fixed order → deterministic ties
                if s == default_strategy:
                    continue
                if scores[s]["f1"] >= best_f1 and (
                        best is None or scores[s]["f1"] > scores[best]["f1"]):
                    best = s
                    # keep threshold at (default + gain); among qualifiers the
                    # strictly-highest F1 wins, first-in-order on exact ties
            if best is None:
                chosen, reason = "default", (
                    f"no strategy beats default ({default_strategy}, "
                    f"f1={default_f1:.4f}) by min_gain={min_gain}")
            else:
                chosen, reason = best, (
                    f"f1={scores[best]['f1']:.4f} beats default "
                    f"({default_strategy}, f1={default_f1:.4f}) by "
                    f">= {min_gain}")
        out[label] = {"strategy": chosen, "support": support,
                      "reason": reason, "scores": scores}
    return out


# ============================================================
# CLI
# ============================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Learn a frozen label-aware policy from a Pipeline V3 "
                    "calibration run (TRAIN split).")
    ap.add_argument("--run_dir", required=True,
                    help="Output directory of a "
                         "`run_pipeline_prompt_v3.py --mode calibrate` run.")
    ap.add_argument("--gold_labels", default=None,
                    help="Gold labels for the calibration articles. Defaults "
                         "to the gold path recorded in the run manifest.")
    ap.add_argument("--out", default=None,
                    help="Policy output path (default: "
                         "<run_dir>/label_policy.json).")
    ap.add_argument("--min_support", type=int, default=DEFAULT_MIN_SUPPORT)
    ap.add_argument("--min_gain", type=float, default=DEFAULT_MIN_GAIN)
    ap.add_argument("--exploratory_dev_tuning", action="store_true",
                    help="Permit a dev-mode run directory. The policy is "
                         "permanently marked exploratory_dev_tuning=true; "
                         "dev results obtained with it are NOT unbiased.")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"ERROR: no manifest.json in {run_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("mode") != "calibrate" and not args.exploratory_dev_tuning:
        raise SystemExit(
            f"ERROR: run mode is {manifest.get('mode')!r}, not 'calibrate'. "
            f"Learning label policies from a dev run and then reporting on "
            f"the same dev set is development-set leakage. Use a "
            f"--mode calibrate run, or pass --exploratory_dev_tuning to "
            f"create an explicitly marked exploratory policy.")
    if manifest.get("dry_run"):
        raise SystemExit("ERROR: the run directory is a dry run.")
    if manifest.get("n_articles_succeeded", 0) == 0:
        raise SystemExit("ERROR: the run has no successful articles.")

    gold_path = Path(args.gold_labels) if args.gold_labels else (
        Path(manifest["gold_labels_path"]) if manifest.get("gold_labels_path")
        else None)
    if gold_path is None or not gold_path.exists():
        raise SystemExit("ERROR: no gold-label path (pass --gold_labels).")

    from evaluation import parse_task1b
    from run_pipeline_prompt_v3 import stage_file_names, filter_by_guids

    succeeded = set(manifest["succeeded_guids"])
    gold = filter_by_guids(parse_task1b(str(gold_path)), succeeded)

    stage_preds = {}
    for stage in STAGE_NAMES:
        _, f1b = stage_file_names(stage)
        p = run_dir / f1b
        if not p.exists():
            raise SystemExit(f"ERROR: missing stage predictions: {p}")
        stage_preds[stage] = filter_by_guids(parse_task1b(str(p)), succeeded)

    default_strategy = manifest.get("default_strategy", "verified")
    labels = select_label_policies(gold, stage_preds, default_strategy,
                                   args.min_support, args.min_gain)

    calib_guids = sorted(succeeded)
    policy = {
        "policy_version": POLICY_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "default_strategy": default_strategy,
        "min_support": args.min_support,
        "min_gain": args.min_gain,
        "strategy_preference_order": list(STRATEGY_PREFERENCE),
        "exploratory_dev_tuning": bool(args.exploratory_dev_tuning
                                       or manifest.get("mode") != "calibrate"),
        "calibration": {
            "run_dir": str(run_dir.resolve()),
            "run_mode": manifest.get("mode"),
            "gold_path": str(gold_path.resolve()),
            "gold_sha256": file_sha256(gold_path),
            "calibration_guid_hash": sha256_text(canonical_json(calib_guids)),
            "n_articles": len(calib_guids),
            "provider": manifest["provider"],
            "model": manifest["model"],
            "temperature": manifest["temperature"],
            "prompt_hashes": manifest["prompt_hashes"],
            "taxonomy_hash": manifest["taxonomy_hash"],
            "rarity_hash": manifest["rarity_hash"],
            "demo_set_hash": manifest["demo_set_hash"],
            "schema_version": manifest["schema_version"],
            "verifier_schema_version": manifest["verifier_schema_version"],
            "verifier_enabled": manifest["use_verifier"],
            "git_commit": manifest.get("git_commit"),
        },
        "labels": labels,
    }

    out_path = Path(args.out) if args.out else run_dir / "label_policy.json"
    out_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    report_path = out_path.with_suffix(".report.csv")
    with open(report_path, "w", encoding="utf-8", newline="") as f:
        strategies = [s for s in STRATEGY_PREFERENCE if s in stage_preds]
        fields = ["label", "support", "chosen_strategy", "reason"]
        for s in strategies:
            fields += [f"{s}_precision", f"{s}_recall", f"{s}_f1"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for label, rec in labels.items():
            row = {"label": label, "support": rec["support"],
                   "chosen_strategy": rec["strategy"], "reason": rec["reason"]}
            for s in strategies:
                row[f"{s}_precision"] = rec["scores"][s]["precision"]
                row[f"{s}_recall"] = rec["scores"][s]["recall"]
                row[f"{s}_f1"] = rec["scores"][s]["f1"]
            w.writerow(row)

    n_overrides = sum(1 for r in labels.values() if r["strategy"] != "default")
    print(f"Policy written: {out_path}")
    print(f"Report written: {report_path}")
    print(f"  labels with a non-default strategy: {n_overrides}/{len(labels)}")
    print(f"  default strategy: {default_strategy}")
    if policy["exploratory_dev_tuning"]:
        print("  WARNING: policy is marked exploratory_dev_tuning=true — "
              "dev results obtained with it are NOT unbiased.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
