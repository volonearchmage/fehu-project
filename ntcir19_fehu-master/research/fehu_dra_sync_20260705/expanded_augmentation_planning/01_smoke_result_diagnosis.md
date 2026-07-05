# Smoke Result Diagnosis — DRA-FEHU (Task-1b)

**Created at:** 2026-07-04T21:42:51
**Source run:** `output/research_ablation_smoke_runs/20260704_201355/` (both conditions exit 0, seed 42)

## 1. Result summary
| Metric | Baseline | Augmented | Delta |
|---|---|---|---|
| micro-F1 | 0.3023 | 0.3060 | +0.0037 |
| macro-F1 | 0.0305 | 0.0309 | +0.0004 |
| DRR | 0.2165 | 0.1620 | −0.0545 (rev 481→360) |
| L1=12 / L1=38 recall | 0 / 0 | 0 / 0 | 0 |

## 2. Why micro/macro-F1 moved only slightly
The 6 synthetic examples are **0.18% of the training set** (3341 actor-examples). The model is heavily
head-class-saturated: it predicts only **8 distinct direction:L1 labels in baseline and 7 in augmented**
(out of 108), blanket-predicting frequent labels (e.g., L1=27 "Have a stable society": 908–912
predictions ≈ both directions on every one of 456 dev instances). Micro-F1 is dominated by these head
labels, so a 6-example change cannot move it; macro-F1 ≈ 0.03 reflects that ~100 of 108 label classes
score zero in both conditions.

## 3. Why DRR improved substantially — the honest decomposition
Per-L1 reversal decomposition (computed from the prediction files with the authoritative
direction_mapping.json convention, 1=aligned / 0=contradictory):

| L1 | Reversals baseline → augmented |
|----|-------------------------------|
| 27 Have a stable society | 197 → 199 |
| **45 Be just** | **188 → 59** |
| 26 Have a safe country | 57 → 63 |
| 42 Be responsible | 30 → 30 |
| 37 Be helpful | 9 → 9 |

**The entire DRR gain comes from L1=45 "Be just"** — a label the augmentation never touched. The
augmented model halved its "Be just" prediction volume (912 → 456, i.e., it stopped predicting both
directions everywhere; recall for 45 dropped 1.0 → 0.67 as a side effect). The augmented run also
spontaneously began predicting L1=15 "Be courageous" (0 → 319 predictions, recall 0.86). Both changes
are best explained as **training-trajectory effects** (the two runs early-stopped at different epochs —
5 vs 11 — selecting different checkpoints), not as a direct causal effect of the 6 candidates.
**The earlier smoke report's DRR interpretation must therefore be tempered:** the DRR drop is real but
not attributable to the augmentation without multi-seed replication.

## 4. Why L1=12 and L1=38 recall stayed at 0
Each had only 1–2 synthetic examples per direction against a BCEWithLogits head with pos_weight capped
at 10 and threshold 0.3. Rare-class logits never cross the threshold — neither condition produces even
a false positive for these labels. The per-label example density was simply far below what class
emergence requires; 33 gold-supported labels with dev support ≥10 are predicted by neither condition.

## 5. Is 6 samples too small? Yes.
6 / 3341 ≈ 0.18% of training mass spread over 4 labels × 2 directions. For any rare label to emerge,
per-label density must rise by roughly an order of magnitude (3–6 accepted examples per
label/direction as the next increment), which is exactly what the expansion plan provides.

## 6. What the result supports
- The end-to-end controlled pipeline (derived inputs, seeding, checkpoint isolation, programmatic
  evaluation) **works and is auditable** — the +6 example delta was verifiably consumed (3335→3341).
- Continuing the **direction-contrastive design** is reasonable: it is unfalsified (no negative
  effect: micro/macro did not degrade), and the direction-consistency question remains the central
  thesis axis — but it now requires per-label density and multi-seed evidence.
- The expansion should prioritize **zero-recall labels with high dev support** so recall effects are
  measurable at all.

## 7. What the result does NOT support
- No claim that DRA-FEHU augmentation improves DRR (the DRR delta localizes to an untouched label).
- No claim of micro/macro-F1 improvement (within single-seed noise).
- No claim about rare-label recall (still zero everywhere).
- No generalization beyond this model/config/seed.
