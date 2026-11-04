# Ablation Execution Readiness Report — DRA-FEHU (Task-1)

**Created at:** 2026-07-04T19:30:38
**Output folder:** `output/research_ablation_readiness/20260704_193038`

## Current branch
`main`

## Pre-existing git status (unrelated, untouched)
`src/hybrid_pipeline.py` (M), `src/run_pipeline.py` (M), `src/train_deberta.py` (M),
`HYBRID_ROADMAP.md`, `research/`, `src/collect_results.py`, `src/hybrid_v2.py`,
`src/regenerate_deberta_predictions.py`, `src/run_pipeline_deepseek_flash.py` (untracked).
Note: the ablation entrypoint `src/train_deberta.py` is itself among the modified files.

## Files read
- Execution plan: `01_controlled_ablation_execution_plan.md`, `02_metric_and_direction_risk_analysis.md`,
  `03_evaluator_invocation_spec.json`, `04_ablation_run_matrix.json`.
- Ablation input manifest `07_ablation_input_manifest.json`; dry-run manifest `05_dryrun_manifest.json`.
- Source: `src/train_deberta.py`, `src/run_pipeline.py`, `src/hybrid_pipeline.py`, `src/hybrid_v2.py`,
  `src/run_pipeline_deepseek_flash.py`, `src/regenerate_deberta_predictions.py`, `src/collect_results.py`.
- `evaluation.py` (invocation awareness). (`run_pipeline.py` at repo root does not exist.)

## Files written (new folder only)
`01_pipeline_entrypoint_audit.md`, `02_ablation_command_spec.json`, `03_blockers_and_decisions.md`,
`04_readiness_validation_table.csv`, `05_ablation_readiness_report.md`.

## Readiness classification
**BLOCKED_NEEDS_EXPLICIT_SOURCE_CHANGE.**

## Main blockers
1. **Hardcoded training input paths** (`src/train_deberta.py:93-94`, used at line 401) with no CLI/env
   override → the augmented condition cannot be loaded.
2. **No seed control** anywhere → the "same seed" invariant is unenforceable (nondeterministic A vs B).
3. **Shared checkpoint dir** (`line 62`) → baseline and augmented runs collide.
The `evaluation.py` CLI is separately blocked (DEBUG=True), but that is *not* an ablation blocker
because training already calls the evaluator functions programmatically.

## Can existing code run the ablation as planned?
No. The entrypoint is correct and prediction/evaluator integration is compatible, but the three blockers
above prevent a controlled A/B run. Fixes are minimal and backward-compatible (`--train_articles/--train_labels`,
`--seed`, `--checkpoint_dir`, defaults preserving current behavior) but edit the official training script
and must be **explicitly approved in a later task**. Not implemented here.

## Source-state risk conclusion
The dirty working tree (including a modified `train_deberta.py`) is acceptable for planning/audit but
**not** for final reported experiments: results must pin to a known git commit for reproducible
provenance. Before final runs, commit the entrypoint (with the approved edits) on a dedicated branch or
run in a path-isolated worktree, and write all artifacts under `output/research_ablation_runs/<timestamp>/`.

## Recommended next step
Open an **explicit source-change proposal task** for the three minimal edits to `src/train_deberta.py`,
requiring Peiyang's approval. In the same approval, resolve reproducibility (commit on a branch or use a
worktree) and confirm fixed seed + per-condition output/checkpoint isolation. Only after that approval
should a controlled **smoke run** (e.g., tiny `MAX_EPOCHS`, small subset) be attempted, followed by the
full A/B ablation. Do not train until this approval is recorded.

## Validation results
25 checks: **21 PASS / 1 REVIEW / 3 FAIL**. The 3 FAIL checks
(`custom_train_event_path_supported`, `custom_train_gold_path_supported`,
`baseline_augmented_conditions_representable`) are the *intended, correct audit findings* that establish
the BLOCKED classification — not task failures. The 1 REVIEW (`dev_eval_path_configurable`) reflects dev
being hardcoded to the official set, which is the desired invariant.

## Statement
This task performed an ablation execution readiness audit only. It did not train a model, did not run
inference, did not run ablation, did not modify source code, and did not modify official data.
