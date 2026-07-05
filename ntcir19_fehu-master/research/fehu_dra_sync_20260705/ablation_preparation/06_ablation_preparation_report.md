# Ablation Preparation Report — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T16:56:50
**Output folder:** `output/research_ablation_preparation/20260702_165650`

## Current branch
`main`

## Pre-existing git status (unrelated, untouched)
Prior hybrid-pipeline work, left untouched: `src/hybrid_pipeline.py` (M), `src/run_pipeline.py` (M),
`src/train_deberta.py` (M), `HYBRID_ROADMAP.md`, `research/`, `src/collect_results.py`,
`src/hybrid_v2.py`, `src/regenerate_deberta_predictions.py`, `src/run_pipeline_deepseek_flash.py`.

## Files read (read-only)
- Updated verified pool (6 records), old verified pool (5 records).
- Official schemas: train/dev event_base + gold_labels; hv_categories (L1, L2, L1->L2).
- `evaluation.py`; `src/run_pipeline.py`, `src/train_deberta.py`, `src/hybrid_pipeline.py` (inspection only).

## Files written (this task, in the new folder only)
- 01_ablation_input_construction_plan.md
- 02_verified_pool_manifest.json
- 03_candidate_label_delta_table.csv
- 04_ablation_conditions_spec.json
- 05_risk_control_checklist.md
- 06_ablation_preparation_report.md

## Verified pool validation summary
6 records; all human_decision=ACCEPT; all verified_for_candidate_pool=true; all training_ready=false;
no duplicate candidate_id; L1=12 pair complete ['0 contradictory', '1 aligned']; L1=38 pair complete ['0 contradictory', '1 aligned'];
L1->L2 mappings consistent with hv_categories = True.

## Old pool unchanged confirmation
Old verified pool `20260702_132154` remains 5 records and is byte-identical (sha256 unchanged).

## Official data unchanged confirmation
All 16 files under `dataset/` are byte-identical (sha256 unchanged). No official
train/dev/test/gold file was modified.

## evaluation.py unchanged confirmation
`evaluation.py` is byte-identical (sha256 unchanged).

## Validation results
14 PASS / 0 REVIEW / 0 FAIL of 14.

| # | check_name | status | explanation |
|---|-----------|--------|-------------|
| 1 | one_new_timestamped_folder | PASS | Created exactly one folder: output/research_ablation_preparation/20260702_165650 |
| 2 | six_required_output_files_exist | PASS | All 6 required files written. |
| 3 | updated_pool_has_6_records | PASS | 6 records. |
| 4 | all_human_decision_accept | PASS | All 6 human_decision=ACCEPT. |
| 5 | all_verified_for_candidate_pool_true | PASS | All 6 verified_for_candidate_pool=true. |
| 6 | all_training_ready_false | PASS | All 6 training_ready=false. |
| 7 | l1_12_pair_complete | PASS | L1=12 dirs ['0 contradictory', '1 aligned']. |
| 8 | l1_38_pair_complete | PASS | L1=38 dirs ['0 contradictory', '1 aligned']. |
| 9 | l1_l2_mapping_consistent | PASS | All pool labels match hv_categories L1->L2. |
| 10 | old_verified_pool_unchanged | PASS | Old pool 5 records, sha256 unchanged. |
| 11 | official_dataset_unchanged | PASS | All 16 dataset files sha256 unchanged. |
| 12 | evaluation_py_unchanged | PASS | evaluation.py sha256 unchanged. |
| 13 | no_source_files_modified | PASS | No source changes beyond acknowledged pre-existing set. |
| 14 | only_new_folder_written | PASS | git status invariant (output/ gitignored); no entries outside output/research_ablation_preparation/20260702_165650. |

## Statement
This task prepared an ablation input construction plan only. It did not create augmented training
data, did not run ablation, and did not run training.

## Next step
After human review of this plan, create derived baseline/augmented input files under
`output/research_ablation_inputs/<timestamp>/` without modifying official data.
