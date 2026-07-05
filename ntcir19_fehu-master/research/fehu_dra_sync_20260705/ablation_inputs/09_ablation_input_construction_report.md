# Ablation Input Construction Report — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T19:37:01
**Output folder:** `output/research_ablation_inputs/20260702_193701`

## 1. Current branch
`main`

## 2. Pre-existing git status (unrelated, untouched)
Prior hybrid-pipeline work, left untouched: `src/hybrid_pipeline.py` (M), `src/run_pipeline.py` (M),
`src/train_deberta.py` (M), `HYBRID_ROADMAP.md`, `research/`, `src/collect_results.py`,
`src/hybrid_v2.py`, `src/regenerate_deberta_predictions.py`, `src/run_pipeline_deepseek_flash.py`.

## 3. Files read (read-only)
Verified pool; ablation preparation folder; official train/dev event_base + gold_labels;
hv_categories (L1, L2, L1->L2); evaluation.py. sha256 captured before and after.

## 4. Files written (new folder only)
01_baseline_train_event_base.json, 02_baseline_train_human_values.json,
03_augmented_train_event_base.json, 04_augmented_train_human_values.json,
05_synthetic_event_base_additions.json, 06_synthetic_human_value_additions.json,
07_ablation_input_manifest.json, 08_ablation_input_validation_table.csv,
09_ablation_input_construction_report.md.

## 5. Verified pool summary
6 verified candidates; all human_decision=ACCEPT; all verified_for_candidate_pool=true; all
training_ready=false; no duplicate candidate_id; L1=12 and L1=38 direction pairs complete.

## 6. Official train/dev/schema summary
Official train: 1228 event_base records / 1228 gold records. Gold direction
codes observed: ['0', '1'] (matches 1=aligned/0=contradictory). hv_categories: 54 L1, 20 L2,
L1->L2 name mapping. dev + evaluation.py read for schema awareness only.

## 7. Baseline condition summary (Condition A)
Exact JSON copies of official train: 1228 event_base / 1228 gold. No augmentation.

## 8. Augmented condition summary (Condition B)
Official train + 6 synthetic records: 1234 event_base / 1234 gold. Only added factor
is the 6 verified augmented candidates.

## 9. Synthetic conversion design summary
Per candidate: guid `aug_<candidate_id>`, actor id `aug_<candidate_id>-0`, title
"DRA-FEHU synthetic augmentation: <L1 name> <direction>", content verbatim, one actor, one traceability
subevent (evidence sentence). Gold: one article_human_values entry (actor, l1_value, l2_value,
direction code, explanation=evidence_sentence); subevents_human_values empty (Task-1 only).

## 10. Per-candidate synthetic guid and label summary
- `prev_rare_positive_32_001_83df110175` -> guid `aug_prev_rare_positive_32_001_83df110175`, actor `aug_prev_rare_positive_32_001_83df110175-0`, L1=32 "Be behaving properly" / L2=11 / direction 1 aligned (code 1)
- `prev_dir_contrast_12_002_aligned_ce1da19f54` -> guid `aug_prev_dir_contrast_12_002_aligned_ce1da19f54`, actor `aug_prev_dir_contrast_12_002_aligned_ce1da19f54-0`, L1=12 "Have success" / L2=4 / direction 1 aligned (code 1)
- `prev_dir_contrast_38_003_contradictory_e969e14138` -> guid `aug_prev_dir_contrast_38_003_contradictory_e969e14138`, actor `aug_prev_dir_contrast_38_003_contradictory_e969e14138-0`, L1=38 "Be honest" / L2=14 / direction 0 contradictory (code 0)
- `prev_dir_contrast_38_003_aligned_e969e14138` -> guid `aug_prev_dir_contrast_38_003_aligned_e969e14138`, actor `aug_prev_dir_contrast_38_003_aligned_e969e14138-0`, L1=38 "Be honest" / L2=14 / direction 1 aligned (code 1)
- `prev_rare_positive_24_004_98671d8d01` -> guid `aug_prev_rare_positive_24_004_98671d8d01`, actor `aug_prev_rare_positive_24_004_98671d8d01-0`, L1=24 "Be neat and tidy" / L2=8 / direction 1 aligned (code 1)
- `repl_dir_contrast_12_002_contradictory_3cfa8093d2` -> guid `aug_repl_dir_contrast_12_002_contradictory_3cfa8093d2`, actor `aug_repl_dir_contrast_12_002_contradictory_3cfa8093d2-0`, L1=12 "Have success" / L2=4 / direction 0 contradictory (code 0)

