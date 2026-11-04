# Run Integrity Report — DRA-FEHU Smoke Run 20260704_201355

**Created at:** 2026-07-04T20:35:00

| Integrity question | Result | Evidence |
|--------------------|--------|----------|
| Official data unchanged? | **YES** | All `dataset/` guard files sha256-identical before/after (`sha256_before.txt` vs `sha256_after.txt` diff = ALL_HASHES_UNCHANGED) |
| evaluation.py unchanged? | **YES** | sha256 `e4a7f89e…8ad47` identical before/after; only imported programmatically |
| Source code unchanged during this task? | **YES** | `src/train_deberta.py` sha256 `ed84d92a…4d674` identical before/after (the pre-approved version from the source-change task); git status unchanged from pre-task |
| Ablation inputs unchanged? | **YES** | All four input files sha256-identical before/after |
| Verified pool unchanged? | **YES** | `20260702_165107` pool sha256 `3268acaf…` identical |
| Output/checkpoint isolation worked? | **YES** | Baseline wrote only to `baseline/output` + `baseline/checkpoints`; augmented only to `augmented/…`; separate adapter/classifier files per condition; no shared `checkpoints/best_model` used |
| Explicit train paths actually used? | **YES** | Each run's `run_config.json` records the derived input paths (`01/02_baseline_*` and `03/04_augmented_*`) and train example counts differ accordingly (3335 vs 3341 = +6 synthetic actor-examples) |
| Any fallback behavior? | **NO** | Explicit paths validated by `is_file()`; both resolved successfully; no fallback branch exists or fired |
| Any unexpected files changed? | **NO** | `git status --short` after == before (pre-existing dirty set only); all writes confined to `output/research_ablation_smoke_runs/20260704_201355/` (output/ is gitignored) |

## Notes
- Train example delta between conditions is exactly +6 (3335 → 3341), matching the 6 verified
  synthetic candidates — direct evidence the augmented file was really consumed.
- The harness session restarted mid-augmented-run; the detached training process was unaffected and
  wrote exit code 0. A stale harness wrapper reported −1; the authoritative code is the run's own
  `exit_code.txt` (0). No retry was needed.
- Seed 42 was applied in both runs (recorded in each `run_config.json`).
