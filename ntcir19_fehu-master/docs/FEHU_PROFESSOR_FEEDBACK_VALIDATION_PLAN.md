# FEHU Professor-Feedback Validation Plan

**Document date:** 2026-07-19
**Repository state:** branch `sync-safe-fehu-dra-20260705`, HEAD `6b6f4cc` (working tree clean)
**Companion documents:** `docs/FEHU_PROJECT_RESEARCH_SUMMARY.md` (project state), `docs/FEHU_RESEARCH_ROUTE_CRITICAL_REVIEW.md` (route-level critique)
**Nature of this document:** planning and diagnosis only. No source code, dataset, prompt, metric, or experiment artifact was modified; no training, inference, or API call was executed in its preparation. Every quantitative statement below is read or recomputed from existing repository artifacts, with paths given.

---

## 1. Executive Summary

The professor's five comments translate into five concrete validation obligations:

1. **Target-vs-non-target evaluation** — report precision/recall/F1 for the 18 augmented target labels separately from the other labels. *Partially answerable today by recomputation*: a per-target table already exists (`output/research_augmented_deberta_v2_unfiltered/20260714_032758/metrics/target_label_metrics.csv`), but group-level micro/macro aggregates, false-negative counts, non-target group metrics, and direction-reversal detail must be recomputed from the stored prediction files. No new training is needed for this item.
2. **Full macro and micro P/R/F1** — the official evaluator (`evaluation.py`) reports macro-**F1** only; macro precision and macro recall have never been computed anywhere in the repository. This is a pure recomputation task from existing predictions.
3. **Manual-filtering effectiveness** — **cannot be answered, because no manual (human) filtering was ever applied to the 900 samples.** The 900 passed automated structural validation only; the earlier 340 passed automated LLM screening; the only human-reviewed pool (6 records) is not part of any v1/v2 training set. §3 prepares the honest clarification and §11 designs the controlled experiment that would be required if the professor wants this question answered.
4. **Positive–negative ratio** — under the current 108-class multi-label encoding, each target label trains at a known-positive : known-negative ratio between roughly **1:29 and 1:475** (before augmentation) and roughly **1:30 to 1:60** (after), nowhere near 50:50. §9 interprets the professor's comment for the multi-label setting and designs per-class negative down-sampling experiments using the existing loss-mask machinery.
5. **Room for improvement on the 18 labels** — deliberately out of scope here per instruction; §14 notes what to say, and the route-level options are already catalogued in `FEHU_RESEARCH_ROUTE_CRITICAL_REVIEW.md` §7.

The central structural problem is that **the existing baseline-vs-augmented comparison changes two factors at once** (adding 1,240 synthetic records *and* switching synthetic-label supervision to masked loss) **on a single seed**, so no current result isolates the effect of the 900 samples. §8 specifies the minimum factorized ablation (≈12 local GPU runs, ~10 min each, no API cost) that makes the professor's first question answerable with a causal interpretation.

---

## 2. Interpretation of the Professor's Feedback

Original comments, with this plan's reading of each. One wording issue is flagged rather than silently corrected.

| # | Professor's comment (verbatim) | Interpretation | Where addressed |
|---|---|---|---|
| P1 | "You generated 900 augmented samples for 18 selected labels. Please evaluate precision/recall/F1 on these 18 labels separately from other labels. Check precisely the effect of your augmentation on the target labels." | Produce a three-way split evaluation (18 targets / remaining labels / all labels) for every compared system, with per-target detail, and establish whether target gains are attributable to the augmentation rather than to simultaneous changes. | §7, §8, tables T2–T4, T6 |
| P2 | "Please show macro precision, macro precision, macro F1. Of course also micro-PR, RC, F1." | **Interpretation, marked as such:** the repeated phrase "macro precision, macro precision, macro F1" is read as *macro precision, macro **recall**, macro F1* — i.e., all six of {macro, micro} × {P, R, F1}. This reading should be confirmed with the professor, but it is the only self-consistent one. Note the official evaluator computes macro-F1 only (mean of per-label F1 over gold-supported labels, `evaluation.py:123–155`); macro-P/macro-R require a supplementary script. | §7, all tables |
| P3 | "Manual filtering of samples are effective?" | The professor believes manual filtering was applied to the 900. **It was not** (see §3). The honest answer distinguishes the automated procedures that *were* applied from human review that was not, and proposes a controlled experiment if the question must be answered empirically. | §3, §11, table T8 |
| P4 | "Usually, finetuning samples are roughly 50:50 positive-negative ratio... Maybe you need to down-sample negative cases." | Read as a concern about per-label negative dominance during fine-tuning. In a 108-class multi-label encoding the *global* dataset cannot and should not be 50:50; the actionable reading is per-target-label positive:negative balance in the loss, addressed by per-class negative down-sampling/masking experiments. | §9, tables T5, T6 |
| P5 | "Perhaps there would be still room for improvement on the 18 labels. What approaches are possible?" | A request for forward-looking options. Out of scope for this validation plan by instruction; the within-scope partial answers are the threshold/calibration analysis (§10) and negative-sampling study (§9); the broader option catalogue exists in the critical review (§7 there). | §14 |

