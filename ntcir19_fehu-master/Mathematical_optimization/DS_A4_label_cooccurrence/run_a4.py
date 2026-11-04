#!/usr/bin/env python3
"""
DS-A4: Label Co-occurrence Graph Regularization
================================================
Mathematical Principle:
  Build a label co-occurrence graph G = (V, E) from training data, where
  edge weight w_{ij} = P(label_j = 1 | label_i = 1) — the conditional
  probability that label j co-occurs with label i for the same actor.

  Given E1's discrete prediction vector p (108-dim binary), apply graph
  diffusion to "spread" predictions to related labels:

    p^{(0)} = p_E1
    p^{(t+1)} = (1 - α) · p^{(0)} + α · D^{-1/2} W D^{-1/2} · p^{(t)}

  After T iterations, apply threshold τ_diffuse to recover binary predictions.

  The intuition: If E1 predicts "Be just" (label i), and "Be fair" (label j)
  strongly co-occurs with "Be just" in training, graph diffusion will boost
  the probability of "Be fair" — potentially recovering missed labels.

Key parameters:
  - α: diffusion strength (0.1–0.5) — how much we trust the graph vs. E1
  - T: diffusion steps (1–5) — how far the signal propagates
  - τ_diffuse: threshold for accepting diffused labels (0.4–0.7)

Usage:
    python DS_A4_label_cooccurrence/run_a4.py \
        --e1_pred path/to/pred_task1b.json \
        --output path/to/output_pred_task1b.json \
        --alpha 0.3 --t_steps 3 --threshold 0.5
"""

from __future__ import annotations

import json
import argparse
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]

TRAIN_LABELS = BASE / "dataset" / "gold_labels" / "train" / "train_human_values.json"
CALIB_SPLIT  = HERE.parent / "calib" / "calib_split.json"
L1_TO_L2     = BASE / "dataset" / "hv_categories" / "level_1_to_level_2.json"
L1_VALUES    = BASE / "dataset" / "hv_categories" / "human_value_level1_values.json"
L2_VALUES    = BASE / "dataset" / "hv_categories" / "human_value_level2_values.json"

NUM_CLASSES = 108  # 54 L1 × 2 directions


def load_l1_to_l2():
    l1_name_to_id = json.loads(L1_VALUES.read_text(encoding="utf-8"))
    l2_name_to_id = json.loads(L2_VALUES.read_text(encoding="utf-8"))
    raw = json.loads(L1_TO_L2.read_text(encoding="utf-8"))["level_1_to_level_2"]
    return {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}


def label_to_idx(direction: str, l1_value: str) -> int:
    """Map (direction, l1_value) → index in [0, 107]."""
    return int(l1_value) * 2 + (0 if direction == "0" else 1)


def idx_to_label(idx: int) -> tuple[str, str]:
    """Map index → (direction, l1_value)."""
    l1 = idx // 2
    direction = "0" if idx % 2 == 0 else "1"
    return direction, str(l1)


def build_cooccurrence_matrix(train_labels, use_calib_only=True):
    """
    Build 108×108 co-occurrence matrix from training data.

    For each (article, actor), count which labels co-occur.
    w_{ij} = P(label_j=1 | label_i=1) = count(i,j both 1) / count(i=1)

    Co-occurrence is measured WITHIN the same actor (per-actor label sets).
    """
    if use_calib_only and CALIB_SPLIT.exists():
        split = json.loads(CALIB_SPLIT.read_text(encoding="utf-8"))
        split_map = split["split_map"]
    else:
        split_map = {}

    # Aggregate per-actor label sets
    cooccur_count = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.float64)
    label_count = np.zeros(NUM_CLASSES, dtype=np.float64)

    for item in train_labels:
        guid = item["guid"]
        if use_calib_only and split_map.get(guid) == "calib":
            continue

        # Group labels by actor
        per_actor: dict[str, set[int]] = defaultdict(set)
        for hv in item.get("article_human_values", []):
            idx = label_to_idx(str(hv["direction"]), str(hv["l1_value"]))
            per_actor[str(hv["actor"])].add(idx)

        for aid, label_set in per_actor.items():
            label_list = list(label_set)
            for i in label_list:
                label_count[i] += 1
                for j in label_list:
                    cooccur_count[i][j] += 1

    # Normalize to conditional probabilities
    W = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.float64)
    for i in range(NUM_CLASSES):
        if label_count[i] > 0:
            W[i] = cooccur_count[i] / label_count[i]

    # Apply Laplace smoothing for unseen pairs
    W = 0.99 * W + 0.01 / NUM_CLASSES
    # Add self-loops to ensure every node has at least self-connection
    np.fill_diagonal(W, np.maximum(np.diag(W), 0.01))

    return W, label_count


