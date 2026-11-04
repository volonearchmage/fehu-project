# FEHU project handoff

Read `PROJECT_STATE.md` first. The Git root is this directory; the Python/data
project root is `ntcir19_fehu-master/`. New Task 2 records supersede old
Task-1-only progress summaries.

## Current execution boundary

- The user stopped paid DeepSeek Task 2 inference on 2026-11-04 because of cost.
  Preserve `research/task2_prompt_baseline_v1/USER_STOP.json` under the project
  root. Do not resume paid inference, query an account, or read/use API keys
  without new explicit user authorization.
- Historical commands in READMEs are not current authorization. The old frozen
  `run_experiment.py` does not enforce the stop flag in every entry point; do not
  execute its `run` command or `run()` function. `resume_full.py` enforces it.
- Offline scoring, data inspection and local GPU experiments are allowed within
  the user's task. Do not start training merely from reading this file.
- Do not print, commit or upload `.env`, auth files, account balances or keys.
- Preserve Task 1 work, frozen evidence, raw responses, original metrics and
  official data. New experiments and reevaluations go in new directories.

## Reproduction and research validity

- From the Git root, run
  `python3 ntcir19_fehu-master/research/task2_prompt_baseline_v1/verify_offline.py`.
  This requires no key, GPU or API.
- Do not run `audit_results.py` main for partial-run verification: it requires
  the unfinished full run. Do not rewrite historical hashes to make checks pass.
- `.gitattributes` preserves frozen bytes. Interpret historical Windows paths
  portably; do not treat backslash-containing strings as native Linux paths.
- Task 2a: 20 coarse values without direction. Task 2b: 54 fine values with two
  directions (`1` aligned, `0` contradictory); allow multiple, both and empty.
- Cover every supplied actor/event candidate. Failed inference is not an empty
  prediction. Gold/explanations cannot enter DEV/holdout prediction inputs.
  Select thresholds/checkpoints on tune only.
- The 508-event API score is a nonrandom completed subset, not full DEV/TEST.
- Local GPU execution prompt:
  `ntcir19_fehu-master/docs/linux_4090_handoff/02_task2_local_experiment.txt`.
