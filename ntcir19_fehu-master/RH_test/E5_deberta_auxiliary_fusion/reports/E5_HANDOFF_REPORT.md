# E5 — Calibrated Auxiliary Fusion: E1 primary + augmented DeBERTa-v2 LoRA auxiliary

**Status: DESIGNED + IMPLEMENTED + OFFLINE-VALIDATED. Dev experiments NOT yet run (by instruction).**
Date: 2026-07-24. All artifacts under `RH_test/E5_deberta_auxiliary_fusion/`; no file outside this
directory was created or modified (verified with `git status`).

---

## 1. Which augmented DeBERTa-LoRA checkpoint was selected, and why

**Selected:** `output/research_augmented_deberta_v2_unfiltered/20260714_032758/checkpoint`
(“augmented v2”, masked-loss run).

| Property | Value |
|---|---|
| Base model | `microsoft/deberta-v3-base` + LoRA (r=16, α=32, dropout 0.1, SEQ_CLS) + linear head (`classifier.pt`) |
| Label space | 108 = 54 L1 values × 2 directions; index = `l1*2 + direction` |
| Training data | official 1228 articles **+ 340 first-round AI-screened silver + 900 label-aware round-2** = 2468 articles / 4575 actor examples |
| Supervision | masked partial-label (3785 fully supervised, 790 target-only masked) — the policy Phase 3 confirmed as the main config at full data |
| Inference threshold | 0.30 (its documented operating point) |
| Frozen dev result | 1b micro 0.3306 / macro 0.1303, P 0.2381 / R 0.5406, DRR 0.2880 |

Rejected alternatives: the **old DeBERTa baseline** (`research_ablation_smoke_runs/.../baseline`, official data
only — explicitly out of scope); **augmented v1** (`20260712_231751`, 340-only, no 900, rare labels still at 0);
Phase-3 **Gp/N1/N3** runs (different supervision/negative-sampling policies, not the main config).
Phase-3 **Fp seeds 42/44/43** are exact re-trainings of the v2 config and are used only as an optional
seed-ensemble signal (variant F7), never as the primary auxiliary.

**Probabilities:** `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/02_deberta_actor_probabilities.jsonl`
(459 dev actor rows: 456 gold-parity + 3 `article_only_actor_not_in_frozen_run`). Re-validated here:
thresholding at 0.30 reproduces the frozen v2 `pred_task1b.json` **exactly** on all 456 parity keys
(`analysis/analyze_complementarity.py` aborts otherwise). E1 predictions:
`RH_test/E1_fewshot_repair/runs/20260722_152456/` (1b micro 0.5480 / macro 0.3719, DRR 0.0347 — reproduced).
All input hashes: `inputs/INPUT_MANIFEST.json`.

## 2. Are the errors complementary? (analysis results, dev)

Full numbers in `analysis/outputs/` (`ANALYSIS_SUMMARY.md`, `recovery_sweep.csv`, `filter_analysis.json`,
`direction_analysis.json`, `veto_design.json`, `per_class_metrics.csv`).

**Nominal coverage complementarity exists** — of 2390 gold cells: both systems hit 864, E1-only 464,
**v2-only 428**, neither 634. But it is **not actionable at useful precision**:

1. **Missing-label recovery fails.** Adding v2 cells that E1 lacks has precision 0.104 at τ=0.30 (4132 cells)
   rising only to 0.22 at τ=0.70 (59 cells) — always far below E1's own micro-precision 0.5405, so every
   global add policy lowers micro-F1. Requiring cross-seed agreement raises precision to ~0.19–0.21 but
   erases all target-18 candidates. Above τ=0.45 the candidates include **zero** target-18 cells: v2's
   probabilities on rare classes never reach confident levels (its 0.30-threshold rare hits are low-precision noise).
2. **Direction assistance is decisively refuted.** v2's dev DRR is 0.2880 (vs E1's 0.0347). On cells where
   E1 has the value right and gold direction is unique, flipping direction to v2's argmax gives
   42 fixes / 312 breaks (margin ≥0: net −270), and stays net-negative at every margin (−171/−99/−34/−10).
   **The fusion therefore never takes direction from v2.**