---

## 3. Clarification About Manual Filtering

### 3.1 What was actually applied to each dataset (from run artifacts)

| Dataset | Deterministic structural validation | Automated LLM checks | AI (LLM) semantic screening | **Human manual review** |
|---|---|---|---|---|
| Verified pilot pool (**6** records; `output/research_verified_candidates/20260702_165107/`) | Yes | Yes | Yes | **Yes — human ACCEPT decisions.** *Not part of any v1/v2 training set* (used only in the +6 smoke run) |
| Round-1 silver (**340** of 422; `output/research_first_round_ai_filtered_augmentation/20260712_214315/`) | Yes (3,798 checks, 0 FAIL) | Yes (67 generation-time rejects) | **Yes — Fable 5 screening: 337 KEEP / 3 LIGHT_REPAIR / 82 DROP** | **No** |
| Round-2 (**900**; `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/`) | Yes (all 900 pass; 472 candidates rejected at generation time by structural gates) | Yes (structural gates only) | **No — explicitly not run** (`07_structural_stage_report.md`: "Fable 5 semantic screening has NOT been run … not human-verified gold data") | **No** |

### 3.2 What can honestly be said

- **No systematic human manual filtering experiment was ever conducted on the 340 or the 900.** The trained models (Augmented v1, Augmented v2-Unfiltered) contain **zero human-reviewed synthetic records**.
- Therefore the effectiveness of manual filtering **cannot be evaluated from existing results, and no claim about it should be made** — positive or negative.
- What existing results do evaluate: (v1) machine-generated + machine-screened data; (v2) additionally machine-generated, *structurally validated but semantically unscreened* data. Even the effectiveness of the **automated** screening is currently unmeasured, because no model was trained on the unscreened 422 (round 1) or on a screened version of the 900 — there is no screened-vs-unscreened training pair anywhere.

### 3.3 Recommended response to the professor

> "We must correct a misunderstanding from the presentation: the 900 round-2 samples were validated only by automated structural checks; no human manual review and no LLM semantic screening was applied to them. An earlier, smaller round (340 samples) was screened automatically by an LLM verifier, and only a 6-sample pilot pool was human-reviewed — those 6 are not in the training data of the models we showed. Consequently we cannot yet report whether manual filtering is effective; we propose a controlled filtering experiment (§11) if this question should be answered empirically."

---

## 4. Reconstruction of Existing Experiments

The two runs currently treated as "baseline" and "augmented" for the 900-sample question, reconstructed from run configs, scripts, and reports. Facts verified directly in `src/train_deberta.py`, `output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_deberta_masked_v2.py`, and the two runs' inputs/metrics folders.

| Factor | **Baseline** (`output/research_ablation_smoke_runs/20260704_201355/baseline/`) | **Augmented v2-Unfiltered** (`output/research_augmented_deberta_v2_unfiltered/20260714_032758/`) | Also relevant: **Augmented v1** (`output/research_augmented_deberta_v1/20260712_231751/`) |
|---|---|---|---|
| Training data | Official only: 1,228 articles / 3,335 actor examples | Official + 340 (round-1 silver) + 900 (round-2 raw) = 2,468 articles / 4,575 actor examples | Official + 340 = 1,568 articles |
| Synthetic samples | 0 | 1,240 (340 AI-screened; 900 unscreened) | 340 (AI-screened) |
| Loss | BCEWithLogits, `sqrt(neg/pos)` pos-weight clamped [1,10] | Same base loss, **element-wise loss masks**: 3,785 examples fully supervised (3,335 official + 450 round-2 `full_multilabel`), **790 `target_only`** (340 round-1 + 450 round-2) supervised only on known positives + 36 records' known negatives; all other entries contribute no gradient. Pos-weight computed on masked counts. | Plain BCE — synthetic labels treated as **complete** (all unlisted classes = negative) |
| Positive/negative construction | Gold labels positive; **all** other 108-dim entries negative ("assume negative") | Official + `full_multilabel`: assume negative. `target_only`: unlisted entries **unknown (masked)**, not negative | Assume negative everywhere, incl. single-label synthetic records |
| Model | DeBERTa-v3-base + LoRA r=16/α=32/do=0.1, 108-way sigmoid head, max_length 512 | identical | identical |
| Seed | 42 (single) | 42 (single) | 42 (single) |
| Epochs / stopping | ≤15, patience 4; best epoch **1** | ≤15, patience 4; best epoch **11** | best epoch **1** |
| Checkpoint selection | **dev Task-1b micro-F1** (`src/train_deberta.py:471–474`) | same | same |
| Threshold | global 0.3 | global 0.3 | global 0.3 |
| Evaluation set | official dev (177 articles), official `evaluation.py` | same | same |
| Reports | `comparison.csv` rows reused as anchor | `metrics/{comparison.csv, final_metrics.json, target_label_metrics.csv}`, `report/` | `report/`, `metrics/` |

