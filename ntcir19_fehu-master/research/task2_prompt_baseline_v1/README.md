# FEHU Task 2: first frozen prompt baseline

**The user stopped the full inference run because of cost. Do not automatically
resume it.** Completed-cache official subset scores are available in
[subset_evaluation_completed/RESULTS_zh.md](subset_evaluation_completed/RESULTS_zh.md).
The continuation helper respects `USER_STOP.json` and submits no requests while
that explicit stop is in force. The original launch commands below are historical
reproduction instructions, not authorization to start more paid requests.

See [STATUS.md](STATUS.md) for the actual execution state. A final `RESULTS.md`
is generated only after the complete DEV run passes scoring and the full audit.

This independent experiment uses DeepSeek-V4.1-Flash through the official
`deepseek-flash` API alias, with thinking enabled and `reasoning_effort=max`.
The mapping and API parameters were checked against official documentation on
2026-11-04. The returned alias cannot independently prove remote weight identity.

The frozen zero-shot prompt receives the target subevent, full article background,
all supplied actors, and all 54 official Level-1 value names and descriptions.
There are no TRAIN demonstrations, learned thresholds, label caps, forced-positive
actors, ensembles or second-pass label editing. Every actor must appear explicitly,
including empty outputs. Task-2a is a deterministic deduplicated L1-to-L2 projection.

One request is made per subevent, considering all candidate actors together. A
five-subevent smoke run checks API/format/scoring operation. The full run is an
independent pass over all 177 official DEV records, 1,526 subevents and 3,998
actor-event pairs. Smoke predictions are not reused or selected for the full run.
The prompt is frozen before the smoke run; smoke scores are not used for tuning.

## Run from fehu-project

```powershell
python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/test_protocol.py
python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/run_experiment.py prepare
python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/run_experiment.py run --phase smoke --workers 5
Set-Location ntcir19_fehu-master/research/task2_prompt_baseline_v1
python -X utf8 -c "import run_experiment as experiment; experiment.run('full', 128)"
```

The script needs only the Python 3.10+ standard library. It reads the key from the
existing project `.env`; it neither prints it nor copies it into the experiment.
The model is fixed by the protocol rather than the `.env` model setting.
Rerunning a phase verifies and reuses its successful per-event response cache;
technical failures get at most three attempts per invocation. No failed, blank,
truncated, invalid-ID or missing-actor response is treated as an empty prediction.
Incomplete coverage prevents scoring. Authentication/balance/configuration HTTP
errors stop request submission. Successful response caches are atomic and resumable.
The full run uses the Python runner API with 128 concurrent requests; this changes
throughput only, not the frozen prompt or model parameters. The CLI exposes a
smaller worker range for debug runs. The actual worker count is in run_config.json.
If the provider stops the run for insufficient balance, completed response caches
remain valid. After balance is available, continue with the conservative entry:

```powershell
python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/resume_full.py --workers 8
python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/audit_results.py
```

These two commands are run from the outer fehu-project directory. Continuation
worker counts are recorded separately in `runs/full/invocation_history.json`.

## Files and scoring

- `prompt_template.txt`: editable source used before the protocol is frozen.
- `frozen/`: rendered prompt, code snapshot, input/request hashes and fixed protocol.
- `runs/smoke/`, `runs/full/`: original requests without auth headers, raw responses,
  explicit empty-actor coverage, Task-2a/2b predictions, official metrics, usage,
  per-label/per-article tables, and individual FP/FN errors.
- `evaluator/`: official evaluator from pinned resource commit
  `c27e19d97c24bd764c2ea520217dba9873fab455`, its provenance, and a runnable copy.

The runnable official evaluator differs only by `DEBUG=True` becoming
`DEBUG=False`, disabling its hardcoded test-path override. All parsers and metric
functions are unchanged. It is executed as a subprocess with the actual gold and
prediction files, and its exit status/stdout/output are saved. Full DEV uses the
complete official DEV gold; the smoke run uses only its selected gold subevents.
Independent set-based counts cross-check micro/macro F1 and DRR.

Full results must be interpreted as one frozen-prompt DEV run, not official TEST,
statistical significance, or proof of superiority over a different model/prompt.

Official references:
- https://api-docs.deepseek.com/
- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/guides/json_mode/
- https://github.com/ii-research/NTCIR-19-FEHU-resource/tree/c27e19d97c24bd764c2ea520217dba9873fab455