3. **Negative-evidence filtering looks good only as an artifact.** Unrestricted, removing E1 cells with very low
   v2 probability projects micro 0.5535 (τ=0.10) — but macro collapses 0.3719→0.3217 because the removals
   concentrate on rare/target-18 classes, where v2's low probability is *ignorance, not evidence* (70 of 197
   removed cells at τ=0.10 are target-18). With the principled exemption (only classes with official-train
   count > 130 may be vetoed — the frozen rarity cutoff of the target-selection policy; 38/108 classes,
   0 overlap with target-18), the projected effect shrinks to ≈ +0.0005 micro at best. Real but marginal.
4. **No per-class delegation niche.** v2 beats E1's F1 on only 3 of 93 gold-supported classes (all via
   low-precision recall); v2 has **zero** classes with precision above E1's average 0.54.
5. **Class-level fallback fails.** On the 13 classes where E1 abstains entirely, v2's top-ranked candidates
   contain 0 true positives (39 tried). **Empty-actor backfill** (10 gold actors E1 leaves without labels)
   has top-1 precision 0.30 — roughly break-even, kept only as an ablation arm.
6. **Agreement is a genuine confidence signal.** Within E1's predictions, v2's probability separates TP from FP
   with AUC 0.68 (TP median 0.36 vs FP median 0.27). Too weak to act on aggressively, but valuable as a
   **disagreement-detection / verification-routing annotation** (e.g., for an E3-style verifier stage).

**Honest conclusion:** the augmented v2 model is weaker than E1 in every actionable regime; its errors overlap
E1's on the long tail (the "neither" 634 cells, 93/140 target-18 gold cells missed by both). The defensible
fusion is therefore a *guarded, calibrated, near-pass-through* design whose arms activate only where the data
supports action, plus an annotation layer — not an aggressive combiner. Expected headline movement is small;
part of E5's value is documenting rigorously *where and why* the augmented model does not help, with the
annotation layer as the durable product.

## 3. Fusion design (implemented in `scripts/fusion_lib.py`)

A single decision-theoretic rule — **plug-in expected-F1 maximization under cross-fitted isotonic
calibration** — rather than hand-picked thresholds:

