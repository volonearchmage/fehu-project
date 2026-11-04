# Phase-0 Validation Report

**Date:** 2026-07-19
**Repository state:** branch `sync-safe-fehu-dra-20260705`, HEAD `6b6f4cc`
**Plan being executed:** `docs/FEHU_PROFESSOR_FEEDBACK_VALIDATION_PLAN.md`, Phase 0
**Workspace:** everything produced by this validation lives under `new_check/phase0/`; no file outside `new_check/` was created or modified. No model was trained, no inference was run, no API was called. All numbers below were recomputed from existing repository artifacts by `scripts/run_phase0.py` and `scripts/addendum_nontarget_gain.py`, and every recomputed headline metric was cross-checked against the officially documented value before any further analysis was allowed to proceed (tolerance 0.001; all six systems matched exactly — see `outputs/experiment_comparability.csv`).

---

## 1. What Phase 0 examined

Phase 0 answers, from existing artifacts only: (a) what the current experiments actually show for the 18 augmentation target labels, separately from the other labels, in all six metrics the professor asked for; (b) whether target gains came at the expense of other labels; (c) how severe the positive–negative imbalance is; (d) how much of the target failure is explained by the decision threshold rather than by learning; and (e) which conclusions are supported, which are confounded, and which need the Phase-2 training runs.

## 2. Existing artifacts used

| Artifact | Role |
|---|---|
| `dataset/gold_labels/dev/dev_human_values.json` | gold (456 instances, 2,390 Task-1b labels, 93 gold-supported classes of 108) |
| `output/research_ablation_smoke_runs/20260704_201355/baseline/output/pred_task1b.json` | DeBERTa official-only baseline predictions (threshold 0.3, seed 42) |
| `output/research_augmented_deberta_v1/20260712_231751/predictions/pred_task1b.json` | Augmented v1 (+340, assume-negative loss) |
| `output/research_augmented_deberta_v2_unfiltered/20260714_032758/predictions/pred_task1b.json` | Augmented v2 (+1,240, masked loss) |
| `output/task1/runs/dev_deepseek_…targeted_more_shot_balanced…/pred_task1b.json` | Liu frozen LLM run (context only) |
| `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/14_…h2.json`, `16_…h3.json` | Hybrid H2/H3 (context only) |
| `…20260714_184515/02_deberta_actor_probabilities.jsonl` | v2 dev probabilities (459 actor rows) — threshold analysis |
| `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/02_selected_targets_and_allocation.json` | frozen 18-target definition |
| `…v2_unfiltered/20260714_032758/inputs/{supervision_map.json, augmented_train_human_values_v2.json}` | ratio analysis (mask reconstruction) |
| `dataset/gold_labels/train/train_human_values.json`, official train articles | official positives; baseline-input provenance check |

Provenance checks performed before use: the smoke-run baseline's training-input copies are **content-identical** to the official train files (verified by full JSON comparison); the 18-target list is identical across three independent artifacts; thresholding the exported probabilities at 0.30 **exactly reproduces** the frozen v2 prediction file on all 456 gold instances (this also validates the class-index convention `idx = l1×2 + direction`).

## 3. How the 18 target labels are defined

Each target is a **direction-specific** Task-1b class `direction:l1` (direction `1` = aligned, `0` = contradictory, per `direction_mapping.json`): fourteen contradictory (0:31, 0:48, 0:53, 0:16, 0:19, 0:20, 0:13, 0:37, 0:29, 0:2, 0:33, 0:32, 0:40, 0:28) and four aligned (1:31, 1:10, 1:49, 1:4). Aligned and contradictory classes of the same L1 are never merged anywhere in this analysis. All 18 have dev gold support (3–21; total 140 gold instances-labels), so the "18-target" group is unaffected by zero-support conventions.

## 4. How the metrics were calculated

- **Instance rule, undefined values:** identical to `evaluation.py` — instances = gold ∪ predicted instance keys; any 0/0 division is 0.0.
- **Per-label counts:** TP/FP/FN per each of the 108 classes over all instances.
- **Group micro:** sums of TP/FP/FN over the group's labels only (a false positive on a non-group label does not enter that group's table).
- **Group macro:** unweighted mean of per-label precision, recall, and F1 (each label's F1 from its own P and R). Two variants: **gold-supported** (only labels with dev gold ≥ 1 — matches the official macro-F1 convention; verified to reproduce `evaluation.py`'s macro-F1 to machine precision) and **full-universe** (all group labels; the 15 dev classes with zero gold enter as R=0-denominator cases). The headline numbers below use the gold-supported variant; both are in the CSVs. For the target-18 group the two variants coincide (all 18 supported).
- **Reversals:** official gold-exclusive DRR logic, additionally attributed to the directed **gold** class, with the per-class sums verified to equal the official reversal counts exactly (denominator 2,222; 84 ambiguous gold values excluded, constant across systems).

