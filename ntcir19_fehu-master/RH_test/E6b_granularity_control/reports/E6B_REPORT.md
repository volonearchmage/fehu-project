# E6b — granularity-controlled self-segmentation

**Status: EXECUTED on full dev (run `20260724_224243`).** Date: 2026-07-25.
Pre-registered as the granularity-repair cell in E6's report §4.3 and the method doc
(`docs/FEHU_TEST_TRANSFER_AND_LIU_MARGIN_METHOD_20260724.md`).

## 1. Design

Identical to E6 in every respect (offline checks 6/6, including scaffold system prompt
**byte-identical to the frozen E3a snapshot** and pipeline byte-identical to E6 modulo run-dir
env var + provenance strings) except **one sentence in the segmentation prompt**:

> E6: "Aim for 6-12 subevents … and more for very long ones."
> E6b: "Aim for **6-9** subevents …; **merge closely-related sentences that describe the same
> development into ONE subevent** … at most a few more for very long ones."

Motivation (E6 report §3): E6's self-segmenter ran finer than the official annotation
(median 12 vs 9 units), and the +33% units produced +189 FPs at −21 TPs — a pure precision
loss. E6b tests whether matching the official granularity recovers it.

**Segmentation achieved:** 177/177; units min 2 / median 8 / max 10 / mean 7.89 — on top of
the official distribution (median 9). One transient JSON failure, recovered on in-script retry.
Stage 1: clean run, **zero empty-response articles** (no cache repair needed).

## 2. Results (dev, same scorer for all systems)

| metric | E1 | E6 (self, fine) | **E6b (self, 6–9)** | E3a (official segs) | Liu best |
|---|---|---|---|---|---|
| 1b micro-F1 | 0.5480 | 0.5412 | **0.5496** | 0.5666 | 0.5657 |
| 1b micro P / R | 0.5405 / 0.5556 | 0.4855 / 0.6113 | 0.5017 / 0.6075 | 0.5216 / 0.6201 | 0.6149 / 0.5067 |
| 1b macro-F1 | 0.3719 | 0.4079 | **0.4124** | 0.4173 | 0.3870 |
| 1a micro-F1 | 0.6574 | 0.6535 | 0.6621 | 0.6727 | 0.6555 |
| DRR | 0.0347 | 0.0504 | 0.0459 | 0.0414 | 0.0279 |
| target-18 micro | 0.2460 | 0.2963 | **0.3145** | 0.3136 | — |
| non-target-90 micro | 0.5685 | 0.5582 | 0.5656 | 0.5841 | — |

Deltas E6b vs E6: micro **+0.0084**, macro +0.0045, precision **+0.0162**, recall −0.0038,
DRR −0.0045, t18 **+0.0182**. Deltas E6b vs E1: micro +0.0016, macro **+0.0405**,
t18 **+0.0686**.

## 3. Findings

1. **The granularity mechanism is confirmed.** Coarsening the self-segmentation from median 12
   to median 8 units recovered +0.016 precision at a −0.004 recall cost — almost exactly the
   knob the E6 report predicted. Micro-F1 moved +0.0084 on this one sentence.
2. **E6b is the best test-legal single system** (0.5496 > E1 0.5480), with a large macro lead
   (+0.0405) and the **best target-18 result of any system to date (0.3145, above even
   dataset-subevent E3a's 0.3136)**. The scaffold's tail gain not only transfers with
   self-segmentation — with matched granularity it fully transfers.
3. **The remaining gap to E3a (−0.017 micro) is still precision** (0.502 vs 0.522) on frequent
   classes (nt90 0.5656 vs 0.5841) — exactly the population the E7 calibrated veto targets, and
   the E7 smoke on E6 already showed the veto recovers precision there without touching t18.
4. **Still short of Liu's reported 0.5657** as a single system; E6b's role is the primary
   generator inside E7.

## 4. Records

`runs/20260724_224243/`: `segments_dev.json` (+ raw responses, segmentation cache),
`pred_task1a/b.json`, scaffold cache, `run_config.json`, `system_prompt_snapshot.txt`,
`fewshot_meta.json`, `metrics.json`, `per_class_metrics.csv` (E5 scorer).
Scripts + offline checks under `scripts/`.
