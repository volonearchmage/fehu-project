# FEHU Repair & Augmentation Planning — Final Summary

**Session date:** 2026-06-14
**Inputs:** the audit (`output/research_project_audit/20260613_151432/`) and the diagnosis (`output/research_label_diagnosis/20260613_145847/`).
**Status:** all planned work completed without any API call, training, or destructive change.

---

## 1. Motivation

The audit identified two CRITICAL bugs (C1, C2), four HIGH issues (H1, H3, H4, H5), and several provenance gaps in the legacy scripts. The diagnosis showed strong, label-conditioned variation in recall, precision, and direction-error patterns — a clear case for *targeted* augmentation rather than uniform paraphrase. This session repairs the engineering issues and lays the planning foundation for diagnosis-driven augmentation, while explicitly **not** generating any augmented data, training any model, or calling any API.

---

## 2. What changed (files modified)

| File | Audit issue addressed | Summary of change |
|---|---|---|
| `src/run_pipeline.py` | C1, H1, H4, partly C2 | `--model` now reaches the API; cache is `cache_{mode}_openai_{slug}.json`; default output dir is `output/task1_prompt_openai_{slug}/`; `--limit N` filters the dev gold to the same N guids before scoring; `run_config.json` and `metrics.json` emitted next to predictions; overwrite-safe (timestamped sibling unless `--force_overwrite`). |
| `src/train_deberta.py` | C2 | Default output dir is now `output/task1_deberta/` (no more collision with `run_pipeline.py`); new CLI args `--output_dir/--version/--threshold/--force_overwrite`; `run_config.json` written next to predictions. |
| `src/hybrid_pipeline.py` | H3, M4, M5 | `DEBERTA_OUT` → `output/task1_deberta/`; cache is `cache_hybrid_v1_{mode}_openai_{slug}.json`; deprecated `datetime.utcnow()` replaced with timezone-aware `datetime.now(timezone.utc)`; `run_config.json` enriched with provider, model_slug, output_dir, cache_path, command_line, git_commit. |
| `src/collect_results.py` | output management | Drops `output/task1/` from method sources; documents legacy state; cache discovery prefers `cache_dev_openai_gpt_4o_mini.json` and `cache_dev_openai_gpt_4o.json` (the new convention) with the pre-audit caches as fallbacks. |
| `src/regenerate_deberta_predictions.py` | provenance gap | New CLI args (`--threshold`, `--output_dir`, `--force_overwrite`); emits `run_config.json` recording threshold, checkpoint dir, command line, git commit, timestamp. |

**Not modified** (by design): `evaluation.py`, `src/run_pipeline_deepseek_flash.py`, `src/hybrid_v2.py`, `src/prompts.py`, `research/fehu_label_diagnosis/label_diagnosis.py`, all dataset files, every `output/task1*/` and `logs/*` file.

---

## 3. What is new (files created)

### `research/fehu_repair_and_augmentation_v1/`
- `WORKLOG.md` — pre-patch inventory and safety constraints.
- `FINAL_SUMMARY.md` — this report.

### `research/fehu_experiment_management/`
- `experiment_registry.py` — scans every known output folder, classifies it (canonical / legacy / orphan / limit), and writes a registry CSV/JSON.
- `visualize_results.py` — reads a label-diagnosis output and produces a presentation-ready dashboard (8 PNGs + CSV summaries).
- `README.md` — usage docs.
- `OUTPUT_NAMING.md` — canonical naming convention for current and future runs.

### `research/fehu_augmentation_v1/`
- `METHOD_DESIGN.md` — graduate-level method design: "Diagnosis-driven Recall-focused Targeted Augmentation for FEHU Human Value Classification".
- `build_augmentation_plan.py` — diagnosis-driven planner; selects target labels, computes priority scores, extracts TRAIN-only seed instances, allocates pilot budget, emits prompt blueprints. **Does not call an API.**
- `augmentation_schema.json` — strict JSON Schema for future augmented samples.
- `validate_augmented_data.py` — local schema + semantic validator (no API).
- `README.md` — usage docs.

---

## 4. Why these changes improve reproducibility

