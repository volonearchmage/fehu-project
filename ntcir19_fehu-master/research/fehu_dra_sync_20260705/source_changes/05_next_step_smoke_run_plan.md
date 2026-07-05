# Next Step — Controlled Smoke Run Plan (DO NOT EXECUTE YET)

**Created at:** 2026-07-04T20:03:42
**Status:** PLAN ONLY. Requires Peiyang's explicit approval before any execution. No training here.

The source change now makes a controlled A/B smoke run *possible*. The next task — only after explicit
approval — is a small, deterministic smoke run to confirm the wiring end-to-end before a full ablation.

## Preconditions (must hold before running)
- Peiyang approves execution of the smoke run.
- Reproducibility resolved: `src/train_deberta.py` committed on a dedicated branch (or run in a
  path-isolated worktree) so results pin to a known commit.
- `fehu` conda env is the interpreter (has torch 2.6 / transformers 5.8 / numpy).
- Official data untouched; all artifacts written only under `output/research_ablation_runs/<timestamp>/`.

## Baseline condition (illustrative — do not run now)
```
python src/train_deberta.py \
  --train_articles output/research_ablation_inputs/20260702_193701/01_baseline_train_event_base.json \
  --train_labels   output/research_ablation_inputs/20260702_193701/02_baseline_train_human_values.json \
  --seed 42 \
  --output_dir     output/research_ablation_runs/<timestamp>/baseline \
  --checkpoint_dir output/research_ablation_runs/<timestamp>/baseline/ckpt
```

## Augmented condition (illustrative — do not run now)
```
python src/train_deberta.py \
  --train_articles output/research_ablation_inputs/20260702_193701/03_augmented_train_event_base.json \
  --train_labels   output/research_ablation_inputs/20260702_193701/04_augmented_train_human_values.json \
  --seed 42 \
  --output_dir     output/research_ablation_runs/<timestamp>/augmented \
  --checkpoint_dir output/research_ablation_runs/<timestamp>/augmented/ckpt
```

## Controls (identical between conditions)
- **Same `--seed`** (e.g. 42) for both runs — the only changed factor is the training data.
- **Separate `--output_dir`** and **separate `--checkpoint_dir`** per condition (no collision).
- Same threshold and unchanged hyperparameters (model/LoRA/epochs/LR).
- Dev evaluation stays on official dev (hardcoded, unchanged).
- No official data modification; no edits to `evaluation.py`.

## Smoke-run scope recommendation
For the *smoke* run, temporarily reduce cost via a tiny epoch budget or a limited subset **only if a
future, separately approved change adds such a control** — the current script has no `--max_epochs`/
`--limit` flag, so a true smoke run would either use the full config or require another approved edit.
Do not add such a control now. If full-config is too costly for a smoke check, propose the minimal
`--max_epochs` flag as a separate approval rather than patching around it.

## After the smoke run (later)
- Confirm both conditions produce `pred_task1b.json` accepted by `parse_task1b`.
- Compare micro-F1, macro-F1, DRR, and per-target L1=12 / L1=38 recall (A vs B).
- Only then proceed to the full controlled ablation and thesis reporting, with the small-sample caveat.
