# E5 — Calibrated Auxiliary Fusion: DEV RESULTS

**Status: EXECUTED. Full pre-registered dev grid (9 variants) run and scored.**
Date: 2026-07-24. Run timestamp: `20260724_125935`. All outputs under
`RH_test/E5_deberta_auxiliary_fusion/`. No experiment design, threshold, or data was changed.
Every input matched its frozen `INPUT_MANIFEST.json` sha256 before running (14/14 OK).

---

## 1. What was run

- **Offline validation:** `tests/test_fusion_offline.py` → 25/25 green.
- **F7 prerequisite (documented in handoff §7 step 2):** the frozen Phase-3 seed exports
  (`new_check/phase3/runs/Fp_seed{42,43,44}/probabilities.jsonl`) cover only the 456 gold-parity
  actors; F7 refuses partial coverage. Re-exported full-coverage dev probabilities for all **459**
  dev actors from each seed checkpoint with `scripts/export_v2_probs.py`, each **validated against its
  own frozen `pred_task1b.json`** (probs@0.30 reproduce the frozen predictions exactly on all 456 keys)
  → `inputs/dev_fp_seed{42,43,44}_probs.jsonl`. As handoff §7 instructs, `SEED_PROB_FILES` in
  `scripts/run_fusion_e5.py` was repointed to these full-coverage exports (the only edit made; it is a
  documented input-path repoint, not a design/threshold change).
- **Grid:** all 9 variants via `run_fusion_e5.py --calibration crossfit` + `evaluate_run.py`.
- **Baselines under the same scorer:** E1 (= F0 by construction), the frozen DeBERTa-v2 predictions,
  and the existing **H3** hybrid (`…/20260714_184515/16_pred_task1b_h3.json`), all scored with
  `evaluate_run.py` (staged in `baselines_eval/`). No test-set inference was run.

`F0_identity` reproduces E1 **exactly** (every delta 0.0000; 447 keys / 2457 labels identical) — the
sanity anchor holds, so all downstream deltas are attributable to the fusion arms alone.

## 2. Full result table (dev, Task-1b unless noted)

"all-108" micro-F1 **is** the Task-1b micro-F1 (target-18 ∪ non-target-90 = 108 labels); the macro
columns are the gold-supported macro over those 108 classes. The scorer reports **group micro** for
target-18 / non-target-90 (its `group_micro`); it does not define a per-group macro, so none is invented.

| system | mi-F1 | mi-P | mi-R | Ma-F1 | Ma-P | Ma-R | 1a mi-F1 | DRR | t18 mi-F1 | nt90 mi-F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| DeBERTa-v2 (frozen aux) | 0.3306 | 0.2381 | 0.5406 | 0.1303 | 0.0964 | 0.2307 | 0.5405 | 0.2880 | 0.0805 | 0.3405 |
| H3 (existing hybrid) | 0.5474 | 0.5480 | 0.5469 | 0.3382 | 0.4097 | 0.3344 | 0.6617 | 0.0311 | 0.2480 | 0.5640 |
| **E1 = F0_identity** | **0.5480** | 0.5405 | 0.5556 | **0.3719** | 0.4162 | 0.3919 | 0.6574 | 0.0347 | 0.2460 | 0.5685 |
| **F1_veto_value (MAIN)** | 0.5471 | 0.5424 | 0.5519 | 0.3707 | 0.4166 | 0.3891 | 0.6557 | 0.0347 | 0.2460 | 0.5677 |
| F2_veto_nogate | 0.5518 | 0.5635 | 0.5406 | 0.3369 | 0.4095 | 0.3295 | 0.6572 | 0.0347 | 0.2385 | 0.5702 |
| F3_veto_exact | 0.5472 | 0.5431 | 0.5515 | 0.3709 | 0.4181 | 0.3887 | 0.6557 | 0.0347 | 0.2460 | 0.5679 |
| F4_full | 0.5464 | 0.5381 | 0.5548 | 0.3697 | 0.4106 | 0.3909 | 0.6556 | 0.0347 | 0.2460 | 0.5668 |
| F5_full_backfill | 0.5459 | 0.5366 | 0.5556 | 0.3696 | 0.4102 | 0.3910 | 0.6553 | 0.0351 | 0.2460 | 0.5663 |
| F7_seedmean | 0.5474 | 0.5443 | 0.5506 | 0.3712 | 0.4192 | 0.3878 | 0.6555 | 0.0347 | 0.2460 | 0.5681 |
| F6_union_diag | 0.3911 | 0.2665 | 0.7347 | 0.2912 | 0.2465 | 0.4801 | 0.5758 | 0.3047 | 0.2043 | 0.4012 |
| REF_v2_alone | 0.3293 | 0.2367 | 0.5406 | 0.1297 | 0.0958 | 0.2307 | 0.5383 | 0.2880 | 0.0805 | 0.3391 |

**Delta of the MAIN variant vs E1:** mi-F1 −0.0009, Ma-F1 −0.0012, 1a −0.0016, DRR +0.0000,
t18 +0.0000, nt90 −0.0008. **Vs H3:** mi-F1 −0.0003, Ma-F1 **+0.0325**, t18 −0.0020, nt90 +0.0037.

