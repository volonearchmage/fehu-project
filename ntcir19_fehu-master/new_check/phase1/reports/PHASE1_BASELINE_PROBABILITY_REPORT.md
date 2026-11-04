# Phase-1 Report — Baseline Probability Export and Latent-Signal Analysis

**Date:** 2026-07-20
**Follows:** `new_check/phase0/reports/PHASE0_VALIDATION_REPORT.md`
**Workspace:** all new code and outputs are under `new_check/phase1/`; no existing artifact was modified. This phase performed exactly one local GPU inference pass from a stored checkpoint (permitted for Phase 1); no training, no API calls.

---

## 1. What Phase 1 did

Phase 0 could analyze score-level behavior only for Augmented v2 (its dev probabilities had been exported by the hybrid run). The corresponding question for the **official-only baseline** — *"did the baseline also carry latent target-label signal below the 0.30 threshold, or did it simply never learn the targets?"* — was blocked. Phase 1 unblocks it:

1. Exported dev-set actor-level 108-class sigmoid probabilities from the frozen baseline checkpoint (`output/research_ablation_smoke_runs/20260704_201355/baseline/checkpoints/`), reusing the exact protocol of the v2 export (`…20260714_184515/scripts/03_export_probabilities.py`): same architecture and adapter loading, same tokenization (`text`, `actor_name`; `truncation="only_first"`; max_length 512), same gold-file-order example construction (456 trainer-parity instances + 3 article-only actors exported with a flag), same batch size, same index rule (`idx = l1×2 + direction`).
2. **Hard validation before anything else was computed:** thresholding the exported probabilities at 0.30 reproduces the frozen baseline `pred_task1b.json` **exactly** on all 456 trainer-parity instances (the script aborts with no output on any mismatch; none occurred). Checkpoint file SHA-256 hashes and environment details are in `outputs/export_manifest.json`.
3. Ran the identical threshold sweep and per-target oracle analysis used for v2 in Phase 0, plus a new per-target **separation comparison** (rank-based AUC, gold-score quantiles, oracle F1) between baseline and v2.

Outputs: `baseline_actor_probabilities.jsonl`, `threshold_sensitivity_baseline.csv`, `per_target_oracle_thresholds_baseline.csv`, `baseline_vs_v2_target_separation.csv`, `separation_summary.json`, `export_manifest.json`.

## 2. Headline result — the baseline had essentially no latent target signal

Separation of each target's gold instances from its non-gold instances, measured by rank AUC (probability that a gold instance scores above a non-gold one; 0.5 = chance). From `baseline_vs_v2_target_separation.csv`:

| Statistic (over the 18 targets) | Baseline | Augmented v2 |
|---|---|---|
| Mean AUC | **0.536** | **0.697** |
| Targets with AUC ≤ 0.55 | 11 of 18 | 3 of 18 |
| Targets with AUC below chance (< 0.5) | 8 | 2 |
| Mean per-target oracle F1 (dev-tuned upper bound) | 0.053 | 0.112 |
| Max gold-instance probability, worst→best target | 0.048 – 0.157 | 0.021 – 0.452 |

In plain language: **the baseline's target scores are statistically indistinguishable from noise for most targets.** Its highest probability on *any* gold target instance is 0.157 — nowhere near the 0.30 threshold — and no per-label threshold, tuned with full knowledge of the dev labels, gets any target's F1 above 0.16 (mean 0.053). Several targets score *below* chance (e.g., 0:19 AUC 0.34, 0:32 AUC 0.33: the baseline systematically ranks gold instances *lower* than others).

