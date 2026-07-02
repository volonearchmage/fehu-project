# Augmentation Generation Preview + FEHU Format Safety Guard — Final Report

**Session date:** 2026-06-14
**Phase:** controlled first step of the augmentation pipeline
**Status:** all planned work completed without any API call, training, or destructive change.

---

## 1. Purpose

The objective of this step is to **convert the existing augmentation plan into reviewable request objects** without generating any actual data, and to **build the safety guards** that will protect both FEHU prediction submissions and any future augmented training set.

The session deliberately produces zero augmented samples. It produces:
- 18 LLM request previews (ready for a human reviewer to read before any API call)
- A FEHU prediction format guard that has now been smoke-tested on `Prompt_DS_Flash`
- A FEHU augmented-training-data guard ready to validate future generations
- Three new documentation files (`FORMAT_REQUIREMENTS.md`, `MODEL_SELECTION_AND_COST_STRATEGY.md`, plus per-module READMEs)

---

## 2. Why this step does not violate FEHU requirements

| FEHU rule | How this step honours it |
|---|---|
| Predictions in pred_task1a.json must follow `{guid, article_human_values:[{actor, l2_value}]}` | This step does not produce any prediction file. |
| Predictions in pred_task1b.json must follow `{guid, article_human_values:[{actor, l1_value, direction}]}` | Same. |
| `direction ∈ {"0","1"}` with `"0"=contradictory`, `"1"=aligned` | All preview metadata uses the authoritative mapping from `direction_mapping.json`. |
| Test labels must never be used | Test gold is not opened by any script in this session. |
| Dev gold must not be reused for training | Dev gold and dev articles are not used as seed content; only TRAIN gold seeds appear in the preview. |
| Official dataset files must not be modified | Only read access to `dataset/`. |
| Final predictions must be human-verifiable | A dedicated guard (`fehu_prediction_format_guard.py`) is now in place. |

Both guards are local-only (no network, no API). The preview file marks every request with `"preview_only": true` and `"do_not_execute": true`, so any future runner can hard-fail if asked to forward a request unchanged.

---

## 3. Files created

### `research/fehu_augmentation_generation_preview_v1/`
| File | Purpose |
|---|---|
| `README.md` | Module overview, inputs/outputs, commands |
| `WORKLOG.md` | Pre-session inventory + safety constraints |
| `run_generation_preview.py` | Builds request previews (no API) |
| `inspect_generation_preview.py` | Read-only summary tool for a preview folder |
| `FINAL_REPORT.md` | This file |

### `research/fehu_submission_safety/`
| File | Purpose |
|---|---|
| `README.md` | Module overview, commands |
| `FORMAT_REQUIREMENTS.md` | Authoritative spec for predictions + augmented samples |
| `fehu_prediction_format_guard.py` | Validates final `pred_task1*.json` (exit 0/2) |
| `augmented_training_data_guard.py` | Validates future `augmented_samples.jsonl` (exit 0/2) |

### `research/fehu_generation_model_strategy/`
| File | Purpose |
|---|---|
| `README.md` | Strategy module overview |
| `MODEL_SELECTION_AND_COST_STRATEGY.md` | Tier-by-tier generator/verifier strategy + cost guard rails |

**11 new files. Zero existing files modified.**

---

## 4. Existing files NOT modified

- `evaluation.py`, `dataset/**`
- Every `pred_task1*.json` and every `logs/cache_*.json`
- The full `output/task1*/` tree
- The previous research outputs: `output/research_label_diagnosis/`, `output/research_project_audit/`, `output/research_augmentation_plan/`, `output/research_experiment_registry/`, `output/research_visualization_dashboard/`
- The patched legacy scripts (`run_pipeline.py`, `train_deberta.py`, `hybrid_pipeline.py`, etc.)
- `evaluation.py` (untouched as required)

`git status --short` shows the same three modified tracked files as the previous session (the legacy-script patches) and no new staged changes.

---

## 5. Output folders created

| Folder | Created by |
|---|---|
| `output/research_generation_preview/20260614_163649/` | `run_generation_preview.py` (tiny pilot) |
| `output/research_submission_safety/20260614_163804/` | `fehu_prediction_format_guard.py` (smoke test on Prompt_DS_Flash) |

Both are fresh timestamped folders; no overwrite of any prior result.

---

## 6. Preview totals

- **Total preview requests:** 18 (under the 20-request hard cap)
- **TRAIN seeds used:** 8 unique seed instances
- **Requests with a seed:** 8 (4 paraphrase + 4 seeded rare_positive)
- **Requests without a seed:** 10 (hard_negative + direction_contrastive — definition-only)
- **Direction-contrastive pairs:** 3 (linkage verified by inspector)

---

## 7. Request counts by augmentation type

| Type | Target | Actual |
|---|---:|---:|
| paraphrase | 4 | 4 |
| rare_positive | 4 | 4 |
| hard_negative | 4 | 4 |
| direction_contrastive | 8 (4 pairs) | 6 (3 pairs)¹ |
| **TOTAL** | 20 | **18** |

¹ Only 3 labels in the plan carry the `direction_contrastive` flag (`29 Be holding religious faith`, `12 Have success`, `38 Be honest`). The script honoured the actual plan rather than padding with unrelated labels.

---

## 8. Top labels included in the preview

(Frequency = how many preview requests target that label)

| L1 | Label | # requests |
|---:|---|---:|
| 29 | Be holding religious faith | 3 |
| 32 | Be behaving properly | 3 |
| 51 | Have the wisdom to accept others | 3 |
| 7  | Have an exciting life | 3 |
| 12 | Have success | 2 |
| 24 | Be neat and tidy | 2 |
| 38 | Be honest | 2 |

