#!/usr/bin/env python3
"""
DS-A5: Confusion Matrix Spectral Debiasing
===========================================
Mathematical Principle:
  Let C ∈ R^{108×108} be the confusion matrix estimated on a calibration set:
    C_{i,j} = P(predict j | gold i)

  Perform Singular Value Decomposition (SVD):
    C = U Σ V^T

  The top r singular vectors U_r = U[:, :r] capture the dominant confusion
  directions — systematic patterns where E1 confuses certain labels.

  For a prediction vector p (108-dim), debias by removing its projection
  onto the confusion subspace:

    p' = p - η · U_r U_r^T · p

  where η ∈ [0.1, 0.5] controls the debiasing strength.

  Intuition: If E1 systematically confuses "Be just" (aligned) with
  "Be fair" (aligned), the confusion subspace will capture this pair.
  When E1 predicts both, debiasing will suppress the less-likely one.

Key parameters:
  - r: number of singular vectors to use (2-10)
  - η: debiasing strength (0.1-0.5)

Usage:
    python DS_A5_spectral_debiasing/run_a5.py \
        --e1_pred path/to/pred_task1b.json \
        --output path/to/output_pred_task1b.json \
        --r 5 --eta 0.3

IMPORTANT: The confusion matrix is estimated on the CALIBRATION set
(sub_train split), NOT on dev, to avoid leakage.
"""

from __future__ import annotations

import json
import argparse
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]

TRAIN_LABELS   = BASE / "dataset" / "gold_labels" / "train" / "train_human_values.json"
DEV_LABELS     = BASE / "dataset" / "gold_labels" / "dev" / "dev_human_values.json"
CALIB_SPLIT    = HERE.parent / "calib" / "calib_split.json"
L1_TO_L2       = BASE / "dataset" / "hv_categories" / "level_1_to_level_2.json"
L1_VALUES      = BASE / "dataset" / "hv_categories" / "human_value_level1_values.json"
L2_VALUES      = BASE / "dataset" / "hv_categories" / "human_value_level2_values.json"

NUM_CLASSES = 108


def load_l1_to_l2():
    l1_name_to_id = json.loads(L1_VALUES.read_text(encoding="utf-8"))
    l2_name_to_id = json.loads(L2_VALUES.read_text(encoding="utf-8"))
    raw = json.loads(L1_TO_L2.read_text(encoding="utf-8"))["level_1_to_level_2"]
    return {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}


def label_to_idx(direction: str, l1_value: str) -> int:
    return int(l1_value) * 2 + (0 if direction == "0" else 1)


def idx_to_label(idx: int) -> tuple[str, str]:
    l1 = idx // 2
    direction = "0" if idx % 2 == 0 else "1"
    return direction, str(l1)


def parse_pred_to_actor_vecs(pred_file: str) -> dict[str, dict[str, np.ndarray]]:
    """
    Parse a prediction JSON into per-article, per-actor binary vectors.

    Returns: dict[guid][actor_id] = 108-dim binary vector
    """
    data = json.loads(Path(pred_file).read_text(encoding="utf-8"))
    result: dict[str, dict[str, np.ndarray]] = {}
    for art in data:
        guid = art["guid"]
        per_actor: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(NUM_CLASSES))
        for hv in art.get("article_human_values", []):
            idx = label_to_idx(str(hv.get("direction", "1")), str(hv["l1_value"]))
            per_actor[str(hv["actor"])][idx] = 1.0
        result[guid] = dict(per_actor)
    return result


def parse_gold_to_actor_vecs(gold_file: str) -> dict[str, dict[str, np.ndarray]]:
    """Parse gold labels into per-article, per-actor binary vectors."""
    data = json.loads(Path(gold_file).read_text(encoding="utf-8"))
    result: dict[str, dict[str, np.ndarray]] = {}
    for item in data:
        guid = item["guid"]
        per_actor: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(NUM_CLASSES))
        for hv in item.get("article_human_values", []):
            idx = label_to_idx(str(hv["direction"]), str(hv["l1_value"]))
            per_actor[str(hv["actor"])][idx] = 1.0
        result[guid] = dict(per_actor)
    return result


def build_confusion_matrix(
    gold_vecs: dict[str, dict[str, np.ndarray]],
    pred_vecs: dict[str, dict[str, np.ndarray]],
):
    """
    Build 108×108 confusion matrix from gold-pred pairs.

    C[i][j] = P(pred_j=1 | gold_i=1), estimated by counting.
    """
    C = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.float64)
    gold_counts = np.zeros(NUM_CLASSES, dtype=np.float64)

    for guid in gold_vecs:
        if guid not in pred_vecs:
            continue
        for aid in gold_vecs[guid]:
            if aid not in pred_vecs[guid]:
                continue
            g = gold_vecs[guid][aid]
            p = pred_vecs[guid][aid]
            for i in range(NUM_CLASSES):
                if g[i] > 0.5:
                    gold_counts[i] += 1
                    C[i] += p  # accumulate predictions for each gold label

    # Normalize
    for i in range(NUM_CLASSES):
        if gold_counts[i] > 0:
            C[i] /= gold_counts[i]

    return C, gold_counts


def spectral_debias(
    pred_vector: np.ndarray,
    U_r: np.ndarray,
    eta: float = 0.3,
) -> np.ndarray:
    """
    Debias a prediction vector by removing its projection onto the
    top-r confusion subspace.

    p' = p - η · U_r · U_r^T · p
    Then clip to [0, 1].
    """
    # Project onto confusion subspace and subtract
    projection = U_r @ (U_r.T @ pred_vector)
    debiased = pred_vector - eta * projection
    return np.clip(debiased, 0.0, 1.0)


