# FEHU Tiny Pilot Dry-Run (v1)

> **This module never calls an API.** It validates the human-approved manifest
> and writes a complete set of dry-run artifacts that prove the tiny pilot is
> *ready* to execute but has *not been executed*.

## Files

| File | Purpose |
|---|---|
| `run_tiny_pilot_dry_run.py` | The dry-run script (standard library only) |
| `README.md` | This file |

## Hard guarantees of the script

- Imports only the Python standard library (`argparse`, `csv`, `json`, `re`, `sys`,
  `datetime`, `pathlib`, `typing`).
- Does NOT import `openai`, `anthropic`, `google.generativeai`, `requests`,
  `httpx`, `aiohttp`, `urllib3`, or any other network/API client.
- Does NOT read `.env`.
- Does NOT require an API key.
- Has **no `--execute` flag**. The only mode is `--dry-run`.
- Writes only into the user-supplied `--outdir`. Never touches `dataset/`,
  `output/task1*/`, `logs/cache_*`, the approved manifest, or any prior
  research folder.

## Usage

From project root:

```bash
python research/fehu_tiny_pilot_dry_run_v1/run_tiny_pilot_dry_run.py \
    --manifest output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl \
    --outdir   output/research_generation_dry_run/<YYYYMMDD_HHMMSS> \
    --dry-run
```

`--dry-run` is the default and only supported mode; the flag is accepted for
clarity. Output goes into the timestamped folder you pass in.

## Output (8 files)

```
output/research_generation_dry_run/<YYYYMMDD_HHMMSS>/
├── 00_DRY_RUN_DASHBOARD.md
├── 01_manifest_validation_report.md
├── 02_execution_plan.csv
├── 03_prompt_preview_samples.md
├── 04_expected_output_schema.md
├── 05_safety_checklist.md
├── 06_api_key_and_execution_notes.md
└── 07_session_report.md
```

If manifest validation fails, only `01_manifest_validation_report.md` and
`07_session_report.md` are written (plus an empty `--outdir`). The script
exits with code 2 in that case.

## What this module is NOT

- Not API generation.
- Not a runner for real LLM calls.
- Not authorisation for future API execution.

The next phase (a real runner) requires a separate, explicit user
authorisation and a new module (likely
`research/fehu_augmentation_v1/run_generation.py`). This dry-run intentionally
provides no scaffolding for that, beyond the documentation in
`06_api_key_and_execution_notes.md` of the dry-run output folder.
