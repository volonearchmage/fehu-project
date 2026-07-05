# Source Change Summary — train_deberta.py ablation enablement

**Created at:** 2026-07-04T20:03:42
**Current branch:** `main`

## Pre-task git status (unrelated, pre-existing)
`src/hybrid_pipeline.py` (M), `src/run_pipeline.py` (M), **`src/train_deberta.py` (M — the approved
target, already modified pre-task from prior work)**, `HYBRID_ROADMAP.md`, `research/`,
`src/collect_results.py`, `src/hybrid_v2.py`, `src/regenerate_deberta_predictions.py`,
`src/run_pipeline_deepseek_flash.py` (untracked). These were not created by this task and, apart from
the approved edits to `src/train_deberta.py`, were not touched.

## Reason for the source change
The ablation readiness audit (`output/research_ablation_readiness/20260704_193038/`) classified the
controlled baseline-vs-augmented ablation as `BLOCKED_NEEDS_EXPLICIT_SOURCE_CHANGE`: training input
paths were hardcoded, there was no seed control, and the checkpoint directory was shared across runs.
Peiyang approved one minimal, backward-compatible source change to remove these blockers.

## Approved scope
Modify **only** `src/train_deberta.py` to add four backward-compatible CLI arguments
(`--train_articles`, `--train_labels`, `--seed`, `--checkpoint_dir`) and wire them into the active
training flow, with loud failure (no silent fallback) on invalid explicit input paths.

## Files modified
- `src/train_deberta.py` (approved).

## Files NOT modified
- `evaluation.py` (sha256 unchanged: `e4a7f89e…8ad47`).
- `dataset/` official train/dev/gold/hv_categories (sha256 unchanged).
- All other `src/*.py`, verified pools, ablation-input/dry-run/execution-plan/readiness folders.

## Statement
No training, inference, or ablation was run. Only `python -m py_compile` and `--help` were executed for
validation. No predictions or real model metrics were produced.
