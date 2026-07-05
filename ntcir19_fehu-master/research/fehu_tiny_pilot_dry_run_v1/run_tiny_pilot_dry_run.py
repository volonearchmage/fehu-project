#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_tiny_pilot_dry_run_v1/run_tiny_pilot_dry_run.py

Dry-run-only generation readiness check for the FEHU human-approved tiny pilot.

⚠ This script never calls an API. It validates the approved manifest and
   writes a complete set of dry-run artifacts. There is no `--execute` flag.
   There is no code path that opens a network connection.

Run from project root:
    python research/fehu_tiny_pilot_dry_run_v1/run_tiny_pilot_dry_run.py \\
        --manifest output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl \\
        --outdir   output/research_generation_dry_run/<YYYYMMDD_HHMMSS> \\
        --dry-run

The default mode is dry-run.

Standard library only (no openai / requests / httpx / aiohttp / urllib3 / gemini / anthropic).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ============================================================
# CONSTANTS
# ============================================================

EXPECTED_APPROVED_COUNT = 6
SENSITIVE_L1 = {"29", "44", "51"}
FORBIDDEN_FIELDS = {"execute", "should_execute_now"}
REQUIRED_PAIRS = [
    (
        "prev_dir_contrast_12_002_aligned_ce1da19f54",
        "prev_dir_contrast_12_002_contradictory_ce1da19f54",
    ),
    (
        "prev_dir_contrast_38_003_aligned_e969e14138",
        "prev_dir_contrast_38_003_contradictory_e969e14138",
    ),
]
DIR_NAME = {"1": "aligned", "0": "contradictory"}

# Conservative pattern to catch sk-…, ds-…, anthropic-…, etc.
SECRET_PAT = re.compile(r"\b(sk|ds|anthropic)[-_][A-Za-z0-9_-]{16,}\b")


# ============================================================
# IO
# ============================================================

