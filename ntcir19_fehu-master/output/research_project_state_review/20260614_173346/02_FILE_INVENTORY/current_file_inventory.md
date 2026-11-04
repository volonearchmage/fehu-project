# Current File Inventory

Each row is independently checked against the filesystem at audit time.
Size for directories is the sum of all contained file sizes.

## Official benchmark

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `evaluation.py` | file | yes | 2026-05-17T17:39:23 | 11718 |
| `dataset/dev/dev_event_base.json` | file | yes | 2026-05-17T17:39:23 | 1138358 |
| `dataset/train/train_event_base.json` | file | yes | 2026-05-17T17:39:23 | 8010742 |
| `dataset/test/test_article_event_base.json` | file | yes | 2026-05-17T17:39:23 | 865214 |
| `dataset/test/test_subevent_event_base.json` | file | yes | 2026-05-17T17:39:23 | 1072171 |
| `dataset/gold_labels/train/train_human_values.json` | file | yes | 2026-05-17T17:39:23 | 13220101 |
| `dataset/gold_labels/dev/dev_human_values.json` | file | yes | 2026-05-17T17:39:23 | 1918804 |
| `dataset/hv_categories/direction_mapping.json` | file | yes | 2026-05-17T17:39:23 | 48 |
| `dataset/hv_categories/human_value_level1_values.json` | file | yes | 2026-05-17T17:39:23 | 1569 |
| `dataset/hv_categories/human_value_level2_values.json` | file | yes | 2026-05-17T17:39:23 | 573 |
| `dataset/hv_categories/level_1_to_level_2.json` | file | yes | 2026-05-17T17:39:23 | 2544 |

## Legacy patched scripts (tracked, modified)

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `src/run_pipeline.py` | file | yes | 2026-06-13T23:29:09 | 25822 |
| `src/train_deberta.py` | file | yes | 2026-06-13T23:34:00 | 21423 |
| `src/hybrid_pipeline.py` | file | yes | 2026-06-13T23:34:38 | 25367 |

## Untracked but present scripts

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `src/run_pipeline_deepseek_flash.py` | file | yes | 2026-05-19T19:53:20 | 23900 |
| `src/hybrid_v2.py` | file | yes | 2026-05-19T19:29:04 | 37089 |
| `src/collect_results.py` | file | yes | 2026-06-14T00:20:11 | 14185 |
| `src/regenerate_deberta_predictions.py` | file | yes | 2026-06-14T00:36:41 | 6495 |
| `src/prompts.py` | file | yes | 2026-05-17T17:39:23 | 7038 |

## Research modules

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `research/fehu_label_diagnosis/label_diagnosis.py` | file | yes | 2026-06-13T14:50:55 | 68746 |
| `research/fehu_project_audit/README.md` | file | yes | 2026-06-13T17:40:33 | 1755 |
| `research/fehu_repair_and_augmentation_v1/WORKLOG.md` | file | yes | 2026-06-13T18:18:14 | 5818 |
| `research/fehu_repair_and_augmentation_v1/FINAL_SUMMARY.md` | file | yes | 2026-06-14T15:27:11 | 12830 |
| `research/fehu_experiment_management/experiment_registry.py` | file | yes | 2026-06-14T01:16:21 | 9855 |
| `research/fehu_experiment_management/visualize_results.py` | file | yes | 2026-06-14T01:50:15 | 16069 |
| `research/fehu_experiment_management/OUTPUT_NAMING.md` | file | yes | 2026-06-14T00:54:13 | 5670 |
| `research/fehu_augmentation_v1/build_augmentation_plan.py` | file | yes | 2026-06-14T12:35:19 | 41058 |
| `research/fehu_augmentation_v1/validate_augmented_data.py` | file | yes | 2026-06-14T01:53:03 | 10960 |
| `research/fehu_augmentation_v1/augmentation_schema.json` | file | yes | 2026-06-14T01:52:01 | 4746 |
| `research/fehu_augmentation_v1/METHOD_DESIGN.md` | file | yes | 2026-06-14T01:51:59 | 10628 |
| `research/fehu_augmentation_generation_preview_v1/run_generation_preview.py` | file | yes | 2026-06-14T17:16:07 | 55512 |
| `research/fehu_augmentation_generation_preview_v1/inspect_generation_preview.py` | file | yes | 2026-06-14T16:33:26 | 6957 |
| `research/fehu_augmentation_generation_preview_v1/README.md` | file | yes | 2026-06-14T17:18:05 | 3748 |
| `research/fehu_augmentation_generation_preview_v1/WORKLOG.md` | file | yes | 2026-06-14T16:23:24 | 2847 |
| `research/fehu_augmentation_generation_preview_v1/FINAL_REPORT.md` | file | yes | 2026-06-14T16:41:48 | 10943 |
| `research/fehu_augmentation_generation_preview_v1/PREVIEW_REVISION_REPORT.md` | file | yes | 2026-06-14T17:19:23 | 10852 |
| `research/fehu_submission_safety/fehu_prediction_format_guard.py` | file | yes | 2026-06-14T16:34:49 | 18893 |
| `research/fehu_submission_safety/augmented_training_data_guard.py` | file | yes | 2026-06-14T16:36:25 | 14019 |
| `research/fehu_submission_safety/FORMAT_REQUIREMENTS.md` | file | yes | 2026-06-14T16:25:23 | 7613 |
| `research/fehu_submission_safety/README.md` | file | yes | 2026-06-14T16:23:30 | 3599 |
| `research/fehu_generation_model_strategy/MODEL_SELECTION_AND_COST_STRATEGY.md` | file | yes | 2026-06-14T16:25:28 | 6212 |

