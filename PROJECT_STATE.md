# FEHU Project State — 2026-11-05

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
