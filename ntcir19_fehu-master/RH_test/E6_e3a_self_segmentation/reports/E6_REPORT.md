# E6 — E3a-self: the subevent scaffold with model-generated segmentation

**Status: EXECUTED on full dev (run `20260724_152658`). Pre-registered gate experiment from
`docs/FEHU_TEST_TRANSFER_AND_LIU_MARGIN_METHOD_20260724.md` §2.**
Date: 2026-07-24. All artifacts under `RH_test/E6_e3a_self_segmentation/`.

## 1. Question and design

Task-1 **test** articles carry no `subevents` field (and the Task-2 test file's 175 articles have
zero guid overlap), while E3a's best-ever dev result (1b micro 0.5666) consumed the **official dev
segmentation** as input. E6 asks: how much of E3a's gain survives when the model segments the
article **itself** — i.e., how much is *procedural* (per-unit reading, transfers to test) vs
*annotation* (official segmentation quality, does not transfer)?

One-variable design, enforced by 26 offline checks (`scripts/offline_check_e6.py`, all green):

- **Stage 0** (`run_segmentation_e6.py`): taxonomy-blind segmentation — the prompt contains no
  value names, no direction vocabulary, no actor list (checked); DeepSeek JSON mode,
  `deepseek-v4-flash`, temp 0.1; ids normalized to official style; per-article cache; fail-loud
  validation (2–30 units, non-empty text).
- **Stage 1** (`run_pipeline_e6.py`): byte-copy of the E3a pipeline; the **only** functional
  delta is a required `--segments` file whose units **replace** the eval articles' subevents
  before any prompt is built (missing guid → abort; no fallback to dataset subevents). The
  generated system prompt is **byte-identical to the frozen E3a run's snapshot** (demos are
  training articles, which legitimately keep official subevents at all times). Same model,
  variant (`targeted_more_shot_balanced`), temperature (0.1), max tokens (8000) as E3a run
  `20260723_141123`.

**Segmentation achieved:** 177/177 articles; units min 2 / median 12 / max 24 / mean 12.19
(official dev: min 2 / median 9 / max 20). The self-segmenter runs finer than the official
annotation — it was instructed "6–12" and sat at the top of that range. 3 transient per-article
failures (1 truncated JSON, 1 over-length 32-unit output, 1 empty content) were caught by the
validator and recovered on in-script retry.

**Quality gate:** after the run, one article (`2-34752-6-1`) had an empty cached result with no
logged API failure (E3a produced 11 items for the same article). Its cache entry was purged and
re-fetched once — the refetch returned 7 items and was accepted as-is. Metrics below are the
final (post-repair) run; pre-repair headline was 1b micro 0.5404/macro 0.4072.

## 2. Results (dev, all systems under the same scorer — E5 `evaluate_run.py`)

| metric | E1 | **E3a (official segs)** | **E6 (self segs)** | Liu best (reported) |
|---|---|---|---|---|
| 1b micro-F1 | 0.5480 | **0.5666** | 0.5412 | 0.5657 |
| 1b micro P / R | 0.5405 / 0.5556 | 0.5216 / 0.6201 | 0.4855 / 0.6113 | 0.6149 / 0.5067 |
| 1b macro-F1 | 0.3719 | 0.4173 | **0.4079** | 0.3870 |
| 1b macro P / R | 0.4162 / 0.3919 | 0.4474 / 0.4812 | 0.4230 / 0.4840 | — |
| 1a micro-F1 | 0.6574 | 0.6727 | 0.6535 | 0.6555 |
| DRR | 0.0347 | 0.0414 | 0.0504 | 0.0279 |
| target-18 micro | 0.2460 | 0.3136 | 0.2963 | — |
| non-target-90 micro | 0.5685 | 0.5841 | 0.5582 | — |
| TP / FP / FN (108) | 1328 / 1129 / 1062 | 1482 / 1359 / 908 | 1461 / 1548 / 929 | — |

Deltas: E6 vs E1 → micro −0.0068, macro **+0.0360**, t18 **+0.0503**, DRR +0.0158.
E6 vs E3a → micro −0.0254, macro −0.0094, t18 −0.0173, precision −0.0361, recall −0.0088.

## 3. Verdict against the pre-registered decision tree