def graph_diffusion(
    pred_vector: np.ndarray,
    W: np.ndarray,
    alpha: float = 0.3,
    T: int = 3,
) -> np.ndarray:
    """
    Apply graph diffusion to a prediction vector using random-walk normalization.

    p^{(0)} = pred_vector (binary, 108-dim)
    S = D^{-1} W  — row-normalized adjacency (random walk)
    p^{(t+1)} = (1-α)·p^{(0)} + α·S·p^{(t)}
    """
    # Row-normalized adjacency (random walk Laplacian) — numerically stable
    D = W.sum(axis=1, keepdims=True)
    D = np.maximum(D, 1e-8)  # avoid division by zero
    S = W / D  # each row sums to 1
    S = np.nan_to_num(S, nan=0.0, posinf=0.0, neginf=0.0)

    p = pred_vector.astype(np.float64).copy()
    p0 = p.copy()

    for _ in range(T):
        p_new = (1 - alpha) * p0 + alpha * (S @ p)
        p_new = np.nan_to_num(p_new, nan=0.0, posinf=1.0, neginf=0.0)
        p = np.clip(p_new, 0.0, 1.0)

    return p


def apply_a4(
    e1_predictions: list[dict],
    W: np.ndarray,
    alpha: float = 0.3,
    T: int = 3,
    threshold: float = 0.5,
    l1_to_l2: dict[str, str] | None = None,
) -> list[dict]:
    """
    Apply Label Co-occurrence Graph Regularization to E1 predictions.

    For each article:
      1. Build 108-dim binary vector from E1 predictions
      2. Apply graph diffusion
      3. Accept labels where diffused probability > threshold
      4. Keep ALL original E1 predictions (graph only ADDS, never removes)
    """
    result = []
    n_added_total = 0

    for art_pred in e1_predictions:
        guid = art_pred["guid"]
        existing = art_pred.get("article_human_values", [])

        # Build per-actor prediction vectors
        per_actor_preds: dict[str, list[dict]] = defaultdict(list)
        per_actor_vec: dict[str, np.ndarray] = {}

        for hv in existing:
            aid = str(hv["actor"])
            per_actor_preds[aid].append(hv)

        for aid, hvs in per_actor_preds.items():
            vec = np.zeros(NUM_CLASSES, dtype=np.float64)
            for hv in hvs:
                idx = label_to_idx(str(hv.get("direction", "1")), str(hv["l1_value"]))
                vec[idx] = 1.0
            per_actor_vec[aid] = vec

        # Apply diffusion per actor
        new_hvs = list(existing)
        existing_set = {
            (str(hv["actor"]), str(hv.get("direction", "1")), str(hv["l1_value"]))
            for hv in existing
        }

        for aid, vec in per_actor_vec.items():
            diffused = graph_diffusion(vec, W, alpha, T)

            for idx in range(NUM_CLASSES):
                if diffused[idx] > threshold and vec[idx] < 0.5:
                    # This label was NOT in E1's original prediction but
                    # graph diffusion boosted it above threshold → ADD
                    direction, l1_id = idx_to_label(idx)
                    key = (aid, direction, l1_id)
                    if key not in existing_set:
                        new_hvs.append({
                            "actor": aid,
                            "l1_value": l1_id,
                            "direction": direction,
                        })
                        existing_set.add(key)
                        n_added_total += 1

        result.append({
            "guid": guid,
            "article_human_values": new_hvs,
        })

    print(f"[A4] Graph Diffusion: added {n_added_total} label instances across {len(result)} articles")
    print(f"[A4] alpha={alpha}, T={T}, threshold={threshold}")
    return result


def main():
    parser = argparse.ArgumentParser(description="DS-A4: Label Co-occurrence Graph Regularization")
    parser.add_argument("--e1_pred", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--output_1a", type=str, default=None)
    parser.add_argument("--alpha", type=float, default=0.3,
                        help="Diffusion strength (0-1). Higher = more trust in graph.")
    parser.add_argument("--t_steps", type=int, default=3,
                        help="Number of diffusion steps (1-5).")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Threshold for accepting diffused labels (0-1).")
    parser.add_argument("--use_full_train", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("DS-A4: Label Co-occurrence Graph Regularization")
    print("=" * 60)

    l1_to_l2 = load_l1_to_l2()

    # Load training labels for co-occurrence estimation
    train_labels = json.loads(TRAIN_LABELS.read_text(encoding="utf-8"))
    print("Building co-occurrence matrix...")
    W, label_counts = build_cooccurrence_matrix(train_labels, use_calib_only=not args.use_full_train)
    print(f"  Matrix shape: {W.shape}")
    print(f"  Sparsity: {(W > 0.01).sum() / (NUM_CLASSES * NUM_CLASSES):.3f}")

    # Load E1 predictions
    e1_pred = json.loads(Path(args.e1_pred).read_text(encoding="utf-8"))
    print(f"Loaded {len(e1_pred)} E1 predictions")

    # Apply graph diffusion
    adjusted = apply_a4(e1_pred, W, args.alpha, args.t_steps, args.threshold, l1_to_l2)

    # Write output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(adjusted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Adjusted predictions written to {args.output}")

    if args.output_1a:
        import sys, os
        sys.path.insert(0, str(HERE.parent / "DS_A3_bayesian_prior"))
        from run_a3 import derive_1a
        derive_1a(adjusted, args.output_1a, l1_to_l2)
        print(f"Derived Task-1a written to {args.output_1a}")


if __name__ == "__main__":
    main()
