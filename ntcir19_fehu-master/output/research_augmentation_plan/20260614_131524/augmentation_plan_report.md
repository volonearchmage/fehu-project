# FEHU Augmentation Plan Report (Pilot)

**Generated:** 20260614_131524  
**Source diagnosis:** `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_label_diagnosis/20260613_145847`  
**Budget profile:** `pilot`  
**Max labels:** 20

> No augmented data has been generated. This is a planning artifact.

## Method weights

- rare_score: 0.4
- low_recall_score: 0.25
- direction_error_score: 0.2
- false_positive_score: 0.15

## Selected labels (top by priority)

| Rank | L1 ID | Label | Train | Group | Types | Priority |
|---|---|---|---|---|---|---|
| 1 | 32 | Be behaving properly | 60 | frequent | rare_positive|paraphrase|hard_negative | 0.7882 |
| 2 | 51 | Have the wisdom to accept others | 36 | medium | rare_positive|paraphrase|hard_negative | 0.7679 |
| 3 | 7 | Have an exciting life | 58 | frequent | rare_positive|paraphrase|hard_negative | 0.7537 |
| 4 | 24 | Be neat and tidy | 4 | very_rare | rare_positive|paraphrase | 0.6492 |
| 5 | 35 | Be humble | 25 | medium | rare_positive|paraphrase | 0.6451 |
| 6 | 39 | Be forgiving | 30 | medium | rare_positive|paraphrase | 0.6441 |
| 7 | 31 | Be self-disciplined | 34 | medium | rare_positive|paraphrase | 0.6433 |
| 8 | 8 | Have a varied life | 35 | medium | rare_positive|paraphrase | 0.6431 |
| 9 | 49 | Have a world of beauty | 44 | frequent | rare_positive|paraphrase | 0.6413 |
| 10 | 10 | Have pleasure | 45 | frequent | rare_positive|paraphrase | 0.6411 |
| 11 | 17 | Have the right to command | 47 | frequent | rare_positive|paraphrase | 0.6407 |
| 12 | 9 | Be daring | 35 | medium | rare_positive|paraphrase | 0.6362 |
| 13 | 48 | Have harmony with nature | 28 | medium | rare_positive|paraphrase | 0.6356 |
| 14 | 4 | Be independent | 57 | frequent | rare_positive|paraphrase | 0.6316 |
| 15 | 43 | Have loyalty towards friends | 90 | frequent | rare_positive|paraphrase | 0.6268 |
| 16 | 29 | Be holding religious faith | 255 | frequent | hard_negative|direction_contrastive | 0.4980 |
| 17 | 41 | Be loving | 133 | frequent | hard_negative | 0.4924 |
| 18 | 12 | Have success | 338 | frequent | hard_negative|direction_contrastive | 0.4845 |
| 19 | 3 | Be choosing own goals | 123 | frequent | hard_negative | 0.4829 |
| 20 | 38 | Be honest | 486 | frequent | hard_negative|direction_contrastive | 0.4711 |

## Seed pool

- Selected labels: 20
- With TRAIN article seeds: 20
- Without article seeds: 0
- Total seed instances written: 194

## Budget (pilot)

| Category | Samples |
|---|---|
| rare_positive | 45 |
| paraphrase | 135 |
| hard_negative | 24 |
| direction_contrastive (samples) | 12 |
| **TOTAL** | **216** |

## Outputs

All artifacts written to `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_augmentation_plan/20260614_131524`:

- `augmentation_target_labels.csv` — scored labels (full table)
- `augmentation_plan_by_label.csv` — per-label budget allocation
- `augmentation_budget_summary.csv` — totals by type
- `selected_seed_instances.jsonl` — TRAIN seeds (one per line)
- `target_label_definitions.json` — definitions + rationale per selected label
- `augmentation_prompt_blueprints.md` — templates (NOT executed)
- `augmentation_plan_config.json` — run config
- `figures/` — three diagnostic PNGs

## What this plan does NOT do

- No LLM was called.
- No augmented samples were written.
- No training was started.
- No existing files were modified.

The next step (not authorised in this session) would be `run_generation.py` —
consuming `selected_seed_instances.jsonl` + the prompt blueprints to produce
actual augmented data, then validating it via `validate_augmented_data.py`
against `augmentation_schema.json`.