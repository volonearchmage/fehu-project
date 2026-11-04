# E4 Dev Evaluation Report — Actor Evidence Decomposition and Verification

**Run:** `RH_test/E4_actor_evidence_decomposition_and_verification/runs/dev_20260723_full/`
**Date:** 2026-07-24
**Scope:** full 177-article dev set, all three variants (E4a, E4b, E4c),
single API pass (temperature 0.1, DeepSeek Flash). No test-set inference.

## TL;DR

**No E4 variant improved on E1 or E3a, and none reached Liu's reported
0.5657.** The actor-evidence scaffold (E4a), the dual-view union (E4b), and
the verifier+aggregation (E4c) each traded precision for recall or added
machinery that removed as much signal as noise. On Task-1b Micro-F1 the E4
variants land at 0.5324 / 0.4831 / 0.4659 — below the frozen Liu baseline
(0.5347), E1 (0.5480), and E3a (0.5666). The verifier does behave as
designed (it improves precision and direction quality *relative to E4b*),
but cannot recover the precision the dual-view generation gives away.
**E3a remains the best method overall.**

## Results (all recomputed on the full 177-article dev set, one evaluator)

Columns: m* = micro, M* = macro, P/R/F1. DRR = direction reverse rate
(reversal count). lbl/actor = predicted Task-1b labels per gold actor.
cov = distinct predicted directed classes / 108.

| Method | 1a mF1 | 1a MF1 | 1b mP | 1b mR | **1b mF1** | 1b MP | 1b MR | 1b MF1 | DRR (rev) | lbl/actor | cov |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Liu single-prompt (frozen) | 0.6447 | 0.4777 | 0.5677 | 0.5054 | **0.5347** | 0.4424 | 0.3212 | 0.3385 | 0.0230 (51) | 4.67 | 88 |
| Liu label-aware ensemble | — | — | — | — | **0.5657 ⚠** | — | — | — | — | — | — |
| E1 few-shot repair | 0.6574 | 0.5018 | 0.5405 | 0.5556 | **0.5480** | 0.4162 | 0.3919 | 0.3719 | 0.0347 (77) | 5.39 | 95 |
| E2 bias control | 0.6365 | 0.4782 | 0.5493 | 0.5126 | **0.5303** | 0.3890 | 0.3304 | 0.3270 | 0.0351 (78) | 4.89 | 92 |
| E3 subevent union | 0.6384 | 0.5068 | 0.6201 | 0.4883 | **0.5463** | 0.4824 | 0.3870 | 0.3912 | 0.0243 (54) | 4.13 | 87 |
| **E3a task1-only subevent** | 0.6727 | 0.5626 | 0.5216 | 0.6201 | **0.5666** | 0.4474 | 0.4812 | 0.4173 | 0.0414 (92) | 6.23 | 97 |
| E4a evidence scaffold | 0.6567 | 0.5159 | 0.4951 | 0.5757 | **0.5324** | 0.3682 | 0.4047 | 0.3549 | 0.0500 (111) | 6.09 | 96 |
| E4b dual-view union | 0.6221 | 0.5176 | 0.3915 | 0.6305 | **0.4831** | 0.3238 | 0.5085 | 0.3563 | 0.0432 (96) | 8.44 | 102 |
| E4c verifier + aggregation | 0.5893 | 0.4937 | 0.4198 | 0.5234 | **0.4659** | 0.3364 | 0.4060 | 0.3241 | 0.0297 (66) | 6.54 | 99 |

Full numeric detail (incl. Task-1a P/R, labels/actor, undirected-L1
coverage): `runs/dev_20260723_full/e4_dev_comparison.{json,md}`.

