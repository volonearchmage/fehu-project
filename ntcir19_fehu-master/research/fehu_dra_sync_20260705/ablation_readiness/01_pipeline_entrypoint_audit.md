# Pipeline Entrypoint Audit — DRA-FEHU Ablation Readiness

**Created at:** 2026-07-04T19:30:38
**Status:** AUDIT ONLY. No training, inference, ablation, or source modification.

## Scripts inspected (read-only)
| Script | Role | argparse surface | Trains on train_event_base? |
|--------|------|------------------|-----------------------------|
| `src/train_deberta.py` | DeBERTa-v3 + LoRA fine-tuning for Task-1 | `--output_dir`, `--version`, `--threshold`, `--force_overwrite` | **YES** |
| `src/run_pipeline.py` | GPT-4o(-mini) prompt pipeline | `--mode`, `--limit`, `--model`, `--api_key`, `--output_dir`, `--version`, `--force_overwrite` | No (prompt/inference; few-shot only) |
| `src/hybrid_pipeline.py` | DeBERTa+LLM hybrid inference | `--mode`, `--model`, `--api_key`, `--deberta_threshold`, `--top_k`, `--max_candidates_per_actor`, `--limit`, `--skip_deberta` | No |
| `src/hybrid_v2.py` | Hybrid v2 (openai/deepseek) inference | `--mode`, `--provider`, `--model`, ... `--output_dir` | No |
| `src/run_pipeline_deepseek_flash.py` | DeepSeek prompt pipeline | `--mode`, `--limit`, `--api_key` | No |
| `src/regenerate_deberta_predictions.py` | Re-run inference from a saved DeBERTa checkpoint (imports `train_deberta` as `td`) | `--output_dir`, `--threshold`, `--force_overwrite` | No (inference only) |
| `src/collect_results.py` | Aggregate/collect result files | none (no argparse) | No |

## Likely entrypoint
**`src/train_deberta.py::main()`** — it is the only script that consumes
`train_event_base.json` + `train_human_values.json` to *train* a model, which is exactly the factor
the DRA-FEHU augmentation ablation changes. The GPT/hybrid pipelines are prompt/inference systems
driven by `--mode dev|test`; adding synthetic rows to the training file does not flow into them as a
training signal, so they are not valid ablation entrypoints for this thesis claim.

## CLI / config arguments discovered (train_deberta.py)
- `--output_dir` (str, default `output/task1_deberta/`)
- `--version` (str tag appended to output dir)
- `--threshold` (float, sigmoid cutoff, default 0.3)
- `--force_overwrite` (flag)
No other CLI arguments exist.

## Data path configurability
**NOT configurable for training inputs.** Train/dev paths are module-level constants:
- `TRAIN_ARTICLES` = `dataset/train/train_event_base.json` (line 93)
- `TRAIN_LABELS`   = `dataset/gold_labels/train/train_human_values.json` (line 94)
- `DEV_ARTICLES`   = `dataset/dev/dev_event_base.json` (line 95)
- `DEV_LABELS`     = `dataset/gold_labels/dev/dev_human_values.json` (line 96)

They are passed directly into `build_examples(TRAIN_ARTICLES, TRAIN_LABELS)` / `build_examples(DEV_ARTICLES, DEV_LABELS)`
at lines 401–402, and `DEV_LABELS` is referenced for evaluation at lines 322/324/501/503. **There is no
CLI flag or environment variable to redirect the training set to the derived augmented file**
(`output/research_ablation_inputs/20260702_193701/03_augmented_train_event_base.json` /
`04_augmented_train_human_values.json`). Condition A (baseline) coincidentally matches the hardcoded
official train, but Condition B (augmented) cannot be loaded without editing these constants.

Additional determinism gaps:
- **No seed is set anywhere** (`grep seed|manual_seed` → empty). `DataLoader(shuffle=True)` (line 406)
  and unseeded model/LoRA init make runs non-deterministic, so the planned "same seed" invariant
  cannot be locked without a source change.
- `CHECKPOINT_DIR` is a single fixed path `checkpoints/best_model` (line 62); baseline and augmented
  runs would overwrite the same checkpoint, so best-model selection is not isolated per condition.

## Output path configurability
**Configurable.** `--output_dir` (+ overwrite-safe `_safe_output_dir`) directs `pred_task1a.json`,
`pred_task1b.json`, and `run_config.json`. Baseline vs augmented predictions can be written to separate
folders. (Checkpoints, however, are not per-condition — see above.)

## Evaluation path configurability
**NOT configurable** (`DEV_LABELS` hardcoded). This is acceptable for the ablation because dev must be
the official dev set anyway (an intended invariant), but it is not a settable argument.

## Prediction format compatibility
**Compatible with the Task-1b evaluator.** `to_submission` (lines 285–304) emits
`{"guid", "article_human_values": [{"actor", "l1_value", "direction"}]}`, which is exactly what
`evaluation.parse_task1b` consumes. Direction is derived as `idx % 2` with the docstring convention
`"0"=contradictory, "1"=aligned` (label index = `l1*2 + dir`), consistent with
`dataset/hv_categories/direction_mapping.json`. The evaluator is already invoked **programmatically**
inside training (`from evaluation import parse_task1b, evaluate, direction_reverse_rate_gold_excl, ...`
at lines 309–312 and 497–500), never via the blocked CLI.

## Current limitation summary
The training entrypoint is correct and its prediction/evaluator integration is compatible, but it
**cannot run the controlled A/B ablation as-is**:
1. Training input paths are hardcoded constants with no override → the augmented condition cannot be loaded.
2. No seed control → the "same seed" invariant is unenforceable.
3. Shared checkpoint dir → conditions collide.
All three require explicit, approved source edits to `src/train_deberta.py` (which is itself currently
in a modified/uncommitted state). No change is implemented here.
