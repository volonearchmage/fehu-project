#!/usr/bin/env python3
"""
DS Stacking Pipeline: A3 → A4 → A5 Sequential Post-Processing
==============================================================
Applies the three mathematical post-processing methods in sequence:
  1. A3 (Bayesian Actor-Type Prior)    — ADD potentially missed labels
  2. A4 (Label Co-occurrence Graph)    — ADD related co-occurring labels
  3. A5 (Spectral Debiasing)           — REMOVE systematic false positives

Each stage reads the output of the previous stage.
The order A3→A4→A5 is principled:
  - A3 first: uses external prior knowledge (actor types) independent of
    the prediction structure
  - A4 second: uses internal structure (co-occurrence) that benefits from
    A3's additions
  - A5 last: removes confusion artifacts, which is safest after all
    additions are complete

Usage:
    python stacking/run_stacking.py \
        --e1_pred_1b path/to/E1_pred_task1b.json \
        --e1_pred_1a path/to/E1_pred_task1a.json \
        --output_dir stacking/outputs/ \
        --alpha_add 2.0 --alpha_diffuse 0.3 --t_steps 3 --threshold 0.5 \
        --r 5 --eta 0.3
"""

from __future__ import annotations

import json
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]

# Import the three method modules
sys.path.insert(0, str(HERE.parent))

from DS_A3_bayesian_prior.run_a3 import (
    estimate_priors, bayesian_adjust, derive_1a, load_l1_to_l2 as load_l1_to_l2_a3,
)
from DS_A4_label_cooccurrence.run_a4 import (
    build_cooccurrence_matrix, apply_a4,
)
from DS_A5_spectral_debiasing.run_a5 import (
    build_confusion_matrix, apply_a5,
    parse_gold_to_actor_vecs, parse_pred_to_actor_vecs,
)

TRAIN_ARTICLES = BASE / "dataset" / "train" / "train_event_base.json"
TRAIN_LABELS   = BASE / "dataset" / "gold_labels" / "train" / "train_human_values.json"
DEV_LABELS     = BASE / "dataset" / "gold_labels" / "dev" / "dev_human_values.json"


