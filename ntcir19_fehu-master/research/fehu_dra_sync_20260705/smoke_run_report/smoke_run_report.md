# DRA-FEHU Controlled Smoke Run — Final Report

**Run folder:** `output/research_ablation_smoke_runs/20260704_201355/`
**Created at:** 2026-07-04T20:35:00
**Status:** Both conditions completed successfully (exit 0 / exit 0). This is a controlled smoke run /
initial A/B run — **not** the final thesis ablation result.

## 1. Experiment purpose
First end-to-end test of the DRA-FEHU hypothesis: does adding a small, verified, direction-consistent
augmentation set (6 human-accepted candidates) to the official training data change actor-level
Task-1b behavior — especially rare-label recall (L1=12 "Have success", L1=38 "Be honest") and
direction consistency (DRR) — under otherwise identical conditions?

## 2. Conditions
- **A Baseline:** derived exact copy of official train (1228 articles → 3335 actor-examples).
- **B Augmented:** official train + 6 verified synthetic candidates (1234 articles → 3341 actor-examples).

## 3. What was controlled (identical A vs B)
Same model (DeBERTa-v3-base + LoRA r=16), same code (`src/train_deberta.py`, sha-verified unchanged),
same hyperparameters (bs=8, accum=4, ≤15 epochs, lr=2e-4, patience=4, threshold=0.3), **same seed=42**,
same official dev evaluation (456 examples), same programmatic evaluator functions.
**The only changed factor:** +6 verified synthetic training examples.

## 4. Key metrics (official dev, Task-1b)

| Metric | Baseline | Augmented | Delta |
|--------|----------|-----------|-------|
| micro-F1 | 0.3023 | 0.3060 | **+0.0037** |
| macro-F1 | 0.0305 | 0.0309 | +0.0004 |
| micro-P / micro-R | 0.2664 / 0.3494 | 0.2727 / 0.3485 | +0.006 / −0.001 |
| **Direction Reverse Rate** | **0.2165** | **0.1620** | **−0.0545 (−25% rel.)** |
| Direction reversals (of 2222 gold-exclusive) | 481 | 360 | −121 |
| Predicted labels | 3134 | 3055 | −79 |
| Exact matches (TP) | 835 | 833 | −2 |
| L1=12 recall (aligned / contradictory) | 0.0 / 0.0 | 0.0 / 0.0 | 0 |
| L1=38 recall (aligned / contradictory) | 0.0 / 0.0 | 0.0 / 0.0 | 0 |

## 5. Interpretation (no overclaiming)
- **The pipeline works end-to-end**: explicit derived train paths, seeding, checkpoint isolation, and
  programmatic evaluation all functioned; the +6-example delta is visible in the data loader
  (3335→3341), proving the augmented file was really trained on.
- **Direction consistency moved in the hypothesized direction**: DRR dropped 25% relative (481→360
  reversals) with slightly higher precision and ~2 fewer TPs. This is the most interesting signal, and
  it is *consistent with* the direction-contrastive augmentation rationale — but with a single seed and
  different early-stop epochs (5 vs 11), training noise cannot be ruled out as the cause.
- **The rare-label recall target was NOT achieved**: neither condition ever predicts L1=12 or L1=38 on
  dev (recall 0, and no false positives — the classes are simply never above threshold). Six examples
  are evidently far too few to lift rare classes in a 108-way multi-label head, and overall macro-F1
  (~0.03) shows the model concentrates on a handful of frequent labels.
- micro/macro-F1 changes are within plausible single-seed noise; do not cite them as improvement.

## 6. Limitations
1. Only **6 verified candidates** — far below the density needed for rare-class emergence.
2. **Single seed (42)**; early-stopping selected different epochs (5 vs 11), so the compared checkpoints
   differ in training length as well as data.
3. Smoke/initial run — **not** the final thesis ablation result; no significance claims.
4. DRR caveat: the aggregate DRR from `evaluation.py` is numerically correct, but per-direction
   decomposition must use `direction_mapping.json` (1=aligned, 0=contradictory), not the evaluator's
   internal variable names.

## 7. Recommended next step
The run was technically successful but **inconclusive for the rare-label goal**. Recommended:
**expand the verified candidate pool to 20–40 candidates** (same verify-first workflow: generation →
AI-assisted semantic verification → human ACCEPT → pool update), concentrating on L1=12/L1=38 and other
diagnosed rare labels, then repeat this A/B protocol with **3–5 seeds** and report mean±std for
micro/macro-F1, DRR, and per-target recall. The DRR signal (−25% relative) justifies continuing the
direction-contrastive line; multi-seed replication is required before any thesis claim.