The apparent counter-signal — baseline target-18 recall 0.936 at threshold 0.05 — is an artifact of blanket prediction: at 0.05 the baseline fires on nearly everything (all-108 micro-recall 0.988 at micro-precision 0.058, 102 distinct classes, DRR 0.90). By threshold 0.15 its target recall has already collapsed to 0.007, versus 0.271 for v2 (`threshold_sensitivity_baseline.csv` vs. Phase 0's `threshold_sensitivity_v2.csv`).

## 3. Baseline vs. v2 per-target comparison

v2 improved separation on 14 of 18 targets (AUC) and dev-oracle F1 on 16 of 18 (`separation_summary.json`). The improvement is largest exactly on the five targets Phase 0 found "recovered" at 0.30 — e.g., 0:29 AUC 0.43 → 0.91, 0:2 0.49 → 0.79, 0:33 0.43 → 0.78, 0:32 0.33 → 0.76, 0:28 0.67 → 0.73 — and v2's median gold-instance probability rose correspondingly (e.g., 0:29: 0.085 → 0.260). Small-support caveats apply throughout (n = 3–21 gold instances per target; single seed on both sides; AUC on n=3 targets such as 0:48's baseline 0.86 is noise-dominated).

## 4. What this changes in the interpretation of Phase 0

This is the most consequential correction Phase 1 delivers:

1. **The "decision-rule artifact" hypothesis is now largely refuted for the baseline.** Phase 0 (and the earlier critical review) held open the possibility that the baseline had learned the targets but the fixed 0.30 threshold discarded them. The exported probabilities show otherwise: there was nothing to recover — no threshold policy, global or per-label, would have given the baseline usable target performance (near-chance separation, max gold score 0.157, oracle F1 ≤ 0.16 everywhere).
2. **The v2 training run produced a genuine score-level change on the targets**, not merely a threshold-crossing effect: mean AUC +0.16, oracle F1 roughly doubled, and the gains concentrate on the targets that became visible at 0.30. The change is real but still far from usable (v2 oracle F1 ≤ 0.25 on every target, as Phase 0 showed).
3. **The binding constraint therefore shifts from "thresholding" to "learning/supervision."** Threshold tuning alone can modestly help v2 (its overall micro-F1 peaks at 0.35, macro at 0.25) but could not have rescued the baseline, and cannot make v2's targets usable. The open causal question is unchanged and now more clearly the central one: whether the score-level change came from the 900 records, the 340, the masked supervision policy, or their combination — exactly the Phase-2 factorized cells (C vs. A vs. B) of the validation plan.
4. A nuance worth carrying forward: 8 baseline targets score below chance, consistent with the assume-negative loss actively teaching the baseline to suppress rare classes (every unlabeled slot was a training negative). This is a testable signature for Phase 2: if masked supervision is the active ingredient, cell B (900 added, assume-negative) should lift target AUC less than cell C (900 added, masked).

## 5. Verification and constraints

- Hard 0.30 reproduction check passed on all 456 instances before any output was written; checkpoint SHA-256 inventory recorded in `outputs/export_manifest.json`.
- Analysis-side sanity check: the baseline sweep at 0.30 reproduces the frozen overall micro-F1 (0.3023) through the Phase-0 metric code path.
- The 3 non-gold dev actors are exported with `actor_source = article_only_actor_not_in_frozen_run` and excluded from all metrics, matching the Phase-0 convention.
- No training, no fine-tuning, no API calls; one local inference pass (456+3 examples, seconds on the RTX 4090); nothing outside `new_check/phase1/` written; no existing artifact modified.

## 6. Rerun

```bash
# step 1: export (requires the fehu conda env with torch/peft, GPU)
/home/szf-4090/miniconda3/envs/fehu/bin/python \
    ntcir19_fehu-master/new_check/phase1/scripts/export_baseline_probabilities.py
# step 2: analysis (stdlib only)
python ntcir19_fehu-master/new_check/phase1/scripts/analyze_baseline_probabilities.py
```

## 7. Next step justified by Phase 1

Phase 2, cells **C vs. A vs. B** (official-only vs. official+900 under masked and assume-negative supervision, 3 seeds, internal-split selection), now with a sharpened readout: report per-target **AUC and oracle F1** alongside the fixed-threshold metrics, since Phase 1 shows score-level separation is where the real signal (or its absence) lives.