**Micro: COLLAPSES.** 0.5412 ≤ 0.548 — E6 lands below E1 on the headline metric. Under the
frozen tree, **the micro-F1 case for the scaffold does not transfer to test**, and E1 (or a
repaired E6, see §4) must be the test-time generator of record for micro.

**But the tail gain largely survives — the collapse is not uniform.** E6 retains **79%** of
E3a's macro gain over E1 (+0.0360 of +0.0454) and **74%** of its target-18 gain (+0.0503 of
+0.0677), with macro-recall essentially equal to E3a's (0.4840 vs 0.4812). The per-unit reading
recovers tail values just as well with self-generated units.

**The transfer loss is a precision effect with a clear mechanism.** Recall barely moved
(0.6113 vs 0.6201) while micro-precision fell 0.522 → 0.486. The self-segmenter runs finer
than the official annotation (median 12 vs 9 units, +33%), and more units ⇒ more label
emissions: 3,009 predicted cells vs E3a's 2,841 (+168, nearly all FPs: +189 FP, −21 TP). The
damage concentrates on frequent classes (nt90 0.5582, below even E1's 0.5685) — exactly where
FP inflation hurts micro most — while the tail (t18, macro) keeps its gain. DRR also rose
(0.0414 → 0.0504), continuing the known "more labels → more direction exposure" trend.

**Honest summary:** the scaffold's *recall/tail mechanism is procedural and transfers*; the
*precision discipline came partly from the official segmentation's coarser, cleaner units and
does not transfer as-is*.

## 4. Implications for the beat-Liu plan (method doc §3)

1. **No current single system legally beats Liu's reported 0.5657 on test.** E3a (0.5666) is
   not test-legal; E6 (0.5412) and E1 (0.5480) are legal but short. The margin must come from
   the **E7 fusion stage** — as anticipated.
2. **E6 is a good E7 *generator* despite the micro number.** E7's veto arm repairs precision;
   what it cannot manufacture is recall/tail coverage — which is precisely what E6 retains
   (R 0.6113, macro 0.4079, t18 +0.05 over E1). A calibrated plug-in veto (remove cell iff
   calibrated P(gold) < F/2 ≈ 0.27) now has ~1,548 FPs of actionable mass, ~37% more than E3a
   offered, plus jury evidence (E1/Liu agreement, cross-replicate votes) to act on.
3. **Two pre-registerable repairs before/alongside E7** (both are new cells, not post-hoc edits
   of E6):
   - **E6b — granularity control:** instruct the segmenter toward the official distribution
     ("aim for 6–9 units; merge closely-related sentences into one event") and rerun Stage 1
     unchanged. Tests the §3 mechanism directly; if precision recovers with recall held, E6b
     becomes the generator.
   - **Direction-QA repair** (method doc §3.4): E6's DRR 0.0504 ≈ 112 reversals is the largest
     direction-repair surface of any system yet; each fixed reversal is +1 TP, −1 FP, −1 FN.
4. **×3 replication** now attaches to the chosen generator (E6b if it works, else E6/E1) —
   never to dataset-subevent E3a, which remains a dev-only diagnostic.

## 5. Reproduction

```bash
cd /home/szf-4090/projects/fehu-project/ntcir19_fehu-master
python RH_test/E6_e3a_self_segmentation/scripts/offline_check_e6.py     # 26/26
# Stage 0 (segments_dev.json + cache + raw responses under runs/20260724_152658/)
python RH_test/E6_e3a_self_segmentation/scripts/run_segmentation_e6.py --mode dev \
  --model deepseek-v4-flash --out RH_test/E6_e3a_self_segmentation/runs/<ts>/segments_dev.json
# Stage 1 (E6_RUN_TS pins the run dir; cache-resumable)
E6_RUN_TS=<ts> python RH_test/E6_e3a_self_segmentation/scripts/run_pipeline_e6.py \
  --mode dev --provider deepseek --model deepseek-v4-flash \
  --prompt_variant targeted_more_shot_balanced \
  --segments RH_test/E6_e3a_self_segmentation/runs/<ts>/segments_dev.json
# scoring
python RH_test/E5_deberta_auxiliary_fusion/scripts/evaluate_run.py \
  --run_dir RH_test/E6_e3a_self_segmentation/runs/<ts>
```

Test-time flow is identical with `--mode test` on both stages (no gold needed anywhere).