## 5. Results for the 18 target labels

From `outputs/target18_group_metrics.csv` (all systems, dev):

| System | micro-P | micro-R | micro-F1 | macro-P | macro-R | macro-F1 | ΣTP | ΣFP | ΣFN |
|---|---|---|---|---|---|---|---|---|---|
| DeBERTa baseline | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 140 |
| Augmented v1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 140 |
| **Augmented v2** | 0.076 | 0.086 | **0.081** | 0.026 | 0.069 | **0.036** | 12 | 146 | 128 |
| Liu frozen (context) | 0.304 | 0.200 | 0.241 | 0.407 | 0.211 | 0.213 | 28 | 64 | 112 |
| Hybrid H2 (context) | 0.257 | 0.250 | 0.254 | 0.333 | 0.251 | 0.229 | 35 | 101 | 105 |
| Hybrid H3 (context) | 0.282 | 0.221 | 0.248 | 0.330 | 0.222 | 0.212 | 31 | 79 | 109 |

In plain language: **the baseline and v1 predict literally nothing on any of the 18 targets** (zero predictions, not merely zero correct). The v2 model recovers 12 of the 140 target gold labels, at the cost of 146 wrong target predictions — about one hit per thirteen tries. For context, the Liu LLM — which uses **no augmentation at all** — recovers 28 of 140 with far fewer false positives, and the hybrids recover the most (35 for H2). So even after augmentation, the student remains well below an un-augmented LLM on precisely the labels the augmentation targeted.

Per-target detail is in `outputs/per_target_18_metrics.csv`. Only 5 of 18 targets have any v2 true positive (1:10, 0:29, 0:2, 0:33, 0:28); 0:32 gets 18 predictions with zero correct; the remaining 12 targets still receive no predictions at all. These numbers agree exactly with the v2 run's own `metrics/target_label_metrics.csv`, which independently validates both computations.

## 6. Results for the 90 non-target labels

From `outputs/nontarget90_group_metrics.csv` (75 of the 90 are gold-supported):

| System | micro-P | micro-R | micro-F1 | macro-P | macro-R | macro-F1 |
|---|---|---|---|---|---|---|
| DeBERTa baseline | 0.266 | 0.371 | 0.310 | 0.025 | 0.092 | 0.038 |
| Augmented v1 | 0.306 | 0.314 | 0.310 | 0.024 | 0.068 | 0.032 |
| **Augmented v2** | 0.243 | 0.569 | **0.341** | 0.113 | 0.270 | **0.153** |
| Liu frozen (context) | 0.580 | 0.524 | 0.551 | 0.451 | 0.348 | 0.369 |
| Hybrid H2 (context) | 0.516 | 0.611 | 0.560 | 0.419 | 0.412 | 0.392 |
| Hybrid H3 (context) | 0.561 | 0.567 | 0.564 | 0.429 | 0.361 | 0.369 |

Answer to the professor's "at the expense of the other labels?" question: **no — the non-target group also improved** under v2 (micro-F1 0.310 → 0.341, macro-F1 0.038 → 0.153). The cost was paid in *precision*, not in other labels' F1: non-target false positives rose from 2,299 to 3,989 and non-target micro-precision fell 0.266 → 0.243.

A decomposition (`outputs/nontarget_gain_decomposition.csv`, summary JSON alongside) adds important nuance: 60 of the 75 gold-supported non-target classes **also received synthetic training positives** (round-1 records and round-2 secondary labels), so "non-target" does not mean "untouched by augmentation." Classes with synthetic positives gained on average ΔF1 +0.131; the 15 classes with zero synthetic positives gained +0.052 on average, and 4 of them improved substantially (e.g., 1:14 +0.364 with no synthetic data at all). Descriptively: part of the v2 improvement tracks synthetic exposure, and part is diffuse — consistent with the trajectory/supervision-policy change also contributing. This is descriptive, not causal (single seed, confounded run).