⚠ **Liu label-aware ensemble (0.5657)** is a *reported* number only. Its
artifacts are absent from this repository and prior work marks it
BLOCKED/unreproducible (`docs/FEHU_PROJECT_PROGRESS_SUMMARY.md` §"Liu's
reported 0.5387 and 0.5657: not reproducible locally"). It is shown as the
stated goal-line, not a locally-recomputed result. The locally auditable Liu
baseline is the frozen single-prompt run (0.5347), reproduced here exactly.

Baseline reproduction check: Liu 0.5347, E1 0.5480, E2 0.5303, E3 0.5463,
E3a 0.5666 all reproduce the numbers in their original reports to 4 dp,
confirming the evaluator and file wiring.

## Answers to the five questions

### 1. Does E4a improve E1? **No.**
E4a (0.5324 1b micro / 0.3549 macro) is *below* E1 (0.5480 / 0.3719) on both
F1 aggregates. The evidence scaffold shifted the operating point toward
recall — 1b micro recall 0.5757 vs E1's 0.5556, and 6.09 vs 5.39 labels per
actor — but paid for it in precision (0.4951 vs 0.5405) and, most sharply,
in direction quality: DRR 0.0500 (111 reversals) vs E1's 0.0347 (77), the
worst DRR of any method measured. Task-1a is a wash (0.6567 vs 0.6574). Net:
the self-generated evidence units push the model to assign more values,
including weakly-supported ones and more wrong-direction ones, without a
compensating F1 gain.

### 2. Does E4b improve recall or macro-F1? **Recall yes, macro-F1 no.**
E4b has the highest recall of any E4 variant (1b micro recall 0.6305; Task-1a
recall 0.7668, the highest of *all* methods) — the dual-view union is doing
what unions do. But macro-F1 does **not** improve: 1b macro 0.3563 is below
E1 (0.3719) and far below E3a (0.4173). The union over-generates (8.44
labels/actor, the highest measured), collapsing precision to 0.3915 and
dragging 1b micro-F1 down to 0.4831. Broader coverage (102/108 directed
classes) does not translate into per-class quality.

### 3. Does E4c improve precision and direction quality? **Yes, relative to
E4b — but not enough to win.**
The verifier does its designed job: versus E4b it raises 1b micro precision
(0.4198 vs 0.3915), cuts labels/actor (8.44 → 6.54), and improves direction
quality to DRR 0.0297 (66) — the best DRR among all three E4 variants and
better than E1/E3a. So relevance-pruning + direction-repair work
directionally. However: (a) the verifier can only *remove*, so it cannot
repair the dual-view's fundamental over-generation, and it also removes true
positives (recall 0.6305 → 0.5234); (b) E4c precision (0.4198) is still below
even E4a (0.4951), because it starts from a far noisier candidate pool. Net
1b micro-F1 falls to 0.4659, the lowest of the three.

### 4. Does any E4 variant exceed Liu's 0.5657? **No.**
Best E4 is E4a at 0.5324 (1b micro) — below both Liu 0.5657 (reported) and
Liu 0.5347 (local), and below E1 and E3a. The only method in this study that
exceeds 0.5657 is **E3a (0.5666)**, marginally (+0.0009), and E3a uses the
official subevent segmentation that E4 was explicitly built to avoid.

### 5. Which variant is best overall? **E3a (not an E4 variant).**
Ranking by 1b micro-F1: E3a 0.5666 > E1 0.5480 > E3 0.5463 > Liu 0.5347 >
**E4a 0.5324** > E2 0.5303 > E4b 0.4831 > E4c 0.4659. By 1b macro-F1: E3a
0.4173 > E3 0.3912 > E1 0.3719 > E4b 0.3563 > E4a 0.3549 > Liu 0.3385 > E2
0.3270 > E4c 0.3241. **E3a is best on both.** Among the E4 variants alone,
**E4a is the best E4 method** (highest E4 micro-F1, competitive macro) —
though it has the worst DRR; E4c is the best-calibrated E4 variant (best
precision/recall balance and DRR) but the lowest F1.

## Why E4 underperformed (analysis)

1. **The evidence scaffold trades precision and direction for recall.** E4a
   vs E1 isolates this: same frozen E1 prediction logic, only the evidence
   units added. Recall up, precision down, DRR nearly doubled. Presenting
   pre-organized per-actor evidence appears to *prime* the model to attach a
   value to every unit, and the unit framing (actions/consequences/etc.)
   does not carry reliable direction cues.
2. **The taxonomy-family view is the precision killer.** Scanning each of
   four families in isolation with "scan this family's values one by one"
   instructions generates many locally-plausible candidates that the global
   view never proposed; the union balloons to 8.44 labels/actor and
   precision to 0.39. Family-local context lacks the cross-family
   competition that suppresses weak labels.
3. **The verifier is a remover, not a repairer.** It improves on E4b but is
   structurally unable to recover the precision lost upstream, and the
   lenient "both-views survive on KEEP *or* UNCERTAIN" rule keeps too much.
   It also removes real positives, so F1 net-declines.
4. **E3a's advantage was the official subevents, not "decomposition" per
   se.** E4a was designed to reproduce E3a's structural benefit using
   self-generated evidence units instead of official subevents. It did not —
   E4a is below E1, while E3a is the best method. This is the report's main
   scientific finding: E3a's gain is attributable to the *human-authored
   subevent segmentation*, which the evidence-extraction stage does not
   substitute for; the extra self-generated structure adds more noise than
   signal.

## Operational metrics

- **Articles:** 177/177 processed for every variant; **0 unrecovered
  failures, 0 schema violations** in the final state (all 7 stage caches
  hold 177 entries).
- **API calls (all under `dev_20260723_full`):** **1,343 DeepSeek Flash
  calls total.** Breakdown by invocation: 58 (8-article validation) + 1,179
  (full e4c) + 31 + 41 + 9 (transient-failure resume passes) + 25
  (token-escalation resume) + 0 (e4a) + 0 (e4b). E4a and E4b were produced
  entirely from the shared cache (0 new calls). Minimum for 177×7 stages =
  1,239; the extra 104 calls are retries/escalations.
- **Failures & retries:** 105 stage-level schema/parse retry events across
  the run (empty or truncated JSON). 8 articles failed transiently in the
  first full pass; 5 recovered on plain resume; the final 3 (large articles,
  9k–33k chars) were deterministic 8000-token truncations and recovered via
  max-token escalation (see "Execution fixes"). Final unrecovered: **0**.
- **Estimated token usage:** ~4.2M input + ~1.5M output ≈ **5.6M tokens**
  (derived from measured prompt sizes: evidence sys≈460 tok / user 1–3k;
  global sys≈3.8k / user 1–3k; family sys≈675 / user 1.5–3k ×4; verify
  sys≈600 / user up to 3k; outputs 0.8–11k). Retries add ~8%.
- **Estimated cost:** at an assumed blended DeepSeek-Flash rate of ~$0.30
  per 1M tokens, ≈ **$1.8** for the full three-variant dev run. The exact
  `deepseek-v4-flash` rate is not recorded in-repo; confirm against the
  DeepSeek account for a precise figure. Order of magnitude: a few dollars.
- **Wall time:** ~90 min for the full e4c pass at 10 workers; E4a/E4b
  near-instant (cache reads).

## Execution fixes applied (method unchanged)

Per the instruction to fix genuine execution bugs but not change the method
to improve results, the following were changed. **None** alters a prompt,
mapping, taxonomy family, sibling set, or aggregation rule; the offline
suite (now 60 tests) and `freeze_check.py` (E1/E2/E3/E3a/Liu byte-identical)
both pass.

1. **Retry backoff on schema/parse errors** (`e4_common.py`): the API-error
   path already slept; the schema/parse path retried transient empty/
   truncated responses instantly. Added the same backoff.
2. **Non-fatal per-article failures** (`run_e4.py`): a stage exhausting its
   retries no longer aborts the whole run. The article is recorded to
   `failures.jsonl` + `run_summary`, given empty predictions, and the run
   continues; it aborts only if failures exceed `--max_article_failures`
   (default 15). Explicit surfacing, not a silent skip.
3. **Article-level concurrency** (`run_e4.py --workers`, default 1): a
   thread pool over independent articles with lock-protected caches/logs. A
   new test proves concurrent output is byte-identical to sequential; the
   default (1) is the originally-tested path.
4. **max-token escalation on truncation** (`e4_common.py`): root-caused the
   3 stubborn failures to `finish_reason=length` at the inherited 8000-token
   ceiling (a large evidence extraction needs ~11k output tokens). On a
   parse/empty failure the token budget doubles (cap 32000) and the request
   timeout scales with it. The base budget still defines cache identity, so
   the 174 already-cached articles were untouched; only the truncating
   articles escalated. This lets a valid response finish — it does not change
   what is asked.

These were validated by re-probing the failing articles directly (e.g.
`32-2285-2-1` returned empty 4/4 at 8000 tokens but parsed cleanly with all
4 actors at 16000), confirming truncation, not model incapacity.

## Recommendation

The E4 hypothesis — that self-generated actor-evidence decomposition +
dual-view generation + verification would match E3a's structural benefit
without official subevents — is **not supported** by the dev evidence. Do
not promote any E4 variant over E1/E3a. If E4 is pursued further, the
evidence points to specific levers (NOT applied here, since that would be a
new experiment): drop or tighten the family view (the precision sink); make
the verifier able to *reweight/replace*, not only remove; and tighten the
aggregation ("both-views" should perhaps require KEEP, not KEEP-or-UNCERTAIN).
The single most useful next comparison is a ×3 replication of E1 vs E3a vs
E4a to confirm the E3a>E1>E4a ordering is stable and not single-pass noise
(the E3a−E1 micro gap is 0.0186, ~4–5× the documented ±0.004 run variance;
the E4a−E1 gap is −0.0156).

## Compliance

- Dev experiments only; **no test-set inference was run.**
- No model trained or fine-tuned; prompt-only throughout.
- No prompt, taxonomy family, sibling map, or aggregation rule was modified
  based on dev performance. The only code changes are the four execution
  fixes above.
- E1, E2, E3, E3a and the Liu pipeline remain byte-identical
  (`freeze_check.py` passes).