**Conclusion of the reconstruction:** the baseline→v2 comparison changes **at least two substantive factors simultaneously** — (i) training data (+1,240 records, of two different provenances and screening levels) and (ii) the supervision policy for synthetic labels (assume-negative vs. masked partial-label). A third emergent difference (training trajectory: best epoch 1 vs. 11) follows from these. **The existing result therefore cannot isolate the effect of the 900 augmented samples**, and no statement of the form "the 900 samples improved/did not improve the targets" is currently justified. This must be said plainly to the professor (§14).

A subtle but important design fact: with official data only, the masked trainer's masks are all ones and it **reduces exactly to the original trainer** (docstring and code of `train_deberta_masked_v2.py`). So "loss function" is not an independent factor on official-only data; the real second factor is *how synthetic labels are supervised*. §8 exploits this.

---

## 5. Definition of the 18 Target Labels

Source of record: `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/02_selected_targets_and_allocation.json`, cross-checked against `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/05_historical_18_targets.csv` and the v2 run's `metrics/target_label_metrics.csv`. All three agree.

- Each target is a **direction-aware class** `direction:l1_value` in the 108-class Task-1b space (the evaluator's internal `"{direction}:{l1}"` encoding) — **not** a bare L1 value. 14 are contradictory-direction, 4 aligned. Aligned and contradictory classes of the same L1 (e.g., 0:31 and 1:31) are distinct targets and must not be merged in any target-level analysis.
- Each target received exactly **50 generated records as its primary target** (18 × 50 = 900). In addition, because 450 records are multi-label (`full_multilabel`, 2–4 labels each), targets appear as secondary labels in other targets' records. Actual added positive counts (recomputed from `inputs/augmented_train_human_values_v2.json` + `supervision_map.json` of the v2 run) appear below.

| Target | L1 name | Train support (official) | Added positives (round-2: full / target_only) | Total v2 positives | Dev gold support | Baseline recall | v2 recall (existing, confounded) |
|---|---|---|---|---|---|---|---|
| 0:31 | Be self-disciplined | 7 | 32 / 23 | 62 | 3 | 0.0 | 0.0 |
| 0:48 | Have harmony with nature | 12 | 25 / 18 | 55 | 3 | 0.0 | 0.0 |
| 0:53 | Have an objective view | 14 | 25 / 19 | 58 | 6 | 0.0 | 0.0 |
| 1:31 | Be self-disciplined | 27 | 25 / 23 | 75 | 8 | 0.0 | 0.0 |
| 0:16 | Have influence | 33 | 29 / 19 | 81 | 5 | 0.0 | 0.0 |
| 1:10 | Have pleasure | 35 | 26 / 18 | 79 | 5 | 0.0 | 0.200 |
| 0:19 | Have social recognition | 38 | 27 / 20 | 85 | 6 | 0.0 | 0.0 |
| 0:20 | Have a good reputation | 40 | 85 / 19 | 144 | 6 | 0.0 | 0.0 |
| 1:49 | Have a world of beauty | 40 | 25 / 18 | 83 | 6 | 0.0 | 0.0 |
| 0:13 | Be capable | 45 | 27 / 18 | 90 | 5 | 0.0 | 0.0 |
| 0:37 | Be helpful | 46 | 31 / 18 | 95 | 9 | 0.0 | 0.0 |
| 0:29 | Be holding religious faith | 46 | 25 / 19 | 90 | 7 | 0.0 | 0.286 |
| 1:4 | Be independent | 51 | 29 / 18 | 98 | 9 | 0.0 | 0.0 |
| 0:2 | Have freedom of thought | 51 | 25 / 19 | 95 | 7 | 0.0 | 0.429 |
| 0:33 | Be polite | 56 | 29 / 19 | 104 | 12 | 0.0 | 0.083 |
| 0:32 | Be behaving properly | 59 | 27 / 20 | 106 | 10 | 0.0 | 0.0 (18 predictions, 0 TP) |
| 0:40 | Have the own family secured | 76 | 25 / 18 | 119 | 12 | 0.0 | 0.0 |
| 0:28 | Be respecting traditions | 128 | 30 / 19 | 177 | 21 | 0.0 | 0.238 |

Notes: (i) *added positives* counts above include only round-2 records — the round-1 340 target six different L1 values (22, 30, 38, 12, 5, 46 × both directions) that do not overlap the 18; (ii) all 18 targets have dev support ≥3 by construction of the selection rule, so none has zero dev support, but supports of 3–12 mean single predictions move per-target recall by 0.08–0.33 — every per-target delta must be reported with raw counts, not only rates; (iii) 0:20's larger added count (85 full-multilabel positives) comes from frequent co-occurrence as a secondary label — worth remembering when interpreting per-target dose–response.

---

## 6. Existing Evidence and Current Confounds

### 6.1 What existing artifacts already contain

| Question | Artifact | Status |
|---|---|---|
| Per-target TP/pred/P/R/F1 for baseline, v1, v2 | `…v2_unfiltered/20260714_032758/metrics/target_label_metrics.csv` | **Exists** (shown in §5); lacks FN column (derivable: FN = support − TP), group aggregates, and reversal info |
| Overall 1a/1b micro-F1, macro-F1, P, R, DRR for the three runs | same run, `metrics/comparison.csv`, `final_metrics.json` | **Exists**; macro-P/macro-R absent (evaluator computes macro-F1 only) |
| Per-class P/R/F1 for 108 classes, all seven *early* systems | `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/per_class_108_metrics.csv` | Exists, but **does not cover v1/v2/hybrid** |
| Dev per-actor probability vectors for **v2** (all 108 classes) | `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/02_deberta_actor_probabilities.jsonl` | **Exists** — enables threshold analysis for v2 without any new inference |
| Candidate recall at thresholds 0.10/0.20/0.30 for v2 | same run, `03_deberta_candidate_diagnostics.csv` | Exists (0.951 / — / 0.613 direction-neutral recall) |
| Prediction files for baseline / v1 / v2 / Liu / hybrids | respective run folders' `predictions/` and numbered JSONs | Exist — all group/macro recomputation possible |
| Probability vectors for the **baseline** model | not exported | **Missing** — requires one local re-inference pass from the stored baseline checkpoint (minutes; no API) |

### 6.2 Confounds in the current comparison (explicit list)

1. **Data × supervision-policy confound** (§4): +1,240 records and masked loss introduced together. *Blocks any causal claim about the 900.*
2. **Mixed provenance within the added data**: the 1,240 = 340 AI-screened + 900 unscreened; effects of the 900 alone are additionally entangled with the 340.
3. **Single seed (42) everywhere**; the repository's own reports document that DRR and trajectory-sensitive metrics move substantially across epochs within one seed. No variance estimate exists for any delta.
4. **Checkpoint selection and early stopping on the dev set that is also the reporting set** (`src/train_deberta.py:471`), for every run. Group-level target metrics are therefore mildly optimistic for all systems, and any *new* threshold tuning on dev would compound the leakage (§10).
5. **Fixed global threshold 0.3** never swept for baseline or v1; v2 evidence (0.951 candidate recall at 0.10) shows the decision rule, not only learning, governs target recall.
6. **Target selection itself used dev statistics** (dev support ≥3, dev recall = 0), so the 18-target set is not independent of the evaluation data; per-target dev gains should be interpreted as *diagnostic*, with the official test phase as the eventual confirmatory set.

---

## 7. Target-vs-Non-Target Evaluation Protocol

This protocol answers P1 + P2. It is **pure recomputation** over existing prediction files (plus the official gold), implemented as a new standalone analysis script in a new timestamped output folder; `evaluation.py` itself is not modified.

### 7.1 Label groups

- **G_target**: the 18 direction-aware classes of §5.
- **G_nontarget**: the remaining 90 of the 108 classes.
- **G_all**: all 108 (equals the official evaluation universe).

### 7.2 Metrics per group — exact definitions

For each system and each group *G*, count per label *ℓ* ∈ *G* over all dev instances: TP(ℓ), FP(ℓ), FN(ℓ) (an FP of a label outside *G* does not enter *G*'s table).

- **Micro-P** = ΣTP / (ΣTP + ΣFP); **Micro-R** = ΣTP / (ΣTP + ΣFN); **Micro-F1** harmonic mean — sums over *G* only.
- **Macro-P / Macro-R / Macro-F1** = unweighted means over labels of per-label P, R, F1, where per-label P = TP/(TP+FP) with the official `safe_div` convention (0 when the denominator is 0), R = TP/(TP+FN), F1 from per-label P and R (not from the macro-P/macro-R pair).
- **Macro averaging population — two variants, both reported:**
  - *(a) Gold-supported* (official convention, matches `evaluation.py`): average only over labels with dev gold support ≥1. On dev this is 18/18 targets (all have support) and 75 gold-supported non-targets; 15 classes have zero dev gold.
  - *(b) Full-universe*: average over all labels in *G*, counting zero-gold labels as R = 0-denominator cases. **Recommendation: report (a) as headline (comparable to official macro-F1) and note (b) is dominated by structural zeros.** For zero-gold labels the meaningful quantity is their FP count, reported separately (they inflate micro-FP but are invisible to gold-supported macro). This distinction must be stated when presenting to the professor, since "macro precision" over labels with no gold is ill-defined.
- **DRR by group**: the official DRR is defined over gold L1 values with a unique gold direction, not over direction-aware classes; report, per group, the count of reversals whose gold class falls in the group, alongside the official overall DRR (denominator 2,222). A per-group "DRR" rate should use as denominator the gold-exclusive values whose directed class is in the group.

### 7.3 Per-target detail (Table T4)

For each of the 18 targets and each compared system: dev gold support, predicted positives, TP, FP, FN, P, R, F1, Δ vs. baseline (in counts *and* rates), reversal count for the target's L1 (gold direction = target's direction, predicted opposite). Raw counts are mandatory because supports are 3–21.

### 7.4 Systems to include in the recomputation

Minimum: baseline, Augmented v1, Augmented v2-Unfiltered. Recommended additions (same script, zero extra cost): Liu frozen (H0) and hybrid H2/H3, since the professor will reasonably ask whether target gains survive into the best system; the hybrid run's `18_per_label_comparison.csv` already contains much of this and should be cross-checked, not duplicated.

---

## 8. Controlled Augmentation Ablation

### 8.1 Design

The professor's "check precisely the effect of your augmentation" requires a factorized design. Because masked loss ≡ original loss on official-only data (§4), the honest factors are **(data added)** × **(synthetic-label supervision policy)**:

| Condition | Training data | Synthetic-label policy | Status |
|---|---|---|---|
| A | Official only | — (policy vacuous; original trainer) | Exists at seed 42; rerun at 2 further seeds |
| A′ | Official only | masked trainer, all-ones masks | 1 run, equivalence check vs. A (should match up to nondeterminism) |
| B | Official + **900 only** | assume-negative (synthetic labels treated as complete) | **New** |
| C | Official + **900 only** | masked (`target_only` masked as designed; `full_multilabel` fully supervised) | **New — this is the cell that isolates the professor's question** |
| D | Official + 340 | assume-negative | Exists at seed 42 (= Augmented v1); rerun 2 seeds |
| E | Official + 340 | masked (340 as `target_only`) | **New** |
| F | Official + 1,240 | masked | Exists at seed 42 (= Augmented v2); rerun 2 seeds |
| G (optional) | Official + 1,240 | assume-negative | New; completes the 2×2 at full data |

### 8.2 What each contrast estimates

- **Augmentation main effect (the professor's question):** C vs. A (masked, 900 only) and B vs. A (assume-negative, 900 only) — each isolates the 900 records under one fixed supervision policy, uncontaminated by the 340.
- **Supervision-policy (masked-loss) main effect:** C vs. B (at +900) and E vs. D (at +340) and G vs. F (at +1,240).
- **Interaction:** (C−A) − (B−A) = C − B compared across data levels; if masked supervision only matters in the presence of target-only records (as the design predicts), the interaction term carries the story.
- **Provenance decomposition:** F vs. C (marginal value of the 340 on top of the 900) and F vs. E (marginal value of the 900 on top of the 340).

### 8.3 Held-constant protocol

Same base model and LoRA config; same preprocessing and max_length; same epoch budget (≤15, patience 4); same threshold policy; same evaluation. Two protocol changes apply to **all** cells equally (so comparisons remain internally valid) and fix documented leakage:

1. **Checkpoint selection on an internal validation split**, not dev: carve ~15% of official *train* articles (stratified so each of the 18 targets keeps ≥1 positive in the remaining train portion where possible; targets with <7 positives may be exempted from stratification and flagged). Dev is used for final reporting only.
2. **Two decision rules reported for every cell:** (i) frozen global 0.3 (continuity with all prior reports) and (ii) per-label thresholds tuned on the internal split (§10). Never tune on dev.

**Seeds: minimum 3** (42 plus two new, e.g., 43/44), identical seed set for every cell. Summarize each metric as mean ± SD over seeds, with per-seed paired deltas (same seed, different cell) and the sign-consistency of the delta across seeds; with n=3, present this as descriptive consistency evidence, not p-values. Cost: 8 cells × 3 seeds ≈ 24 runs ≈ 4–5 GPU-hours on the RTX 4090 (≈10 min/run at current settings); A′ needs 1 run. If budget must be cut, the priority order is: C, A, B (3 seeds each) > F, E > D, G.

---

## 9. Positive–Negative Imbalance Analysis

### 9.1 Current construction (from code)

`src/train_deberta.py::build_examples`: each training example is one (article, actor) pair with a 108-dim binary vector; gold labels are positives and **every other class is a training negative** (assume-negative), except in the masked trainer where `target_only` records leave non-target classes **unknown** (no gradient) and 36 `hard_negative` records add explicit known negatives. Imbalance is mitigated only by `pos_weight = sqrt(neg/pos)` clamped to [1,10] — for the 18 targets the true neg/pos ratios (25–475) imply desired weights of 5–22 before sqrt/clamp, so the clamp binds for the rarest targets.

### 9.2 Ratios (computed for this plan; to be finalized as Table T5 by script)

- **Global, official data:** 3,335 examples × 108 = 360,180 label slots; 16,905 positive → ≈ **1 : 20** positive:negative overall.
- **Per target, official (before augmentation):** positives 7–128 vs. ≈3,335 known negatives → **1:475 (0:31) to 1:29 (0:28)**.
- **Per target, v2 (after augmentation):** positives 55–177 (Table §5); known negatives ≈ 3,785 fully-supervised examples minus the target's positives among them, plus the few explicit known negatives; unknown (masked) slots ≈ 790 minus the target's own `target_only` records. Representative: 0:31 → 62 : ~3,750 known-neg : ~770 unknown ≈ **1:60**. Exact per-target numbers must be emitted by the T5 script directly from `supervision_map.json` + the v2 label file, distinguishing **positive / known-negative / unknown-masked** counts — the three-way distinction is mandatory and must never collapse unknown into negative.
- **Interpretation of "roughly 50:50":** the professor's heuristic comes from single-task binary fine-tuning. In a 108-class multi-label problem, forcing the *global* slot ratio to 50:50 would require discarding ~95% of negative supervision and is neither standard nor desirable. The defensible reading: **per-label effective balance in the loss** should be much closer to parity than 1:60–1:475. This can be achieved without deleting examples, via the existing mask machinery.

### 9.3 Proposed negative down-sampling experiments (new runs, local only)

Implementation principle: down-sampling must be **per-class and loss-level**, not example-level — removing whole examples to balance one class would distort all 107 other classes. The masked trainer already supports element-wise masks, so "down-sample negatives for class ℓ" = randomly zero the loss mask on a fraction of ℓ's known-negative slots (per epoch or fixed per seed; fixed is more reproducible).

| Condition | Per-target effective ratio | Notes |
|---|---|---|
| N0 | current (no negative sampling) | = cell C or F of §8, shared runs |
| N1 | 1 : 3 known negatives per target class | negatives sampled uniformly at random among known negatives |
| N2 | 1 : 1 | professor's suggestion, taken literally per class |
| N3 (optional) | 1 : 3 with half the retained negatives drawn from *hard* negatives (same L2 family or high co-occurrence with the target) | separates "fewer negatives" from "better negatives" |

Design decisions, stated explicitly: (i) sampling applies **only to the 18 target classes** in the first round (target-specific; non-target classes keep full supervision) — a global variant is a follow-up only if target results are positive; (ii) only **training** loss is affected — dev evaluation is untouched; (iii) **unknown ≠ negative** throughout: masked slots are never eligible for "sampling" since they were never supervised; (iv) 3 seeds, same protocol as §8. **Calibration caveat:** down-sampling negatives raises the target classes' output probabilities by construction, so fixed-0.3 results will mechanically shift; N-runs must therefore be read primarily under the internal-split-tuned per-label thresholds (§10), and the fixed-0.3 numbers labeled as calibration-confounded.

---

## 10. Threshold and Calibration Analysis

Purpose: decide how much of the 18-target failure is **learning failure** (targets never separate from noise in score space) vs. **decision-rule failure** (scores present but below 0.3) vs. **calibration failure** (scores systematically compressed) vs. **negative dominance** (addressed jointly with §9).

### 10.1 Recomputation available today (no training, no inference)

Using `02_deberta_actor_probabilities.jsonl` (v2 model, dev): global threshold sweep (0.05–0.5), per-label oracle-best thresholds, per-target score distributions (max score per gold-positive instance vs. distribution over negatives), and rank-based diagnostics (median rank of each target among the 108 scores on its gold instances). **Leakage label:** any threshold *chosen* on dev and *evaluated* on dev is a diagnostic upper bound, not a performance claim; every such number must carry an explicit "dev-tuned (oracle)" tag. The corresponding honest protocol for performance claims is tuning on the internal split (§8.3) — available only for the new runs.

### 10.2 Diagnostic decision tree per target

For each target ℓ, with dev-gold instances I⁺(ℓ):
1. If scores on I⁺(ℓ) are indistinguishable from ℓ's negative-instance score distribution (e.g., AUC ≈ 0.5) → **not learned**; augmentation/data conclusions apply.
2. If scores on I⁺(ℓ) separate but sit below 0.3 (AUC high, oracle threshold ≪ 0.3 recovers R > 0) → **decision-rule artifact**; the professor's target-recall question is then partly answerable without new data at all.
3. If separation exists at some threshold but per-label oracle F1 remains near 0 due to mass FPs → **calibration/precision failure**; connects to §9 (negative sampling raises scores) and to verifier-based filtering downstream.

The same analysis for the **baseline** model requires exporting its dev probabilities: one local inference pass from the stored baseline checkpoint (`output/research_ablation_smoke_runs/20260704_201355/baseline/`) — minutes of GPU, no API; classified as a new (cheap) run in §13, and required before claiming that the baseline "failed to learn" the targets rather than merely thresholding them away.

### 10.3 Reporting

Table/curve T7: for each of {baseline, v2} (and later each §8 cell): target-18 micro/macro R and P as functions of global threshold; per-target oracle threshold and oracle F1 (dev-tuned, flagged); internal-split-tuned per-label thresholds and their dev performance (claimable). Include distinct-class count and overall micro-F1 at each threshold so precision collapse is visible.

---

## 11. Manual-Filtering Validation (Proposed Experiment — Not an Existing Result)

Only if the professor confirms the question matters after §3's clarification. Design goals: measure filtering-quality effects **without confounding dataset size**, and position human review against the existing automated procedures.

### 11.1 Arms (all trained under the §8 protocol, masked supervision, 3 seeds)

| Arm | Training addition (on top of official) | Size |
|---|---|---|
| M0 | none (baseline) | 0 |
| M1 | 900 unscreened (structural only) | 900 |
| M2 | AI-screened subset of the 900 (Fable-5 semantic screening, same rubric as round 1) | n₂ (outcome of screening; expected ~80% by round-1 precedent) |
| M3 | **Human-reviewed** subset: stratified sample of the 900 (e.g., 10 per target = 180) reviewed by a human annotator with ACCEPT/REPAIR/REJECT decisions; ACCEPTed records train | n₃ ≤ 180 |
| M4 | Random subset of the 900, **size-matched to n₃**, same per-target stratification, no quality selection | n₃ |
| M5 (optional) | Random subset size-matched to n₂ | n₂ |

### 11.2 Confound controls

- **Size vs. quality:** M3 vs. M4 (equal n, equal stratification) isolates human selection quality; M2 vs. M5 does the same for AI screening. M1 vs. M2 alone confounds size with quality and must not be interpreted causally without M5.
- **Reviewer independence:** the human reviewer must not see model predictions or dev data; review criteria = the round-1 screening rubric (label correctness, direction correctness, evidence support, non-redundancy) for comparability.
- **Cheap high-value byproduct:** human-vs-AI agreement (Cohen's κ on the 180 double-screened records) quantifies whether the automated screening approximates human judgment — this may answer the professor's real question ("can we trust unscreened/auto-screened data?") at a fraction of the training cost.
- Costs: one Fable-5 screening pass over 900 records (LLM, no training); ~180-record human review (hours of annotator time); 4–6 training cells × 3 seeds locally.

---

## 12. Required Tables and Figures

| # | Table/Figure | Rows | Columns | Compared experiments | Metrics | Interpretation question |
|---|---|---|---|---|---|---|
| T1 | Overall Task-1b comparison | one per system/cell (mean ± SD over seeds) | micro-P/R/F1, macro-P/R/F1 (gold-supported), DRR (+count), distinct classes, best epoch | §8 cells + existing anchors | all six P/R/F1 + DRR | Do overall metrics move, and at what precision cost? |
| T2 | Target-18 group metrics | systems/cells | group micro-P/R/F1, macro-P/R/F1, ΣTP/ΣFP/ΣFN, group reversal count | same | §7.2 definitions | Did the target group improve? |
| T3 | Non-target group metrics | systems/cells | same as T2 + FP count on zero-gold labels | same | same | Were non-targets harmed (the professor's "at the expense of" concern)? |
| T4 | Per-target 18-label table | 18 targets | support, pred, TP, FP, FN, P, R, F1, Δcounts vs. A, reversals — per system | A vs. C (headline), then F | raw counts mandatory | Which targets moved, by how many instances? |
| T5 | Positive–negative ratio table | 18 targets (+ global row) | positives / known-neg / unknown-masked, ratios before & after augmentation, effective ratio under N1/N2 | data conditions | counts + ratios | Is the professor's imbalance concern quantitatively confirmed? |
| T6 | Data × supervision ablation | §8 cells A–G | T1 columns + target-18 micro/macro from T2 | 3 seeds each | mean ± SD, paired per-seed Δ | Augmentation main effect, policy main effect, interaction |
| T7 | Threshold sensitivity | thresholds 0.05–0.5 (+ per-label tuned rows) | target-18 R/P/F1, overall micro-F1, distinct classes; per-target oracle threshold | baseline & v2 (then all cells) | flag dev-tuned as oracle | Learning failure vs. decision-rule artifact |
| T8 | Filtering status & ablation | datasets (6 / 340 / 900) then arms M0–M5 | validation applied (structural/AI/human), n, and after runs: T2 metrics | §11 | status columns are factual today; metric columns are *proposed* | What filtering exists; is human filtering worth it? |
| T9 | Error-category summary | systems/cells | omissions (gold FN) split target/non-target, FPs split target/non-target/zero-gold, direction reversals split by group | A, C, F | counts | Which error type dominates and which the augmentation shifts |
| F1 | Per-target score distributions (figure) | 18 panels | score histograms: gold-positive vs. negative instances, thresholds marked | baseline vs. v2 | — | Visual verdict on learned-but-thresholded-away |

---

## 13. Step-by-Step Validation Execution Plan

**Phase 0 — Recomputation only (no training, no API; ~1 day).**
1. New analysis script (new output folder) computing §7 group metrics + macro-P/R for baseline/v1/v2 (+Liu, H2/H3) from existing prediction files → T1–T4, T9 (existing-systems columns).
2. T5 ratio table from `supervision_map.json` + label files.
3. v2 threshold/calibration analysis from the exported probabilities → T7 (v2 columns), F1 (v2 half).
4. Draft the manual-filtering clarification (§3) and T8 status columns.
*Exit criterion: every professor question answerable from existing artifacts is answered, with confounds labeled.*

**Phase 1 — Cheap local inference (minutes).**
5. Export baseline dev probabilities from the stored checkpoint → complete T7/F1 baseline columns.

**Phase 2 — Factorized training runs (local GPU, ~4–5 h total).**
6. Implement internal validation split + per-label threshold tuning (new scripts; originals untouched).
7. Run §8 cells (priority C, A, B → F, E → D, G; A′ equivalence check), 3 seeds → T6, and refresh T1–T4/T9 with cell columns.

**Phase 3 — Negative-sampling study (local, ~2–3 h).**
8. Run N1/N2 (+N3 optional) on the best-understood data condition from Phase 2 → T5 effective-ratio columns, T6 extension.

**Phase 4 — Conditional (requires professor's go-ahead / annotation time).**
9. Fable-5 screening of the 900; human review of the 180-sample; M-arm runs → T8 metric columns; κ agreement.

**Standing rules for all phases:** every run in a fresh timestamped `output/` folder; official data and `evaluation.py` untouched; single-factor changes between compared cells; all selection decisions on the internal split; dev used for reporting only; seeds {42, 43, 44} everywhere.

---

## 14. What Can Be Reported to the Professor Now

**Answerable today (existing artifacts, honestly caveated):**
- The 18 targets, their supports, and the per-target results of the single existing comparison (Table §5): at the frozen threshold, baseline and v1 predict **zero** instances of all 18 targets; the v2 model gives non-zero recall on 5 of 18 (1:10, 0:29, 0:2, 0:33, 0:28) with low precision (0.03–0.14), plus 18 zero-TP predictions on 0:32.
- Overall metrics including the macro-F1 rise 0.0305 → 0.1303 — **with the explicit statement that this run changed data and supervision policy together, on one seed, so the effect cannot yet be attributed to the 900 samples.**
- The imbalance quantification (§9.2): the professor's concern is directionally correct — targets train at 1:29 to 1:475, far from any balanced regime, and the current clamp caps re-weighting at 10.
- The filtering clarification (§3): what was and was not applied; that manual-filtering effectiveness is currently unknowable.
- The v2 threshold fact: direction-neutral candidate recall 0.951 at threshold 0.10 vs. 0.613 at 0.30 — evidence that part of the target failure may be decision-rule, not learning; full analysis in Phase 0/1.

**Requiring recomputation (days, no cost):** macro-P/R everywhere; target vs. non-target group tables; per-target FN/reversals; threshold curves.

**Requiring new training runs (Phase 2–3):** the isolated effect of the 900 (C vs. A); the masked-supervision effect (C vs. B); whether targets improved at non-targets' expense *causally*; negative down-sampling effects.

**Not answerable without a new experiment that was never conducted:** manual-filtering effectiveness (Phase 4); anything about the official test set.

---

## 15. Remaining Questions That Require New Experiments

1. Does adding the 900 alone (masked) improve target-18 recall over official-only, at equal seeds and decision rules? (Cell C vs. A — the professor's core question.)
2. Is the v2 macro gain driven by the masked supervision policy rather than the data? (C vs. B; E vs. D.)
3. Do target gains cost non-target performance once the decision rule is fair (per-label thresholds)? (T3 across cells.)
4. Does per-class negative down-sampling (1:3, 1:1) improve targets beyond re-weighting, and at what calibration cost? (N1/N2.)
5. Is AI screening a reliable proxy for human review (κ), and does either filtering level change training outcomes at matched size? (Phase 4.)
6. Do any of these effects survive on the official test set? (Out of scope until the above are settled.)

---

## 16. Final Validation Checklist

- [ ] Professor comment P1 answered by T2/T3/T4 with the A-vs-C causal contrast, not by the confounded existing run alone.
- [ ] P2: all six of macro/micro × P/R/F1 present in every table; "macro recall" interpretation flagged to the professor once.
- [ ] P3: no document or slide claims manual filtering occurred; §3 wording used; T8 status table shown.
- [ ] P4: T5 ratios presented; 50:50 reinterpreted per-label; N-experiments proposed with calibration caveat.
- [ ] P5: acknowledged; deferred to the route-level document by explicit reference.
- [ ] Every reported delta carries seed count and, where n=3, mean ± SD + per-seed sign consistency.
- [ ] Dev never used for tuning in any new run; all dev-tuned diagnostics labeled "oracle".
- [ ] Unknown/masked labels never counted as negatives in any ratio or loss.
- [ ] Aligned and contradictory target classes never merged in target-level tables.
- [ ] No source file, dataset, prompt, or existing artifact modified; all new outputs in fresh timestamped folders.

---

*Prepared from repository evidence only; file paths cited inline. This plan proposes experiments but executes none.*
