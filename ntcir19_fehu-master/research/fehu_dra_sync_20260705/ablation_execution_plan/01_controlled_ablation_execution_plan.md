# Controlled Ablation Execution Plan — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T20:08:24
**Status:** PLANNING ONLY. No training, no ablation, no model inference performed.

## Current research state
- Verified candidate pool: 6 human-accepted candidates (`output/research_verified_candidates/20260702_165107/`),
  all `training_ready=false`. L1=12 "Have success" and L1=38 "Be honest" direction pairs complete.
- Derived ablation inputs built (`output/research_ablation_inputs/20260702_193701/`):
  baseline = official train (1228/1228); augmented = official train + 6 synthetic (1234/1234).
- Schema + evaluator dry-run passed (`output/research_ablation_dryrun/20260702_194637/`):
  official `parse_task1b` accepts the derived Task-1b format; identical gold/pred gives micro-F1=1.0,
  macro-F1=1.0, DRR=0. The shipped CLI cannot be used on arbitrary paths (DEBUG=True; see below).
- Official train/dev/test data unmodified throughout.

## Condition A — Baseline
- **Train input:**
  - `output/research_ablation_inputs/20260702_193701/01_baseline_train_event_base.json`
  - `output/research_ablation_inputs/20260702_193701/02_baseline_train_human_values.json`
- **Dev evaluation:** official dev data (`dataset/dev/dev_event_base.json` +
  `dataset/gold_labels/dev/dev_human_values.json`).
- **No synthetic candidates.**

## Condition B — DRA-FEHU augmented
- **Train input:**
  - `output/research_ablation_inputs/20260702_193701/03_augmented_train_event_base.json`
  - `output/research_ablation_inputs/20260702_193701/04_augmented_train_human_values.json`
- **Dev evaluation:** identical official dev data.
- **Only changed factor:** addition of the 6 verified synthetic candidates to the training set.

## Invariant settings (identical across A and B)
- Same model.
- Same prompt / training code.
- Same hyperparameters.
- Same seed (if the training procedure is stochastic).
- Same dev evaluation set (official dev).
- Same evaluator function invocation (official `parse_task1b` / `evaluate` /
  `direction_reverse_rate_gold_excl`; see `03_evaluator_invocation_spec.json`).
- Same prediction formatting (Task-1b JSON: `guid`, `article_human_values[*].{actor,l1_value,direction}`).
- No official data modification.

The **only** permitted difference between A and B is the training-data augmentation factor.

## Metrics
- **Task-1b micro-F1**
- **Task-1b macro-F1** (gold-supported, as implemented in `evaluation.py`)
- **Direction Reverse Rate (DRR)** — see direction caveat in `02_metric_and_direction_risk_analysis.md`
- **Rare-label recall** — per-class recall on the augmented rare labels, derivable from per-label
  tp/fn using the same instance sets `evaluate()` builds. Gold support (article-level) for context:
  - L1=12 "Have success": train aligned=276 / contradictory=62; dev aligned=47 / **contradictory=7**.
  - L1=38 "Be honest": train aligned=287 / contradictory=199; dev aligned=44 / contradictory=28.
- **Per-target inspection for L1=12 and L1=38** — report aligned vs contradictory recall/precision
  separately; L1=12 contradictory (dev support 7) is the highest-variance target and the primary
  augmentation focus.

## Future run procedure (executed only in a later, approved task)
1. Resolve or path-isolate the dirty working tree (see `05_pre_ablation_approval_checklist.md`).
2. Train the model twice with identical config — once on Condition A input, once on Condition B input.
3. Generate Task-1b dev predictions for each condition using the unchanged prediction formatting.
4. Score both with the official evaluator **functions** (not the CLI) on official dev gold.
5. Record metrics, per-label recall, and per-target L1=12/L1=38 breakdowns.

## Future output files (under `output/research_ablation_runs/<timestamp>/`, later task)
- `pred_task1b_baseline.json`, `pred_task1b_augmented.json`
- `metrics_baseline.json`, `metrics_augmented.json`
- `ablation_comparison_table.csv` (A vs B, deltas)
- `run_manifest.json` (sha256 of official files before/after, seeds, config, input paths)

## Stopping conditions
- Any official dataset file changes sha256 → stop.
- `evaluation.py` changes → stop.
- Synthetic guid/actor id collides with an official id at load time → stop.
- Evaluator raises on the derived format → stop.
- Training config differs between A and B in any factor other than augmentation → stop.
- Prediction schema fails `parse_task1b` → stop.

## What NOT to claim (before results exist)
- No F1 / DRR / recall improvement claim until both conditions are actually run and scored.
- No statistical-significance claim from 6 augmented examples; treat as small-sample directional signal.
- No generalization claim beyond the targeted rare labels/directions (L1=12, L1=38).
- No DRR directional-decomposition claim (see direction caveat) until real prediction errors inspected.
