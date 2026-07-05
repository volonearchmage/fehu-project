# Repair + Augmentation Planning Work Log

**Timestamp:** 2026-06-13 (audit-driven repair session)
**Git HEAD:** 4142f10c00b2fb9b4942c22cd3b6e521f582a415
**Branch:** main

## Git status at start

```
?? HYBRID_ROADMAP.md
?? research/
?? src/collect_results.py
?? src/hybrid_v2.py
?? src/regenerate_deberta_predictions.py
?? src/run_pipeline_deepseek_flash.py
```

Note: the touched legacy scripts (`src/run_pipeline.py`, `src/train_deberta.py`, `src/hybrid_pipeline.py`) are **tracked** in git. After patches the diff will be visible via `git diff`. The new research modules under `research/` are untracked.

## Sources of truth consulted

- `output/research_project_audit/20260613_151432/final_audit_report.md`
- `output/research_project_audit/20260613_151432/proposed_patch_plan.md`
- `output/research_label_diagnosis/20260613_145847/diagnosis_report.md`
- `output/research_label_diagnosis/20260613_145847/overall_metrics.csv`
- `output/research_label_diagnosis/20260613_145847/rare_low_recall_labels.csv`
- `output/research_label_diagnosis/20260613_145847/high_false_positive_labels.csv`
- `output/research_label_diagnosis/20260613_145847/high_direction_error_labels.csv`
- `output/research_label_diagnosis/20260613_145847/frequency_group_summary.csv`
- `output/research_label_diagnosis/20260613_145847/label_frequency_l1.csv`
- `output/research_label_diagnosis/20260613_145847/method_gap_analysis.csv`
- `CLAUDE.md`

## Files this session WILL change

Code patches (legacy script repair):

| File | Reason |
|---|---|
| `src/run_pipeline.py` | Fix C1 (`--model` ignored), H1 (cache not model-keyed), H4 (limit not filtering gold), C2 (default output collision); add `run_config.json` + `metrics.json` |
| `src/train_deberta.py` | Fix C2 (default `output/task1/` collision) → `output/task1_deberta/`; add `--output_dir` / `--version` / `--threshold` / `--force_overwrite`; emit `run_config.json` for future runs |
| `src/hybrid_pipeline.py` | Fix H3 (`DEBERTA_OUT = output/task1`) → `output/task1_deberta/`; method-keyed cache; deprecated `datetime.utcnow()` removed; richer `run_config.json` |
| `src/collect_results.py` | Use canonical folders only; never use `output/task1/` as a method source |
| `src/regenerate_deberta_predictions.py` | Write `run_config.json` next to its predictions; record threshold + checkpoint provenance |

New research modules:

| Path | Purpose |
|---|---|
| `research/fehu_repair_and_augmentation_v1/` | This worklog + final summary |
| `research/fehu_experiment_management/experiment_registry.py` | Scan output folders → registry CSV/JSON |
| `research/fehu_experiment_management/visualize_results.py` | Dashboard figures from diagnosis CSVs |
| `research/fehu_experiment_management/README.md` | Usage of registry + visualizer |
| `research/fehu_experiment_management/OUTPUT_NAMING.md` | Canonical output naming convention |
| `research/fehu_augmentation_v1/build_augmentation_plan.py` | Plan + seed extraction (no LLM) |
| `research/fehu_augmentation_v1/validate_augmented_data.py` | Schema validator for future augmented data |
| `research/fehu_augmentation_v1/augmentation_schema.json` | JSON Schema for augmented samples |
| `research/fehu_augmentation_v1/METHOD_DESIGN.md` | Graduate-level research method design |
| `research/fehu_augmentation_v1/README.md` | Module usage |

## Files this session will NOT change

| File | Reason |
|---|---|
| `evaluation.py` | User constraint: never modify |
| `dataset/**` | Official data; never modify |
| any `pred_task1*.json` | Prediction outputs are immutable for this session |
| any `logs/cache_*.json` | Cache files are immutable for this session |
| `output/task1/`, `output/task1_prompt/`, `output/task1_deberta/`, `output/task1_hybrid*` | Existing output folders are immutable; new outputs go to new timestamped folders |
| `src/run_pipeline_deepseek_flash.py` | Already audit-clean; no changes needed |
| `src/hybrid_v2.py` | Already audit-clean; no changes needed |
| `src/prompts.py` | Dead-code cleanup deferred per patch plan P10 |
| `research/fehu_label_diagnosis/label_diagnosis.py` | Already audit-clean; no changes needed |
| Any `.env` file | Will not be created or read |

## Safety constraints honored

- No API calls (OpenAI, DeepSeek, Claude, Gemini, etc.)
- No model training
- No full inference
- No git commit / git push
- Only patches + new files; no deletions, renames, or moves of existing files
- Every new analysis output goes to a fresh `YYYYMMDD_HHMMSS` folder under `output/research_*/`
- Patches preserve all prior functional behavior unless explicitly identified as a bug fix

## Output folders that will be created during this session

- `output/research_experiment_registry/YYYYMMDD_HHMMSS/`
- `output/research_visualization_dashboard/YYYYMMDD_HHMMSS/`
- `output/research_augmentation_plan/YYYYMMDD_HHMMSS/`

No new outputs will go into `output/task1*/` or `logs/`.

## Diagnosis-data signals driving the augmentation plan

Top signals to encode into priority scores:

| Signal | Top labels (from diagnosis) |
|---|---|
| Rare + recall_dir = 0.0 across all methods | Have loyalty towards friends (43), Be behaving properly (32), Have an exciting life (7), Be independent (4), Have the right to command (17), Have pleasure (10), Have a world of beauty (49), Be self-disciplined (31), Be forgiving (39), Have harmony with nature (48), Be humble (35) |
| Catastrophic direction reversal (DeBERTa) | Be just (45) DRR=0.90, Have a stable society (27) DRR=0.84, Have a safe country (26) DRR=0.76, Be responsible (42) DRR=0.11 |
| Over-predicted (low precision, high FP) | Be helpful (37), Have good health (22), Be compliant (30), Be courageous (15), Have success (12), Be honest (38), Be holding religious faith (29) |

These will be encoded as priority components in `build_augmentation_plan.py`.
