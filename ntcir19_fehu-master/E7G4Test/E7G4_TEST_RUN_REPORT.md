# E7-G4 — Official Task-1 TEST Inference Run Report

**Date:** 2026-07-26 → 2026-07-27. **Status: COMPLETE. All validation checks passed.**
One complete Task-1 test inference with the frozen E7-G4 pipeline (dev reference:
`RH_test/E7_calibrated_jury_fusion/runs/20260725_004522_G4_dirqa`, dev 1b micro 0.5817).

> **No Task-1 test gold labels exist locally, so no F1 / precision / recall / DRR can be
> computed for this run.** All quality figures cited below are the frozen **dev** results of the
> identical pipeline. This report documents execution, prediction statistics, validation, and
> the exact files for the FEHU organizers.

## 1. What was run (frozen; nothing redesigned or retuned)

Input: **`dataset/test/test_article_event_base.json` only** (175 articles, 479 official
actors). No official subevents (the file has none), no Task-2 test data, no manual annotation,
no test-score-based adjustment. All segmentation used at test time is **model-generated** by the
frozen E6/E6b segmenters.

| stage | frozen artifact reused | test output |
|---|---|---|
| E1 base | `run_pipeline_e1.py`, variant `targeted_more_shot_balanced`, flash, temp 0.1 | 2,556 1b labels |
| Liu juror | `liu_method/run_pipeline.py`, same variant/model | 2,153 1b labels |
| E6 seg + preds | E6 segmenter (median-12 prompt) + E6 pipeline | segs: median 12 (mean 12.98); 3,075 labels |
| E6b seg + preds (**primary**) | E6b segmenter (6–9 prompt) + E6b pipeline | segs: median 8 (mean 8.16 — matches dev's 7.89); 2,928 labels |
| E6c juror | E6c pipeline, `deepseek-v4-pro` **non-thinking**, E6b's segments | 3,582 labels |
| DeBERTa-v2 features | `export_v2_probs.py` (E5 validated path), frozen v2 checkpoint | 479 rows (= actor count, hard-checked) |
| Fusion G3 | `run_fusion_e7.py --calibration apply`; calibration **fitted on full dev** (θ = 0.27479, jury identity verified at load) | 2,928 → **529 removals + 365 additions** → 2,764 labels |
| G4 direction-QA | frozen flag rule + QA prompt, flash | 207 flagged → **77 flipped**, 125 kept, 5 QA-failed (kept, logged) |
| Task-1a | deterministic L2 projection of final Task-1b | 2,136 labels (validated ≡ projection) |

The test fusion action profile (529 rm / 365 add / 77 flips on 175 articles) closely tracks the
dev profile (484 / 364 / 46 on 177 articles) — no sign of distribution breakage.
Calibration transfer used the pre-registered `fit`(dev) → `apply`(test) path; a regression test
confirmed the extended runner reproduces the frozen dev G1 output byte-for-byte.

## 2. Execution health

- **All 5 member caches: 175/175 articles, zero empty responses, zero unrecovered API
  failures.** The per-stage health protocol (purge empty → re-fetch once → loud abort on
  persistent failure) found nothing to repair; `logs/confirmed_empty.txt` is empty.
- Transient retries: a handful of within-stage parse retries in the two segmentation stages
  (recovered; visible in `logs/seg_e6*.log`); `seg_e6b` needed one outer restart. Every member
  pipeline stage completed on its first outer attempt.
- Direction-QA: 5 of 207 cells failed all 3 attempts (persistent empty responses on one
  article's cells); per the frozen rule they **keep their original direction** and are recorded
  in `fusion/G4_dirqa/dir_qa_decisions.jsonl` (`"reason": "qa_failed"`).
- Dev artifacts untouched: all member runs used fresh `e7g4test_20260726` run dirs; Liu's test
  run created the new `output/task1/runs/test_…` tag.

## 3. Final prediction statistics (Task-1b unless noted)

| statistic | value |
|---|---|
| articles / official actors | 175 / 479 |
| actors with ≥1 prediction | 470 (9 without — model judgment, not failures) |
| Task-1b labels | **2,764** (5.88 per predicted actor; min 1, max 22) |
| Task-1a labels | **2,136** |
| distinct 1b classes (of 108) | 93 |
| distinct L1 values (of 54) | **54 — full coverage** |
| direction split | aligned 1,884 (68.2%) / contradictory 880 (31.8%) |
| top classes | 1:42 (266), 1:37 (189), 1:45 (166), 0:27 (117), 1:27 (115) |

These are in line with dev-side expectations (dev G4: 5.9 labels/actor, ~68/32 direction split,
frequent classes led by 42/37/45).

## 4. Validation (all PASS — `validation/validation_report.json`)

1. Both files valid JSON in the official schema (`guid` + `article_human_values`; 1b fields
   `actor`/`l1_value`/`direction`, 1a fields `actor`/`l2_value`).
2. Every test GUID present exactly once; no extra GUIDs.
3. Every actor ID belongs to the article's official actor list (0 violations).
4. All labels in range (l1 0–53, direction ∈ {0,1}, l2 0–19); zero duplicates.
5. **Task-1a ≡ deterministic L2 projection of Task-1b** (recomputed independently).
6. Member caches: complete coverage, no empty-prediction articles, no unrecovered failures.

## 5. Files for the FEHU organizers

**Submit these two files** (byte-identical copies at both locations):

- `E7G4Test/submission/pred_task1a.json` (sha256 `cbd8a021…`)
- `E7G4Test/submission/pred_task1b.json` (sha256 `072e168f…`)

(top-level copies: `E7G4Test/pred_task1a.json`, `E7G4Test/pred_task1b.json`)

## 6. Record inventory (`E7G4Test/`)

```
pred_task1a.json / pred_task1b.json      final predictions (= submission copies)
run_manifest.json                        frozen-method description + sha256 of every input,
                                         member prediction file, and final output
submission/                              submission-ready copies
inputs/test_v2_probabilities.jsonl       DeBERTa-v2 test probabilities (479 rows)
fusion/calfit_dev/                       dev-fitted calibration (calibration.json, θ=0.27479)
fusion/G3_veto_add/                      fused preds, actions.jsonl (every removal/addition
                                         with calibrated p + jury votes), annotations.jsonl,
                                         fusion_manifest.json (input sha256s)
fusion/G4_dirqa/                         final preds, dir_qa_decisions.jsonl (all 207 verdicts),
                                         dir_qa_cache.json, fusion_manifest.json
members/{E1,Liu,E6,E6b,E6c}/             per-member pred files, full API caches, run_config,
                                         prompt snapshots (Liu: prompt fixed by frozen script,
                                         no snapshot emitted), E6/E6b: segmentation/ with
                                         segments_test.json + raw responses + cache
validation/validation_report.json        19/19 checks PASS
validation/stats.json                    label-count / coverage / direction statistics
logs/                                    per-stage execution logs + health log
scripts/                                 orchestrator, cache-health, validator
```

## 7. Caveats

- Dev-side expectation for this exact pipeline: 1b micro 0.5817 / macro 0.4308 (single dev
  pass; the pre-registered ×3 replication of E6b was not yet run). Test scores rest with the
  organizers.
- The calibration was fitted on dev and applied unchanged; test-side distribution shift would
  degrade gracefully (θ-gated, frequent-tier-only vetoes; capped value-disjoint additions).
- 5 QA-failed direction cells retain the generator's direction (logged individually).
