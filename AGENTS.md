# FEHU project handoff

Read `PROJECT_STATE.md` first. The Git root is this directory; the Python/data
project root is `ntcir19_fehu-master/`. New Task 2 records supersede old
Task-1-only progress summaries.

## Current execution boundary

- On 2026-11-05 the user separately authorized a small non-thinking Task 2
  prompt/fusion experiment. Its sole paid scope is
  `research/task2_prompt_intuition100_v1/`: 12 TRAIN-fit exploration events and
  100 input-selected full-DEV events, three frozen prompts, shared USD 1.50
  conservative budget and at most 360 HTTP attempts. Follow its frozen scope,
  stop flag and ledger; do not repeat or extend it from this file alone.
  This exception does not authorize resuming the old full run or querying an
  account. See `docs/linux_4090_handoff/09_prompt_fusion_experiment_20261105.txt`.

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
- Current local GPU research protocol and execution prompt:
  `ntcir19_fehu-master/docs/linux_4090_handoff/05_task2_research_protocol_v2.md`
  and `ntcir19_fehu-master/docs/linux_4090_handoff/06_run_task2_pilot_v2.txt`.
  Protocol v2 prospectively supersedes the old 04 numerical learning gate and
  immediate holdout/DEV evaluation. Preserve the failed old diagnostic; run the
  full fit/tune pilot without using holdout/DEV model scores for development.
  On Linux, fetch the published documentation at a fixed commit and read it
  without overwriting newer local research code, caches, or experiment results.
- The v2 pilot has now completed and its review bundle was verified at research
  commit `0da5687da453dc3f891468c19e8e80c4024d2618`. Read
  `ntcir19_fehu-master/docs/linux_4090_handoff/07_task2_method_review_20261105.md`
  for the subsequent method review. Do not rerun the completed pilot merely by
  following the earlier execution prompt. The review proposes future comparisons;
  it does not lift the paid-API stop or itself launch new experiments.
- The user's subsequent request authorizes autonomous Linux ModernBERT research
  through `docs/linux_4090_handoff/08_run_modernbert_adaptive_research.txt`.
  Continue evidence-driven fit/tune experiments within that protocol; new seeds
  on the same tune are not an independent test. Freeze the final plan before
  one-time holdout evaluation. Do not rerun GPU/system recovery.