Every variant matched its pre-registered expectation (handoff §5): F2 micro↑/macro↓ artifact;
F3 ≤ F1; F4 additions active (32) but net-neutral-to-slightly-negative; F5 backfill ~neutral
(DRR +0.0005); F6 union is the documented harm bound (micro −0.157); REF_v2_alone ≈ 0.33.

## 3. Does E5 improve over E1?

**No — not by any meaningful margin.** The MAIN calibrated variant F1_veto_value moves micro-F1 by
**−0.0009** and macro-F1 by **−0.0012**; it is statistically and practically indistinguishable from E1.
The entire fusion effect is **25 removed cells** out of 2457 E1 predictions: **16 removed cells were
E1 false-positives (helps precision), 9 were true-positives (hurts recall)**. The veto is genuinely
FP-enriched (64% of its removals were FPs vs E1's 46% baseline FP rate) — but not enriched enough for
micro-F1 to prefer it, so precision rises (0.5405→0.5424) exactly as recall falls (0.5556→0.5519) and
F1 nets slightly negative. The seed-robust variant F7 (39 removals across 4 seed scores) lands at the
same place (micro 0.5474, −0.0005), confirming the null is not a single-seed accident.

The **only** micro gain in the grid is F2_veto_nogate (+0.0038) — but this is the **pre-registered
artifact**, not an improvement: it costs macro −0.0350 and target-18 −0.0075 because, without the
frequent-class gate, the veto removes rare/target-18 cells where v2's low probability is *ignorance,
not evidence*. The gate exists precisely to forbid this, and with the gate the supported effect
collapses to ≈ 0. No addition/recovery arm is viable (F4/F5 ≤ E1), consistent with the analysis
finding that v2's addition precision never exceeds 0.22 < θ ≈ 0.27.

## 4. Does E5 improve over H3?

**Micro: no** (F1 0.5471 vs H3 0.5474, −0.0003 — a tie). **Macro: yes, materially** (0.3707 vs
0.3382, **+0.0325**), and E5/E1 also has a slightly better direction profile only on non-targets.
**But this macro advantage is not produced by E5's fusion — it is inherited from E1**: F0 (≡ E1)
already scores macro 0.3719 vs H3's 0.3382. The fusion layer contributes nothing on top of E1 toward
beating H3; if anything it shaves macro by 0.0012. H3 retains small edges on 1a-F1 (0.6617 vs 0.6557),
DRR (0.0311 vs 0.0347), and target-18 micro (0.2480 vs 0.2460). Net: the E1 family already ≥ H3 on the
headline micro and clearly on macro; **E5 does not change that verdict in either direction.**

## 5. Statistical / practical significance

- **Not meaningful.** The MAIN effect (−0.0009 micro) sits on a 25-cell perturbation (16 vs 9 discordant)
  and is dwarfed by the documented replication noise it must be judged against: v2's own seed variance is
  micro 0.290–0.358 (Phase 3), and the E1 base is pending ×3 replication. A −0.0009 shift is well inside
  that band and negative, so there is no positive effect to test.
- The design is deterministic given E1's predictions and cross-fit-calibrated (an article's own gold never
  influences its own decision), so the null is a real null, not calibration leakage. `F0` anchors exact
  E1 equality, bounding any implementation artifact at zero.
- DeBERTa-v2 remains far below E1 everywhere (micro 0.3306, macro 0.1303, t18 0.0805), and its raw union
  with E1 (F6) is actively harmful (−0.157 micro, DRR +0.27) — confirming it is only ever an auxiliary.

## 6. Verdict and durable product

**E5 does not beat E1, and does not change E1's standing vs H3.** The augmented DeBERTa-v2 model is
weaker than E1 in every actionable regime; the defensible, leakage-guarded fusion is a near-pass-through
whose one supported action (frequent-tier calibrated veto) is a wash on dev. This is the pre-registered,
honest negative result — direct evidence for the paper's augmentation story about *where and why* the
augmented model does not help.

The **durable deliverables** are: (i) `annotations.jsonl` — per-cell v2 exact probability, direction-
agnostic value score, and agree@0.30 tier for every output cell (the disagreement-detection input for an
E3-style verifier; v2 separates E1's TPs from FPs at AUC ≈ 0.68); (ii) a validated test-time path for the
v2 checkpoint (`--calibration fit`→`apply`, no gold at apply); (iii) full-coverage seed exports and a
fully reproduced, fail-fast grid.

**Recommendation:** keep **E1 (= F0)** as the primary system; do **not** ship any veto/addition arm as a
scorer — the gain is absent. Carry the annotation layer forward into the E3/E3a verifier work, where the
confidence tiers have a use that the fusion arms do not.

## 7. Reproduction

```bash
cd /home/szf-4090/projects/fehu-project/ntcir19_fehu-master
python RH_test/E5_deberta_auxiliary_fusion/tests/test_fusion_offline.py         # 25/25
# seed re-export (GPU, fehu env) → inputs/dev_fp_seed{42,43,44}_probs.jsonl (validated)
# grid: run_fusion_e5.py --variant <V> --calibration crossfit ; evaluate_run.py --run_dir <...>
# runs/20260724_125935_<variant>/  hold pred_task1{a,b}.json, metrics.json, per_class_metrics.csv,
#   actions.jsonl, annotations.jsonl, fusion_manifest.json
# baselines_eval/{H3,DeBERTa_v2_frozen}/metrics.json  hold the same-scorer baseline numbers
```
