# Generation Preview Work Log

**Session date:** 2026-06-14
**Phase:** Augmentation Generation Preview + FEHU Format Safety Guard
**Trigger:** post-repair-verification project state; user requested controlled first step of the augmentation research pipeline.

## Inputs

- `output/research_augmentation_plan/20260614_131524/` — the existing augmentation plan
  - `augmentation_plan_by_label.csv` — 20 selected labels with per-label budgets
  - `augmentation_target_labels.csv` — full priority-scored label table
  - `selected_seed_instances.jsonl` — 194 TRAIN-only seed instances
  - `target_label_definitions.json` — definitions + rationales
  - `augmentation_prompt_blueprints.md` — text templates (not yet executed)
  - `augmentation_plan_config.json`
- `output/research_label_diagnosis/20260613_145847/` — high_false_positive / high_direction_error tables

## Files this session WILL create

- `research/fehu_augmentation_generation_preview_v1/{README,WORKLOG,FINAL_REPORT}.md`
- `research/fehu_augmentation_generation_preview_v1/run_generation_preview.py`
- `research/fehu_augmentation_generation_preview_v1/inspect_generation_preview.py`
- `research/fehu_submission_safety/{README,FORMAT_REQUIREMENTS}.md`
- `research/fehu_submission_safety/fehu_prediction_format_guard.py`
- `research/fehu_submission_safety/augmented_training_data_guard.py`
- `research/fehu_generation_model_strategy/{README,MODEL_SELECTION_AND_COST_STRATEGY}.md`

## Files this session will NOT modify

- `evaluation.py`, `dataset/**`, any existing `pred_task1*.json`, any `logs/cache_*.json`
- The existing augmentation plan folder (`output/research_augmentation_plan/20260614_131524/`)
- Any existing research module
- Patched legacy scripts (run_pipeline.py, train_deberta.py, hybrid_pipeline.py, etc.)

## New output folders to be created

- `output/research_generation_preview/YYYYMMDD_HHMMSS/` (from preview script)
- `output/research_submission_safety/YYYYMMDD_HHMMSS/` (from format guard)

## Constraints honoured

- No API calls. The preview script emits request objects with `"preview_only": true` and `"do_not_execute": true`.
- No augmented data generated. No model trained. No inference run.
- All TRAIN seeds; no dev/test content used in any preview prompt.
- Direction encoded as `"0"=contradictory`, `"1"=aligned` per `direction_mapping.json`.
- Every new output is timestamped; nothing overwrites prior results.

## tiny_pilot_v1 allocation plan (derived from the plan CSV)

| Type | Plan labels available | Target requests |
|---|---|---|
| paraphrase | 15 labels, all have seeds | top 4 by priority |
| rare_positive | 15 labels | top 4 by priority |
| hard_negative | 8 labels | top 4 by priority |
| direction_contrastive | 3 labels (29, 12, 38) | 3 pairs × 2 = 6 |

Expected total: 4 + 4 + 4 + 6 = **18 requests** (under the 20 cap).