def load_manifest(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


# ============================================================
# VALIDATION (Task B)
# ============================================================

def validate_manifest(rows: List[Dict[str, Any]]) -> List[str]:
    """Return a list of failure messages; empty list means valid."""
    failures: List[str] = []

    if len(rows) != EXPECTED_APPROVED_COUNT:
        failures.append(
            f"manifest has {len(rows)} rows, expected {EXPECTED_APPROVED_COUNT}"
        )

    ids = {r.get("request_id") for r in rows}

    for r in rows:
        rid = r.get("request_id", "<unknown>")
        if r.get("manual_approval_status") != "APPROVED_BY_HUMAN":
            failures.append(
                f"{rid}: manual_approval_status must be 'APPROVED_BY_HUMAN' "
                f"(got {r.get('manual_approval_status')!r})"
            )
        if r.get("api_generation_authorized_now") is not False:
            failures.append(
                f"{rid}: api_generation_authorized_now must be False "
                f"(got {r.get('api_generation_authorized_now')!r})"
            )
        if r.get("requires_separate_generation_runner_approval") is not True:
            failures.append(
                f"{rid}: requires_separate_generation_runner_approval must be True "
                f"(got {r.get('requires_separate_generation_runner_approval')!r})"
            )
        # Defensive: no PENDING status
        if r.get("manual_approval_status") == "PENDING_HUMAN_APPROVAL":
            failures.append(f"{rid}: forbidden status PENDING_HUMAN_APPROVAL")
        # Forbidden fields
        for fld in FORBIDDEN_FIELDS:
            if fld in r:
                failures.append(f"{rid}: forbidden field present: {fld!r}")
        # Forbidden types
        atype = r.get("augmentation_type")
        if atype == "hard_negative":
            failures.append(f"{rid}: hard_negative is forbidden in this pilot")
        if atype == "paraphrase":
            failures.append(f"{rid}: paraphrase is forbidden in this pilot")
        # Sensitive labels
        l1 = str(r.get("target_l1_value_id", ""))
        if l1 in SENSITIVE_L1:
            failures.append(f"{rid}: sensitive label L1={l1} is forbidden in this pilot")
        # Direction convention
        d = r.get("target_direction")
        dn = r.get("target_direction_name")
        if d in ("0", "1"):
            if dn != DIR_NAME[d]:
                failures.append(
                    f"{rid}: direction {d!r} should map to {DIR_NAME[d]!r}, "
                    f"got direction_name={dn!r}"
                )
        elif d is None and atype == "hard_negative":
            pass  # not in this pilot anyway
        elif d is None:
            failures.append(f"{rid}: target_direction is null but augmentation_type={atype!r}")
        else:
            failures.append(f"{rid}: target_direction must be '0' or '1' (got {d!r})")

    # Pair completeness
    for a, b in REQUIRED_PAIRS:
        if a not in ids or b not in ids:
            failures.append(
                f"required direction-contrastive pair incomplete: ({a}, {b})"
            )

    # Secret scan over JSON-serialised manifest content
    blob = json.dumps(rows, ensure_ascii=False)
    for m in SECRET_PAT.finditer(blob):
        failures.append(f"secret-shaped token detected in manifest: {m.group()[:8]}…")

    return failures


# ============================================================
# WRITERS (Tasks C, D, E, F, G, H, I)
# ============================================================

def write_validation_report(rows: List[Dict[str, Any]], failures: List[str], outdir: Path) -> None:
    lines = [
        "# Manifest Validation Report",
        "",
        f"**Manifest:** `{rows[0].get('approved_by','?')}` source — see `00_DRY_RUN_DASHBOARD.md`.",
        f"**Rows loaded:** {len(rows)}",
        f"**Expected rows:** {EXPECTED_APPROVED_COUNT}",
        f"**Verdict:** {'PASS' if not failures else 'FAIL'}",
        "",
        "## Checks performed",
        "",
        "1. Manifest has exactly 6 rows.",
        "2. Every row has `manual_approval_status == 'APPROVED_BY_HUMAN'`.",
        "3. Every row has `api_generation_authorized_now == False`.",
        "4. Every row has `requires_separate_generation_runner_approval == True`.",
        "5. No row has `manual_approval_status == 'PENDING_HUMAN_APPROVAL'`.",
        "6. No row has any field named `execute` or `should_execute_now`.",
        "7. No `hard_negative` request is included.",
        "8. No `paraphrase` request is included.",
        "9. No sensitive-label request (L1 ∈ {29, 44, 51}) is included.",
        "10. Both required direction_contrastive pairs are present:",
        "    - prev_dir_contrast_12_002_aligned_… / contradictory_…",
        "    - prev_dir_contrast_38_003_aligned_… / contradictory_…",
        "11. Direction convention `'1'` = aligned, `'0'` = contradictory consistent on every row.",
        "12. No secret-shaped tokens (`sk-…`, `ds-…`, `anthropic-…`) in the manifest payload.",
        "",
        "## Result",
        "",
    ]
    if failures:
        lines.append(f"❌ **{len(failures)} validation failures** — dry-run halted.")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append("✅ **All checks passed.**")
        lines.append("")
        lines.append("| Row | request_id | type | L1 | direction |")
        lines.append("|---|---|---|---|---|")
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | `{r['request_id']}` | {r['augmentation_type']} | "
                f"{r['target_l1_value_id']} | {r.get('target_direction','—')} |"
            )

    lines += [
        "",
        "## What this validation does NOT do",
        "",
        "- Does not call any API.",
        "- Does not read `.env`.",
        "- Does not authorise execution.",
        "- Does not modify the manifest or any other existing file.",
    ]
    (outdir / "01_manifest_validation_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_execution_plan(rows: List[Dict[str, Any]], outdir: Path) -> None:
    """Task C: 02_execution_plan.csv with PLANNED_ONLY status."""
    cols = [
        "execution_order", "request_id", "augmentation_type",
        "target_l1_value_id", "target_l1_value_name",
        "target_l2_value_id", "target_l2_value_name",
        "direction", "direction_name", "is_positive",
        "seed_guid", "seed_actor_id", "canonical_actor_name",
        "expected_output_file",
        "dry_run_status", "generation_allowed_now",
    ]
    out_rows = []
    for i, r in enumerate(rows, 1):
        d = r.get("target_direction")
        is_positive = r.get("augmentation_type") != "hard_negative"
        out_rows.append({
            "execution_order":        i,
            "request_id":             r["request_id"],
            "augmentation_type":      r["augmentation_type"],
            "target_l1_value_id":     r.get("target_l1_value_id"),
            "target_l1_value_name":   r.get("target_l1_value_name"),
            "target_l2_value_id":     r.get("target_l2_value_id"),
            "target_l2_value_name":   r.get("target_l2_value_name"),
            "direction":              d if d is not None else "",
            "direction_name":         (
                r.get("target_direction_name")
                or (DIR_NAME.get(d) if d else "")
            ),
            "is_positive":            str(is_positive).lower(),
            "seed_guid":              r.get("seed_guid") or "",
            "seed_actor_id":          r.get("seed_actor_id") or "",
            "canonical_actor_name":   r.get("canonical_actor_name") or "",
            # planned hypothetical output path — does not exist
            "expected_output_file":   (
                f"output/research_augmentation_data/<future_TS>/"
                f"{r['request_id']}.json"
            ),
            "dry_run_status":         "PLANNED_ONLY",
            "generation_allowed_now": "NO",
        })

    with open(outdir / "02_execution_plan.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)


def write_prompt_previews(rows: List[Dict[str, Any]], outdir: Path) -> None:
    """Task D: 03_prompt_preview_samples.md (compact, dry-run-only)."""
    lines = [
        "# Prompt Preview Samples — DRY-RUN PREVIEW ONLY",
        "",
        "> Every block below is **DRY-RUN PREVIEW ONLY**. No prompt has been sent",
        "> to any LLM. There is no command in this document that would execute generation.",
        "",
        f"Total approved requests previewed: **{len(rows)}**",
        "",
    ]
    for i, r in enumerate(rows, 1):
        sp = (r.get("system_prompt") or "")
        up = (r.get("user_prompt") or "")
        # Compact preview: first 4 lines of each, joined, truncated.
        def compact(text: str, max_lines: int = 8, max_chars: int = 700) -> str:
            head = "\n".join(text.split("\n")[:max_lines])
            if len(head) > max_chars:
                head = head[:max_chars] + "…"
            return head

        l1 = r.get("target_l1_value_id"); l1n = r.get("target_l1_value_name")
        l2 = r.get("target_l2_value_id"); l2n = r.get("target_l2_value_name")
        d  = r.get("target_direction"); dn = r.get("target_direction_name") or ""
        can = r.get("canonical_actor_name") or "(generator will invent)"
        mentions = r.get("suggested_actor_mentions") or []
        if isinstance(mentions, list):
            mentions_str = " | ".join(mentions[:4]) if mentions else "—"
        else:
            mentions_str = str(mentions)

        lines += [
            f"## [{i}] `{r['request_id']}`",
            "",
            "**DRY-RUN PREVIEW ONLY — no API call.**",
            "",
            f"- Augmentation type: `{r['augmentation_type']}`",
            f"- Target L1: **{l1}** — {l1n}",
            f"- Target L2: **{l2}** — {l2n}",
            f"- Direction: `{d}` ({dn})  · per `direction_mapping.json` (`'1'`=aligned, `'0'`=contradictory)",
            f"- Canonical actor: {can}",
            f"- Suggested actor mentions: {mentions_str}",
            f"- Seed guid: `{r.get('seed_guid') or '—'}`",
            f"- Seed actor id: `{r.get('seed_actor_id') or '—'}`",
            f"- Paired request id: `{r.get('paired_request_id') or '—'}`",
            f"- `manual_approval_status`: `{r.get('manual_approval_status')}`",
            f"- `api_generation_authorized_now`: `{r.get('api_generation_authorized_now')}`",
            "",
            "### System prompt (compact preview)",
            "",
            "```",
            compact(sp),
            "```",
            "",
            "### User prompt (compact preview)",
            "",
            "```",
            compact(up),
            "```",
            "",
            "---",
            "",
        ]
    (outdir / "03_prompt_preview_samples.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


EXPECTED_SCHEMA_MD = """# Expected Output Schema (Future Generated Sample)

> This documents the **future** generated-response schema. **No sample has been generated.**

Every future generated sample (one per approved request) must conform to this schema before
entering any training pool. The augmented-training-data guard at
`research/fehu_submission_safety/augmented_training_data_guard.py` enforces these rules.

## Required JSON fields

| Field | Type | Description |
|---|---|---|
| `title` | string | News-style headline, ≤ 200 chars |
| `content` | string | News-style body, 50–1500 chars |
| `actor_name` | string | Canonical actor identifier — must equal the request's `canonical_actor_name` (or, for invented-actor types, the name the generator picked) |
| `actor_mention` | string | The actual surface form used inside `content`. **MUST appear verbatim in `content`.** May be the canonical name, the primary mention, an alias, or any natural surface form |
| `evidence_sentence` | string | **MUST appear verbatim in `content`**, MUST describe the target actor's action/stance/decision/behavior, MUST support the target value+direction (for hard_negative: must support the ALTERNATIVE value) |
| `explanation` | string | One-sentence justification of (actor, value, direction). For hard_negative: WHY the target label does not apply |
| `l1_value_id` | string | One of `"0".."53"` |
| `l1_value_name` | string | Must match `l1_value_id` per `dataset/hv_categories/human_value_level1_values.json` |
| `l2_value_id` | string | One of `"0".."19"` |
| `l2_value_name` | string | Must match `l2_value_id` per `dataset/hv_categories/human_value_level2_values.json` |
| `direction` | `"0"` / `"1"` / `null` | `"1"` = aligned, `"0"` = contradictory; `null` only for hard_negative |
| `direction_name` | `"aligned"` / `"contradictory"` / `null` | Must match `direction` |
| `is_positive` | boolean | `True` for paraphrase / rare_positive / direction_contrastive; `False` for hard_negative |
| `_type_specific_rule` | string | Echo of the type-specific rule the generator agreed to |

## Future validation rules

The augmented-data guard will enforce, at minimum:

1. **Schema validity** — every required field present, correct type, correct enum / pattern.
2. **`evidence_sentence` verbatim in `content`** (or, if marked `[derived] `, semantically derived).
3. **`actor_mention` verbatim in `content`**.
4. **L1↔L2 mapping** matches `dataset/hv_categories/level_1_to_level_2.json`.
5. **Direction / direction_name consistency** per `dataset/hv_categories/direction_mapping.json`
   (`"1"` = aligned, `"0"` = contradictory). The `evaluation.py` docstring inverts this; the
   guard does NOT use `evaluation.py` for direction semantics.
6. **L1 / direction / is_positive must match the approved request**. A request asking for
   `(l1=12, direction="1", is_positive=true)` and a response carrying
   `(l1=12, direction="0", …)` is automatically rejected.
7. **No more salient non-target value** — generated content must not make any other human
   value more salient than the target value for the target actor.
8. **No defamation or unsupported factual accusations** about real, identifiable individuals.
9. **No dev/test article content** used as seed (`seed_guid` must not be in dev or test
   event_base files).
10. **No secret-shaped strings** (no API-key tokens) in any field.

## Path forward

Once samples exist, run:

```bash
python research/fehu_submission_safety/augmented_training_data_guard.py \\
    --input output/research_augmentation_data/<future_TS>/augmented_samples.jsonl \\
    --strict
```

A clean exit-0 is required before any training-data integration. **No such file exists yet.**
"""


SAFETY_CHECKLIST_MD = """# Safety Checklist

## Go / No-Go

| # | Item | Decision |
|---|---|---|
| 1 | Approved manifest exists | ✅ GO |
| 2 | Manifest has exactly 6 rows | ✅ GO |
| 3 | Dry-run completed | ✅ GO |
| 4 | API generation now | 🛑 NO-GO |
| 5 | API key required now | 🛑 NO-GO |
| 6 | Run real generation now | 🛑 NO-GO |
| 7 | Training now | 🛑 NO-GO |
| 8 | Final FEHU submission now | 🛑 NO-GO |
| 9 | Official dataset modification | 🛑 NO-GO |
| 10 | Old prediction modification | 🛑 NO-GO |

## Negative invariants (verified by `01_manifest_validation_report.md`)

- ✅ No row carries `manual_approval_status == "PENDING_HUMAN_APPROVAL"`.
- ✅ No row carries `api_generation_authorized_now == true`.
- ✅ No row contains the field `execute` or `should_execute_now`.
- ✅ No `hard_negative` request approved.
- ✅ No `paraphrase` request approved.
- ✅ No sensitive-label (L1 ∈ {29, 44, 51}) request approved.
- ✅ Both required direction-contrastive pairs are complete.
- ✅ No secret-shaped tokens in the manifest payload.

## What this dry-run is NOT

- Not API generation.
- Not a model training step.
- Not a prediction submission.
- Not a quality / performance claim — it does not measure F1, recall, or DRR.

## What this dry-run IS

- Proof that the human-approved manifest is structurally valid.
- A documented execution plan that a future runner could consume.
- A static set of prompt previews so the professor / reviewer can sanity-check.
- A reaffirmation that real API generation requires a separate explicit authorisation.
"""


API_NOTES_MD = """# API Key and Future Execution Notes

> **No API key is needed for this dry-run.** The script in this folder cannot make a network
> call: it imports only the Python standard library and writes only to the dry-run output folder.

## Hard rules going forward

1. **Do NOT paste API keys into prompts, reports, CSV, JSONL, or logs.**
   The dry-run scans the manifest for tokens of shape `sk-…`, `ds-…`, `anthropic-…` and
   fails fast if any are found. Future runners must keep that scan.

2. **Future real API generation must require a separate, explicit user authorisation.**
   This document does not constitute that authorisation. The approved manifest also
   does not constitute it — every row carries `api_generation_authorized_now: false`
   and `requires_separate_generation_runner_approval: true`.

3. **Future real API generation must use environment variables, not hard-coded keys.**
   Recommended variables:
   - OpenAI: `OPENAI_API_KEY`
   - DeepSeek: `DEEPSEEK_API_KEY`
   The future runner should refuse to start if the variable is empty.

4. **The future runner must mask any key that accidentally appears in any input.**
   - On read: redact patterns `\\b(sk|ds|anthropic)[-_][A-Za-z0-9_-]+\\b` before logging.
   - On write: never include the key in any output file.

5. **The future runner must write outputs to a new timestamped folder:**
   ```
   output/research_augmentation_data/YYYYMMDD_HHMMSS/
   ├── augmented_samples.jsonl               # validated samples
   ├── augmented_samples_rejected.jsonl      # samples that failed verification
   ├── raw_responses.jsonl                   # raw LLM responses (key-redacted)
   ├── failures.jsonl                        # API failures, parse errors
   ├── validation_report.md                  # final guard output
   ├── generation_run_config.json            # provider/model/budget/timestamp
   └── verification_summary.json
   ```
   The runner must NEVER write into `output/task1*/`, `dataset/`, or `logs/cache_*`.

6. **The future runner must run the augmented-data guard automatically after generation:**
   ```
   python research/fehu_submission_safety/augmented_training_data_guard.py \\
       --input augmented_samples.jsonl --strict
   ```
   A non-zero exit must abort the pipeline before any downstream consumer reads the file.

## What this dry-run authorises

> **Nothing.** This dry-run authorises no API call, no spending, and no downstream action.
> It only demonstrates that the manifest is valid and the execution plan is well-formed.
"""


def write_dashboard(rows: List[Dict[str, Any]], outdir: Path, manifest_path: Path) -> None:
    """Task H: 00_DRY_RUN_DASHBOARD.md"""
    n = len(rows)
    pairs = []
    by_id = {r["request_id"]: r for r in rows}
    for a, b in REQUIRED_PAIRS:
        if a in by_id and b in by_id:
            ra, rb = by_id[a], by_id[b]
            pairs.append((
                ra.get("target_l1_value_id"),
                ra.get("target_l1_value_name"),
                a, b,
                ra.get("target_direction"), rb.get("target_direction"),
            ))

    lines = [
        "# Dry-Run Dashboard",
        "",
        "**Current stage:** dry-run completed. **No generation has happened.** No API has been called.",
        "",
        "## Input",
        "",
        f"- Approved manifest: `{manifest_path}`",
        "- Approved manifest dashboard: `output/research_human_approval/20260616_004845/00_APPROVAL_DASHBOARD.md`",
        "",
        "## Output dry-run folder",
        "",
        f"`{outdir}`",
        "",
        "```",
        f"{outdir}/",
        "├── 00_DRY_RUN_DASHBOARD.md             ← this file",
        "├── 01_manifest_validation_report.md",
        "├── 02_execution_plan.csv",
        "├── 03_prompt_preview_samples.md",
        "├── 04_expected_output_schema.md",
        "├── 05_safety_checklist.md",
        "├── 06_api_key_and_execution_notes.md",
        "└── 07_session_report.md",
        "```",
        "",
        "## Counts",
        "",
        f"- Approved requests in manifest: **{n}**",
        f"- Planned (dry-run only) executions: **{n}**",
        "- Real executions performed: **0**",
        "",
        "## Planned requests",
        "",
        "| Order | request_id | type | L1 | label | direction |",
        "|---:|---|---|---:|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | `{r['request_id']}` | {r['augmentation_type']} | "
            f"{r.get('target_l1_value_id')} | {r.get('target_l1_value_name')} | "
            f"{r.get('target_direction','—')} ({r.get('target_direction_name','—')}) |"
        )

    lines += [
        "",
        "## Direction-contrastive pairs (complete)",
        "",
        "| L1 | Label | aligned member | contradictory member |",
        "|---|---|---|---|",
    ]
    for l1, ln, a, b, da, db in pairs:
        a_dir = "aligned" if da == "1" else "contradictory"
        b_dir = "aligned" if db == "1" else "contradictory"
        if a_dir == "aligned":
            lines.append(f"| {l1} | {ln} | `{a}` | `{b}` |")
        else:
            lines.append(f"| {l1} | {ln} | `{b}` | `{a}` |")

    lines += [
        "",
        "## Safety summary",
        "",
        "- ✅ No API was called.",
        "- ✅ No `.env` was read.",
        "- ✅ No model was trained.",
        "- ✅ No network library was imported.",
        "- ✅ `evaluation.py`, `dataset/**`, `output/task1*/`, `logs/cache_*` untouched.",
        "- ✅ Approved manifest and prior research folders untouched (read-only).",
        "- ✅ Every approved row in the manifest carries `api_generation_authorized_now: false`.",
        "",
        "## Professor-facing summary",
        "",
        "> This dry-run demonstrates that the FEHU targeted augmentation tiny pilot has a",
        "> verified human-approved manifest and a safe execution plan. It does not yet claim",
        "> performance improvement.",
        "",
        "## Final recommendation",
        "",
        "> **Proceed to real tiny pilot generation only after separate explicit authorization.**",
    ]
    (outdir / "00_DRY_RUN_DASHBOARD.md").write_text("\n".join(lines), encoding="utf-8")


def write_session_report(rows: List[Dict[str, Any]],
                         failures: List[str],
                         outdir: Path,
                         manifest_path: Path) -> None:
    """Task I: 07_session_report.md"""
    lines = [
        "# Session Report — Tiny Pilot Dry-Run",
        "",
        "## Safety attestations",
        "",
        "| Question | Answer |",
        "|---|---|",
        "| Any API called? | **No.** Standard library only; no network import. |",
        "| Any API key required? | **No.** Dry-run does not need a key. |",
        "| Was `.env` read? | **No.** |",
        "| Any model training run? | **No.** |",
        "| Was `evaluation.py` modified? | **No.** |",
        "| Was `dataset/**` modified? | **No.** |",
        "| Was `output/task1*/` modified? | **No.** |",
        "| Were `logs/cache_*.json` modified? | **No.** |",
        "| Were previous research folders modified? | **No** (read-only access to manifest only). |",
        "",
        "## New paths created by this session",
        "",
        "| Path | Role |",
        "|---|---|",
        "| `research/fehu_tiny_pilot_dry_run_v1/` | New research code folder (script + README) |",
        f"| `{outdir}/` | New timestamped dry-run output folder (8 artifacts) |",
        "",
        "## Inputs",
        "",
        f"- Approved manifest: `{manifest_path}`",
        "",
        "## Files created in this dry-run output folder",
        "",
        "- `00_DRY_RUN_DASHBOARD.md`",
        "- `01_manifest_validation_report.md`",
        "- `02_execution_plan.csv`",
        "- `03_prompt_preview_samples.md`",
        "- `04_expected_output_schema.md`",
        "- `05_safety_checklist.md`",
        "- `06_api_key_and_execution_notes.md`",
        "- `07_session_report.md`  ← this file",
        "",
        "## Validation result",
        "",
    ]
    if failures:
        lines.append(f"❌ **FAIL** — {len(failures)} issue(s) found.")
        for f in failures:
            lines.append(f"- {f}")
    else:
        lines.append(f"✅ **PASS** — all checks succeeded on {len(rows)} approved rows.")

    lines += [
        "",
        "## Final statement",
        "",
        "> **Dry-run completed. API generation is still not authorized.**",
    ]
    (outdir / "07_session_report.md").write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# MAIN
# ============================================================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="FEHU tiny-pilot dry-run (no API; no network imports).",
        epilog=(
            "This script has NO --execute flag and no code path that opens a network "
            "connection. Real API generation requires a separately-authored runner "
            "and a separate explicit user authorisation."
        ),
    )
    ap.add_argument("--manifest", type=str, required=True,
                    help="Path to the human-approved manifest (JSONL).")
    ap.add_argument("--outdir", type=str, required=True,
                    help="Output folder for dry-run artifacts. "
                         "Should be inside output/research_generation_dry_run/.")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="Dry-run only (the default and only mode).")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: dry-run is the only supported mode.", file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("FEHU Tiny Pilot Dry-Run (no API, no network imports)")
    print("=" * 64)
    print(f"manifest : {manifest_path}")
    print(f"outdir   : {outdir}")
    print()

    if not manifest_path.exists():
        msg = f"manifest file not found: {manifest_path}"
        (outdir / "07_session_report.md").write_text(
            f"# Session Report\n\n❌ {msg}\n", encoding="utf-8"
        )
        print(msg, file=sys.stderr)
        return 2

    rows = load_manifest(manifest_path)
    failures = validate_manifest(rows)

    # 01 always written (records the verdict)
    write_validation_report(rows, failures, outdir)

    if failures:
        # No execution plan, no previews — but a session report explaining.
        write_session_report(rows, failures, outdir, manifest_path)
        print(f"VALIDATION FAILED: {len(failures)} issue(s). See 01_manifest_validation_report.md")
        return 2

    # All checks passed — write the rest of the dry-run artifacts.
    write_execution_plan(rows, outdir)
    write_prompt_previews(rows, outdir)
    (outdir / "04_expected_output_schema.md").write_text(EXPECTED_SCHEMA_MD, encoding="utf-8")
    (outdir / "05_safety_checklist.md").write_text(SAFETY_CHECKLIST_MD, encoding="utf-8")
    (outdir / "06_api_key_and_execution_notes.md").write_text(API_NOTES_MD, encoding="utf-8")
    write_dashboard(rows, outdir, manifest_path)
    write_session_report(rows, failures, outdir, manifest_path)

    print(f"VALIDATION PASS — {len(rows)} approved rows.")
    print(f"Dry-run artifacts written to: {outdir}")
    print()
    print("Dry-run completed. API generation is still not authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
