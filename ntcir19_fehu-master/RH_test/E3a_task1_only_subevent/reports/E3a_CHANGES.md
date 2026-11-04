# E3a — Task-1-only Subevent Scaffold: E1 → E3a changes (prepared, NOT yet run)

**Date prepared:** 2026-07-23
**Status:** ready for later execution. **No API was called, no inference/training/evaluation was run, no credits spent.** The only executed code was local: the pipeline generator, a dry-run prompt preview, and stdlib offline checks.
**Base:** `RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py`, frozen. Nothing in `liu_method/`, `E1_fewshot_repair/`, `E2_prompt_bias_control/`, or the Task-2-based `E3_subevent_decomposition/` was modified.

## What E3a is

E3a is the **"soft" decomposition** variant: it keeps E1 almost entirely intact — the same repaired few-shot demos with their **Task-1 article-level gold** labels, the same output format, the same model settings, the same high-recall posture — and adds exactly one thing. Each article's existing **subevent texts** (the `subevents` field of `event_base.json`) are shown to the model as a reasoning scaffold, with an instruction to walk the article subevent by subevent so a value expressed in only one part of the story is not overlooked. The model still emits **one consolidated article-level Task-1 prediction per actor**, in a single API call, parsed exactly as in E1.

Crucially, the subevent texts are **input segmentation, not labels**: they exist in `train/dev/test_..._event_base.json` for every article and carry no value annotations. E3a therefore uses **zero Task-2 gold** — no `subevents_human_values`, no per-subevent label supervision. That is the design contract that separates it from the Task-2-based E3.

## E3a vs E1 vs the Task-2-based E3

| | E1 | **E3a (this)** | E3 (`E3_subevent_decomposition/`) |
|---|---|---|---|
| Few-shot demo gold | Task-1 article-level | **Task-1 article-level (byte-identical to E1)** | Task-2 `subevents_human_values` (per-subevent) |
| Subevents in prompt | none | **texts, as reasoning scaffold** | texts, as prediction units |
| Model output | article-level list | **article-level list (unchanged)** | one block per subevent |
| Article-level prediction | direct | **direct** | code-side direction-specific union |
| Uses Task-2 gold? | no | **no** | yes |
| Parser / `process_results` | E1 | **byte-identical to E1** | modified (flatten + union + `unit_support`) |
| API calls/article | 1 | **1** | 1 (chunked) |

E3a is the strictly-lighter cousin of E3: it tests whether merely *presenting* the subevent structure and asking for a per-unit scan recovers tail recall, without paying E3's cost of per-subevent output, code-side union, or any dependence on Task-2 annotations. The two can be compared later to isolate how much of any recall gain needs the "hard" decomposition.

## The generated diff (10 asserted deltas in `scripts/build_e3a_pipeline.py`)

Every delta is a string replacement asserted to match exactly once in the E1 source; the complete E1→E3a diff is auditable from that one file. Grouped:

- **Scaffold (A2, A3, A4, A5, A6, A7).** Demo example dict carries the article's subevent texts (input only; the Task-1 `output` construction is untouched). Demo rendering and the user prompt gain a `Subevents:` block. The TASK line explains subevents are provided to examine the article unit by unit, with the final answer a single article-level list per actor. New guideline 7 is a **recall-oriented** completeness pass ("walk the subevents… a value counts if expressed in ANY subevent") — not a strictness or evidence gate. The user-prompt closing line and its DeepSeek JSON-object rewrite anchor are updated together.
- **Bookkeeping (A1, A8, A9).** `E3A_RUN_TS` env var; `fewshot_meta` records subevent counts; `run_config` experiment name/base/delta list.

**Explicitly unchanged from E1** (verified): OUTPUT FORMAT (article-level), the DeepSeek system-prompt object rewrite, `parse_model_json`, `process_results` (article-level `(actor, direction, l1)` dedup, still returns exactly two values), the demo-selection rule and full-content rendering, the `targeted_more_shot_balanced` calibration text, the L1→L2 mapping, and the official evaluation path. **No E2 evidence/bias-control rules were added.**

## Verification performed (all local, no API)

1. `build_e3a_pipeline.py` — all 10 deltas matched exactly once; output compiles.
2. **Dry-run preview** (`runs/dryrun_preview/`, `logs/e3a_dryrun_preview.log`): full system prompt snapshot (17,595 chars) + first dev article user prompt, generated with no API client. 21 invariants passed, including: subevent scaffold in TASK/guideline 7/demos/user prompt; **output format still E1 article-level** (no `subevent_id`, no `subevents` wrapper); E1 guidelines retained; **E2 bias/role-prior wording absent**; no numeric caps; and **no Task-2 leak in demo outputs** (no `l2_value`, no `explanation`, no `subevent_id`, no `reasoning`).
3. **`offline_check_e3a.py`** (real taxonomy/train data, stdlib): no code reads `subevents_human_values`; the few-shot demo `output` is **byte-identical to E1's** (label counts 15 + 10 — E1's Task-1 gold, not E3's 13 + 8 Task-2 counts); demos add subevent texts only (8 + 6); parser/`process_results` behave exactly as E1 and `process_results` returns two values (no E3-style union machinery). **All 14 checks passed.**

## How to run later (unchanged protocol; one call/article, ≈ E1 cost)

```bash
python3 RH_test/E3a_task1_only_subevent/scripts/build_e3a_pipeline.py    # regenerate (asserted)
set -a && . ./.env && set +a
export E3A_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E3a_task1_only_subevent/scripts/run_pipeline_e3a.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E3a_task1_only_subevent/scripts/analyze_e3a.py $E3A_RUN_TS
```

`analyze_e3a.py` produces the three-way Liu/E1/E3a comparison (`comparison_liu_e1_e3a.csv`) and per-target-18 counts, re-verifying the frozen Liu baseline at 0.5347 before comparing. **Hypothesis:** the subevent scaffold lifts recall (especially tail/macro) over E1 at little precision cost, purely from Task-1 supervision. Single-pass caveat applies (±0.004 documented run variance; ×3 replication before strong claims).
