# E2 Report — Prompt Bias Control (executed)

**Date:** 2026-07-23
**Run:** `runs/20260723_000019/` — full 177-article dev set, DeepSeek `deepseek-v4-flash`, temperature 0.1, max_tokens 8000, JSON mode, variant `targeted_more_shot_balanced`, single pass, **0 failed articles** (`logs/e2_full_run.log`)
**Compared against:** frozen Liu baseline (`output/task1/runs/dev_deepseek_..._targeted_more_shot_balanced.../`, re-evaluated to its documented 0.5347 before comparison) and the completed E1 run (`RH_test/E1_fewshot_repair/runs/20260722_152456/`). No Liu or E1 file was modified; the E2 prompt was not changed during execution (no error required it).

## What E2 is

E2 inherits E1's few-shot repairs unchanged (verified: same demos `0-4349-1-t` / `0-4352-3-1`) and adds only bias-control **instructions**: it replaced the inherited role-prior "Common patterns" guideline (B1) and added a 5-rule `EVIDENCE AND BIAS CONTROL` block (B2) — per-actor evidence test, exact-definition discrimination of confusable value pairs, no semantic expansion to adjacent values, direction from actual behavior not actor status, and a victim rule. Full change log: `reports/E2_CHANGES.md`.

## Results (official evaluator, dev 177)

Task-1b (from `runs/20260723_000019/comparison_liu_e1_e2.csv`):

| System | micro P / R / F1 | macro P / R / F1 | DRR (rev) | TP / FP / FN | labels/actor | classes |
|---|---|---|---|---|---|---|
| Liu frozen | 0.5677 / 0.5054 / 0.5347 | 0.4424 / 0.3212 / 0.3385 | 0.0230 (51) | 1208 / 920 / 1182 | 4.69 | 88 |
| **E1** | 0.5405 / 0.5556 / **0.5480** | 0.4162 / 0.3919 / **0.3719** | 0.0347 (77) | 1328 / 1129 / 1062 | 5.50 | 95 |
| **E2** | 0.5493 / 0.5126 / 0.5303 | 0.3890 / 0.3304 / 0.3270 | 0.0351 (78) | 1225 / 1005 / 1165 | 5.41 | 92 |
| **Δ E2−E1** | +0.009 / **−0.043** / **−0.018** | −0.027 / **−0.062** / **−0.045** | +0.0004 (+1) | −103 / −124 / +103 | −0.08 | −3 |

Task-1a: E2 micro-F1 0.6365 (E1 0.6574, −0.021), macro-F1 0.4782 (E1 0.5018, −0.024).
Target-18: E2 micro-F1 0.2317 (E1 0.2460), TP 30 vs 38, FP 89 vs 131. Non-target-90 macro-F1: E2 0.3556 vs E1 0.4056.
Per-target detail: `runs/20260723_000019/per_target_18_comparison.csv`.

## Did E2 improve on E1? No.

The bias-control instructions did move the prediction distribution in the intended *direction* — E2 predicts fewer labels than E1 (2,230 vs 2,457; labels/actor 5.41 vs 5.50), cutting false positives overall (−124) and on the 18 targets (−42), and lifting micro-precision +0.009. But the trade was unfavorable on every F1 aggregate:

- **Recall fell more than precision rose.** Micro-recall −0.043 (FN +103) against micro-P +0.009 → **micro-F1 −0.018**. The "evidence test" and "no semantic expansion" rules suppressed correct labels alongside spurious ones.
- **Macro was hit hardest: macro-F1 −0.045** (macro-recall −0.062), and 3 fewer distinct classes predicted — the instructions disproportionately removed less-frequent, weakly-evidenced-but-correct tail labels, exactly the labels E1 had recovered. Non-target-90 macro-F1 −0.05 confirms the loss is broad, not target-specific.
- **The direction rule did not work.** DRR is essentially unchanged (0.0347 → 0.0351; reversals 77 → 78). The explicit "judge direction from behavior, not role" instruction produced no measurable reversal reduction.
- **Net vs. the original baseline, E2 is also slightly below Liu** on 1b micro (0.5303 vs 0.5347) and macro (0.3270 vs 0.3385) — the precision-leaning instructions gave back E1's gains without a compensating benefit.

Interpretation (single-pass caveat applies, as for E1): the model was already reasonably calibrated on precision after E1; adding stricter evidence gates mostly removed true positives, and the anti-role-prior/direction wording did not translate into fewer reversals. The direction of the effect is consistent across micro, macro, 1a, 1b, target, and non-target, and the macro drop (−0.045) is large relative to the ±0.004 documented run-to-run variance, so this is unlikely to be noise — though a ×3 replication would firm it up before any final claim.

## Verdict

**E2 does not improve on E1 and should not replace it.** E1 remains the best prompt configuration (1b micro 0.5480 / macro 0.3719). The bias-control hypothesis, in this instruction-only form, is **rejected**: reducing false positives via prompt gates costs more recall than it saves in precision, and the direction instructions were inert on DRR. If precision/DRR recovery is still wanted, the evidence from E1+E2 points away from stricter *instructions* and toward a *separate verification stage* that can remove false positives without suppressing the generator's recall (the per-candidate QA-verifier idea) — but that is out of scope here and not started.

## Reproduction

```bash
python3 RH_test/E2_prompt_bias_control/scripts/build_e2_pipeline.py     # regenerate pipeline (5 asserted deltas)
set -a && . ./.env && set +a
export E2_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E2_prompt_bias_control/scripts/run_pipeline_e2.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E2_prompt_bias_control/scripts/analyze_e2.py $E2_RUN_TS
```

All artifacts (predictions, cache, prompt snapshot, run config, comparison CSVs, logs) are under the timestamped run folder; no earlier run was overwritten; no key material is stored in any artifact.
