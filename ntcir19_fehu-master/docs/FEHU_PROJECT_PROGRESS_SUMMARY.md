# FEHU Project Progress Summary

**Date:** 2026-07-22
**Repository:** `fehu-project` (project root `ntcir19_fehu-master/`), branch `sync-safe-fehu-dra-20260705`, HEAD `fb7b0fb` (tracked tree clean; untracked additions: `docs/FEHU_RESEARCH_ROUTE_CRITICAL_REVIEW.md`, `docs/FEHU_PROFESSOR_FEEDBACK_VALIDATION_PLAN.md`, `new_check/`)
**Method:** read-only analysis of repository reports, configurations, logs, and result artifacts. Every number cites its source file. No training, inference, or API calls were performed for this summary; nothing outside this document was created or modified.

---

## 1. Project Background and Task Objectives

**Task.** NTCIR-19 FEHU (Fact-based Event-centric Human-value Understanding) asks systems to identify the human values expressed by **each actor** in factual news articles (`README.md`, `CLAUDE.md`). All work here targets **Task-1** (article level); Task-2 (subevent level) has no implemented system.

- **Task-1a:** per `(article, actor)`, predict Level-2 value categories (20 classes).
- **Task-1b:** per `(article, actor)`, predict Level-1 values (54 classes) **plus a binary direction** — `"1"` aligned (actor supports the value) vs. `"0"` contradictory (actor violates it), per `dataset/hv_categories/direction_mapping.json`. The official evaluator (`evaluation.py`, never modified) scores 1b over a **108-class direction-aware space** (`direction:l1`), with micro-F1, gold-supported macro-F1, and the Direction Reverse Rate (DRR; gold-exclusive denominator 2,222 on dev).

**Data scale** (`new_check/phase0/`, diagnosis CSVs): train 1,228 articles / 3,335 actor examples / 16,905 labels; dev 177 articles / 456 gold actor instances / 2,390 direction-aware labels over 93 gold-supported classes (16 with support ≤2). The label distribution is strongly long-tailed (top-5 L1 classes carry 41.8% of labels; per-class counts 4–2,031; `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/label_frequency_l1.csv`), and direction is imbalanced ~2.1:1 aligned.

**Main research problem.** Rare (tail) direction-aware classes get near-zero recall from trained classifiers, while LLM prompting handles direction well but plateaus in recall. The project studies whether **diagnosis-guided LLM data augmentation**, **partial-label (masked) supervision**, and **classifier×LLM hybrids** can fix the tail without sacrificing overall F1 and direction accuracy.

## 2. Overall Research Approach

**Evolution** (details: `docs/FEHU_PROJECT_RESEARCH_SUMMARY.md` §6–7):

