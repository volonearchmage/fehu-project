# Blockers & Decisions — DRA-FEHU Ablation Readiness

**Created at:** 2026-07-04T19:30:38

## Can current code run the controlled ablation as-is?
**No.** `src/train_deberta.py` is the correct entrypoint and its prediction/evaluator integration is
already compatible, but the controlled A/B ablation cannot be executed without source edits:

1. **Training input paths are hardcoded** (`TRAIN_ARTICLES`/`TRAIN_LABELS`, lines 93–94; consumed at
   line 401). There is no CLI flag or env var to point training at the derived augmented file. The
   baseline condition happens to equal the hardcoded official train, but the **augmented condition
   cannot be loaded** without editing the constants.
2. **No seed control** (no `manual_seed`/`seed` anywhere; `DataLoader(shuffle=True)`). The planned
   "same seed" invariant is unenforceable, so A-vs-B deltas would be confounded by nondeterminism.
3. **Shared checkpoint dir** (`CHECKPOINT_DIR`, line 62). Baseline and augmented runs overwrite the
   same best-model checkpoint, breaking per-condition isolation.

## Does the dirty working tree block final experiments?
**Yes, for *final reported* experiments — not for planning.**
- The entrypoint itself, `src/train_deberta.py`, is currently **modified (M)** and uncommitted, and the
  tree also carries untracked hybrid-pipeline files (`src/hybrid_v2.py`, `src/collect_results.py`,
  `src/regenerate_deberta_predictions.py`, `src/run_pipeline_deepseek_flash.py`, `HYBRID_ROADMAP.md`,
  `research/`) plus modified `src/run_pipeline.py`, `src/hybrid_pipeline.py`.
- A thesis-grade ablation must be reproducible from a known commit. Training from an uncommitted,
  modified `train_deberta.py` yields results that cannot be pinned to a git state (its own
  `run_config.json` records `git_commit` = repo HEAD while the file on disk differs → provenance is
  misleading). **Acceptable for planning/smoke exploration; not acceptable for final reported numbers.**

## Are code changes required?
**Yes** — the three minimal, backward-compatible edits in `02_ablation_command_spec.json`
(`--train_articles/--train_labels`, `--seed`, `--checkpoint_dir`). Defaults must preserve current
behavior so unrelated runs are unaffected. **Not implemented here.**

## Does the evaluation.py CLI remain blocked?
**Yes.** `evaluation.py` line 262 `DEBUG=True` overwrites `sys.argv` with hardcoded `/tmp` paths, so the
CLI cannot score arbitrary files (dry-run exit code 1, FileNotFoundError). This is **not** a blocker for
the ablation because `train_deberta.py` already calls the evaluator functions programmatically. Policy:
do not modify `evaluation.py`; keep using the official functions programmatically.

## Explicit decision required from Peiyang before any training
1. Approve (or reject) the three minimal source edits to `src/train_deberta.py`
   (`--train_articles/--train_labels`, `--seed`, `--checkpoint_dir`), to be made in a **separate,
   explicitly approved** task — not now.
2. Decide how to make the run reproducible: commit `train_deberta.py` (and the intended edits) on a
   dedicated branch, or run inside a path-isolated worktree, so final numbers pin to a known commit.
3. Confirm the fixed seed and identical hyperparameters/threshold for both conditions.
4. Confirm per-condition output and checkpoint isolation under `output/research_ablation_runs/<timestamp>/`.

## No-fallback statement
No fallback path, shim, data-swap, or wrapper is introduced to work around these blockers. The blockers
are reported exactly as found; resolving them requires explicit human-approved source changes in a later
task. Official data, `evaluation.py`, and all source files remain unmodified by this audit.