- **Calibration.** Per fold (2-fold split by `md5(guid) % 2`), fit pool-adjacent-violators isotonic
  regressions on the *other* fold mapping v2 scores → P(cell is gold), separately for
  (a) E1-predicted cells (**removal calibrator**, scored by the direction-agnostic *value score*
  `max(p[v,0], p[v,1])` — immune to v2's direction noise) and (b) non-E1 candidate cells
  (**addition calibrator**, scored by the exact directed probability). An article's own gold never
  influences its own fusion decision.
- **Action threshold.** θ = (E1 micro-F1 on the calibration fold)/2 ≈ 0.27 — the classical plug-in rule:
  under micro-F1, a cell is worth predicting iff its posterior ≥ F/2.
- **Removal arm (veto).** Remove an E1 cell only if calibrated P(gold) < θ **and** its class is in the
  frequent tier (official-train count > 130; target-18 and all rare classes are structurally untouchable)
  **and** the actor retains ≥ 1 label. Lowest-probability cells removed first.
- **Addition arm (recovery).** Add a non-E1 cell only if calibrated P(gold) ≥ θ, class in frequent tier,
  the actor does not already hold the same value in **either** direction (never fight E1 on direction),
  capped at 2 additions/actor. Given measured precision ceilings (§2.1), this arm is expected to stay
  nearly inactive — it is principled and self-limiting, and quantifies exactly that.
- **Direction policy.** v2 never changes or supplies a direction for a value E1 holds; backfill/additions
  use v2's directed label only for values E1 does not predict at all.
- **Annotation layer.** Every output cell is tagged (`annotations.jsonl`) with v2 exact probability,
  value score, and agree@0.30 — the disagreement-detection deliverable for downstream verification
  (E3/E3a integration). Never alters outputs.
- **Task-1a.** Recomputed as the L2 projection of the fused 1b set via the official mappings — verified
  identical to E1's own 1a under identity fusion (447/447 actors).
- **Fail-fast.** Missing probability rows, malformed vectors, duplicate keys, stray E1 keys, non-empty
  output dirs, calibration/variant mismatches all raise immediately. No fallback paths.

## 4. How E1 remains the primary predictor

- Structurally: the fused set **starts as E1's set**; with no arms enabled the output is byte-equivalent to
  E1 (enforced by an end-to-end test on the real dev inputs, `TestEndToEndIdentity`).
- Weak v2 evidence cannot remove a strong E1 prediction: removal requires *calibrated* strong negative
  evidence (P(gold) < θ under a monotone calibrator fitted on held-out cells), is barred from all 70
  rare-tier classes where v2's low probability means ignorance, and can never empty an actor.
- v2 can never override E1's direction, and additions are capped and value-disjoint from E1's choices.
- v2 alone appears only as the reference arm `REF_v2_alone`, never inside the fusion path.

## 5. Ablation variants (pre-registered; report all cells, no post-hoc selection)

| Variant | Arms / change | Question it answers | Expectation from analysis |
|---|---|---|---|
| `F0_identity` | none (annotation only) | sanity anchor ≡ E1 | exact E1 metrics |
| `F1_veto_value` | **MAIN**: removal, value score, frequent gate | does calibrated veto help micro without macro cost? | micro +0.000…+0.005, macro ≈ flat |
| `F2_veto_nogate` | F1 without frequent gate | documents why the gate exists | micro up, macro down (artifact) |
| `F3_veto_exact` | F1 with exact-label score | direction-noise sensitivity of the veto | ≤ F1 (punishes direction disagreement) |
| `F4_full` | F1 + addition arm | is any calibrated recovery viable? | additions ≈ 0 |
| `F5_full_backfill` | F4 + top-1 backfill of E1-empty actors | coverage repair value | ~neutral (precision 0.30) |
| `F6_union_diag` | E1 ∪ v2@0.30 | harm bound of naive union | micro ≪ E1 (documented) |
| `F7_seedmean` | F1 with scores averaged over v2 + Fp42/43/44 | single-seed noise robustness | ≈ F1, tighter |
| `REF_v2_alone` | v2@0.30 only | auxiliary reference | micro ≈ 0.3306 |

## 6. Expected benefits and risks

**Benefits.** (i) A small, honest micro-precision repair (the only statistically supported action);
(ii) per-cell confidence/disagreement annotations enabling a later verification stage (E3's verifier showed a
monotone unit-support precision signal — these tiers are its natural routing input); (iii) a pre-registered,
leakage-guarded negative/positive result on every standard fusion role for the augmented model — direct
evidence for the paper's augmentation story; (iv) a validated test-time path for the v2 checkpoint.

**Risks.** (1) *Design-on-dev*: thresholds/gates were chosen after inspecting dev analyses. Mitigations:
cross-fitted calibration (no self-leakage), a frozen grid reported in full, replication over the planned ×3
E1 reruns (fusion is deterministic given E1 preds — rerun it per E1 replicate), final judgment on test.
(2) *Effect size may be ≈ 0*: acceptable outcome; F0 anchors exact equality. (3) *Calibration transfer to
test* uses dev-fitted calibrators (`fit`→`apply`) — standard, but distribution shift on test could reduce the
veto's ratio; the arms' conservatism bounds the damage (θ-gated removals only on frequent classes).
(4) *Seed variance of v2* (Phase 3: micro 0.290–0.358 across reproductions) — F7 quantifies sensitivity.

## 7. Exact commands for the later dev experiments

```bash
cd /home/szf-4090/projects/fehu-project/ntcir19_fehu-master

# 0) offline validation (already green, 25 tests)
python RH_test/E5_deberta_auxiliary_fusion/tests/test_fusion_offline.py

# 1) main grid — one command per variant (any python3; no GPU, no API)
TS=$(date +%Y%m%d_%H%M%S)
for V in F0_identity F1_veto_value F2_veto_nogate F3_veto_exact \
         F4_full F5_full_backfill F6_union_diag REF_v2_alone; do
  python RH_test/E5_deberta_auxiliary_fusion/scripts/run_fusion_e5.py \
      --variant $V --calibration crossfit \
      --out_dir RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_${V}
  python RH_test/E5_deberta_auxiliary_fusion/scripts/evaluate_run.py \
      --run_dir RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_${V}
done

# 2) F7_seedmean needs full-coverage seed exports first (GPU, fehu env;
#    the Phase-3 exports cover only the 456 gold-parity actors, and E5
#    refuses partial coverage rather than falling back):
for S in 42 43 44; do
  /home/szf-4090/miniconda3/envs/fehu/bin/python \
    RH_test/E5_deberta_auxiliary_fusion/scripts/export_v2_probs.py \
      --articles dataset/dev/dev_event_base.json \
      --checkpoint new_check/phase3/runs/Fp_seed${S}/checkpoints \
      --validate_against new_check/phase3/runs/Fp_seed${S}/output/pred_task1b.json \
      --out RH_test/E5_deberta_auxiliary_fusion/inputs/dev_fp_seed${S}_probs.jsonl
done
# then point SEED_PROB_FILES (scripts/run_fusion_e5.py) at the new exports and run:
python RH_test/E5_deberta_auxiliary_fusion/scripts/run_fusion_e5.py \
    --variant F7_seedmean --calibration crossfit \
    --out_dir RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_F7_seedmean
python RH_test/E5_deberta_auxiliary_fusion/scripts/evaluate_run.py \
    --run_dir RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_F7_seedmean

# 3) replication: repeat step 1 with each new E1 rerun via
#      --e1_pred_1b RH_test/E1_fewshot_repair/runs/<new_run>/pred_task1b.json

# 4) test-time flow (when the winning variant is frozen; no gold needed at apply):
/home/szf-4090/miniconda3/envs/fehu/bin/python \
  RH_test/E5_deberta_auxiliary_fusion/scripts/export_v2_probs.py \
    --articles dataset/test/test_article_event_base.json \
    --out RH_test/E5_deberta_auxiliary_fusion/inputs/test_v2_probabilities.jsonl
python RH_test/E5_deberta_auxiliary_fusion/scripts/run_fusion_e5.py \
    --variant F1_veto_value --calibration fit \
    --out_dir RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_calfit_dev   # fits on dev, saves calibration.json
python RH_test/E5_deberta_auxiliary_fusion/scripts/run_fusion_e5.py \
    --variant F1_veto_value --calibration apply \
    --calibration_file RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_calfit_dev/calibration.json \
    --articles dataset/test/test_article_event_base.json \
    --e1_pred_1b <E1 test predictions>/pred_task1b.json \
    --v2_probs RH_test/E5_deberta_auxiliary_fusion/inputs/test_v2_probabilities.jsonl \
    --out_dir RH_test/E5_deberta_auxiliary_fusion/runs/${TS}_F1_test
```

Compatibility: the pipeline consumes only official Task-1 inputs (`*_event_base.json` articles + actor lists)
plus system predictions/probabilities; it uses no official subevents and no Task-2 supervision.

## 8. File inventory

```
RH_test/E5_deberta_auxiliary_fusion/
├── analysis/
│   ├── analyze_complementarity.py   first-stage analysis (validation + overlap + sweeps)
│   ├── analyze_veto_design.py       second-stage analysis (veto variants + backfill)
│   └── outputs/                     ANALYSIS_SUMMARY.md, per_class_metrics.csv,
│                                    recovery_sweep.csv, filter_analysis.json,
│                                    direction_analysis.json, overlap_summary.json, veto_design.json
├── inputs/INPUT_MANIFEST.json       sha256 of every frozen input
├── scripts/
│   ├── fusion_lib.py                core library (loaders, PAV, calibration, fusion, output)
│   ├── run_fusion_e5.py             CLI runner (variants × calibration modes, manifest)
│   ├── evaluate_run.py              official scorer + macro-P/R + t18/nt90 + per-class + Δ vs E1
│   └── export_v2_probs.py           checkpoint inference for dev/test (hard-validated)
├── tests/test_fusion_offline.py     25 offline tests (all green)
└── reports/E5_HANDOFF_REPORT.md     this report
```

All prior experiment artifacts (E1, E2, E3, E3a, E4, DeBERTa checkpoints, predictions, reports) are untouched.
