# Phase-3 Report — Full-Data Supervision Comparison and Target-Class Negative Down-Sampling

**Date:** 2026-07-20
**Follows:** Phase-0/1/2 reports under `new_check/`
**Workspace:** everything new is under `new_check/phase3/` (12 training runs, probability exports, analysis outputs, this report). The frozen masked trainer, all Phase-2 artifacts, and every historical artifact are retained untouched; the masked-supervision implementation is used unmodified in stage 1 and extended only in a Phase-3 **copy** (`scripts/train_phase3_negsample.py`) for stage 2.

---

## 1. Design

**Stage 1 — full 1,240-record data, both supervision policies (3 seeds each):**

| Cell | Data | Supervision | Notes |
|---|---|---|---|
| **F′** | official + 340 + 900 (the v2 run's own input files, read-only) | **masked** (790 target_only, 3,785 full) | byte-for-byte the historical v2 configuration; seed 42 doubles as a replication probe |
| **G′** | same files | **assume-negative** (empty map) | the configuration Phase 2's B-result predicted to be best; never previously trained |

**Stage 2 — target-class negative down-sampling on the stage-1 winner (masked), 3 seeds each:**

| Cell | Ratio (per target class) | Mechanism |
|---|---|---|
| **N3** | 1 : 3 positives:negatives | for each of the 18 target classes, keep a random `ceil(3×n_pos)` subset of its supervised negatives, mask the rest out of the loss (positives, hard-negative known-negatives, and unknown/masked slots untouched; dedicated RNG so the example stream is unchanged) |
| **N1** | 1 : 1 | same, `ceil(1×n_pos)` |

All runs: seeds 42/43/44, identical protocol to Phases 2 (≤15 epochs, patience 4 on dev 1b micro-F1, threshold 0.3, same LoRA/optimizer). Down-sampling summaries in the logs confirm exact per-class counts (e.g., 0:31: 62 positives, 3,748 → 186 kept negatives), matching the Phase-0 ratio table. All 12 probability exports hard-validated (0.30-thresholding reproduces each run's own frozen predictions). Full tables: `outputs/per_run_metrics.csv` (all micro/macro P/R/F1 for target-18 / non-target-90 / all-108, DRR, reversals, AUC, oracle), `per_target_per_run.csv`, `cell_aggregates.csv`, `paired_contrasts.csv`, `summary.json`.

## 2. Stage-1 results — masked vs. assume-negative at full data

Mean ± SD over 3 seeds (dev; full six-metric tables in the CSVs):

| Metric | **F′ masked** | **G′ assume-negative** |
|---|---|---|
| all-108 micro-F1 | **0.3211** ± 0.0343 | 0.3030 ± 0.0025 |
| all-108 macro-F1 | **0.0878** ± 0.0844 | 0.0779 ± 0.0126 |
| target-18 micro-F1 | **0.0447** ± 0.0774 | 0.0260 ± 0.0355 |
| target-18 macro-F1 | **0.0258** ± 0.0403 | 0.0057 ± 0.0080 |
| target-18 TP (of 140) | **12.3** (0 / 0 / 37) | 2.7 (0 / 1 / 7) |
| mean target AUC | **0.632** ± 0.105 | 0.598 ± 0.021 |
| mean target oracle-F1 | **0.111** ± 0.049 | 0.079 ± 0.011 |
| DRR (lower better) | **0.177** ± 0.095 | 0.285 ± 0.030 |

**Findings:**

1. **The historical v2 result is *not* exactly reproducible, but is reproducible in distribution.** F′ seed 42 — the same trainer, data files, supervision map, and seed as the historical v2 run — scored micro 0.3154 / macro 0.0587, not v2's 0.3306 / 0.1303. The trainer seeds the samplers but CUDA kernels are not bitwise deterministic, and an ~11-epoch trajectory accumulates divergence (Phase-2's cell A, whose best is epoch 1, *did* reproduce exactly). Across F′'s three seeds micro spans 0.290–0.358 and macro 0.022–0.182, comfortably containing v2's numbers: **v2 was a mid-range draw from a wide distribution, and its precise values should no longer be quoted without this caveat.**
2. **At full data, masked supervision wins on every mean readout** — the *reverse* of Phase 2's 900-only result. Combined with Phase 2, this establishes a **data-composition × supervision-policy interaction**: assume-negative extracts more from the 900 alone (multi-label vignettes whose implied negatives are mostly correct), but once the 340 single-label round-1 records are included, assume-negative's false-negative supervision (the mechanism behind Augmented v1's macro *decline*) drags it down, while masking protects against exactly that. Phase 2's "masking refuted" conclusion was correct for its data condition and wrong as a generalization.
3. **The per-seed contrast is *not* sign-consistent** (F′−G′ all-108 macro: −0.005 / −0.059 / +0.093). Masked training is high-variance, high-ceiling: F′ seed 44 is the **best student run ever observed in this project** (micro 0.358, macro 0.182, 37 target TPs, 8 targets with hits, target AUC 0.747), while F′ seed 43 collapsed at epoch 1 (macro 0.022, target AUC 0.537) — the same instability C showed in Phase 2. Assume-negative is low-variance, low-ceiling (macro 0.064–0.089, at most 7 target TPs).

**Decision for stage 2 and for the project's main configuration: masked supervision (F′)** — best means on every target readout, best DRR, and continuity with v2 — with its seed instability documented as a first-class caveat.

## 3. Stage-2 results — negative down-sampling on the masked full-data base

Mean ± SD over 3 seeds; F′ repeated for reference:

| Metric | F′ (no sampling) | **N3 (1:3)** | N1 (1:1) |
|---|---|---|---|
| all-108 micro-F1 | **0.3211** | 0.2347 ± 0.0674 | 0.1434 ± 0.0190 |
| all-108 macro-F1 | 0.0878 | **0.1074** ± 0.0662 | 0.0424 ± 0.0040 |
| target-18 micro-F1 | 0.0447 | **0.0537** ± 0.0210 | 0.0351 ± 0.0029 |
| target-18 macro-F1 | 0.0258 | **0.0491** ± 0.0142 | 0.0341 ± 0.0055 |
| target-18 micro-recall | 0.088 | **0.593** ± 0.154 | 0.938 ± 0.065 |
| target-18 micro-precision | 0.030 | 0.028 ± 0.012 | 0.018 ± 0.002 |
| target-18 TP (of 140) | 12.3 | **83** (61–104) | 131 (122–140) |
| targets with ≥1 TP (of 18) | 2.7 | **16** (15–17) | 17.3 |
| mean target AUC | **0.632** | 0.608 ± 0.119 | 0.507 ± 0.049 |
| DRR | **0.177** | 0.319 ± 0.009 | 0.297 ± 0.045 |

**Findings:**

4. **1:3 down-sampling converts latent target signal into predictions — by calibration, not by better learning.** N3 lifts target-group recall from 0.09 to 0.59, covers 15–17 of 18 targets (including, in some seeds, first-ever hits on the four historically zero-prediction targets), and achieves the **best target-18 F1 (0.054) and best mean overall macro-F1 (0.107) of any cell in Phases 2–3**. But mean target AUC does *not* improve over F′ (0.608 vs. 0.632): the ranking is unchanged — removing negative pressure simply inflates target scores past the fixed 0.30 threshold, exactly the calibration shift the validation plan predicted. The price is severe at the fixed threshold: overall micro-F1 −0.09, target precision ~3%, DRR worse (0.32).
5. **1:1 is destructive.** N1 reaches near-perfect target recall (0.94–1.00) by effectively firing targets everywhere (~7,900 target FPs), and — decisively — mean target AUC drops to chance (0.507, seed 44 *below* chance): with only ~60–180 supervised negatives per target class, the model no longer learns to rank at all. The professor's 50:50 heuristic, applied literally per class in this multi-label setting, removes so much negative supervision that learning itself fails; 1:3 is the useful end of this dial, 1:1 is past it.
6. **Seed instability again dominates the masked family**: N3 macro spans 0.045–0.177 across seeds. No single-seed claim from any masked-family configuration is trustworthy.

## 4. What the experiment proves

- **Main configuration going forward: masked supervision on the full 1,240-record data (F′).** It wins the full-data comparison on all mean target readouts and DRR (stage 1), and stage 2 shows plain negative down-sampling is not a safe improvement to it.
- The **supervision-policy effect is data-dependent** (Phase 2 × Phase 3 interaction) — a genuine methodological finding: masking earns its place only when partially-labeled single-label records are present.
- The historical v2 numbers are **only distributionally reproducible**; all past single-run deltas of ≲0.03 micro / ≲0.1 macro are within the now-measured seed+nondeterminism spread of the masked family.
- Target-class negative down-sampling at 1:3 **raises tail metrics (target F1, overall macro) at a large micro/DRR cost, via calibration rather than ranking**; at 1:1 it destroys learning. As a standalone decision-rule fix it is not viable; as a *recall source* it is the strongest yet seen (0.59 target recall, 16/18 targets).
- Direction accuracy worsens under every augmented/sampled configuration (DRR 0.18–0.32 vs. baseline 0.16); direction must continue to be delegated to the LLM stage in any deployed system.

## 5. What remains uncertain

- Whether F′'s seed-44 peak (macro 0.182) is attainable reliably — e.g., via more seeds, longer patience, or macro-aware checkpoint selection — or is a lottery ticket; 3 seeds cannot say.
- Whether N3's calibration shift plus **per-class threshold re-tuning on an internal split** (raising target thresholds instead of global 0.30) could keep its recall while recovering precision — untested, and the natural reconciliation of stage-2's trade-off.
- Whether N3-style candidates (0.59 direction-aware target recall) improve the **hybrid** (where the LLM verifier absorbs the precision cost) more than v2's candidates did — the highest-value downstream test.
- All results remain dev-set, with dev-based model selection shared across cells; per-target supports of 3–21 cap per-class certainty.

## 6. Next experiment

In order of information per GPU-hour: (1) **per-class threshold tuning on an internal split applied to the existing F′ and N3 checkpoints** — no new training, directly tests whether N3's recall can be kept at usable precision; (2) **hybrid re-run with N3 (or F′ seed-44) candidates** replacing v2's, to measure downstream value where precision is verifier-managed; (3) **5–7 additional F′ seeds** to characterize the bimodal collapse/peak behavior and test macro-aware selection.

## 7. Reproduction

```bash
bash new_check/phase3/scripts/run_stage1_full_data.sh          # F' and G' (6 runs)
/home/szf-4090/miniconda3/envs/fehu/bin/python \
     new_check/phase3/scripts/export_probs_phase3.py Fp_seed42 Fp_seed43 Fp_seed44 \
                                                     Gp_seed42 Gp_seed43 Gp_seed44
bash new_check/phase3/scripts/run_stage2_negsample.sh masked   # N3 and N1 (6 runs)
/home/szf-4090/miniconda3/envs/fehu/bin/python \
     new_check/phase3/scripts/export_probs_phase3.py N3_seed42 N3_seed43 N3_seed44 \
                                                     N1_seed42 N1_seed43 N1_seed44
python new_check/phase3/scripts/analyze_phase3.py              # all tables
```

Operational notes for reproducers: run the shell scripts and exports as detached/background jobs from the start (a foreground-to-background migration stalled one export mid-run here and it was cleanly rerun); the export script hard-aborts on any 0.30-reproduction mismatch.
