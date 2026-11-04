# FEHU Project State — 2026-11-05

## New authorized work — non-thinking prompts and adaptive ModernBERT

The user now requests a small non-thinking, temperature-zero Task 2 experiment,
multiple prompt views and fusion gates, with attention to small-sample versus
full-DEV differences. New scope: `research/task2_prompt_intuition100_v1/` and
`docs/linux_4090_handoff/09_prompt_fusion_experiment_20261105.txt` (paths under
`ntcir19_fehu-master/`). It uses 12 TRAIN-fit exploration events and a frozen
100-event input-only sample from all 1526 DEV events, three prompts each, with a
shared USD 1.50 conservative spending cap and 360 HTTP attempts maximum. This
does not authorize historical full-run resumption. The old USER_STOP stays.
The protocol alone is not evidence of completed calls; use the new run ledger
and RESULTS_zh.md for actual completion, cost estimates and scores.

The scoped run has now completed: all 336 responses valid, no retries, 100 DEV
events / 78 articles / 267 candidates. Exploration selected VETO before confirmation.
Confirmed Task2b F1: A 17.08%, B 17.96%, C 18.06%, VETO 18.39%, CONSENSUS 17.93%,
UNION 15.63%. VETO removes 128 FP and 3 TP versus A; absolute performance remains
weak. Peak uncached usage estimate is USD 0.4923756, not an account bill.
On the shared 35-event historical intersection, old max F1 is 29.29% versus new
A 18.78% and VETO 21.05%; this is not evidence that non-thinking is more accurate.
See `research/task2_prompt_intuition100_v1/INTERPRETATION_zh.txt` under the project
root. The scoped paid run is complete; do not replay it or start full DEV inference.
For archived verification use `rebuild_cache.py` then `verify_archive.py`, never
`score` in place because it would rewrite locked evaluation evidence.

Linux autonomous ModernBERT instructions are in
`ntcir19_fehu-master/docs/linux_4090_handoff/08_run_modernbert_adaptive_research.txt`.
They extend the completed v2 pilot with fit diagnostics, matched WBCE/ASL
experiments and evidence-driven further rounds. Tune F1 0.35 is an internal
engineering target, not a claim of matching an official TEST baseline. Preserve
the existing research branch, local CUDA environment and one-time holdout boundary.
The historical review below predates this separate authorization.

## Latest verified review — 2026-11-05

The Linux v2 pilot and its review bundle are now published on research branch
`task2-local-4090-20261104-2033` at
`0da5687da453dc3f891468c19e8e80c4024d2618`. The Windows agent directly read the
published code, PILOT_RESULTS, learning curves, metric availability, and per-label
tables. T/J/S completed three epochs and 498 updates each; P reuses J. Tune Task2b
micro-F1 is T 10.58%, J 10.92%, S 11.28%, P 11.37%. No holdout/DEV/TEST model
evaluation was performed in this pilot. The older preparation status below is historical.

New review: `ntcir19_fehu-master/docs/linux_4090_handoff/07_task2_method_review_20261105.md`.
It recommends first diagnosing sparse positive-label learning and running a limited
T weighted-BCE/ASL comparison before further S research. Prompt proposals prioritize
non-thinking/low and fit-only examples. These are proposals, not newly run results
or authorization for paid calls. The paid USER_STOP remains in force.

Offline review found 99.27% of output tokens in the 508 successful prompt responses
were reasoning tokens. This supports a cost investigation, not a causal claim that
max thinking caused false positives. Official API docs currently route the legacy
V4 Flash name to V4.1-Flash-1017; temperature has no effect in thinking mode.
Reproducible review artifacts are under `output/task2_scope_diagnostics/review_20261105/`.

## Latest Linux status — user-reported, 2026-11-05

The user reports that the RTX 4090 blocker is resolved. J/S forward/backward on
20 real fit bags each, an AdamW update after 16 accumulated bags, the longest bag
with optimizer state allocated, and checkpoint round-trip checks passed. Reported
peak memory on the post-update longest bag is 9.44 GiB allocated / 10.19 GiB reserved.
The Windows agent has not directly read the new Linux GPU reports. Verify them in
`output/linux_handoff/gpu_recovered_20261105-003426/` and
`output/task2_scope_local_v1/gpu_preflight_20261105-003426/` under the project root.

