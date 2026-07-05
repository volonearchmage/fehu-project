# Ablation Execution Plan Report — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T20:08:24
**Output folder:** `output/research_ablation_execution_plan/20260702_200824`

## 1. Current branch
`main`

## 2. Pre-existing git status (unrelated, untouched)
Prior hybrid-pipeline work, left untouched: `src/hybrid_pipeline.py` (M), `src/run_pipeline.py` (M),
`src/train_deberta.py` (M), `HYBRID_ROADMAP.md`, `research/`, `src/collect_results.py`,
`src/hybrid_v2.py`, `src/regenerate_deberta_predictions.py`, `src/run_pipeline_deepseek_flash.py`.

## 3. Files read
- `output/research_ablation_inputs/20260702_193701/07_ablation_input_manifest.json`
- `output/research_ablation_dryrun/20260702_194637/05_dryrun_manifest.json`
- `output/research_ablation_dryrun/20260702_194637/06_schema_evaluator_dryrun_report.md`
- `evaluation.py`
- `dataset/hv_categories/human_value_level1_values.json`, `human_value_level2_values.json`,
  `level_1_to_level_2.json`, and **`direction_mapping.json`** (found)
- `dataset/gold_labels/train/train_human_values.json`, `dataset/gold_labels/dev/dev_human_values.json`

## 4. Files written (new folder only)
`01_controlled_ablation_execution_plan.md`, `02_metric_and_direction_risk_analysis.md`,
`03_evaluator_invocation_spec.json`, `04_ablation_run_matrix.json`,
`05_pre_ablation_approval_checklist.md`, `06_execution_plan_report.md`.

## 5. Summary of dry-run findings
Schema/evaluator dry-run (`20260702_194637`) passed 43/43: the official `parse_task1b` accepts the
derived Task-1b format; for identical gold/pred, micro-F1=1.0, macro-F1=1.0, DRR=0. The shipped CLI
returned exit code 1 on arbitrary files because `DEBUG=True` (line 262) overwrites `sys.argv` with a
hardcoded `/tmp/ntcir19_fehu/...` path (FileNotFoundError). Approved method: invoke the evaluator
functions programmatically.

## 6. Summary of direction mapping caveat
A direction mapping file **exists**: `dataset/hv_categories/direction_mapping.json = {"aligned":"1",
"contradictory":"0"}`. This agrees with the gold labels, the verified candidates, and the derived
inputs (`1`=aligned, `0`=contradictory). `evaluation.py`'s DRR **internal variable naming** is inverted
(`0`=aligned, `1`=contradictory), but all reported DRR quantities are direction-symmetric aggregates, so
the DRR rate/count/denominator are numerically correct and F1 (exact-string) is unaffected. Only a
per-direction decomposition read from the evaluator's variable names would be mislabeled; compute any
such breakdown from raw labels using `direction_mapping.json`. Do not overclaim DRR until real
predictions are inspected (L1=12 contradictory dev support is only 7). Full analysis in
`02_metric_and_direction_risk_analysis.md`. `evaluation.py` is not modified.

## 7. Official data unchanged confirmation
All read official files are byte-identical before and after this task (sha256 verified):
`human_value_level1_values.json`, `human_value_level2_values.json`, `level_1_to_level_2.json`,
`train_human_values.json`, `dev_human_values.json` — unchanged.

## 8. evaluation.py unchanged confirmation
`evaluation.py` sha256 is unchanged (`e4a7f89e…8ad47`) before and after this task.

## 9. Statement
This task prepared a controlled ablation execution plan only. It did not run training, did not run
ablation, and did not modify official data or evaluation.py.

## 10. Next step
Human review is required. If approved, resolve or isolate the dirty working tree, then run a controlled
ablation execution task.

## Validation results (17/17 PASS)
| # | check | status |
|---|-------|--------|
| 1 | exactly one new folder under research_ablation_execution_plan/ | PASS |
| 2 | exactly six required output files exist | PASS |
| 3 | JSON files parse correctly (03, 04) | PASS |
| 4 | dry-run folder read successfully | PASS |
| 5 | ablation input manifest read successfully | PASS |
| 6 | evaluation.py read but not modified (sha256 unchanged) | PASS |
| 7 | official gold/mapping files read but not modified (sha256 unchanged) | PASS |
| 8 | direction mapping caveat explicitly documented | PASS |
| 9 | CLI blocking reason explicitly documented | PASS |
| 10 | evaluator function invocation policy explicitly documented | PASS |
| 11 | no files outside the new folder changed (git status invariant) | PASS |
| 12 | no official data modified | PASS |
| 13 | no evaluation.py modified | PASS |
| 14 | no source code modified | PASS |
| 15 | no training run | PASS |
| 16 | no ablation run | PASS |
| 17 | no fallback implementation | PASS |
