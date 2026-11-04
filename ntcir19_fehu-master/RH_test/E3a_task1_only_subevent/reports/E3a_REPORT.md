# E3a Report — Task-1-only Subevent Scaffold (executed)

**Date:** 2026-07-23
**Run:** `runs/20260723_141123/` — full 177-article dev set, DeepSeek `deepseek-v4-flash`, temperature 0.1, max_tokens 8000, JSON mode, variant `targeted_more_shot_balanced`, single pass, **0 failed articles** (`logs/e3a_full_run_20260723_141123.log`).
**Compared against:** frozen Liu baseline (re-verified to 0.5347 before comparison — exact) and the completed E1 run (`RH_test/E1_fewshot_repair/runs/20260722_152456/`). No Liu, E1, E2, or Task-2-E3 file was modified.

## What E3a is (recap)

E1 kept intact — same repaired few-shot demos with **Task-1 article-level gold**, same output format, same settings — plus one change: each article's **subevent texts** (input segmentation from `event_base.json`, **no Task-2 gold**) are shown as a reasoning scaffold with an instruction to walk the article subevent by subevent, then emit **one consolidated article-level prediction per actor** in a single API call. Full change log: `reports/E3a_CHANGES.md`.

## Results (official evaluator, dev 177)

Task-1b (`runs/20260723_141123/comparison_liu_e1_e3a.csv`):

| System | micro P / R / F1 | macro P / R / F1 | DRR (rev) | TP / FP / FN | labels/actor | classes |
|---|---|---|---|---|---|---|
| Liu frozen | 0.5677 / 0.5054 / 0.5347 | 0.4424 / 0.3212 / 0.3385 | 0.0230 (51) | 1208 / 920 / 1182 | 4.69 | 88 |
| E1 | 0.5405 / 0.5556 / 0.5480 | 0.4162 / 0.3919 / 0.3719 | 0.0347 (77) | 1328 / 1129 / 1062 | 5.50 | 95 |
| **E3a** | 0.5216 / 0.6201 / **0.5666** | 0.4474 / 0.4812 / **0.4173** | 0.0414 (92) | 1482 / 1359 / 908 | 6.38 | 97 |
| **Δ E3a−E1** | −0.019 / **+0.065** / **+0.019** | **+0.031** / **+0.089** / **+0.045** | +0.0067 (+15) | +154 / +230 / −154 | +0.89 | +2 |

Task-1a: micro-F1 **0.6727** (E1 0.6574, +0.015), macro-F1 **0.5626** (E1 0.5018, **+0.061**).
Target-18 (hardest rare labels): micro-F1 **0.3136** (E1 0.2460, **+0.068**), macro-F1 **0.3147** (E1 0.2314, **+0.083**), TP 53 vs 38 (**+15**), FP 145 vs 131 (+14).
Non-target-90 macro-F1: **0.4419** (E1 0.4056, +0.036).
Per-target detail: `runs/20260723_141123/per_target_18_comparison.csv`.

## Did E3a improve on E1? Yes — on every F1 aggregate.

- **Recall rose broadly and macro-precision rose with it.** 1b micro-recall +0.065 and macro-recall +0.089, while **macro-precision also went up** (+0.031, 0.4162→0.4474). Micro-precision fell only −0.019. Net: **1b micro-F1 +0.019 (0.5666) and macro-F1 +0.045 (0.4173)** — E3a's is the best single-system dev result on both, ahead of E1 (previous best) and the hybrids. 154 more gold labels recovered (FN 1062→908), 2 more distinct classes.
- **The gain is strongest exactly where it was aimed — the tail.** macro-F1 (+0.045) outpaces micro-F1 (+0.019), and the target-18 group, which E1 had barely helped, jumps +0.068 micro / +0.083 macro with **+15 TP at only +14 FP** — a far better recall/precision trade on the hard labels than E1 achieved (E1 had doubled target FPs for +10 TP). This matches the design hypothesis: tail values live in individual subevents and the per-unit scan surfaces them.
- **The one cost is direction (DRR).** 0.0347 → 0.0414 (+15 reversals), continuing the same "more labels → more direction exposure" trend seen from Liu→E1. Still far below any non-LLM system. The targeted direction-QA add-on (analysis idea P6) is the natural patch.

## Interpretation and caveats

The subevent scaffold delivered its intended effect — a broad recall lift, concentrated in the long tail, at modest precision cost — using **Task-1 supervision only** (no `subevents_human_values`). Notably it did **not** exhibit E1's target-FP blowup, suggesting the per-unit reading makes the added labels better-grounded rather than merely more numerous.

Caveats (same protocol as E1/E2): **single pass.** The +0.019 micro / +0.045 macro deltas over E1 are ~4.6× / large relative to the ±0.004 documented cross-machine variance for this exact config, so they are very unlikely to be noise — but a **×3 replication** is the standing requirement before any final claim, and would also bound the DRR change. The direction cost should be quantified against whether P6 can recover it.

## Comparison to the Task-2-based E3 (not yet run)

E3a is the "soft" decomposition (scaffold only, Task-1 gold, article-level output). The parallel E3 (`RH_test/E3_subevent_decomposition/`, prepared, not run) is the "hard" version (Task-2 per-subevent gold demos, per-subevent output, code-side union). Running E3 next would isolate how much, if any, additional gain the hard decomposition buys over E3a's already-strong scaffold result — and whether it is worth the Task-2 dependence.

## Reproduction

```bash
python3 RH_test/E3a_task1_only_subevent/scripts/build_e3a_pipeline.py
set -a && . ./.env && set +a
export E3A_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E3a_task1_only_subevent/scripts/run_pipeline_e3a.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E3a_task1_only_subevent/scripts/analyze_e3a.py $E3A_RUN_TS
```

All artifacts (predictions, cache, prompt snapshot, run config, comparison CSVs, log) are under `runs/20260723_141123/`; no earlier run was overwritten; no key material is stored in any artifact.
