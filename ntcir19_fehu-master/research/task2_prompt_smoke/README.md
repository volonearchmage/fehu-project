# Task 2 DeepSeek smoke comparison

This is a zero-shot pipeline check, not a reproduction of Liu's few-shot B0/B1.
It selects the first 3 DEV subevents in file order without looking at gold.
Both conditions have the same actor candidates, value names, scope instructions,
JSON schema, output budget, and non-thinking settings. Only full-article context differs.
No training, label cap, or gold explanations are used. This tiny sample cannot
establish a method's effectiveness, statistical significance, or full-DEV score.

## Credentials

Open `ntcir19_fehu-master/.env` and fill `DEEPSEEK_API_KEY=`. Keep the key out of
chat and Git. The project `.gitignore` already excludes `.env`.
Get your key at https://platform.deepseek.com/api_keys.
The script uses the project `.env` explicitly regardless of the working directory.
Its three supported variables override same-named process environment variables.

## Run from the outer fehu-project directory

```powershell
python ntcir19_fehu-master/research/task2_prompt_smoke/run_smoke.py --dry-run
python ntcir19_fehu-master/research/task2_prompt_smoke/run_smoke.py
```

Python 3.10+ standard library only; no pip installation needed. A live default run
plans exactly 6 API requests (3 subevents x 2 conditions), with no automatic retry.
Failed, blank, truncated, invalid-ID or missing-actor responses stop the run and
are never silently treated as empty labels. Live API requests may incur charges.

Outputs are in `ntcir19_fehu-master/output/task2_prompt_smoke/` with a Tokyo-time
run folder. Requests exclude authentication headers; responses retain model IDs
and token usage. Gold is loaded after successful prediction and restricted to
selected events before scoring. The script imports the official evaluator's
functions, bypassing its existing CLI `DEBUG=True` parameter override.

Current official API references, checked 2026-11-04:
- https://api-docs.deepseek.com/ (model `deepseek-flash`, base URL `https://api.deepseek.com`)
- https://api-docs.deepseek.com/guides/json_mode/
- https://api-docs.deepseek.com/guides/thinking_mode/

The public model alias may change underlying weights. Store returned model IDs
and execution dates; do not equate today's run with historical API runs.