Software preparation is on research branch `task2-local-4090-20261104-2033`, with
previously verified commit `9d162c6dd8e971cd58e1e240891892de129dc62b`; preserve newer
Linux local work. Formal J/S training has not started; automatic resume is not
implemented according to the latest report. Use the verified FEHU CUDA Python,
not the CPU-only project `.venv`.

The subsequent 8-bag, 100-update diagnostic reportedly finished: J F1 0.2778,
recall 0.1852, AP 0.4833 (TP/FP/FN 5/4/22); S F1 0.5000, recall 0.4074,
AP 0.5201 (11/6/16); frequency-baseline AP 0.06896. The old numerical gate was
not met; targeted review reportedly found no remaining concrete implementation
defect. Preserve the original result at
`output/task2_scope_local_v1/round1_20261105-012630/RESULTS.md`.

Protocol v2 removes that uncalibrated numerical gate prospectively, without
relabeling the diagnostic as passed. Next: [full fit/tune T/J/S pilot and P](ntcir19_fehu-master/docs/linux_4090_handoff/06_run_task2_pilot_v2.txt),
under the [revised research design](ntcir19_fehu-master/docs/linux_4090_handoff/05_task2_research_protocol_v2.md).
Do not evaluate holdout/DEV model scores during this pilot. The former 04 prompt
is historical; its hard gate and immediate holdout evaluation are superseded.
Do not repeat system recovery on the working machine. The sections below retain
the previous main-branch handoff and historical experiment context.

## Current handoff

Repository: https://github.com/volonearchmage/fehu-project (main).
Git root: `fehu-project/`. Project root: `fehu-project/ntcir19_fehu-master/`.

The next machine is Linux with an RTX 4090 and Codex installed. Its old copy may
contain only Task 1. Preserve its work, fetch GitHub, and follow
[the handoff prompts](ntcir19_fehu-master/docs/linux_4090_handoff/README.md).
Linux/GPU execution has not been tested on this Windows machine.

## Task 2: completed API subset; paid inference stopped

The user stopped the expensive full inference run. No automatic paid
continuation is authorized. Preserve `USER_STOP.json`.

Experiment: `ntcir19_fehu-master/research/task2_prompt_baseline_v1/`.
Frozen zero-shot prompt: full article + target event + all actors + taxonomy.
Settings: `deepseek-flash`, thinking enabled, reasoning effort `max`.

- Planned DEV: 177 articles, 1,526 events, 3,998 actor/event candidates.
- Completed and offline scored: 508 events, 66 articles, 1,328 candidates.
- Unfinished: 1,018 events, not counted as empty predictions.
- Task-2a: precision 22.52%, recall 67.67%, micro-F1 33.79%, macro-F1 30.24%.
- Task-2b: precision 18.10%, recall 60.86%, micro-F1 27.90%, macro-F1 22.63%.
- Task-2b: TP 597, FP 2,701, FN 384; DRR 13/981 = 1.3252%.
- The subset is nonrandom. Do not directly compare to full DEV/TEST scores.
  Overprediction is observed; error mechanisms still need case-level analysis.

Source of truth: the experiment's `subset_evaluation_completed/metrics_official.json`,
`evaluation_manifest.json`, and `RESULTS_zh.md`. Official evaluator is pinned to
`c27e19d97c24bd764c2ea520217dba9873fab455`; only the DEBUG path override is disabled.
Successful raw responses and requests are archived. An offline migration verifier
is included. Local account details and a redundant interrupted ZIP are excluded.

## Original local GPU experiment plan (historical main-branch handoff)

Read `ntcir19_fehu-master/docs/2026-11-03_Task2_组会准备/Task2_研究判断与实验设计.md`.
Initial scope: ModernBERT-base J/S with matched inputs/supervision, and P reusing
J scores. Use fixed grouped TRAIN fit/tune/holdout. Official DEV has 86/177 article
bodies also present in TRAIN; report separately. The handoff prompt defines smoke
tests, training budget, evaluation and outputs. No paid inference is required.

## Task 1 and older records

Task 1 E7G4 results, papers and code remain available. Do not relabel Task 1 scores
as Task 2 scores or overwrite old work. The earlier DRA-FEHU pilot is historical:
`ntcir19_fehu-master/output/research_verified_candidates/20260702_132154/` had
5 verified and 1 rejected candidates. Its rejected L1=12 contradictory candidate
must not become training data. Not all `output/` files are approved training inputs.

Credentials, virtual environments, caches and weights stay local.
