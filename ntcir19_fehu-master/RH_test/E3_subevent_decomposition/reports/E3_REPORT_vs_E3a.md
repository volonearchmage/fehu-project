# E3 Report — Task-2 Auxiliary Subevent Union vs E3a (executed)

**Date:** 2026-07-23
**Run:** `runs/20260723_162944/` — full 177-article dev set, DeepSeek `deepseek-v4-flash`, temperature 0.1, max_tokens 8000, JSON mode, variant `targeted_more_shot_balanced`, single pass, **0 failed articles** (`logs/e3_full_run_20260723_162944.log`).
**Compared against:** frozen Liu (re-verified to 0.5347 — exact), completed E1 (`E1_fewshot_repair/runs/20260722_152456/`), completed E3a (`E3a_task1_only_subevent/runs/20260723_141123/`). No prior run was modified or overwritten.
**Note on naming:** the request called this `E3b_task2_auxiliary_subevent_union`; no experiment exists under that name. This is the prepared `E3_subevent_decomposition` — Task-2 `subevents_human_values` gold in the demos, per-subevent prediction, deterministic direction-specific union into Task-1 labels — which is the exact experiment that description denotes.

## The question

Does **Task-2 auxiliary subevent supervision** (E3) improve **Task-1** performance beyond E3a's Task-1-only subevent *scaffold*? E3 and E3a share model, temperature, variant, and the same two demo articles; they differ only in (a) demos rendered from Task-2 per-subevent gold (E3) vs Task-1 article-level gold (E3a), and (b) per-subevent output + code-side union (E3) vs direct article-level output (E3a). So the delta isolates the value of the Task-2 supervision + hard decomposition.

## Results (official evaluator, dev 177)

**Task-1b (Level-1 + direction):**

| System | micro P / R / F1 | macro P / R / F1 | DRR (rev) | pred labels | labels/actor | classes |
|---|---|---|---|---|---|---|
| Liu frozen | 0.5677 / 0.5054 / 0.5347 | 0.4424 / 0.3212 / 0.3385 | 0.0230 (51) | 2128 | 4.69 | 88 |
| E1 | 0.5405 / 0.5556 / 0.5480 | 0.4162 / 0.3919 / 0.3719 | 0.0347 (77) | 2457 | 5.50 | 95 |
| **E3a** | 0.5216 / 0.6201 / **0.5666** | 0.4474 / 0.4812 / **0.4173** | 0.0414 (92) | 2841 | 6.38 | 97 |
| **E3** | **0.6201** / 0.4883 / 0.5463 | **0.4824** / 0.3870 / 0.3912 | **0.0243 (54)** | 1882 | 4.79 | 87 |
| **Δ E3−E3a** | **+0.099** / **−0.132** / **−0.020** | +0.035 / **−0.094** / **−0.026** | **−0.017 (−38)** | −959 | −1.60 | −10 |

**Task-1a:** E3 micro-F1 0.6384 / macro 0.5068 vs E3a 0.6727 / 0.5626 (−0.034 / −0.056).
**Target-18:** E3 micro-F1 0.3260 (E3a 0.3136, **+0.012**), macro-F1 0.2824 (E3a 0.3147, −0.032), TP 37 vs 53 (−16), **FP 50 vs 145 (−95)**.
**Non-target-90 macro-F1:** E3 0.4174 vs E3a 0.4419 (−0.025).
Detail: `comparison_liu_e1_e3a_e3.csv`, `per_target_18_comparison_4way.csv`.

## Answer: No — Task-2 supervision does not beat E3a on the primary metrics.

E3 is **lower than E3a on Task-1b micro-F1 (−0.020) and macro-F1 (−0.026), and on both Task-1a aggregates.** What the Task-2 supervision actually did was **move the operating point sharply toward precision**: micro-P +0.099 but micro-R −0.132; it predicts ~⅓ fewer labels (1,882 vs 2,841, labels/actor back down to 4.79 ≈ Liu's 4.69) and covers **10 fewer classes** (87, below even Liu's 88). The per-subevent gold demos, whose per-unit label sets are sparse, taught the model to be conservative, so tail coverage — E3a's headline strength — regressed. The E3−E3a micro delta (−0.020) is ~5× the ±0.004 run-to-run variance and the macro delta is large, so "E3 does not beat E3a on F1" is robust to single-pass noise.

## But E3 contributes two genuinely useful assets

1. **Best direction quality.** DRR **0.0243** (54 reversals) — 38 fewer than E3a, essentially matching Liu's 0.0230 while keeping far higher F1 than Liu. The Task-2 gold demos, which ground each direction in a specific subevent, transfer direction discipline that no prompt instruction did (E2's direction rule was inert). This directly addresses the DRR cost that E3a/E1 incur, and points at using E3's directions to repair E3a's reversals (the P6 idea, now with a concrete source).
2. **A clean unit-support confidence signal.** Precision rises monotonically with the number of subevents backing a label (`unit_support_histogram.csv`):

   | supporting subevents | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9+ |
   |---|---|---|---|---|---|---|---|---|---|
   | precision | 0.49 | 0.66 | 0.77 | 0.84 | 0.87 | 0.88 | 0.89 | 0.90 | 1.00 |
   | (TP/FP) | 479/491 | 262/138 | 145/43 | 112/22 | 60/9 | 44/6 | 25/3 | 18/2 | 22/1 |

   Single-subevent labels are near coin-flips (0.49); anything backed by ≥2 subevents is markedly reliable. This is exactly the ranking signal the planned **E4 per-candidate verifier** needs — and it can be applied to *E3a's* higher-recall candidates too, not only E3's.

## Interpretation

E3a's soft scaffold remains the **best standalone Task-1 system**; adding Task-2 per-subevent supervision does not raise F1 — it buys precision and direction at the cost of the recall/tail coverage that made E3a win. The productive framing is therefore **not E3 vs E3a but E3 + E3a**: E3a supplies high-recall candidates, and E3's contributions — its low-DRR directions and the monotone unit-support signal — become the precision/verification and direction-repair layer (the E4 verifier + P6 direction patch), rather than a competing generator.

Caveats: single pass (same ±0.004 variance protocol; a ×3 replication would firm the deltas and bound DRR); the unit-support histogram is from one run and should be re-derived per run before being used as a hard confidence gate.

## Reproduction

```bash
python3 RH_test/E3_subevent_decomposition/scripts/build_e3_pipeline.py
set -a && . ./.env && set +a
export E3_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E3_subevent_decomposition/scripts/run_pipeline_e3.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E3_subevent_decomposition/scripts/analyze_e3_vs_e3a.py $E3_RUN_TS
```

All artifacts (predictions, cache, prompt snapshot, run config, four-way comparison CSVs, unit-support histogram, log) are under `runs/20260723_162944/`; no earlier run was overwritten; no key material is stored in any artifact.
