# FEHU Tiny Pilot Repair and Targeted Regeneration

## Purpose

This script performs targeted repair and regeneration of the FEHU tiny pilot generation
results. It is part of the FEHU/NTCIR-19 Task-1 diagnosis-driven augmentation workflow.

---

## What Stage of the Research Pipeline This Belongs To

```
[Tiny Pilot Generation (v1)] → [THIS STAGE: Repair + Targeted Regeneration] →
[Human Verification] → [Ablation Experiment]
```

This script handles the post-generation quality-control pass:
- Reads the previous tiny pilot output (read-only).
- Performs deterministic evidence_sentence repair where applicable.
- Regenerates only the requests that definitively failed (finish_reason=length).
- Unifies all candidates and re-validates them.
- Produces a human verification sheet for final review.

---

## What It Does

1. **Reads** the previous tiny pilot output folder (never modifies it).
2. **Triages** 6 requests into KEEP / DETERMINISTIC_REPAIR / TARGETED_REGENERATION.
3. **Deterministic repair:** Expands a truncated evidence_sentence to the full sentence
   already present verbatim in content — no API call required.
4. **Targeted regeneration:** Calls DeepSeek API only for the 2 requests that failed
   due to token budget exhaustion, now using `max_tokens=4096`.
5. **Unified validation:** Re-validates all candidates with 23-check suite.
6. **Writes 12 output files:** dashboard, triage, repair report, raw responses,
   parsed samples, failures, unified candidates, validation table, human verification
   sheet, research interpretation, session report.

---

## What It Does NOT Do

- Does **not** train any model.
- Does **not** modify the previous tiny pilot output folder.
- Does **not** modify `evaluation.py`, `dataset/**`, `gold_labels/**`,
  `output/task1*/`, `logs/cache_*`, or any prior research folder.
- Does **not** create `pred_task1a.json` or `pred_task1b.json`.
- Does **not** write into the official training dataset.
- Does **not** approve generated samples for training automatically.
- Does **not** print, save, or log the API key value.
- Does **not** retry more than once per regeneration request.
- Does **not** regenerate PASS or WARN samples from the previous pilot.

Generated samples remain `PENDING_HUMAN_VERIFICATION` until explicit human approval.

---

## Dependencies

Python 3.7+ standard library only:
`json`, `csv`, `os`, `sys`, `argparse`, `datetime`, `pathlib`,
`urllib.request`, `urllib.error`, `traceback`, `re`

---

## How to Set the API Key Safely

**NEVER paste your API key into a prompt, terminal, script, CSV, JSONL, or log.**

```bash
read -s DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
```

---

## How to Run — Validation-Only Mode (no API calls)

```bash
python research/fehu_tiny_pilot_repair_v1/repair_and_regenerate_tiny_pilot.py \
  --input output/research_generation_tiny_pilot/20260615_171954 \
  --approved-manifest output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl \
  --outdir output/research_generation_tiny_pilot_repair/20260615_175432 \
  --model deepseek-v4-pro \
  --temperature 0.2 \
  --max-tokens 4096
```

No `--execute` flag → no API calls. All triage and repair logic runs; regeneration is skipped.

---

## How to Run — Execute Mode (calls DeepSeek API)

```bash
read -s DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY

python research/fehu_tiny_pilot_repair_v1/repair_and_regenerate_tiny_pilot.py \
  --input output/research_generation_tiny_pilot/20260615_171954 \
  --approved-manifest output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl \
  --outdir output/research_generation_tiny_pilot_repair/20260615_175432 \
  --model deepseek-v4-pro \
  --temperature 0.2 \
  --max-tokens 4096 \
  --execute
```

---

## Triage Classification (pre-defined from pilot analysis)

| Category | Request IDs |
|----------|-------------|
| KEEP (PASS/WARN) | `prev_dir_contrast_12_002_aligned_ce1da19f54`, `prev_dir_contrast_38_003_contradictory_e969e14138`, `prev_rare_positive_32_001_83df110175` |
| DETERMINISTIC_REPAIR | `prev_dir_contrast_38_003_aligned_e969e14138` |
| TARGETED_REGENERATION | `prev_dir_contrast_12_002_contradictory_ce1da19f54`, `prev_rare_positive_24_004_98671d8d01` |

---

## Key Change from Initial Pilot

| Parameter | Initial Pilot | This Script |
|-----------|--------------|-------------|
| max_tokens | 1800 | 4096 |
| Content length target | unspecified | 120–180 words |
| Evidence sentence rule | stated | Enforced: "copy one exact sentence from content" |
| Response start constraint | implicit | Explicit: "start with `{`" |

---

## Safety Warnings

> **WARNING: Never paste API keys into prompts, reports, CSV, JSONL, logs, or source code.**

> **WARNING: Generated samples remain `PENDING_HUMAN_VERIFICATION`.**
> Do not use any sample for training until a human reviewer has explicitly approved it.

> **WARNING: Do not modify the input tiny pilot folder.**
> The script enforces that `--input` and `--outdir` are different paths.