- **No more silent overwrites.** Both prompt-only and DeBERTa-only had been writing to `output/task1/`. After the patches, each method has a distinct canonical folder and the scripts refuse to overwrite predictions unless explicitly forced (otherwise a timestamped sibling is created).
- **Model-keyed caches.** Every cache now includes provider and model slug in its filename AND in per-entry metadata. The `--model` flag is wired through the API call (the C1 bug). Re-running with a different model can no longer load a stale cache.
- **Provenance metadata.** Every patched script writes `run_config.json` next to its predictions, recording model, provider, version, mode, limit, output dir, cache path, timestamp, git commit, command line, taxonomy/prompt hashes, and key hyperparameters.
- **Correct limit-mode scoring.** `run_pipeline.py` no longer compares limit predictions against full-dev gold — the recall deflation is gone.
- **A single source of truth for naming.** `OUTPUT_NAMING.md` documents which folders are canonical, which are legacy, and what convention future folders must follow.

---

## 5. Improved output management

`experiment_registry.py` classifies the existing folders so the project can be navigated without manually remembering which folder means what:

| Tag | Folders |
|---|---|
| `canonical_prompt_oai` | `output/task1_prompt/` |
| `canonical_prompt_ds_flash` | `output/task1_prompt_deepseek_v4_flash/` |
| `canonical_deberta` | `output/task1_deberta/` |
| `canonical_hybrid_v1` | `output/task1_hybrid/` |
| `canonical_hybrid_v2_ds_pro` | `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` |
| `canonical_hybrid_v2_ds_flash` | `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/` |
| `canonical_hybrid_v2_oai_mini` | (canonical name; folder is currently MISSING) |
| `legacy_duplicate_ambiguous` | `output/task1/` |
| `orphan_legacy_hybrid_v2` | `output/task1_hybrid_v2/` |
| `limit_debug_run` | `output/task1_prompt_deepseek_v4_flash_limit5/`, `output/task1_hybrid_v2_limit20/` |

The visualizer turns the diagnosis CSVs into eight figures + two CSV summaries + a dashboard markdown — all to a new timestamped folder.

---

## 6. Augmentation planning method

**Selection.** Each L1 label is scored over four sub-scores in [0, 1]:

```
priority = 0.40 * rare_score
         + 0.25 * low_recall_score
         + 0.20 * direction_error_score
         + 0.15 * false_positive_score
```

Each label inherits one or more *augmentation types* depending on which diagnostic table flagged it: `rare_positive`, `paraphrase`, `hard_negative`, `direction_contrastive`.

**Budgets.** Three profiles (`pilot` / `medium` / `full`). Only `pilot` was run.

**Seed extraction.** TRAIN gold only. Dev gold is consulted purely as a difficulty signal — its content is never copied into augmented samples.

**Prompt blueprints.** Five templates (paraphrase, rare-positive, hard-negative, direction-contrastive, teacher verifier) are written to disk but **not executed**.

**Validation.** `validate_augmented_data.py` enforces the JSON Schema and semantic rules: L1↔L2 consistency, direction↔direction_name consistency, actor present in content, evidence sentence present (or marked `[derived]`), no duplicate `augmentation_id`, no content hash collisions with conflicting labels.

---

## 7. Outputs of this session

| Output folder | Source |
|---|---|
| `output/research_experiment_registry/20260614_123732/` | `experiment_registry.py` |
| `output/research_visualization_dashboard/20260614_123742/` | `visualize_results.py` |
| `output/research_augmentation_plan/20260614_131524/` | `build_augmentation_plan.py` |

### Top labels selected for the pilot augmentation plan (priority order)