## Output / prediction folders (must remain untouched here)

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `output/task1/` | dir | yes | 2026-05-17T22:11:00 | 418519 |
| `output/task1_prompt/` | dir | yes | 2026-05-18T18:48:32 | 202495 |
| `output/task1_deberta/` | dir | yes | 2026-05-18T19:08:50 | 510564 |
| `output/task1_hybrid/` | dir | yes | 2026-05-17T21:30:47 | 1617412 |
| `output/task1_hybrid_v2/` | dir | yes | 2026-05-18T19:59:11 | 1558089 |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` | dir | yes | 2026-05-18T20:31:37 | 1571252 |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/` | dir | yes | 2026-05-19T19:30:07 | 1579843 |
| `output/task1_prompt_deepseek_v4_flash/` | dir | yes | 2026-05-19T20:01:57 | 321203 |
| `output/task1_prompt_deepseek_v4_flash_limit5/` | dir | yes | 2026-05-19T20:02:40 | 11740 |
| `output/task1_hybrid_v2_limit20/` | dir | yes | 2026-05-18T20:04:57 | 184837 |

## Research outputs (timestamped)

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `output/research_label_diagnosis/20260613_145549/` | dir | yes | 2026-06-13T14:55:49 | 833020 |
| `output/research_label_diagnosis/20260613_145847/` | dir | yes | 2026-06-13T14:58:48 | 2021505 |
| `output/research_project_audit/20260613_151432/` | dir | yes | 2026-06-13T17:58:05 | 83827 |
| `output/research_experiment_registry/20260614_123732/` | dir | yes | 2026-06-14T12:37:32 | 15530 |
| `output/research_visualization_dashboard/20260614_123742/` | dir | yes | 2026-06-14T12:37:43 | 508671 |
| `output/research_augmentation_plan/20260614_131524/` | dir | yes | 2026-06-14T13:15:24 | 737536 |
| `output/research_submission_safety/20260614_163804/` | dir | yes | 2026-06-14T16:38:04 | 2307 |
| `output/research_generation_preview/20260614_163649/` | dir | yes | 2026-06-14T16:36:49 | 225381 |
| `output/research_generation_preview/20260614_171644/` | dir | yes | 2026-06-14T17:16:44 | 271558 |

## Caches (must remain untouched here)

| Path | Kind | Exists | mtime | Bytes |
|---|---|---|---|---:|
| `logs/cache_dev.json` | file | yes | 2026-05-17T17:39:23 | 234426 |
| `logs/cache_dev_deepseek_v4_flash.json` | file | yes | 2026-05-19T20:22:33 | 389579 |
| `logs/cache_hybrid_dev.json` | file | yes | 2026-05-17T22:05:48 | 224223 |
| `logs/cache_hybrid_v2_dev.json` | file | yes | 2026-05-18T20:18:02 | 254423 |
| `logs/cache_hybrid_v2_dev_deepseek_deepseek_v4_pro.json` | file | yes | 2026-05-18T21:03:16 | 284035 |
| `logs/cache_hybrid_v2_dev_deepseek_deepseek_v4_flash.json` | file | yes | 2026-05-19T19:39:30 | 294753 |
| `logs/cache_test_openai.json` | file | yes | 2026-05-17T17:39:23 | 242150 |