# FEHU Augmentation Generation Preview (v1)

> **This module never calls an API.**
> It turns the existing augmentation plan into reviewable request previews.
> Generation itself is a separate, later step that requires explicit approval.

## Purpose

Take the plan produced by `research/fehu_augmentation_v1/build_augmentation_plan.py` and translate it into concrete, ready-to-execute **request objects** that a human can review before any API call is made.

## Inputs

- `output/research_augmentation_plan/{TS}/augmentation_plan_by_label.csv`
- `output/research_augmentation_plan/{TS}/augmentation_target_labels.csv`
- `output/research_augmentation_plan/{TS}/selected_seed_instances.jsonl`
- `output/research_augmentation_plan/{TS}/target_label_definitions.json`
- `output/research_augmentation_plan/{TS}/augmentation_prompt_blueprints.md`
- `output/research_augmentation_plan/{TS}/augmentation_plan_config.json`

## Commands

```bash
# 1. Build the preview (≤ 20 requests, tiny pilot)
python research/fehu_augmentation_generation_preview_v1/run_generation_preview.py \
    --plan_dir output/research_augmentation_plan/20260614_131524 \
    --profile tiny_pilot_v1 \
    --max_total_requests 20

# 2. Inspect the resulting preview folder
python research/fehu_augmentation_generation_preview_v1/inspect_generation_preview.py \
    --preview_dir output/research_generation_preview/<YYYYMMDD_HHMMSS>
```

## Outputs (timestamped, never overwrite previous)

```
output/research_generation_preview/YYYYMMDD_HHMMSS/
├── generation_requests_preview.jsonl     # one request per line, ready for future execution
├── generation_requests_preview.csv       # tabular summary
├── request_summary_by_type.csv
├── request_summary_by_label.csv
├── selected_preview_seed_instances.jsonl # the TRAIN seeds actually used by the preview
├── generation_preview_config.json
├── generation_preview_report.md
├── human_review_sheet.csv                # one row per request, "review_status=pending" by default
└── figures/
    ├── requests_by_augmentation_type.png
    ├── requests_by_label.png
    └── request_budget_vs_plan.png
```

## Safety assumptions

- No environment variable is read for API keys.
- No HTTP libraries are imported in any preview module.
- The preview script writes objects with `"preview_only": true` and
  `"do_not_execute": true` so any future runner can refuse to forward them
  directly to an API.

## Preview revision history

| Revision | Date | Summary |
|---|---|---|
| 1 | 2026-06-14 (16:36 UTC) | Initial preview |
| **2** | 2026-06-14 (17:16 UTC) | Strengthened prompts after manual review: actor-alias support, sentence-boundary seed truncation, expanded output schema (14 fields including `is_positive`, `l1_value_id`, `l2_value_id`, `direction`), stronger actor-specific evidence requirement, "do not make any other value more salient than the target value" instead of forbidding multi-value, clearer topic-vs-actor distinction for hard-negatives. Every request now carries `preview_revision = 2`. See `PREVIEW_REVISION_REPORT.md`. |

## What this module does NOT do

- Does not call OpenAI, DeepSeek, or any other model provider.
- Does not generate, paraphrase, or synthesize any text content.
- Does not modify the existing augmentation plan.
- Does not produce a final FEHU submission file.
- Does not write into any `output/task1*/` folder or `logs/`.

## Relation to FEHU requirements

The previews are *training-data* generation requests. They do not contain any
prediction in the FEHU submission format. Any final FEHU prediction file
produced later must still pass
`research/fehu_submission_safety/fehu_prediction_format_guard.py` before
submission.