Selection logic (encoded in `run_generation_preview.py`):
- Paraphrase: top-4 priority labels with `has_seeds = true` → 32, 51, 7, 24
- Rare-positive: top-4 priority labels with `rare_positive` flag → 32, 51, 7, 24
- Hard-negative: top-4 priority labels with `hard_negative` flag → 32, 51, 7, 29
- Direction-contrastive (pairs): top-3 priority labels with that flag → 29, 12, 38

---

## 9. How FEHU format safety is enforced

Three layers of defence:

1. **`fehu_prediction_format_guard.py`** — every final `pred_task1a.json` / `pred_task1b.json` must pass this guard before submission. Exit 0 = clean, exit 2 = issues found. The guard re-reads `dataset/dev/dev_event_base.json` (or test event base) to validate `guid` and `actor` membership, ID ranges, direction validity, deduplication, cross-file guid agreement, and full-submission status.
2. **`augmented_training_data_guard.py`** — every batch of `augmented_samples.jsonl` must pass this guard before being mixed into training data. It enforces the JSON Schema in `research/fehu_augmentation_v1/augmentation_schema.json` plus FEHU-specific semantics (L1↔L2 mapping, direction↔direction_name consistency, actor present in content, evidence sentence present, no `seed_guid` from dev/test, no API-key-shaped strings).
3. **`FORMAT_REQUIREMENTS.md`** — single source of truth for both file kinds; every new producer script must conform.

The first guard was smoke-tested **in this session** on `output/task1_prompt_deepseek_v4_flash/pred_task1*.json`: 177 articles, 1500 Task-1a predictions, 1736 Task-1b predictions, 0 issues, exit code 0. **CLEAN ✅.**

---

## 10. How augmented samples will remain separate from official gold

| Pool | Folder | Mutability |
|---|---|---|
| Official TRAIN gold | `dataset/gold_labels/train/train_human_values.json` | NEVER MODIFY |
| Augmented samples | `output/research_augmentation_data/<TS>/augmented_samples.jsonl` | new write per TS |
| Combined train set | `output/research_augmentation_data/<TS>/combined_train_set.json` | derived; never overwrites official gold |
| Rejected augmented samples | `output/research_augmentation_data/<TS>/augmented_samples_rejected.jsonl` | quarantined separately |

The augmented-training-data guard refuses any sample with `source = "official_gold"`, refuses any `seed_guid` that appears in dev or test event_base, and flags secret-shaped strings. `FORMAT_REQUIREMENTS.md § Part 3` is the binding contract.

---

## 11. Recommended next steps

1. **Human review of `human_review_sheet.csv`** in the new preview folder. Each row has `review_status = pending` and `should_execute_later = manual_review_required` by default. Reviewer should fill `reviewer_notes` and change `review_status` to `approved` / `rejected` per request.
2. **Inspect any non-trivial prompt** by reading the matching line in `generation_requests_preview.jsonl`. The inspector script provides a fast overview.
3. **Decide on Tier-1 generator + verifier** per `MODEL_SELECTION_AND_COST_STRATEGY.md`. Recommendation: `deepseek-v4-pro` for both at this scale (~20 calls).
4. **Author `research/fehu_augmentation_v1/run_generation.py`** in a future session — only after explicit approval. It will consume the approved preview, dispatch calls, persist results, run the augmented-data guard, and write `augmented_samples.jsonl` + `augmented_samples_rejected.jsonl`.
5. **No earlier than that:** train a student DeBERTa on `(original_train ∪ accepted_augmented_samples)` and re-run the label-diagnosis to measure rare-label recall change.

---

## 12. API called?

**No.** No script in this session imports an HTTP / LLM client. The preview script only constructs prompt strings and writes them to disk.

## 13. Training run?

**No.** No `train_*` invocation occurred. `train_deberta.py` was not invoked.

## 14. Any prediction file modified?

**No.** Every `output/task1*/pred_task1*.json` and every `logs/cache_*.json` retains its pre-session timestamp.

## 15. Safe to proceed?

**Yes.** The preview is mathematically and structurally consistent:

- 18 requests, all `preview_only=true`.
- All paraphrase requests have a TRAIN seed; no dev/test content used.
- Direction-contrastive pair linkage is 100 % consistent (every `paired_request_id` resolves within the preview).
- The FEHU prediction guard passes on `Prompt_DS_Flash` and is ready to gate any future submission.
- The augmented-data guard is ready to gate any future generation batch.

**Open minor item (documented, non-blocking):** 2 of 4 hard-negative requests do not have an `alternative_label_id` chosen automatically because the selected target label is the only entry in its L2 family inside the 20-label subset. The prompt explicitly tells the generator to pick a plausible alternative from the same L2 family. The inspector raises this as a **risk warning**, not an error. A trivial enhancement for a later revision would be to expand the confusable-label pool to all 54 L1 labels (instead of restricting to the planned 20).

---

## 16. Summary

| Item | Value |
|---|---|
| New files | 11 |
| Existing files modified | 0 |
| Output folders created | 2 |
| Preview requests | 18 |
| API calls | 0 |
| Training runs | 0 |
| Predictions modified | 0 |
| FEHU prediction guard verdict on Prompt_DS_Flash | CLEAN ✅ |
| Safe to proceed to tiny-pilot generation? | YES (subject to human review of `human_review_sheet.csv`) |
