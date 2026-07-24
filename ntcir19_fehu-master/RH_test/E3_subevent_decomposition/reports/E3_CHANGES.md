# E3 — Subevent Decomposition: E1 → E3 changes (prepared, NOT yet run)

**Date prepared:** 2026-07-23
**Status:** ready for later execution. **No API was called, no inference/training/evaluation was run, no credits spent.** The only executed code was local: the pipeline generator, a dry-run prompt preview, and stdlib offline checks.
**Design rationale:** `docs/FEHU_E3_DESIGN_ANALYSIS_20260723.md` (E1 retained, E2 rejected → change the unit of prediction, not the strictness of instructions).
**Base:** `RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py`, frozen. Nothing in `liu_method/`, `E1_fewshot_repair/`, or `E2_prompt_bias_control/` was modified.

## What E3 is

E3 keeps E1's entire prompt system (repaired few-shot demos, no numeric caps, no truncation, `targeted_more_shot_balanced` calibration, same model/temperature/JSON mode/retries) and changes **only the unit of prediction**: still **one API call per article** (~same cost as E1), but the model judges each listed subevent separately and returns one labeled block per subevent. The article-level Task-1b prediction is the **deterministic direction-specific union** over `(actor, l1_value, direction)` computed **in code** (the pre-existing dedup loop — the model never self-merges). Task-1a is the L1→L2 projection of the union, as before. **None of E2's rejected evidence-gate / bias-control instructions are present** (verified against the snapshot).

## The generated diff (19 asserted deltas in `scripts/build_e3_pipeline.py`)

Every delta is a string replacement asserted to match exactly once in the E1 source; the complete E1→E3 diff is auditable from that one file. Grouped:

- **S1 — per-subevent prompting.** TASK line reframed to "identify FOR EACH SUBEVENT…, judge every subevent on its own described events, article as background context". New structural guideline 7 (values may recur across subevents; uninvolved actors get nothing — locality, not strictness). OUTPUT FORMAT: a JSON array with one element per subevent, each `{"subevent_id", "items": [...]}`, empty `items` explicitly allowed; the DeepSeek JSON-object rewrite becomes a top-level `{"subevents": [...]}` with a matching worked example; the user prompt lists the article's numbered subevents (dev has them for all 177 articles, median 9) and asks for per-subevent output.
- **S2 — demos from official Task-2 gold.** Same two deterministically selected demo articles as E1 (selection rule untouched; verified identical guids `0-4349-1-t`, `0-4352-3-1`). Their outputs are re-rendered from the **official `subevents_human_values` train gold**: one block per subevent in article order (8 and 6 blocks), deduplicated within each block, compact 3-field items, and one genuinely empty block (limo-crash subevent 5 has no gold labels) demonstrating that empty output is legitimate. Demo subevent lists are shown in the examples. Per-unit demo label totals are 13 and 8 (the official subevent annotation, not a redistribution of the article-level 15/10 sets).
- **S3 — parse + union.** Parser unwraps `{"subevents": [...]}` (legacy `{"items": [...]}` kept as fallback); `process_results` flattens the blocks and the existing `(actor, direction, l1_value)` dedup **is** the union. Direction-specific by construction: opposite directions of the same value survive as separate labels, matching the evaluator's `direction:l1` encoding.
- **S4 — unit-support metadata.** For every predicted 1b label the supporting subevent ids are recorded and written to `unit_support.json`. **Metadata only — never a filter** (a support threshold would be E2's mistake in structural clothing). It feeds the planned E4 per-candidate QA verifier and the FP analysis; `analyze_e3.py` builds a TP/FP-by-support histogram from it.
- **S5 — bookkeeping.** `E3_RUN_TS` env var, run_config experiment name/base/delta list, fewshot_meta now records subevent counts. Outputs isolated under `RH_test/E3_subevent_decomposition/runs/<timestamp>/`.

## Verification performed (all local, no API)

1. `build_e3_pipeline.py` — all 19 deltas matched exactly once; output compiles.
2. **Dry-run preview** (`runs/dryrun_preview/`, `logs/e3_dryrun_preview.log`): full system prompt snapshot (18,452 chars) + first dev article user prompt, generated without any API client. 16 invariants checked and passed: per-subevent TASK/OUTPUT FORMAT present, DeepSeek `"subevents"` object + example present, variant still strips reasoning, E1's guidelines (incl. "Common patterns") retained, **E2's "EVIDENCE AND BIAS CONTROL"/anti-role-prior wording absent**, no numeric caps, no truncated demos, 2 examples with subevent lists.
3. **`offline_check_e3.py`** (synthetic data, stdlib): parser object handling; union merges duplicate labels across units while keeping both directions separately; invalid actor/l1 items dropped as in E1; `unit_support` counts units (not items) and excludes invalid items; flat non-unit responses tolerated; demo blocks byte-equivalent to the official deduped subevent gold. **All 11 checks passed.**

## How to run later (unchanged protocol; ~177 Flash calls, ≈ E1 cost)

```bash
python3 RH_test/E3_subevent_decomposition/scripts/build_e3_pipeline.py    # regenerate (asserted)
set -a && . ./.env && set +a
export E3_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E3_subevent_decomposition/scripts/run_pipeline_e3.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E3_subevent_decomposition/scripts/analyze_e3.py $E3_RUN_TS
```

`analyze_e3.py` produces the three-way Liu/E1/E3 comparison (`comparison_liu_e1_e3.csv`), per-target-18 counts, and `unit_support_histogram.csv`. **Success criterion:** micro/macro recall up vs. E1 with F1 at worst flat; a precision drop is expected by design (the union only adds) — quantifying it, and its relation to unit support, is exactly the input the separate E4 verifier experiment needs. Single-pass caveat applies as for E1/E2 (±0.004 documented run variance; ×3 replication before strong claims).

## Known/accepted differences from a "pure" NEVU map–reduce

- One chunked call per article rather than one call per subevent (9× cheaper; the fallback multi-call variant is E3b if per-unit judgments look contaminated by whole-article context — see design doc §6).
- The long-article user-prompt truncation (`>12000` chars → head+tail) is inherited from Liu/E1 unchanged; the subevent list is appended untruncated, which already mitigates the middle-loss issue.
- Model max_tokens 8000 unchanged; compact 3-field items at median 9 blocks fit comfortably.