def main():
    parser = argparse.ArgumentParser(
        description="DS Stacking: A3 → A4 → A5 sequential post-processing")
    parser.add_argument("--e1_pred_1b", type=str, required=True,
                        help="Path to E1 pred_task1b.json")
    parser.add_argument("--e1_pred_1a", type=str, required=True,
                        help="Path to E1 pred_task1a.json")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Output directory for all stage outputs")
    # A3 params
    parser.add_argument("--alpha_add", type=float, default=2.0,
                        help="A3: Bayes Factor threshold")
    # A4 params
    parser.add_argument("--alpha_diffuse", type=float, default=0.3,
                        help="A4: Graph diffusion strength")
    parser.add_argument("--t_steps", type=int, default=3,
                        help="A4: Diffusion steps")
    parser.add_argument("--graph_threshold", type=float, default=0.5,
                        help="A4: Threshold for accepting diffused labels")
    # A5 params
    parser.add_argument("--r", type=int, default=5,
                        help="A5: Number of singular vectors")
    parser.add_argument("--eta", type=float, default=0.3,
                        help="A5: Debiasing strength")
    parser.add_argument("--suppress_threshold", type=float, default=0.3,
                        help="A5: Suppression threshold")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("DS STACKING PIPELINE: A3 → A4 → A5")
    print("=" * 70)

    # ── Load shared resources ──────────────────────────────────────────
    l1_to_l2 = load_l1_to_l2_a3()
    train_articles = json.loads(TRAIN_ARTICLES.read_text(encoding="utf-8"))
    train_labels   = json.loads(TRAIN_LABELS.read_text(encoding="utf-8"))
    e1_pred_1b = json.loads(Path(args.e1_pred_1b).read_text(encoding="utf-8"))
    e1_pred_1a = json.loads(Path(args.e1_pred_1a).read_text(encoding="utf-8"))

    print(f"E1 baseline: {len(e1_pred_1b)} articles")
    n_labels_1b = sum(len(a.get("article_human_values", [])) for a in e1_pred_1b)
    print(f"  Task-1b labels: {n_labels_1b}")

    # ── Stage 1: A3 — Bayesian Actor-Type Prior ───────────────────────
    print("\n" + "-" * 50)
    print("STAGE 1/3: DS-A3 Bayesian Actor-Type Prior")
    print("-" * 50)
    t0 = time.time()

    prior_given_type, prior_global, type_totals, global_total = estimate_priors(
        train_articles, train_labels, use_calib_only=True
    )
    s1_pred_1b = bayesian_adjust(
        e1_pred_1b, prior_given_type, prior_global,
        type_totals, global_total, args.alpha_add, l1_to_l2,
    )
    n_s1 = sum(len(a.get("article_human_values", [])) for a in s1_pred_1b)
    s1_path_1b = out_dir / "stage1_a3_pred_task1b.json"
    s1_path_1a = out_dir / "stage1_a3_pred_task1a.json"
    s1_path_1b.write_text(json.dumps(s1_pred_1b, indent=2, ensure_ascii=False))
    derive_1a(s1_pred_1b, str(s1_path_1a), l1_to_l2)

    s1_delta = n_s1 - n_labels_1b
    print(f"  Labels: {n_labels_1b} → {n_s1} (Δ = {s1_delta:+d})")
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Stage 2: A4 — Label Co-occurrence Graph ───────────────────────
    print("\n" + "-" * 50)
    print("STAGE 2/3: DS-A4 Label Co-occurrence Graph")
    print("-" * 50)
    t0 = time.time()

    W, label_counts = build_cooccurrence_matrix(train_labels, use_calib_only=True)
    s2_pred_1b = apply_a4(
        s1_pred_1b, W, args.alpha_diffuse, args.t_steps,
        args.graph_threshold, l1_to_l2,
    )
    n_s2 = sum(len(a.get("article_human_values", [])) for a in s2_pred_1b)
    s2_path_1b = out_dir / "stage2_a4_pred_task1b.json"
    s2_path_1a = out_dir / "stage2_a4_pred_task1a.json"
    s2_path_1b.write_text(json.dumps(s2_pred_1b, indent=2, ensure_ascii=False))
    derive_1a(s2_pred_1b, str(s2_path_1a), l1_to_l2)

    s2_delta = n_s2 - n_s1
    print(f"  Labels: {n_s1} → {n_s2} (Δ = {s2_delta:+d})")
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Stage 3: A5 — Spectral Debiasing ──────────────────────────────
    print("\n" + "-" * 50)
    print("STAGE 3/3: DS-A5 Spectral Debiasing")
    print("-" * 50)
    t0 = time.time()

    # Estimate confusion matrix on DEV (diagnostic) or SUB_TRAIN
    # For now, use DEV for diagnostics — flag clearly
    print("  [NOTE] Confusion matrix estimated on DEV (diagnostic mode).")
    gold_vecs = parse_gold_to_actor_vecs(str(DEV_LABELS))
    pred_vecs = parse_pred_to_actor_vecs(str(s2_path_1b))
    C, gold_counts = build_confusion_matrix(gold_vecs, pred_vecs)

    import numpy as np
    U, S, Vt = np.linalg.svd(C, full_matrices=False)
    r_actual = min(args.r, len(S))
    U_r = U[:, :r_actual]

    s3_pred_1b = apply_a5(
        s2_pred_1b, U_r, args.eta, args.suppress_threshold, l1_to_l2,
    )
    n_s3 = sum(len(a.get("article_human_values", [])) for a in s3_pred_1b)
    s3_path_1b = out_dir / "stage3_a5_final_pred_task1b.json"
    s3_path_1a = out_dir / "stage3_a5_final_pred_task1a.json"
    s3_path_1b.write_text(json.dumps(s3_pred_1b, indent=2, ensure_ascii=False))
    derive_1a(s3_pred_1b, str(s3_path_1a), l1_to_l2)

    s3_delta = n_s3 - n_s2
    print(f"  Labels: {n_s2} → {n_s3} (Δ = {s3_delta:+d})")
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STACKING SUMMARY")
    print("=" * 70)
    print(f"{'Stage':<12} {'Labels':>8} {'Delta':>8}")
    print(f"{'E1 baseline':<12} {n_labels_1b:>8}")
    print(f"{'A3 (prior)':<12} {n_s1:>8} {s1_delta:>+8}")
    print(f"{'A4 (graph)':<12} {n_s2:>8} {s2_delta:>+8}")
    print(f"{'A5 (spectral)':<12} {n_s3:>8} {s3_delta:>+8}")
    print(f"{'Net change':<12} {n_s3 - n_labels_1b:>+8}")
    print(f"\nAll outputs in: {out_dir}")


if __name__ == "__main__":
    main()
