# Expanded Augmentation Planning Report — DRA-FEHU

**Created at:** 2026-07-04T21:42:51
**Output folder:** `output/research_expanded_augmentation_planning/20260704_214251`

## 1. Branch and git status
Branch: `main`. Git status before == after (verified by diff): the pre-existing dirty set only
(`src/hybrid_pipeline.py`, `src/run_pipeline.py`, `src/train_deberta.py` modified; `HYBRID_ROADMAP.md`,
`research/`, 4 untracked `src/*.py`). No file outside this planning folder changed (output/ is gitignored).

## 2. Files read
Smoke-run report set (metrics_summary.json, comparison_table.csv, smoke_run_report.md,
artifact_inventory.json, run_config.json), both `pred_task1b.json` files, official dev gold,
hv_categories taxonomy (L1, L2, L1→L2, **direction_mapping.json** = {aligned:"1", contradictory:"0"}),
and the verified pool (6 records). All read-only; nothing modified.

## 3. Files written (this folder only)
01_smoke_result_diagnosis.md, 02_target_label_priority_table.csv, 03_expanded_generation_plan.json,
04_generation_batch_spec.md, 05_planning_report.md.

## 4. Planning conclusion
The smoke run proves the controlled pipeline works but shows extreme head-class saturation (7–8 of 108
labels ever predicted) and zero rare-label emergence at 6-example density. The DRR improvement
decomposes almost entirely into untouched L1=45 "Be just" (188→59 reversals) and is therefore a
trajectory effect, not an augmentation effect. The correct next move is a **density-focused,
direction-balanced expansion targeting zero-recall labels with measurable dev support**, followed by a
multi-seed A/B repeat.

## 5. Recommended expanded pool size
**30 verified candidates** (minimum 20, upper bound 40): 6 existing + 24 new, generated from **72 raw**
DeepSeek V4 Pro candidates (3× buffer; expected acceptance 33–60%).

## 6. Top target labels (all direction-contrastive pairs)
| Rank | L1 | Name | Dev support (al/co) | New aligned + contradictory |
|---|---|---|---|---|
| 1 | 22 | Have good health | 122 (50/72) | 3 + 3 |
| 2 | 30 | Be compliant | 81 (44/37) | 2 + 2 |
| 3 | 38 | Be honest | 72 (44/28) | 2 + 2 |
| 4 | 12 | Have success | 54 (47/7) | 2 + 2 |
| 5 | 5 | Have freedom of action | 72 (30/42) | 2 + 2 |
| 6 | 46 | Have a world at peace | 48 (22/26) | 1 + 1 |

L1=12 and L1=38 **remain priority targets** (thesis continuity; density 2→6 each), with the documented
caveat that L1=12 contradictory has only 7 dev instances (low evaluation power). L1=13 "Be capable" was
deliberately excluded this round: it is the documented confusion axis of L1=12 and its contradictory
dev support is 5.

## 7. Diagnosis limitations
- Single seed; different early-stop epochs (5 vs 11) confound the A/B checkpoint comparison.
- Per-direction reversal attribution uses the authoritative direction_mapping.json, not the evaluator's
  internal names; aggregate DRR numbers are unaffected.
- L1=12-contradictory and several tail labels have too little dev support for reliable recall claims.
- Expected acceptance rate is an estimate from one small pilot (5/6); the 3× raw buffer covers it.

## 8. Confirmations
No candidate generation, no DeepSeek call, no training, no inference, no ablation, no source edit, no
official data modification, no evaluation.py modification, no verified-pool/ablation-input/smoke-run
modification, no commit/branch switch/stash/clean, no fallback implementation.

## 9. Next step
Generate raw candidates with DeepSeek V4 Pro according to 04_generation_batch_spec.md, then run
validation, semantic verification, and human review.