1. **Prompt baselines** (GPT-4o → DeepSeek Flash; Pipelines V2/V3 with strict validation and ensembles) — best single LLM: Liu's frozen `targeted_more_shot_balanced` run, 1b micro 0.5347 (`output/task1/runs/dev_deepseek_…`).
2. **DeBERTa-v3-base + LoRA student** (108-way multi-label BCE, threshold 0.3; `src/train_deberta.py`) — micro 0.30, macro 0.03, DRR 0.22; predicts only ~8 classes.
3. **Value/direction decomposition** (from Hybrid-v1's failure, `HYBRID_ROADMAP.md`): DeBERTa finds *which values* (recall); the LLM decides *relevance and direction* (precision, DRR).
4. **DRA-FEHU augmentation**: per-label diagnosis → DeepSeek-generated, label-conditioned synthetic records (round-1: 340 AI-screened "silver"; round-2: 900 structurally-validated, semantically unscreened, over 18 frozen tail targets) → masked partial-label training (`…v2_unfiltered/…/scripts/train_deberta_masked_v2.py`).
5. **Final hybrid**: augmented student supplies direction-neutral candidates; DeepSeek-Flash (Liu prompt) verifies and assigns direction — current best system (H3 micro 0.5474; `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/`).
6. **Validation program 2026-07-19→20** (`new_check/` Phases 0–3): recomputed all claims, exported probabilities, and ran controlled multi-seed ablations isolating augmentation, supervision policy, and negative down-sampling.

**Likely thesis narrative:** *long-tail human-value recognition via a value/direction-decomposed hybrid, with diagnosis-guided synthetic supervision for the tail studied under controlled partial-label training* — the hybrid decomposition carries the headline result; the augmentation/supervision study carries the methodological contribution (including its negative and interaction findings).

## 3. Completed Experiments and Data

**Data assets** (`docs/FEHU_PROJECT_RESEARCH_SUMMARY.md` §8; verified in `new_check/phase0/outputs/pos_neg_ratio_table.csv`):

| Asset | Size | Screening status | Purpose |
|---|---|---|---|
| Official train | 1,228 articles | gold | base supervision |
| Verified pilot pool | 6 records | **human-ACCEPTed** (only human-reviewed set; in no v1/v2 training run) | process pilot / smoke run |
| Round-1 silver | 340 (of 422) | AI-screened (Fable 5); **no human review** | tail L1 {22,30,38,12,5,46} |
| Round-2 label-aware | 900 | structural checks only; **semantically unscreened, no human review** | 18 frozen `direction:l1` targets |
| Synthetic vs. real shape | — | — | synthetic: median 811 chars / 1 actor / 1 label vs. real 3,331 / 3 / 13 (`new_check/phase0` report §—; computed from v1 inputs) |

**Major training experiments** (all DeBERTa-v3-base+LoRA r16/α32, lr 2e-4, ≤15 epochs, patience 4 on dev 1b micro-F1, threshold 0.3; run configs in each folder):

| Experiment | Data | Synthetic-label policy | Seeds | Source |
|---|---|---|---|---|
| Baseline | official | — | 42 | `output/research_ablation_smoke_runs/20260704_201355/baseline/` |
| Augmented v1 | +340 | assume-negative | 42 | `output/research_augmented_deberta_v1/20260712_231751/` |
| Augmented v2-Unfiltered | +340+900 | masked (790 target_only) | 42 | `output/research_augmented_deberta_v2_unfiltered/20260714_032758/` |
| Phase-2 A / B / C | official / +900 / +900 | — / assume-neg / masked | 42–44 each | `new_check/phase2/runs/` |
| Phase-3 F′ / G′ | +340+900 | masked / assume-neg | 42–44 each | `new_check/phase3/runs/` |
| Phase-3 N3 / N1 | +340+900 masked | + per-target negative down-sampling 1:3 / 1:1 | 42–44 each | `new_check/phase3/runs/` |

**Target-vs-non-target evaluation** exists for every system since Phase 0: the 18 frozen targets (14 contradictory / 4 aligned; supports 3–21; `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/02_selected_targets_and_allocation.json`) vs. the remaining 90 classes vs. all 108, each with all six micro/macro P/R/F1 metrics (`new_check/phase0/outputs/`, `new_check/phase{2,3}/outputs/per_run_metrics.csv`).

## 4. Main Experimental Results

All dev-set, official evaluator conventions; macro = gold-supported. **Historical single-seed systems** (`new_check/phase0/outputs/overall_metrics_all_systems.csv`):

| System (1 run each) | 1b micro P / R / F1 | 1b macro P / R / F1 | 1a micro/macro F1 | DRR (rev) | distinct classes |
|---|---|---|---|---|---|
| DeBERTa baseline | 0.266 / 0.349 / 0.302 | 0.020 / 0.074 / 0.031 | 0.509 / 0.135 | 0.217 (481) | 8 |
| Augmented v1 | 0.306 / 0.296 / 0.301 | 0.019 / 0.055 / 0.026 | 0.509 / 0.135 | 0.136 (303) | 6 |
| Augmented v2 | 0.238 / 0.541 / 0.331 | 0.096 / 0.231 / 0.130 | 0.541 / 0.342 | 0.288 (640) | 50 |
| Liu frozen (LLM) | 0.568 / 0.505 / 0.535 | 0.442 / 0.321 / 0.339 | 0.645 / 0.478 | 0.023 (51) | 88 |
| **Hybrid H2** | 0.504 / 0.590 / 0.543 | 0.402 / 0.381 / **0.360** | 0.660 / **0.504** | 0.036 (79) | 89 |
| **Hybrid H3** | 0.548 / 0.547 / **0.547** | 0.410 / 0.334 / 0.338 | **0.662** / 0.503 | 0.031 (69) | 85 |

**Target-18 group** (`new_check/phase0/outputs/target18_group_metrics.csv`): baseline & v1 predict **nothing** (0 predictions, 140 FN); v2: micro-F1 0.081 / macro-F1 0.036 (12 TP, 146 FP); Liu **without any augmentation**: 0.241 / 0.213; H2 best: 0.254 / 0.229 (35 TP). Non-target-90: v2 improved over baseline (macro 0.038→0.153) — targets did **not** improve at other labels' expense (`nontarget90_group_metrics.csv`).

**Controlled multi-seed cells** (mean over seeds 42–44; `new_check/phase2/outputs/cell_aggregates.csv`, `new_check/phase3/outputs/cell_aggregates.csv`):

| Cell | 1b micro-F1 | 1b macro-F1 | t18 macro-F1 | t18 TP/140 | mean target AUC | DRR |
|---|---|---|---|---|---|---|
| A official only | 0.301 | 0.028 | 0.000 | 0 | 0.513 | 0.158 |
| B +900 assume-neg | 0.311 | 0.089 | 0.011 | 4.7 | 0.624 | 0.282 |
| C +900 masked | 0.310 | 0.047 | 0.002 | 0.7 | 0.577 | 0.220 |
| **F′ +340+900 masked** (= v2 config) | **0.321** | 0.088 | 0.026 | 12.3 | **0.632** | **0.177** |
| G′ +340+900 assume-neg | 0.303 | 0.078 | 0.006 | 2.7 | 0.598 | 0.285 |
| N3 (F′ + 1:3 neg-sampling) | 0.235 | **0.107** | **0.049** | **83** | 0.608 | 0.319 |
| N1 (F′ + 1:1) | 0.143 | 0.042 | 0.034 | 131 | 0.507 | 0.298 |

**Best-performing experiment:** overall system — **Hybrid H3** (1b micro 0.5474), exceeding the strongest non-hybrid baseline (Liu 0.5347) by **+0.0127 micro** (and H2 by +0.0218 macro), *single API pass, unreplicated*; the within-run ablation shows verification is load-bearing (unverified candidates collapse to 0.4057) (`output/research_hybrid_deberta_v2_liu_flash/20260714_184515/report/`). Best *student* single run — **F′ seed 44** (micro 0.358, macro 0.182, 37 target TPs, target AUC 0.747; `new_check/phase3/outputs/per_run_metrics.csv`), +0.056 micro / +0.152 macro over the baseline anchor, but from a wide seed distribution (see §6).

**Explicit conflicts between reports, with causes:**

1. **v2's 0.3306/0.1303** (`…v2_unfiltered/…/metrics/`) vs. **F′ seed 42's 0.3154/0.0587** (identical config+seed; `new_check/phase3/`): CUDA nondeterminism over an ~11-epoch trajectory; v2 is reproducible only *in distribution* (F′ micro 0.290–0.358, macro 0.022–0.182). Historical single-run deltas ≲0.03 micro are within this spread.
2. **Phase-2** "masking is not the active ingredient; assume-negative better" (C−B negative; `new_check/phase2/reports/`) vs. **Phase-3** "masked wins at full data" (`new_check/phase3/reports/`): both correct — a **data-composition × policy interaction**; the 340 single-label records poison assume-negative (same mechanism as v1's macro decline), masking protects.
3. **Critical review's threshold-artifact emphasis** (candidate recall 0.951@0.10; `docs/FEHU_RESEARCH_ROUTE_CRITICAL_REVIEW.md`) vs. **Phase-1** (baseline had *no* latent target signal — AUC 0.536 ≈ chance, max gold prob 0.157; `new_check/phase1/reports/`): the 0.951 figure was direction-neutral and pooled; per-target direction-aware analysis shows a learning failure, only partly a threshold artifact.
4. **Liu's reported 0.5387 and 0.5657**: not reproducible locally / artifacts absent; BLOCKED and excluded from all comparisons (`docs/liu_method_pipeline3_audit.md`, hybrid preflight audit).
5. **METHOD_DESIGN's "a third of L1 labels ≤35 train instances"** (`research/fehu_augmentation_v1/METHOD_DESIGN.md`) vs. actual **10/54** (≤130 is 23/54) — documentation error, flagged in the critical review.

## 5. Effective Findings

- **What works:** the value/direction decomposition with **LLM verification** (largest single verified effect: verified 0.547 vs. unverified 0.406); recall-oriented prompting (V3 variant-B 0.463 > verified ensemble); adding the synthetic data (**score-level** target gains, AUC +0.06–0.11, sign-consistent across seeds in Phases 2–3); masked supervision **when single-label records are present**; per-target 1:3 negative down-sampling **as a recall/macro source** (target recall 0.59, 16/18 targets hit, best mean overall macro 0.107).
- **Did augmentation improve the targets?** Yes at the score level (every augmented cell beats A's chance-level AUC, all seeds); weakly and unstably at the frozen 0.30 threshold (mean 12.3/140 TPs in F′); never near the un-augmented LLM's target performance (Liu 28 TPs, better precision).
- **Masking vs. assume-negative:** neither dominates — data-dependent (conflict #2 above). Masked = high-ceiling/high-variance; assume-negative = low-ceiling/stable.
- **Negative down-sampling:** 1:3 works **by calibration, not learning** (AUC unchanged; scores lifted past 0.30), costing −0.09 micro and worse DRR; 1:1 destroys ranking (AUC → chance). Effective only if paired with per-class threshold/verifier machinery.
- **Trade-off pattern:** every tail intervention so far buys macro/recall with micro-precision and DRR; only the hybrid escapes the trade-off (macro +0.02 *and* micro +0.01 over Liu) because the verifier absorbs precision costs.

## 6. Failures, Problems, and Risks

- **Under-performers:** Augmented v1 (flat/negative; all targets 0 recall); Hybrid v1 (worse than both parents); Pipeline V2 zero-shot (0.398 < few-shot 0.496); N1 down-sampling (destructive); Phase-2 C and Phase-3 G′ (below expectations set by adjacent cells).
- **Engineering/protocol issues (identified, documented):** dev set does triple duty (early stopping, target selection, reporting) in all training runs; historical results are single-seed while measured seed spread is large (masked-family macro SD up to 0.084); GPU nondeterminism breaks exact reproduction of multi-epoch runs; `evaluation.py`'s DRR docstring names directions inversely to `direction_mapping.json` (arithmetic unaffected); V1-era silent-failure bugs (fixed by Pipeline V2); Liu-code defects (direction coercion, dev-fitted add-list — audited, not copied); 512-token truncation hides most of long articles from the student; synthetic data is severely off-distribution (§3).
- **Error structure:** rare-class omission dominates the student (baseline: 140/140 target FNs); augmented/sampled models over-predict (v2: 3,989 non-target FPs; N1: ~7,900 target FPs); DRR worsens under every augmentation (0.16 → 0.22–0.32) — direction remains LLM territory; four targets (0:48, 0:16, 0:19, 1:49) had zero predictions in all historical systems (first hits only in some N3/N1 seeds, at unusable precision).
- **Do not overstate:** the hybrid's +0.0127 over Liu (single API pass; measured cross-machine variance ±0.004; no CIs); any v2-vs-baseline delta (confounded run superseded by Phases 2–3); per-target claims on supports 3–12; F′ seed-44's 0.182 macro (one seed); N3's macro 0.107 (fixed-threshold artifact-prone; micro collapsed); manual-filtering effectiveness (**no human filtering ever occurred** on the 340/900 — `new_check/phase0/outputs/HUMAN_CHECK_REQUIRED.md`, `docs/FEHU_PROFESSOR_FEEDBACK_VALIDATION_PLAN.md` §3).

## 7. Current Research Conclusions

**Experimental facts (multi-seed or within-run ablation):**
- Official-only training cannot learn the 18 targets (0 predictions, chance AUC, 3/3 seeds; Phases 1–2).
- The 900 synthetic records reproducibly improve target score separation under either supervision policy (sign-consistent, 6/6 augmented runs).
- Supervision-policy effect is data-composition-dependent (Phases 2×3).
- LLM verification is load-bearing in the hybrid (0.547 vs. 0.406, same run).
- 1:3 down-sampling shifts calibration (recall 0.59) without improving ranking; 1:1 destroys ranking.
- Thresholded metrics are seed-unstable; multi-epoch runs are only distributionally reproducible.

**Reasonable interpretations:** the 340's single-label records under assume-negative inject false negatives (explains v1 and the G′ gap); assume-negative on multi-label round-2 vignettes supplies approximately-correct negatives (explains B>C); N3-style candidates are promising *hybrid* inputs since the verifier absorbs precision costs; below-chance baseline target AUCs suggest assume-negative actively suppresses rare classes.

**Unverified hypotheses:** the hybrid margin over Liu survives replication; per-class thresholds can keep N3's recall at usable precision; screened round-2 data outperforms unscreened; diagnosis-guided targeting beats untargeted tail generation at equal budget; any of this transfers to the official test set.

## 8. Future Improvement Plan

Independent assessment of what the evidence now makes binding: the project has (a) an unreplicated headline system, (b) a student whose best configurations are unstable and selected on the reporting set, (c) a proven recall source (N3) that is unusable without calibration, and (d) zero test-set exposure. Priorities follow.

**Low-risk, incremental (do first):**
1. **Per-class threshold calibration on an internal train split, applied to existing F′/N3/v2 checkpoints** (no training). *Why:* Phase-3 showed N3's gains are calibration-shaped; the frozen 0.30 rule is provably the wrong instrument. *Evaluate:* target-18 and macro metrics on dev with thresholds tuned only on the internal split. *Supports/rejects:* if N3-with-tuned-thresholds beats F′ on macro without the micro collapse, the recall source is real; if not, N3 is only a hybrid feeder.
2. **Hybrid replication ×3 with candidate-source ablation** (Liu-only vs. v2 vs. F′-seed-44 vs. N3 candidates; ~4×177 calls). *Why:* the thesis headline currently rests on one API pass; Phase-3 produced two candidate sources predicted to beat v2's. *Evaluate:* mean ± bootstrap CI vs. Liu; target-18 group metrics. *Supports/rejects:* CI excluding zero validates the system claim; candidate-source ranking tests whether student improvements matter downstream (assumption A5, still open).
3. **Stabilization study of the masked family:** 5–7 more F′ seeds + macro-aware checkpoint selection on the internal split. *Why:* F′'s collapse/peak bimodality (epoch-1 collapses in 2 of 6 masked-family runs) is the main obstacle to any student claim. *Evaluate:* distribution of macro/AUC; collapse frequency under each selection rule.
4. **Fable-5 semantic screening of the 900 → retrain F′-screened** (1 screening pass + 3 runs). *Why:* the trained models contain unscreened data; screening effect is unmeasured (professor's question). *Evaluate:* screened vs. unscreened at matched size (with a size-matched random control).

**Higher-risk, exploratory (only after 1–3):**
5. **Longer-input student** (max_length 1024 or evidence-sentence selection): attacks the 512-token truncation (median article ~3.3k chars) — plausible recall ceiling contributor never tested; evaluate as a single-factor change on cell A and F′.
6. **Teacher-annotation distillation on real articles** (Liu labels → masked student training): eliminates the synthetic distribution shift by construction; compare against generation at matched budget (generation-vs-annotation is a publishable axis).
7. **Entailment/description-based per-(actor, value) scorer** as an alternative candidate generator: frequency-independent tail handling; pilot on the internal split before any commitment.

Ideas from earlier reports that the evidence has **demoted**: global threshold sweeps alone (Phase 1 showed no latent baseline signal to recover); further un-screened generation rounds (data quality/shape now the binding issue); 1:1 negative sampling (destructive); pursuing Liu's 0.5657 (unauditable).

## 9. Final Project Status

**Completed:** V1–V3 prompt pipelines with tests; label diagnosis; two augmentation rounds (340 screened, 900 unscreened); v1/v2 trainings; frozen Liu reference; hybrid H0–H3 with ablations; full validation program Phases 0–3 (recomputation, baseline probability export, controlled A/B/C, full-data F′/G′, negative-sampling N3/N1 — 21 controlled training runs, all probability-validated); critical review and professor-feedback validation plan.

**In progress:** nothing running; open analysis threads = per-class threshold calibration (§8.1), hybrid replication (§8.2).

**Not yet started:** internal-validation-split protocol in trainers; screening of the 900; multi-pass hybrid CIs; Task-2; **any test-set run or submission**; thesis writing consolidation.

**Single most important next step:** run §8.1 + §8.2 together — per-class thresholds on the existing checkpoints, then a ×3-replicated hybrid with the best resulting candidate source. It is cheap, uses only existing artifacts plus ~700 API calls, and simultaneously (i) decides whether the student line contributes anything downstream and (ii) puts a confidence interval under the thesis's headline number.

---

## Professor-Ready Progress Summary

We completed a four-phase controlled validation of the augmentation pipeline. Separate evaluation of the 18 augmented target labels shows: the official-data model never predicts them (zero predictions, chance-level AUC, confirmed across 3 seeds); adding our 900 generated samples reproducibly improves target score separation under both supervision policies (AUC +0.06–0.11, sign-consistent), though fixed-threshold gains remain small. We found a data-dependent interaction: assume-negative supervision is better for the 900 alone, but masked supervision wins once the 340 single-label samples are included. Target-class negative down-sampling at 1:3 raises target recall to 0.59 and macro-F1 to 0.107 — but by calibration, not better ranking — while 1:1 destroys learning; this addresses your 50:50 suggestion. Important correction: no manual filtering was ever applied to the 900 (automated checks only), so its effectiveness is untested; we have designed that experiment. Our best system remains the DeBERTa×LLM hybrid (micro-F1 0.5474 vs. 0.5347 for the strongest LLM), pending replication. Historical single-seed results proved only distributionally reproducible, so all new conclusions use 3 seeds. Next: per-class threshold calibration and a replicated hybrid with the new candidate sources. (~190 words)
