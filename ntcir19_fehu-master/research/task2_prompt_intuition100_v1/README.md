# Task 2 intuition100 v1

Two-stage zero-shot comparison authorized by the user on 2026-11-05.
All calls use `deepseek-flash`, `thinking.type=disabled`, `temperature=0`, and
`max_tokens=4096`. A uses the historical frozen system prompt without changes;
B adds actor/event attribution instructions, C adds action/value/direction instructions.
All supplied actors are retained; no label minimum, maximum or explanations are imposed.

Exploration uses 12 fixed TRAIN fit events, one per article/body, excluding normalized
body or title overlap with DEV. The normalization is whitespace collapse + casefold.
The existing grouped split is frozen as a source. It is development data, not an
independent test. A/B/C and two predefined set fusions are scored on all 12 events;
the highest Task2b micro-F1 selects the primary method. Exact ties prefer
A, B, C, VETO, CONSENSUS in that order. UNION is diagnostic only.

Confirmation uses 100 SHA256-selected events from the full 1,526-event DEV input,
without looking at gold labels. All three prompts run on each event. The primary
method is locked before confirmation inference or gold access and is never changed
based on confirmation scores. The historical 508-event predictions are compared
only on the intersection with these 100 events, not as a complete 100-event baseline.

For a cloned archive, first reconstruct omitted duplicate caches, then verify
official scores in a temporary directory. These commands never read `.env` or call a model:

```powershell
python -X utf8 ntcir19_fehu-master/research/task2_prompt_intuition100_v1/rebuild_cache.py
python -X utf8 ntcir19_fehu-master/research/task2_prompt_intuition100_v1/rebuild_cache.py --check
python -X utf8 ntcir19_fehu-master/research/task2_prompt_intuition100_v1/run_experiment.py status
python -X utf8 ntcir19_fehu-master/research/task2_prompt_intuition100_v1/verify_archive.py
```

Do not execute `run` or in-place `score`, repeat paid inference, delete stage guards,
or create a new authorization to reproduce this archive. The historical execution
entry points are not a request to rerun the completed experiment.

`cache_selection.json` saves the exact 12/100 event keys and indices, frozen
manifest hash, and all 336 request-cache hashes. `rebuild_cache.py` uses the
repository's official TRAIN/DEV inputs and frozen helpers, verifies source hashes,
rebuilds inputs and requests in memory, and checks every expected frozen/result
hash before writing any missing file. It preserves the archived CRLF JSON bytes
on both Windows and Linux. Existing differing files cause an error and are never
overwritten. The three duplicate frozen input caches and request JSON caches are
ignored by Git; raw responses, results, spending ledger and scoring evidence remain
published. No original cache is deleted or moved by reconstruction.

The archived scores and `confirmation_lock.json` are frozen evidence. In-place
`score` rewrites files and can change Windows CRLF to Linux LF, breaking evidence
hashes. `verify_archive.py` instead validates the archived responses and runs the
official scorer in temporary storage without modifying the published evidence.

`prepare`, `status`, and `score` are offline and do not read API credentials.
Only `run` reads the project `.env` into memory. No account queries are made.
`run` scores automatically only if all stage events have complete valid responses
from all three prompts. `score --stage explore|confirm` can repeat offline verification.
The confirmation command requires a validated `confirmation_lock.json` from exploration.

The global fixed cap is 360 HTTP attempts: 336 initial attempts plus at most 24 technical
retries, at most one retry per affected event/prompt. Schema/label errors and truncation
are not retried. Every attempt durably reserves its pessimistic charge before
HTTP, using UTF-8 request bytes + 1024 input tokens and 4096 output tokens at peak
uncached rates. Reliable usage settles an attempt at peak uncached rates and releases
its excess reservation; missing or invalid usage retains the full reservation.
Charges plus outstanding reservations cannot exceed US$1.50 before a request is sent.
The budget is shared across both stages. Completion is not guaranteed within the cap;
the prepare manifest also reports the worst cost if no reservations could be released.

`AUTHORIZATION.json` binds only this run to its frozen manifest. The historical
`USER_STOP.json` is hashed and preserved. Creating this directory's `RUN_STOP.json`
stops further attempts (already in-flight calls may finish). `run/{stage}/RUN_STARTED.json`
is created exclusively and retained permanently, and `run/ACTIVE_EXECUTION.lock`
excludes concurrent stage execution. Restarted commands cannot replay spending.
Do not delete these guards to rerun. If execution crashes, inspect
the attempt ledger; an unfinished reservation may represent a billed request.

Raw requests contain no authentication header. Raw API responses, parsed results,
attempt ledger, usage and scoring evidence are retained. A completed run writes
`run/{stage}/evaluation/RESULTS_zh.md`, including official scores and independent
counts. Confirmation also writes the top-level `RESULTS_zh.md` and historical max
comparisons on the shared intersection. Confirmation samples the full DEV input,
but is not the full DEV score. Historical time/version and runtime-package changes
prevent a causal claim about reasoning effort alone. Three perspectives from one
model have correlated errors; fusion can sacrifice recall and is not guaranteed to win.