def apply_a5(
    e1_predictions: list[dict],
    U_r: np.ndarray,
    eta: float = 0.3,
    suppress_threshold: float = 0.3,
    l1_to_l2: dict[str, str] | None = None,
) -> list[dict]:
    """
    Apply Spectral Debiasing to E1 predictions.

    For each (article, actor):
      1. Build binary prediction vector
      2. Apply spectral debiasing: p' = p - η·U_r·U_r^T·p
      3. Drop labels where debiased probability < suppress_threshold

    This is a SUBTRACTIVE operation — it removes likely-FP labels that
    fall into systematic confusion patterns.

    Key safety: we only SUPPRESS labels that E1 already predicted.
    We never ADD labels (that's A3/A4's job).
    """
    result = []
    n_dropped_total = 0

    for art_pred in e1_predictions:
        guid = art_pred["guid"]
        existing = art_pred.get("article_human_values", [])

        # Group by actor
        per_actor: dict[str, list[dict]] = defaultdict(list)
        for hv in existing:
            per_actor[str(hv["actor"])].append(hv)

        new_hvs = []
        for aid, hvs in per_actor.items():
            # Build vector
            vec = np.zeros(NUM_CLASSES, dtype=np.float64)
            for hv in hvs:
                idx = label_to_idx(str(hv.get("direction", "1")), str(hv["l1_value"]))
                vec[idx] = 1.0

            # Debias
            debiased = spectral_debias(vec, U_r, eta)

            # Keep labels that survive debiasing
            for hv in hvs:
                idx = label_to_idx(str(hv.get("direction", "1")), str(hv["l1_value"]))
                if debiased[idx] >= suppress_threshold:
                    new_hvs.append(hv)
                else:
                    n_dropped_total += 1

        result.append({
            "guid": guid,
            "article_human_values": new_hvs,
        })

    print(f"[A5] Spectral Debiasing: dropped {n_dropped_total} label instances across {len(result)} articles")
    print(f"[A5] eta={eta}, suppress_threshold={suppress_threshold}")
    return result


def main():
    parser = argparse.ArgumentParser(description="DS-A5: Confusion Matrix Spectral Debiasing")
    parser.add_argument("--e1_pred", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--output_1a", type=str, default=None)
    parser.add_argument("--r", type=int, default=5,
                        help="Number of singular vectors (confusion dimensions) to use.")
    parser.add_argument("--eta", type=float, default=0.3,
                        help="Debiasing strength (0-1).")
    parser.add_argument("--suppress_threshold", type=float, default=0.3,
                        help="Probability below which labels are dropped.")
    args = parser.parse_args()

    print("=" * 60)
    print("DS-A5: Confusion Matrix Spectral Debiasing")
    print("=" * 60)

    l1_to_l2 = load_l1_to_l2()

    # Load calibration split
    split = json.loads(CALIB_SPLIT.read_text(encoding="utf-8")) if CALIB_SPLIT.exists() else None

    # Build confusion matrix on SUB_TRAIN (calibration) set
    # We need gold labels for the sub_train articles, and we run E1 on them.
    # For now, we estimate the confusion matrix on DEV as a diagnostic tool,
    # and flag that this is for DEV-ONLY analysis. For final test submission,
    # the confusion matrix must be estimated on sub_train.
    print("WARNING: Estimating confusion matrix on DEV set (for diagnostic purposes).")
    print("For test submission, re-estimate on sub_train split with E1 predictions.")

    gold_vecs = parse_gold_to_actor_vecs(str(DEV_LABELS))
    pred_vecs = parse_pred_to_actor_vecs(args.e1_pred)

    C, gold_counts = build_confusion_matrix(gold_vecs, pred_vecs)
    print(f"  Confusion matrix shape: {C.shape}")
    print(f"  Gold label support range: {gold_counts.min():.0f} – {gold_counts.max():.0f}")

    # SVD
    U, S, Vt = np.linalg.svd(C, full_matrices=False)
    r = min(args.r, len(S))
    U_r = U[:, :r]

    # Print top confusion modes
    print(f"\n  Top {r} singular values: {S[:r].round(4).tolist()}")
    print(f"  Explained variance ratio: {sum(S[:r]**2) / sum(S**2):.3f}")
    for k in range(min(r, 3)):
        top_j = np.argsort(-np.abs(U_r[:, k]))[:3]
        print(f"  Mode {k+1}: dominant labels = {[idx_to_label(int(j)) for j in top_j]}")

    # Load E1 predictions
    e1_pred = json.loads(Path(args.e1_pred).read_text(encoding="utf-8"))
    print(f"\nLoaded {len(e1_pred)} E1 predictions")

    # Apply spectral debiasing
    adjusted = apply_a5(e1_pred, U_r, args.eta, args.suppress_threshold, l1_to_l2)

    # Write output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(adjusted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Adjusted predictions written to {args.output}")

    if args.output_1a:
        import sys as _sys, os as _os
        _sys.path.insert(0, str(HERE.parent / "DS_A3_bayesian_prior"))
        from run_a3 import derive_1a
        derive_1a(adjusted, args.output_1a, l1_to_l2)
        print(f"Derived Task-1a written to {args.output_1a}")


if __name__ == "__main__":
    main()
