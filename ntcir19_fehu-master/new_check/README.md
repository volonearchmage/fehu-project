# new_check/ — Validation Workspace

Isolated workspace for the validation study defined in
`docs/FEHU_PROFESSOR_FEEDBACK_VALIDATION_PLAN.md`. Nothing outside
`new_check/` is ever written by the code in here; all existing repository
artifacts are used strictly read-only.

## Structure

```
new_check/
├── README.md                  ← this file
└── phase0/                    ← Phase 0: recomputation from existing artifacts
    ├── configs/
    │   └── phase0_config.json     all input paths + analysis settings
    ├── scripts/
    │   ├── phase0_lib.py          shared helpers (metric defs, conventions, fail-fast IO)
    │   ├── run_phase0.py          main runner (produces all core outputs)
    │   └── addendum_nontarget_gain.py  non-target gain decomposition (run after run_phase0)
    ├── outputs/                   machine-readable results (CSV/JSON) + HUMAN_CHECK list
    ├── reports/
    │   └── PHASE0_VALIDATION_REPORT.md  readable summary for discussion with the professor
    └── logs/
        └── run_phase0.log
```

## Required inputs

Everything is read from the existing repository (paths in
`phase0/configs/phase0_config.json`): official dev/train gold labels, the
frozen 18-target allocation JSON, prediction files of six systems (DeBERTa
baseline / augmented v1 / augmented v2 / Liu frozen / hybrid H2 / H3), the
v2 dev probability export, and the v2 training inputs (supervision map +
label file). If any input is missing or malformed the scripts abort with a
`Phase0InputError` naming the path — there are no silent fallbacks.

## How to run / rerun

From the repository root (`ntcir19_fehu-master/`), with any Python ≥3.8
(standard library only — no GPU, no network, no API keys):

```bash
python new_check/phase0/scripts/run_phase0.py
python new_check/phase0/scripts/addendum_nontarget_gain.py
```

Runtime is a few seconds. Outputs are overwritten in place inside
`phase0/outputs/` (they are derived artifacts; the manifest records the
SHA-256 of every input used, so any change in upstream artifacts is
detectable).

## Generated outputs (phase0/outputs/)

| File | Content |
|---|---|
| `experiment_comparability.csv` | per-system provenance, thresholds, supervision policy, instance counts, micro-F1 cross-check vs documented values |
| `overall_metrics_all_systems.csv` | all-108 micro/macro P, R, F1 + DRR per system |
| `group_metrics_long.csv` | all systems × {target_18, nontarget_90, all_108} × both macro variants |
| `target18_group_metrics.csv`, `nontarget90_group_metrics.csv` | convenience extracts of the above |
| `per_target_18_metrics.csv` | per-target support, pred, TP/FP/FN, P/R/F1, Δ vs baseline, reversal counts |
| `pos_neg_ratio_table.csv` | positive / known-negative / unknown-masked counts and ratios, before and after augmentation |
| `threshold_sensitivity_v2.csv` | global threshold sweep for augmented v2 (validated to reproduce the frozen 0.30 predictions) |
| `per_target_oracle_thresholds_v2.csv` | per-target dev-tuned oracle thresholds — flagged, diagnostic only |
| `error_categories.csv` | FN/FP/reversals split by target vs non-target vs zero-gold classes |
| `nontarget_gain_decomposition.csv` + `nontarget_gain_summary.json` | baseline→v2 per-class ΔF1 on non-targets, split by synthetic exposure |
| `HUMAN_CHECK_REQUIRED.md` | items needing human confirmation, with paths and blocking status |
| `run_manifest.json` | input SHA-256 hashes, settings, target list, constraint confirmation |

## Conventions

Metric conventions mirror the official `evaluation.py` exactly (instances =
gold ∪ pred; undefined P/R = 0.0; gold-supported macro), with a documented
second "full-universe" macro variant. Direction semantics follow
`dataset/hv_categories/direction_mapping.json` ("1" = aligned). See
`phase0/scripts/phase0_lib.py` docstrings and the report §4 for details.

## Phase status

- **Phase 0: complete** — see `phase0/reports/PHASE0_VALIDATION_REPORT.md`.
- **Phase 1: complete** — baseline dev probabilities exported from the frozen
  checkpoint (hard-validated: 0.30 thresholding reproduces the frozen
  baseline predictions exactly) and analyzed; see
  `phase1/reports/PHASE1_BASELINE_PROBABILITY_REPORT.md`. Key finding: the
  baseline had essentially no latent target signal (mean target AUC 0.536 ≈
  chance), refuting the threshold-artifact hypothesis for the baseline;
  v2's target signal (AUC 0.697) is a genuine learning change, still
  confounded between data and supervision policy.
  Phase-1 export requires the `fehu` conda env (torch/peft, GPU); the
  analysis step is stdlib-only. Commands in the phase-1 report §6.
- **Phase 2: complete** — controlled 3×3 ablation (A official-only / B +900
  assume-negative / C +900 masked, seeds 42/43/44) using the unmodified
  frozen masked trainer; see
  `phase2/reports/PHASE2_CONTROLLED_ABLATION_REPORT.md`. Key findings: the
  900 records reproducibly improve target scores (AUC +0.11 under B, +0.06
  under C, sign-consistent 3/3); **masked supervision is NOT the active
  ingredient — at fixed data it reduces the benefit (C−B negative)**;
  thresholded metrics are seed-unstable; A seed 42 exactly reproduces the
  frozen historical baseline. Next: G′ (official+340+900, assume-negative)
  and F′ (= v2 config, multi-seed).
- **Phase 3: complete** — full-data F′ (masked, = v2 config) vs G′
  (assume-negative) × 3 seeds, then target-class negative down-sampling
  (N3 = 1:3, N1 = 1:1) on the masked winner; see
  `phase3/reports/PHASE3_FULL_DATA_AND_NEGATIVE_SAMPLING_REPORT.md`.
  Key findings: at full data masked wins on all mean target readouts
  (supervision-policy effect is data-composition-dependent — reverses
  Phase 2's 900-only ordering); historical v2 is only *distributionally*
  reproducible (F′ seed 42 gave 0.3154, seeds span micro 0.290–0.358,
  macro 0.022–0.182; seed 44 is the best student run ever: macro 0.182);
  1:3 down-sampling lifts target recall to 0.59 and overall macro to 0.107
  via calibration (AUC unchanged) at a large micro/DRR cost; 1:1 destroys
  learning (target AUC ≈ chance). Masked supervision stays the main
  configuration. Stage-2 trainer extension:
  `phase3/scripts/train_phase3_negsample.py` (copy; frozen trainer intact).