| Rank | L1 | Label | Train | Group | Augmentation types |
|---|---|---|---:|---|---|
| 1 | 32 | Be behaving properly | 60 | frequent | rare_positive, paraphrase, hard_negative |
| 2 | 51 | Have the wisdom to accept others | 36 | medium | rare_positive, paraphrase, hard_negative |
| 3 | 7  | Have an exciting life | 58 | frequent | rare_positive, paraphrase, hard_negative |
| 4 | 24 | Be neat and tidy | 4 | very_rare | rare_positive, paraphrase |
| 5 | 35 | Be humble | 25 | medium | rare_positive, paraphrase |
| 6 | 39 | Be forgiving | 30 | medium | rare_positive, paraphrase |
| 7 | 31 | Be self-disciplined | 34 | medium | rare_positive, paraphrase |
| 8 | 8  | Have a varied life | 35 | medium | rare_positive, paraphrase |
| 9 | 49 | Have a world of beauty | 44 | frequent | rare_positive, paraphrase |
| 10 | 10 | Have pleasure | 45 | frequent | rare_positive, paraphrase |
| 11 | 17 | Have the right to command | 47 | frequent | rare_positive, paraphrase |
| 12 | 9  | Be daring | 35 | medium | rare_positive, paraphrase |
| 13 | 48 | Have harmony with nature | 28 | medium | rare_positive, paraphrase |
| 14 | 4  | Be independent | 57 | frequent | rare_positive, paraphrase |
| 15 | 43 | Have loyalty towards friends | 90 | frequent | rare_positive, paraphrase |
| 16 | 29 | Be holding religious faith | 255 | frequent | hard_negative, direction_contrastive |
| 17 | 41 | Be loving | 133 | frequent | hard_negative |
| 18 | 12 | Have success | 338 | frequent | hard_negative, direction_contrastive |
| 19 | 3  | Be choosing own goals | 123 | frequent | hard_negative |
| 20 | 38 | Be honest | 486 | frequent | hard_negative, direction_contrastive |

> "Group" is the `threshold_group` (zero_train / very_rare / rare / medium / frequent). Labels with train > 40 are marked `frequent` by threshold even if they are still relatively rare compared to "Be responsible" (2031). Use `rank_by_train_frequency` for the relative order.

### Pilot budget (no samples generated)

| Type | Labels selected | Samples planned |
|---|---:|---:|
| rare_positive | 15 | 45 |
| paraphrase | 15 | 135 |
| hard_negative | 8 | 24 |
| direction_contrastive (pairs × 2 = samples) | 6 | 12 |
| **TOTAL** | — | **216** |

194 TRAIN seed instances were extracted, covering 20/20 selected labels.

---

## 8. What remains to be done

### Before any augmented data is generated
1. **User reviews** the selected labels and the pilot budget. If the rare-positive list should include or exclude particular labels, edit the priority weights or the `--max_labels` cutoff.
2. **User reviews** `augmentation_prompt_blueprints.md` and approves the templates (especially the actor-archetype suggestions for rare positives).
3. **Optional manual fix** for the legacy folders flagged by the audit (`output/task1/`, `output/task1_hybrid_v2/`, manual `pred_task1*_4omini.json` archives). The audit's `proposed_patch_plan.md` lists the safe options; nothing has been deleted or renamed yet.

### Augmentation generation (NEXT phase, not implemented this session)
- A new script `research/fehu_augmentation_v1/run_generation.py` will consume `selected_seed_instances.jsonl` and the prompt blueprints, call an LLM, and produce augmented JSONL files. It will validate against `augmentation_schema.json` and route teacher-rejected samples to a hold-out file.
- Generation will run **only after** explicit user approval and an API budget decision.

### Downstream experiments (after augmentation exists)
- DeBERTa fine-tuning with augmented data, ablations matching the table in `METHOD_DESIGN.md` § 7.
- Hybrid v2 with an augmented student.
- Re-run `label_diagnosis.py` to compare augmented vs. baseline per-label recall.

---

## 9. What the user should review

1. **`research/fehu_augmentation_v1/METHOD_DESIGN.md`** — does the four-type, priority-weighted method match your research direction?
2. **`output/research_augmentation_plan/20260614_131524/augmentation_target_labels.csv`** — is the top-20 list defensible? Any labels you'd remove or add?
3. **`output/research_augmentation_plan/20260614_131524/augmentation_prompt_blueprints.md`** — are the prompts strict enough?
4. **`output/research_augmentation_plan/20260614_131524/selected_seed_instances.jsonl`** — are the train seeds appropriate?
5. **`research/fehu_experiment_management/OUTPUT_NAMING.md`** — do the canonical-name decisions match how you want to run future experiments?

---

## 10. Safety guarantees

- **No API was called.** Provider/key handling is unchanged in the patched scripts; nothing in the new modules touches a network.
- **No training was run.** `train_deberta.py` was modified for output management only; the training loop was not invoked.
- **No existing files were deleted, moved, or renamed.** Patched scripts overwrite themselves, but every dataset, prediction, and cache file is untouched.
- **All syntax checks pass.** 14 scripts compile clean (see § 7 of the run log).
- **All new outputs are timestamped.** Previous research outputs are preserved.

It is safe to proceed to the next phase (actual augmentation generation), subject to the human-review items in § 9.
