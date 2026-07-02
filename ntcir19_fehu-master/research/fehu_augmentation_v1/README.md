# FEHU Augmentation v1 — Planning Stage

> **This module DOES NOT GENERATE augmented data.**
> It only selects targets, extracts seeds, drafts prompts, and defines the
> validation schema. Generation is a later phase that requires explicit
> approval and an API key.

## Files

| File | Purpose |
|---|---|
| `METHOD_DESIGN.md` | Graduate-level method design — read this first |
| `build_augmentation_plan.py` | Pick target labels, extract seeds, write plan |
| `augmentation_schema.json` | Strict JSON Schema for future augmented samples |
| `validate_augmented_data.py` | Local validator (no API) for future augmented JSONL |
| (this file) | Usage overview |

## Run the planner (pilot profile)

```bash
python research/fehu_augmentation_v1/build_augmentation_plan.py \
    --diagnosis_dir output/research_label_diagnosis/20260613_145847 \
    --max_labels 20 \
    --budget_profile pilot
```

Output (timestamped, never overwrites):

```
output/research_augmentation_plan/YYYYMMDD_HHMMSS/
├── augmentation_target_labels.csv
├── augmentation_plan_by_label.csv
├── augmentation_budget_summary.csv
├── selected_seed_instances.jsonl
├── target_label_definitions.json
├── augmentation_prompt_blueprints.md
├── augmentation_plan_report.md
├── augmentation_plan_config.json
└── figures/
```

The planner reads **TRAIN gold only** for seed extraction. Dev gold is consulted
purely as a diagnosis signal (which labels are hard); its content is never
copied into augmented data.

## Run the validator (when you eventually have augmented samples)

```bash
python research/fehu_augmentation_v1/validate_augmented_data.py \
    --input path/to/augmented_samples.jsonl
```

If `--input` is omitted, the validator prints usage and exits cleanly.
No API calls; no model loading.

## What this stage does NOT do

- Does NOT call any LLM provider.
- Does NOT generate, paraphrase, or synthesize any text.
- Does NOT modify existing prediction or cache files.
- Does NOT train any model.
- Does NOT write into `output/task1*` or `logs/`.

## Next phase (not implemented)

`research/fehu_augmentation_v1/run_generation.py` (future) will consume
`selected_seed_instances.jsonl` + `augmentation_prompt_blueprints.md` and
produce real augmented data, with teacher verification and JSON-Schema-checked
output. That step has not been authorised yet.
