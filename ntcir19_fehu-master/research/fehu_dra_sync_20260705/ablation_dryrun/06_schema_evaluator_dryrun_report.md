# Schema & Evaluator Compatibility Dry-Run Report — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T19:46:37
**Output folder:** `output/research_ablation_dryrun/20260702_194637`

## 1. Current branch
`main`

## 2. Pre-existing git status (unrelated, untouched)
`src/hybrid_pipeline.py` (M), `src/run_pipeline.py` (M), `src/train_deberta.py` (M),
`HYBRID_ROADMAP.md`, `research/`, `src/collect_results.py`, `src/hybrid_v2.py`,
`src/regenerate_deberta_predictions.py`, `src/run_pipeline_deepseek_flash.py`.

## 3. Files read
9 ablation input files; official train/dev event_base + gold; hv_categories (L1,L2,L1->L2);
evaluation.py. sha256 captured before/after for all official files and evaluation.py.

## 4. Files written (new folder only)
01_schema_compatibility_table.csv, 02_evaluator_format_dryrun_gold_task1b.json,
03_evaluator_format_dryrun_pred_task1b.json, 04_evaluator_dryrun_result.json,
05_dryrun_manifest.json, 06_schema_evaluator_dryrun_report.md.

## 5. Ablation input summary
Baseline 1228/1228 (event/gold); augmented 1234/1234;
synthetic additions 6/6; augmented == baseline ++ 6 synthetic (order preserved).

## 6. Schema compatibility summary
43 PASS / 0 REVIEW / 0 FAIL of 43. Synthetic events/gold match the
official event_base and Task-1b gold schemas; guids/actor ids unique with no official collision;
every (l1,l2) matches hv_categories; directions are '0'/'1' consistent with 1=aligned/0=contradictory;
no Task-2 labels; one label per synthetic sample.

## 7. Evaluator CLI inspection summary
evaluation.py Task-1b path: parse_task1b builds labels `"{direction}:{l1}"`; evaluate() gives
micro/macro-F1; direction_reverse_rate_gold_excl() gives DRR. **Line 262 sets `DEBUG=True`, which
overwrites `sys.argv` with hardcoded `/tmp/ntcir19_fehu/...` paths** — so the shipped CLI ignores
passed arguments and cannot run on arbitrary files without editing the script (which is prohibited).
We did not modify it. Note: the DRR code internally treats '0'=aligned/'1'=contradictory (opposite of
the project convention), but this symmetric bucketing does not change results for identical gold/pred.

## 8. Evaluator dry-run result
Method: imported the official evaluator functions and ran them on the dry-run gold/pred (6 synthetic
records each; labels accepted). Real CLI attempt was executed and recorded honestly:
- CLI exit code: 1
- CLI stderr tail: FileNotFoundError: [Errno 2] No such file or directory: '/tmp/ntcir19_fehu/dataset/gold_labels/test/test_article_human_values.json'

Function-level result: micro_f1=1.0, macro_f1=1.0,
direction_reverse_rate=0.0 (rev=0/denom=6, ambiguous_filtered=0),
support_instances=6. Task-1b format ACCEPTED; F1 perfect and DRR=0 for
identical gold/pred, as expected.

## 9. REVIEW/FAIL checks and implications
No FAIL. The only material caveat (folded into `evaluator_cli_understood`, still PASS): the shipped
CLI cannot be pointed at arbitrary files due to `DEBUG=True`. Implication for later ablation: invoke
the evaluator functions programmatically (as done here) or set DEBUG=False at run time — but
`evaluation.py` must not be modified in this workflow.

## 10. Official data unchanged confirmation
All official files read are byte-identical (sha256 before == after): True.
evaluation.py sha256 unchanged: True.

## 11. Statement
This task performed schema/evaluator compatibility dry-run only. It did not train a model, did not run
ablation, and did not modify official data.

## 12. Next step
If this dry-run is accepted, prepare a controlled ablation execution plan. Do not run training until
explicit approval.

