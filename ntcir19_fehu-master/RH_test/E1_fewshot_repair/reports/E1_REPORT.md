# E1 Report — Few-Shot Repair of the Liu Prompt

**Date:** 2026-07-22
**Experiment dir:** `RH_test/E1_fewshot_repair/` (all code, prompts, cache, predictions, logs, and analyses inside; nothing in `liu_method/`, `output/`, or `logs/` touched)
**Run:** `runs/20260722_152456/` — full 177-article dev set, DeepSeek `deepseek-v4-flash`, temperature 0.1, max_tokens 8000, JSON mode, variant `targeted_more_shot_balanced`, single pass, **0 failed articles** (`logs/e1_full_run.log`)
**Baseline:** the frozen Liu winner `output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000/`, re-evaluated by the analysis script and required to match its documented 0.5347 before any comparison (it did, exactly).

---

## 1. What was copied, changed, and kept

The E1 pipeline (`scripts/run_pipeline_e1.py`) is generated from the frozen `liu_method/run_pipeline.py` by `scripts/build_e1_pipeline.py`, which applies **12 string replacements, each asserted to match exactly once** — the complete Liu→E1 diff is auditable from that one file. Deltas:

- **D1 — few-shot selection (the experiment's core).** Old rule: first two train articles in file order with 2–3 actors and 4–8 *total* labels (guids `0-4315-1-1`, `0-4333-2-1`) — a rule biased toward small label sets. New deterministic rule: 2–3 actors, *every* listed actor labeled, **both directions present**, ≥1 actor with ≥5 labels, 8–16 total labels, full content ≤2,600 chars; candidates sorted by guid, first two taken → **`0-4349-1-t`** ("Death toll rises in Taiwan bridge collapse", 2 actors, **15 labels**, one actor with 11) and **`0-4352-3-1`** ("Limo crash leaves 20 dead in New York state", 3 actors, **10 labels**). Demo outputs carry the **complete deduplicated gold label set** in the exact compact 3-field output format (`actor_id`, `l1_value_id`, `direction`).
- **D2 — demo rendering.** Removed the `[:4]` output cap and the `[:500]…` article truncation; full demo articles shown (selection guarantees they fit).
- **D3 — numeric caps removed** (mandate item 4): "identify 3-7 relevant values" → "identify every value that has clear actor-specific evidence… do not pad"; "output at most 6 values" → "output every value supported by actor-specific evidence"; "top 6 most relevant values" → "the actor-specific clue is concrete".
- **D4/D5 — isolation only:** outputs/cache/prompt snapshots under `runs/<timestamp>/`; base-dir discovery from the new location. No behavioral effect.

**Unchanged:** model, temperature, max tokens, JSON mode, retry logic, the parser (including its known direction-coercion behavior), dedup/format conversion, the entire `targeted_more_shot_balanced` calibration text except the two capped lines, and the official evaluator. The final system prompt is snapshotted at `runs/20260722_152456/system_prompt_snapshot.txt` (15.3 KB; verified free of "at most 6", "3-7", "top 6", and "(truncated)").

## 2. Results — baseline vs. E1 (official evaluator, dev 177)

From `runs/20260722_152456/comparison_vs_baseline.csv`:

| Metric | Liu frozen | **E1** | Δ |
|---|---|---|---|
| **1b micro P / R / F1** | 0.5677 / 0.5054 / 0.5347 | 0.5405 / 0.5556 / **0.5480** | −0.027 / **+0.050** / **+0.013** |
| **1b macro P / R / F1** | 0.4424 / 0.3212 / 0.3385 | 0.4162 / 0.3919 / **0.3719** | −0.026 / **+0.071** / **+0.033** |
| **1a micro P / R / F1** | 0.6646 / 0.6260 / 0.6447 | 0.6554 / 0.6593 / **0.6574** | −0.009 / +0.033 / **+0.013** |
| **1a macro P / R / F1** | 0.5628 / 0.4426 / 0.4777 | 0.5473 / 0.4916 / **0.5018** | −0.016 / +0.049 / **+0.024** |
| DRR (reversals / 2222) | **0.0230** (51) | 0.0347 (77) | +0.0117 (+26) |
| TP / FP / FN (1b) | 1208 / 920 / 1182 | 1328 / 1129 / 1062 | **+120** / +209 / **−120** |
| Predicted 1b labels | 2,128 | 2,457 | +329 |
| **Labels per actor** | 4.69 | **5.50** | **+0.81** |
| Distinct 1b classes | 88 | 95 | +7 |
| Target-18: TP / FP / micro-F1 / macro-F1 | 28 / 64 / 0.2414 / 0.2125 | **38** / 131 / 0.2460 / **0.2314** | +10 / +67 / +0.005 / +0.019 |
| Non-target-90 micro-F1 / macro-F1 | 0.5506 / 0.3688 | **0.5685** / **0.4056** | +0.018 / +0.037 |

Per-target detail: `runs/20260722_152456/per_target_18_comparison.csv`.

## 3. Were the caps actual bottlenecks?

**Yes — the under-prediction hypothesis is confirmed by the exact predicted signature.** Labels per actor rose 4.69 → 5.50 (recall +0.050 micro / +0.071 macro-recall; 120 previously-missed gold labels recovered; 7 more distinct classes predicted), while precision fell only 0.027. Every F1 aggregate improved — 1a and 1b, micro and macro, target-18 and non-target-90. The macro gain (+0.033) is the larger effect, meaning the freed labels went disproportionately to less-frequent classes, exactly where the 4-label demos had been suppressing output. The precision cost is real but pays for itself at every aggregation level, so the answer to "recall up without unacceptable precision drop?" is **yes**.

Two costs to keep visible: (i) **DRR worsened** 0.0230 → 0.0347 (+26 reversals) — more labels means more direction exposure; still far below any non-LLM system, but E1 gives back part of Liu's direction edge; (ii) target-18 FPs doubled (64 → 131) — target recall rose (0.20 → 0.27, TP +10) but target precision fell; the target group's net F1 gain is small (+0.005 micro). E1 helps the tail broadly (non-target macro +0.037) more than it helps the 18 hardest targets specifically.

**Context (single-pass caveat applies):** E1's 0.5480 / 0.3719 numerically exceeds not only Liu but also the hybrid H3's micro (0.5474) and H2's macro (0.3603) — as a *prompt-only single system*. All these are single API passes; the E1−Liu micro delta (+0.0133) is ~3× the documented cross-machine variance for this exact configuration (±0.004), and the macro delta (+0.033) is large, but a ×3 replication is still the correct next step before any strong claim (same protocol point Phase 2/3 established for training runs).

## 4. Verdict and recommendation

**Retain E1.** The few-shot 4-label cap and demo truncation were genuine, measurable bottlenecks of the strongest prompt system; repairing them yields the project's best single-system dev result at trivial cost (~177 Flash calls). Recommended follow-ups, in order (not executed here): (1) replicate E1 ×2 more passes for a mean ± spread; (2) since E1's added FPs are exactly what the per-candidate QA verifier (analysis idea P3) is designed to absorb — and E1's higher recall makes it a better candidate source — consider E1 as the new base for the hybrid; (3) if DRR matters for ranking, the targeted direction-QA add-on (P6) is the natural patch for the +26 reversals. No revision of E1 itself appears necessary; nothing in this run suggests rejection.

## 5. Reproduction

```bash
python3 RH_test/E1_fewshot_repair/scripts/build_e1_pipeline.py           # regenerate pipeline (asserted deltas)
set -a && . ./.env && set +a                                             # DEEPSEEK_API_KEY at call time only
export E1_RUN_TS=$(date +%Y%m%d_%H%M%S)
python3 RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py \
    --mode dev --provider deepseek --prompt_variant targeted_more_shot_balanced
python3 RH_test/E1_fewshot_repair/scripts/analyze_e1.py $E1_RUN_TS
```

Artifacts per run: `pred_task1a/b.json`, response cache, `system_prompt_snapshot.txt`, `fewshot_meta.json`, `run_config.json`, comparison CSVs. Timestamped run folders are never overwritten. No key material is stored in any artifact.