## 11. Direction mapping confirmation
Mapping used: {'1 aligned': '1', '0 contradictory': '0'} (1=aligned, 0=contradictory). No inversion. Every candidate's leading
direction token equals its mapped code, and official gold uses the same codes ['0', '1'].

## 12. L1/L2 mapping confirmation
Every synthetic (l1_value, l2_value) equals the canonical hv_categories mapping (e.g. L1=12->L2=4,
L1=38->L2=14, L1=32->L2=11, L1=24->L2=8). Any mismatch would have stopped the build.

## 13. Official data unchanged confirmation
All official files read are byte-identical (sha256 before == after): True.

## 14. Statement
This task created derived ablation input files only under output/. It did not modify official data,
did not run ablation, and did not run training.

## 15. Statement
The derived augmented input is for later human-approved ablation execution. It does not mean the
verified candidates are training-ready.

## 16. Next step
Review the derived ablation input files. If approved, run a dry-run schema/evaluator compatibility
check without training.

## Validation results
35 PASS / 0 REVIEW / 0 FAIL of 35.

| # | check_name | status | explanation |
|---|-----------|--------|-------------|
| 1 | verified_pool_exists | PASS | Verified pool file present. |
| 2 | verified_pool_has_6_records | PASS | 6 records. |
| 3 | verified_pool_all_human_accept | PASS | All 6 human_decision=ACCEPT. |
| 4 | verified_pool_all_verified_true | PASS | All 6 verified_for_candidate_pool=true. |
| 5 | verified_pool_all_training_ready_false | PASS | All 6 training_ready=false. |
| 6 | l1_12_pair_complete | PASS | L1=12 dirs ['0 contradictory', '1 aligned']. |
| 7 | l1_38_pair_complete | PASS | L1=38 dirs ['0 contradictory', '1 aligned']. |
| 8 | official_train_event_base_exists | PASS | Official train_event_base.json present. |
| 9 | official_train_human_values_exists | PASS | Official train_human_values.json present. |
| 10 | baseline_event_base_exact_copy | PASS | Baseline event_base parses equal to official train_event_base. |
| 11 | baseline_human_values_exact_copy | PASS | Baseline human_values parses equal to official train_human_values. |
| 12 | synthetic_event_additions_count_is_6 | PASS | 6 synthetic events. |
| 13 | synthetic_gold_additions_count_is_6 | PASS | 6 synthetic gold records. |
| 14 | augmented_event_count_equals_train_plus_6 | PASS | 1234 == 1228+6. |
| 15 | augmented_gold_count_equals_train_plus_6 | PASS | 1234 == 1228+6. |
| 16 | synthetic_guid_unique | PASS | 6 unique guids. |
| 17 | synthetic_guid_no_collision_with_official_train | PASS | No synthetic guid collides with an official train guid. |
| 18 | synthetic_actor_id_unique | PASS | 6 unique actor ids. |
| 19 | each_synthetic_event_has_one_actor | PASS | Exactly one actor per synthetic event. |
| 20 | each_synthetic_gold_has_one_article_label | PASS | Exactly one article_human_values entry each. |
| 21 | all_l1_l2_mappings_valid | PASS | Every synthetic (l1,l2) matches hv_categories. |
| 22 | direction_mapping_consistent_1_aligned_0_contradictory | PASS | All synthetic directions use 1=aligned/0=contradictory; codes match candidate target_direction tokens. |
| 23 | no_training_ready_true_in_manifest | PASS | Manifest introduces no training_ready=true; all 6 source candidates remain training_ready=false. |
| 24 | no_extra_labels_added | PASS | No synthetic article carries more than one label. |
| 25 | no_task2_subevent_labels_added | PASS | All synthetic subevents_human_values are empty. |
| 26 | official_train_event_base_unchanged | PASS | sha256 unchanged. |
| 27 | official_train_human_values_unchanged | PASS | sha256 unchanged. |
| 28 | official_dev_files_unchanged | PASS | dev event_base + gold sha256 unchanged. |
| 29 | official_hv_category_files_unchanged | PASS | hv_categories sha256 unchanged. |
| 30 | evaluation_py_unchanged | PASS | evaluation.py sha256 unchanged. |
| 31 | source_files_unchanged | PASS | No source-file change beyond pre-existing set (git status invariant). |
| 32 | only_new_ablation_input_folder_written | PASS | Only path written is output/research_ablation_inputs/20260702_193701 (output/ gitignored). |
| 33 | no_training_run | PASS | No training invoked by this task. |
| 34 | no_ablation_run | PASS | No ablation invoked by this task. |
| 35 | no_fallback_implementation | PASS | No fallback paths; every precondition/mapping check raises on failure. |