## Validation results
| # | check_name | status | explanation |
|---|-----------|--------|-------------|
| 1 | ablation_input_folder_exists | PASS | output/research_ablation_inputs/20260702_193701 present. |
| 2 | all_required_ablation_input_files_exist | PASS | All 9 ablation input files present. |
| 3 | baseline_event_base_json_parse_valid | PASS | Parsed 1228 baseline event records. |
| 4 | baseline_human_values_json_parse_valid | PASS | Parsed 1228 baseline gold records. |
| 5 | augmented_event_base_json_parse_valid | PASS | Parsed 1234 augmented event records. |
| 6 | augmented_human_values_json_parse_valid | PASS | Parsed 1234 augmented gold records. |
| 7 | synthetic_event_additions_json_parse_valid | PASS | Parsed 6 synthetic events. |
| 8 | synthetic_human_value_additions_json_parse_valid | PASS | Parsed 6 synthetic gold records. |
| 9 | manifest_json_parse_valid | PASS | Manifest parsed. |
| 10 | baseline_event_count_1228 | PASS | 1228 baseline events. |
| 11 | baseline_gold_count_1228 | PASS | 1228 baseline gold. |
| 12 | augmented_event_count_1234 | PASS | 1234 augmented events. |
| 13 | augmented_gold_count_1234 | PASS | 1234 augmented gold. |
| 14 | synthetic_event_count_6 | PASS | 6 synthetic events. |
| 15 | synthetic_gold_count_6 | PASS | 6 synthetic gold. |
| 16 | augmented_equals_baseline_plus_synthetic_events | PASS | Augmented events == baseline ++ 6 synthetic (order preserved). |
| 17 | augmented_equals_baseline_plus_synthetic_gold | PASS | Augmented gold == baseline ++ 6 synthetic (order preserved). |
| 18 | synthetic_guid_unique | PASS | 6 unique synthetic guids. |
| 19 | synthetic_guid_no_collision | PASS | No synthetic guid in official train. |
| 20 | synthetic_actor_id_unique | PASS | 6 unique synthetic actor ids. |
| 21 | synthetic_actor_id_no_collision | PASS | No synthetic actor id in official train. |
| 22 | synthetic_event_schema_valid | PASS | Each synthetic event has guid/title/content/actors/subevents and exactly one actor. |
| 23 | synthetic_gold_schema_valid | PASS | Each synthetic gold has guid/article_human_values/subevents_human_values and full label fields. |
| 24 | synthetic_guid_actor_link_valid | PASS | Actor id follows aug_<candidate_id>-0 and matches the gold label actor for the same guid. |
| 25 | l1_l2_mapping_valid | PASS | Every synthetic (l1,l2) matches hv_categories. |
| 26 | direction_values_valid | PASS | All synthetic directions are '0' or '1'. |
| 27 | direction_mapping_consistent_1_aligned_0_contradictory | PASS | Each synthetic direction code matches candidate target_direction (1=aligned, 0=contradictory). |
| 28 | no_task2_subevent_labels_added | PASS | All synthetic subevents_human_values are empty (no Task-2 labels). |
| 29 | no_extra_synthetic_labels_added | PASS | Exactly one article-level label per synthetic sample. |
| 30 | evaluation_py_readable | PASS | evaluation.py parsed and understood. |
| 31 | evaluator_cli_understood | PASS | CLI uses --gold_task1 + --pred_task1b; label '{direction}:{l1}'. Discovered line 262 DEBUG=True overwrites sys.argv with hardcoded /tmp paths, so the shipped CLI cannot accept arbitrary files. |
| 32 | evaluator_task1b_dryrun_executed | PASS | Ran official parse_task1b+evaluate+DRR via module import on 6 gold / 6 pred instances (labels accepted). Real CLI attempt recorded: exit=1. |
| 33 | evaluator_task1b_drr_zero_for_identical_gold_pred | PASS | DRR=0.0 for identical gold/pred. |
| 34 | evaluator_task1b_f1_perfect_or_explained | PASS | micro_f1=1.0, macro_f1=1.0 (perfect for identical gold/pred). |
| 35 | official_train_files_unchanged | PASS | train event_base+gold sha256 unchanged. |
| 36 | official_dev_files_unchanged | PASS | dev event_base+gold sha256 unchanged. |
| 37 | official_hv_category_files_unchanged | PASS | hv_categories sha256 unchanged. |
| 38 | evaluation_py_unchanged | PASS | evaluation.py sha256 unchanged. |
| 39 | source_files_unchanged | PASS | git status invariant (no source change beyond pre-existing set). |
| 40 | only_new_dryrun_folder_written | PASS | Only path written is output/research_ablation_dryrun/20260702_194637 (output/ gitignored). |
| 41 | no_training_run | PASS | No training invoked. |
| 42 | no_ablation_run | PASS | No ablation invoked. |
| 43 | no_fallback_implementation | PASS | No fallback logic; CLI blocker exposed honestly and dry-run used the real evaluator functions. |
