# FEHU Tiny Pilot Generation — DeepSeek V4

## Purpose

This script runs the **tiny pilot generation stage** of the FEHU/NTCIR-19 Task-1
diagnosis-driven, recall-focused targeted augmentation workflow.

It calls the DeepSeek V4 API to generate candidate augmented training samples from
a human-approved manifest, then validates and reports on the generated samples.

---

## What Stage of the Research Pipeline This Belongs To

```
[Label Diagnosis] → [Augmentation Plan] → [Preview v2] → [Human Review] →
[Human Approval Manifest] → [Dry Run] → [THIS STAGE: Tiny Pilot Generation] →
[Human Verification of Generated Samples] → [Ablation Experiment]
```

This script implements the **Tiny Pilot Generation** stage.
It requires a human-approved manifest from the prior approval stage.

---

## What It Does

1. Loads the human-approved manifest (6 requests).
2. Runs comprehensive preflight validation (15 checks) before any API call.
3. In **validation-only mode**: writes all reports, makes no API calls.
4. In **execute mode**: calls the DeepSeek Chat Completions API for exactly the
   6 approved requests, parses responses, validates generated samples, and writes
   all output reports.
5. Writes 11 structured output files to a timestamped output folder.

---

## What It Does NOT Do

- Does **not** train any model.
- Does **not** modify `evaluation.py`, `dataset/**`, `gold_labels/**`,
  `output/task1*/`, `logs/cache_*`, or any prior research folder.
- Does **not** create `pred_task1a.json` or `pred_task1b.json`.
- Does **not** write generated samples into the official training dataset.
- Does **not** approve generated samples for training automatically.
- Does **not** read `.env` files.
- Does **not** print, save, or log the API key value anywhere.
- Does **not** retry more than once per request.
- Does **not** generate more than one sample per request.
- Does **not** claim that generated samples improve FEHU performance.

Generated samples are permanently `PENDING_HUMAN_VERIFICATION` until a human
reviewer explicitly approves them.

---

## Dependencies

Python 3.7+ standard library only:
`json`, `csv`, `os`, `sys`, `argparse`, `datetime`, `pathlib`,
`urllib.request`, `urllib.error`, `traceback`, `re`

No `requests`, `httpx`, `aiohttp`, `openai`, or `anthropic` package is used.

---

## How to Set the API Key Safely

**NEVER paste your API key into a prompt, terminal history, source file, CSV, JSONL, or log.**

Use the read-then-export pattern:

```bash
read -s DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
```

This reads the key silently (no echo) and exports it to the shell environment.
The script reads it from `os.environ["DEEPSEEK_API_KEY"]` and never writes it anywhere.

---

## How to Run — Validation-Only Mode

No API key required. No API calls are made. All preflight checks run.

```bash
python research/fehu_tiny_pilot_generation_v1/run_tiny_pilot_generation.py \
  --manifest output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl \
  --outdir output/research_generation_tiny_pilot/20260615_171954 \
  --model deepseek-v4-pro \
  --temperature 0.2 \
  --max-tokens 1800
```

Expected result: all 15 preflight checks pass; output files are written;
no API calls are made.

---

## How to Run — Execute Mode

Requires `DEEPSEEK_API_KEY` to be set. Only run after validation-only mode passes.
Use the **same `--outdir`** as the validation-only run.

```bash
read -s DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY

python research/fehu_tiny_pilot_generation_v1/run_tiny_pilot_generation.py \
  --manifest output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl \
  --outdir output/research_generation_tiny_pilot/20260615_171954 \
  --model deepseek-v4-pro \
  --temperature 0.2 \
  --max-tokens 1800 \
  --execute
```

The script will:
- Re-run all preflight checks.
- Call the API for exactly 6 requests (no more).
- Save raw responses, parse JSON, validate samples.
- Write 11 output files to the specified `--outdir`.

---

## Output Files

All output files are written to `--outdir`:

| File | Contents |
|------|----------|
| `00_GENERATION_DASHBOARD.md` | Overall status, counts, results table |
| `01_run_config.json` | Run parameters (no API key value) |
| `02_generation_requests_used.jsonl` | Copy of 6 approved manifest rows |
| `03_raw_responses.jsonl` | Sanitized raw API responses |
| `04_parsed_samples.jsonl` | Parsed + validated generated samples |
| `05_failed_requests.jsonl` | Any API or parse failures |
| `06_validation_report.md` | Per-request validation analysis |
| `07_validation_table.csv` | Machine-readable validation results |
| `08_human_verification_sheet.csv` | Sheet for human reviewers (fill in human_decision column) |
| `09_research_interpretation.md` | Research-level interpretation |
| `10_session_report.md` | Safety audit and session summary |

---

## Safety Warnings

> **WARNING: Never paste API keys into prompts, reports, CSV, JSONL, logs, or source code.**

> **WARNING: Generated samples remain `PENDING_HUMAN_VERIFICATION`.**
> They are candidates only. Do not use them for training until a human reviewer
> has explicitly approved each sample.

> **WARNING: Do not use generated samples for training until verified.**
> Even structurally valid samples may contain hallucinated facts, biased content,
> or annotation-inconsistent labels. Human verification is mandatory.

---

## Approved Request IDs (this pilot only)

The preflight validation enforces that the manifest contains exactly these 6 IDs:

- `prev_rare_positive_24_004_98671d8d01`
- `prev_rare_positive_32_001_83df110175`
- `prev_dir_contrast_12_002_aligned_ce1da19f54`
- `prev_dir_contrast_12_002_contradictory_ce1da19f54`
- `prev_dir_contrast_38_003_aligned_e969e14138`
- `prev_dir_contrast_38_003_contradictory_e969e14138`

Any deviation causes a BLOCKED report and no API calls.

---

## Direction Convention

Per `dataset/hv_categories/direction_mapping.json` (authoritative):

| direction field | meaning |
|-----------------|---------|
| `"1"` | aligned — actor supports/expresses the value |
| `"0"` | contradictory — actor violates/undermines the value |

The script enforces this convention in both preflight validation and sample validation.