## 7. Results for all 108 labels

From `outputs/overall_metrics_all_systems.csv` — this is the first place all six professor-requested metrics exist for these systems (the official scorer reports macro-F1 only):

| System | micro-P | micro-R | micro-F1 | macro-P | macro-R | macro-F1 | DRR (rev/2222) | distinct classes |
|---|---|---|---|---|---|---|---|---|
| DeBERTa baseline | 0.266 | 0.349 | 0.302 | 0.020 | 0.074 | 0.031 | 0.217 (481) | 8 |
| Augmented v1 | 0.306 | 0.296 | 0.301 | 0.019 | 0.055 | 0.026 | 0.136 (303) | 6 |
| **Augmented v2** | 0.238 | 0.541 | 0.331 | 0.096 | 0.231 | 0.130 | 0.288 (640) | 50 |
| Liu frozen | 0.568 | 0.505 | 0.535 | 0.442 | 0.321 | 0.339 | 0.023 (51) | 88 |
| Hybrid H2 | 0.504 | 0.590 | 0.543 | 0.402 | 0.381 | 0.360 | 0.036 (79) | 89 |
| Hybrid H3 | 0.548 | 0.547 | 0.547 | 0.410 | 0.334 | 0.338 | 0.031 (69) | 85 |

Reading the new macro-P/R columns: v2's macro gain is recall-driven (macro-R 0.074 → 0.231) with macro-precision still very low (0.096); the LLM/hybrid systems are the opposite shape (macro-P ≈ 0.4). Zero-gold handling: the 15 classes with no dev gold cannot contribute recall; their false positives (10–15 for the LLM/hybrid systems, 0 for the DeBERTa systems) count in micro-precision and are itemized in `outputs/error_categories.csv`.

## 8. Important per-label findings

