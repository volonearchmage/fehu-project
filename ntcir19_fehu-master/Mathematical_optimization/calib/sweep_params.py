#!/usr/bin/env python3
"""
DS Parameter Sweep on Calibration Set
=====================================
Grid-searches the optimal hyperparameters for A3, A4, A5 on the internal
calibration split (sub_train), then reports the best config.

This script does NOT touch the dev set. All metrics are computed on
the calib split.

Usage:
    python calib/sweep_params.py \
        --e1_pred_calib path/to/E1_on_calib_pred_task1b.json \
        --e1_pred_calib_1a path/to/E1_on_calib_pred_task1a.json \
        --output calib/sweep_results.json
"""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from itertools import product

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

from DS_A3_bayesian_prior.run_a3 import (
    estimate_priors, bayesian_adjust, load_l1_to_l2,
)
from DS_A4_label_cooccurrence.run_a4 import (
    build_cooccurrence_matrix, apply_a4,
)
from DS_A5_spectral_debiasing.run_a5 import (
    build_confusion_matrix, apply_a5,
    parse_gold_to_actor_vecs, parse_pred_to_actor_vecs,
)
from evaluation.eval_full import compute_all_metrics

TRAIN_ARTICLES = BASE / "dataset" / "train" / "train_event_base.json"
TRAIN_LABELS   = BASE / "dataset" / "gold_labels" / "train" / "train_human_values.json"
CALIB_SPLIT    = HERE / "calib_split.json"
import numpy as np


def load_calib_gold_and_pred(e1_pred_1b_path, e1_pred_1a_path):
    """Load calibration gold labels and E1 predictions."""
    split = json.loads(CALIB_SPLIT.read_text(encoding="utf-8"))
    calib_guids = set(split["calib_guids"])

    # Filter E1 predictions to calib articles
    e1_1b = json.loads(Path(e1_pred_1b_path).read_text(encoding="utf-8"))
    e1_1a = json.loads(Path(e1_pred_1a_path).read_text(encoding="utf-8"))

    e1_1b_calib = [a for a in e1_1b if a["guid"] in calib_guids]
    e1_1a_calib = [a for a in e1_1a if a["guid"] in calib_guids]

    # Build calib-only gold (by filtering train gold to calib articles)
    train_labels = json.loads(TRAIN_LABELS.read_text(encoding="utf-8"))
    calib_gold = [item for item in train_labels if item["guid"] in calib_guids]

    return e1_1b_calib, e1_1a_calib, calib_gold


def sweep_a3(e1_1b, e1_1a, calib_gold, l1_to_l2):
    """Sweep A3 alpha_add values."""
    results = []
    train_articles = json.loads(TRAIN_ARTICLES.read_text(encoding="utf-8"))
    train_labels   = json.loads(TRAIN_LABELS.read_text(encoding="utf-8"))

    prior_given_type, prior_global, type_totals, global_total = estimate_priors(
        train_articles, train_labels, use_calib_only=True)

    for alpha in [1.5, 2.0, 2.5, 3.0, 4.0]:
        adj = bayesian_adjust(e1_1b, prior_given_type, prior_global,
                              type_totals, global_total, alpha, l1_to_l2)
        # Save temp files for evaluation
        tmp_1b = HERE / "_tmp_a3_1b.json"
        tmp_1a = HERE / "_tmp_a3_1a.json"
        from DS_A3_bayesian_prior.run_a3 import derive_1a
        tmp_1b.write_text(json.dumps(adj, indent=2, ensure_ascii=False))
        derive_1a(adj, str(tmp_1a), l1_to_l2)

        # Evaluate against calib gold
        calib_gold_1b_path = HERE / "_tmp_calib_gold_1b.json"
        calib_gold_1b_path.write_text(json.dumps(calib_gold, indent=2, ensure_ascii=False))
        # Use dev gold format for evaluation (temporary)
        # For now, skip evaluation on calib — just count additions
        n_added = sum(len(a.get("article_human_values", [])) for a in adj) - \
                  sum(len(a.get("article_human_values", [])) for a in e1_1b)
        results.append({"alpha_add": alpha, "n_added": n_added})

        # Cleanup
        tmp_1b.unlink(missing_ok=True)
        tmp_1a.unlink(missing_ok=True)

    return results


def main():
    parser = argparse.ArgumentParser(description="DS Parameter Sweep on Calibration Set")
    parser.add_argument("--e1_pred_calib", type=str, required=True)
    parser.add_argument("--e1_pred_calib_1a", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    # NOTE: Full sweep requires running E1 on the calib split to get
    # calibration predictions. This is ~184 API calls and should be done
    # once. For now, this script provides the framework.

    print("DS Parameter Sweep Framework")
    print("=" * 50)
    print("This script provides the framework for grid-searching A3/A4/A5")
    print("hyperparameters on the internal calibration split.")
    print()
    print("To use:")
    print("  1. Run E1 on calib split: python base/run_pipeline_e1.py --mode dev --limit 184")
    print("     (with calib articles only)")
    print("  2. Run this sweep script with the calib predictions")
    print("  3. Apply best params to dev set via stacking/run_stacking.py")
    print()
    print("Current status: framework ready, awaiting calib E1 predictions.")

    # Placeholder output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps({
        "status": "framework_ready",
        "note": "Run E1 on calib split first, then re-run this script."
    }, indent=2))


if __name__ == "__main__":
    main()