- The three headline "recovered" targets (0:2, 0:29, 0:28) each rest on 2–5 true positives against 26–36 false positives.
- v2's biggest per-class winners are **non-target** aligned classes with moderate support (1:29 ΔF1 +0.578, 1:11 +0.473, 1:12 +0.456) — classes the baseline ignored entirely (baseline predicts only 8 distinct classes).
- Direction reversals **on target gold labels rose under v2** (9 → 23 of the targets' 137 gold-exclusive values; `outputs/per_target_18_metrics.csv` has the per-class split): the model now predicts target L1 values more often but with the wrong direction more often too.

## 9. Positive–negative imbalance (professor's 50:50 comment)

From `outputs/pos_neg_ratio_table.csv`, reconstructed with the exact trainer mask semantics (positive / known-negative / unknown-masked; "excluded" is 0 everywhere — no trainer excludes slots outside the mask logic):

- Official training, per target class: positives 7–128 against ≈3,300 known negatives → ratios **1:475 (0:31) to 1:29 (0:28)**; global slot ratio ≈ **1:20**.
- After v2 augmentation: positives 55–177, known negatives ≈3,720–3,750, plus 765–770 *unknown* (masked) slots per class → ratios ≈ **1:44 to 1:68**.

So the professor's concern is quantitatively confirmed: even after augmentation, every target trains against ~50× more known negatives than positives, and the sqrt-clamped pos-weight (max 10) cannot compensate at the tail. The 50:50 heuristic cannot apply globally in a 108-class multi-label problem, but per-class effective balance is a legitimate intervention — the negative down-sampling experiments are specified in the validation plan (§9 there) and belong to Phase 2/3.

## 10. Threshold sensitivity (v2 only)

From `outputs/threshold_sensitivity_v2.csv` (global sweep) and `outputs/per_target_oracle_thresholds_v2.csv` (per-target, **dev-tuned oracle — diagnostic upper bound, not a performance claim**):

- Global: overall micro-F1 peaks at threshold 0.35 (0.3377, slightly above the frozen 0.3306); overall macro-F1 peaks at 0.25 (0.1356). Target-18 micro-F1 peaks at 0.25 but only reaches **0.095**. At threshold 0.05, target-18 micro-recall is 0.85 — the probability mass exists — but precision is 0.027.
- Per-target oracle: even choosing the best possible per-label threshold **on dev itself**, 12 of 18 targets stay below F1 0.15, and the best oracle F1 on any target is 0.25 (1:10). Median predicted probability on gold target instances ranges 0.018–0.26.

Plain-language interpretation, and an important refinement of the earlier review's headline: the previously cited "candidate recall 0.951 at threshold 0.10" was **direction-neutral and pooled over all labels**; at the per-target, direction-aware level Phase 0 shows the v2 model's target scores are *present but poorly separated* from negatives. Low target recall at 0.3 is therefore **partly** a threshold artifact (recall is recoverable) but **mostly** a learning/separation problem (precision is unrecoverable at any global or per-label threshold). Neither retuning thresholds alone nor the current augmentation, alone, produced usable target classifiers. The same analysis for the **baseline** model is impossible without exporting its probabilities (Phase 1, one local inference pass — `HUMAN_CHECK_REQUIRED`).

## 11. False positives, false negatives, and direction reversals

`outputs/error_categories.csv`, per system: v2 vs baseline — target FNs fall 140 → 128, target FPs rise 0 → 146, non-target FPs rise 2,299 → 3,989, total reversals rise 481 → 640 (of which target-gold reversals 9 → 23). The dominant v2 error category is **non-target false positives**, i.e., the model became a much broader, less precise predictor everywhere, not specifically a better target predictor.

## 12. Conclusions supported by existing evidence

1. Baseline and v1 predict nothing on all 18 targets; v2 predicts 5 of 18 with any success, weakly (per-target and group tables, exact-match validated).
2. The 18 targets did **not** improve at other labels' expense; the non-target group improved more (in macro terms) than the target group itself.
3. Every headline number in the project's reports reproduces exactly from the stored predictions; the artifacts are internally consistent (comparability table, all cross-checks passed).
4. The imbalance the professor suspected is real and quantified (1:29–1:475 before, ≈1:50 after augmentation).
5. v2's target scores are weakly separated: no threshold policy alone yields target F1 above 0.25 even with dev-oracle tuning.

## 13. Conclusions that remain confounded

- **Whether the 900 samples caused any of the v2 improvement.** v2 differs from baseline in data (+340 and +900 together) *and* supervision policy (masked loss), on one seed. The non-target decomposition (§6) even suggests part of the gain is unrelated to synthetic exposure. Nothing in Phase 0 can separate these.
- Whether v1's slight macro *decline* is a data-quality effect or an assume-negative artifact.
- Any comparison between the DeBERTa family and the Liu/hybrid systems with respect to augmentation (different model families and protocols; context only).

## 14. Questions that require new training runs

Exactly the factorized cells of the validation plan §8: official-only vs official+900 under each supervision policy (A / B / C), then the 340/1240 cells (D–G), ≥3 seeds, checkpoint/threshold selection on an internal split. Also the negative down-sampling arms (plan §9) and baseline probability export (Phase 1).

## 15. HUMAN_CHECK_REQUIRED items

Full details in `outputs/HUMAN_CHECK_REQUIRED.md`; summary:

1. **`evaluation.py` direction naming** — the DRR docstring calls "0" aligned while `direction_mapping.json` defines "1" = aligned. DRR arithmetic is symmetric (numbers unaffected); confirm the official semantic with the task documentation. *Interpretation only.*
2. **Baseline probabilities missing** — threshold analysis exists only for v2; approving one local inference pass from the stored baseline checkpoint (Phase 1) is required to complete the comparison. *Blocks the baseline threshold table.*
3. **LLM/hybrid rows are context, not augmentation evidence** — confirm they are presented that way to the professor. *Interpretation only.*
4. **3 non-gold dev actors** in the probabilities file were excluded from the sweep to match the frozen v2 protocol. *Interpretation only.*

## 16. Next validation step justified by Phase 0

Phase 0 shows the augmentation question is still open and sharpens it: the v2 improvement is real but diffuse, weakly concentrated on the targets, precision-poor, and inseparable from the supervision-policy change. The single most informative next steps are, in order: (1) **Phase 1** — export baseline dev probabilities (one local inference pass) to determine whether the baseline also carried latent target signal; (2) **Phase 2, cells C vs. A vs. B** — official-only vs. official+900 under both supervision policies, 3 seeds, internal-split selection, which directly answers the professor's "check precisely the effect of your augmentation on the target labels."

---

*Rerun everything with:*
```bash
python ntcir19_fehu-master/new_check/phase0/scripts/run_phase0.py
python ntcir19_fehu-master/new_check/phase0/scripts/addendum_nontarget_gain.py
```
