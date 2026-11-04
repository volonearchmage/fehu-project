# FEHU Research Route — Critical Review

**Document date:** 2026-07-19
**Repository state reviewed:** branch `sync-safe-fehu-dra-20260705`, HEAD `6b6f4cc` (working tree clean)
**Primary input:** `docs/FEHU_PROJECT_RESEARCH_SUMMARY.md`, verified selectively against run artifacts and source code
**Nature of this document:** analysis only. No source code, dataset, prompt, metric, or experiment artifact was modified or executed in its preparation. No training, inference, or API calls were run.

Throughout, three kinds of statements are explicitly distinguished:

- **[REPO]** — evidence read directly from this repository (reports, metrics files, CSVs, source code).
- **[LIT]** — evidence from external literature (cited in §12).
- **[INFERENCE]** — this reviewer's reasoned interpretation, not itself verified by an experiment.

---

## 1. Executive Summary

The project is **scientifically serious and unusually well-audited for a single-student research repository** — official evaluator never modified, append-only timestamped runs, hash-pinned inputs, honest negative results. That engineering hygiene is a genuine asset and should be preserved.

However, the central thesis as currently practiced — *diagnosis-guided LLM data augmentation (DRA-FEHU) improves a DeBERTa student on the FEHU long tail* — is **not yet supported by the repository's own evidence**, for three reasons:

1. **The only positive augmentation result is confounded.** Augmented DeBERTa v2's macro-F1 gain (0.0305 → 0.1303) came from changing *two* things at once: adding 900 unscreened records *and* switching to masked partial-label loss. No run isolates either factor. [REPO]
2. **Cheap, standard baselines that could explain the same failure mode were never run.** The rare-label collapse (zero recall on all 18 targets in baseline/v1) is exactly the signature of BCE-with-global-threshold under long-tail multi-label imbalance, for which per-class thresholding, distribution-balanced/asymmetric losses, and logit adjustment are standard remedies [LIT]. None was tried; the implemented calibration module was never executed. [REPO] The repository's own data shows the probability mass exists: DeBERTa v2 candidate recall is 0.951 at threshold 0.10 vs. 0.613 at the frozen 0.30. [REPO]
3. **The system that actually wins is the LLM, and the hybrid's margin over it is within plausible noise.** H3 beats the frozen Liu run by +0.0127 micro-F1 in a single API pass; the repository itself documents ±0.004 run-to-run variance for the very same Liu configuration across machines, and no replication or confidence interval exists. [REPO] [INFERENCE]

There are additional structural problems: severe distribution shift between synthetic and real articles (median 811 vs. 3,331 characters; 1 vs. 3 actors; 1 vs. 13 labels per article) [REPO], a 512-token truncation that hides most of each real article from DeBERTa [REPO], and a dev set that serves simultaneously as early-stopping criterion, augmentation-target selector, and final reporting set [REPO].

**Verdict:** the research *direction* (decompose value-recall from direction; use LLMs to compensate for tail sparsity) is defensible and partially validated. The *current experimental program* does not yet isolate any causal claim. The recommendation (§8) is to **revise rather than abandon**: keep diagnosis-guided augmentation as one arm of a properly controlled study, add the missing cheap baselines as mandatory comparators, and consider promoting the hybrid decomposition — the strand with the strongest empirical support — to the thesis's primary contribution.

---

## 2. Reconstruction of the Current Research Route

Reconstructed from `docs/FEHU_PROJECT_RESEARCH_SUMMARY.md`, git history, and run folders. [REPO]

| Phase | Dates (2026) | What was done | Outcome |
|---|---|---|---|
| 1. Prompt baselines | 05-13 → 05-17 | GPT-4o(-mini) few-shot baseline; DeepSeek Flash port | `Prompt_DS_Flash` 1b micro 0.4964 — strongest early system |
| 2. DeBERTa student | 05-17 | DeBERTa-v3-base + LoRA, 108-class BCE, threshold 0.3 | 1b micro 0.2989–0.3023, macro 0.03, DRR 0.24 |
| 3. Hybrid v1 → v2 | 05-17 → 05-18 | LLM keep/remove verification; then value-only candidates + LLM direction | v1 worse than both parents; v2 design yields the value/direction decomposition |
| 4. Label diagnosis | 06-13 | Per-label recall/precision for 7 methods, frequent → rare | Rare-tertile direction-aware recall ≈ 0 for all non-LLM methods; DeBERTa per-label DRR up to 0.90 |
| 5. DRA round 1 | 06-16 → 07-12 | Human-gated pilot (6 verified) → 340 AI-filtered silver records → Augmented DeBERTa v1 | **Negative result**: all 6 target L1s stay at zero recall; metrics flat |
| 6. Pipeline V2/V3 | 07-13 | Strict zero-shot pipeline; two-variant ensemble + verifier | V3 variant B 0.4628 — below Liu; verifier trades F1 for precision |
| 7. DRA round 2 | 07-13 | 18 direction:L1 targets × 50 records = 900 raw (structurally valid, semantically unscreened) | Prep only |
| 8. Augmented v2 | 07-14 | Masked-loss trainer, 1228 + 340 + 900 articles | Macro 0.0305 → 0.1303; 50 classes predicted; precision and DRR worse |
| 9. Final hybrid | 07-14 | DeBERTa v2 direction-neutral candidates + Liu prompt on DeepSeek Flash as verifier/direction-assigner | H3 micro 0.5474 vs. Liu 0.5347; H2 macro 0.3603 vs. 0.3385 |

**The implicit causal chain the route asserts** is: diagnosis identifies tail labels → label-conditioned synthetic data fixes tail recall in the student → a better student improves the hybrid → the hybrid beats the best LLM. Each arrow is examined in §4.

### Underlying assumptions (answers Q2)

| # | Assumption | Status (see §3–§4) |
|---|---|---|
| A1 | Rare-label failure is primarily a *data scarcity* problem | **Unverified**; competing explanation (threshold/loss artifact) untested |
| A2 | LLM-generated, label-conditioned articles are adequate substitutes for real tail examples | **Partially contradicted** (distribution shift, §4.3) |
| A3 | Target-only synthetic records must not be treated as fully labeled (partial-label assumption) | **Supported in design**, correctly implemented; effect not isolated |
| A4 | DeBERTa is good at value recall, bad at direction; LLMs are the reverse | **Supported** (diagnosis + hybrid ablations) |
| A5 | A better (augmented) student improves the hybrid | **Unverified** — no hybrid run with the non-augmented student |
| A6 | Dev-set improvements will transfer to test | **Unverifiable and at risk** — dev is used for model selection, target selection, and reporting |
| A7 | Single-seed / single-API-pass results are decision-grade | **Contradicted by the repo's own documentation** of trajectory variance and cross-machine API variance |

---

## 3. Evidence from Existing Experiments

All numbers from the named run folders; the summary document's figures were spot-checked against the underlying reports and CSVs and found accurate, with one factual error noted below. [REPO]

### 3.1 What the data actually looks like

Recomputed from `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/label_frequency_l1.csv`: [REPO]

- 54 L1 classes, 16,905 train gold labels; the top 5 classes carry **41.8%** of all labels; counts range 4 → 2,031.
- **10 of 54** classes (18.5%) have ≤35 training instances; **23 of 54** (43%) have ≤130. *(The claim in `research/fehu_augmentation_v1/METHOD_DESIGN.md` §"A third of L1 labels have ≤35 training instances" is incorrect; the correct fraction at ≤35 is roughly one fifth. This does not change the qualitative long-tail picture but should be fixed before it reaches a thesis.)*
- Direction is itself imbalanced: 11,456 aligned vs. 5,449 contradictory (~2.1 : 1) overall, with per-class ratios far more extreme (e.g., "Be responsible" 1,735 : 296).
- Dev: 177 articles, 459 actor slots of which 456 are gold-labeled, 2,390 direction-aware gold labels over **93 distinct 1b classes, 16 of which have support ≤2**.

### 3.2 The four load-bearing experimental facts

1. **Baseline DeBERTa collapses to the head.** 8 distinct 1b classes predicted out of 108; macro 0.0305; best checkpoint at epoch 1. [REPO]
2. **Round-1 augmentation (+340 screened silver records, unchanged trainer) changed nothing.** All six target L1 values at exactly zero recall (TP=0, FP=0); best epoch again 1. An honestly reported negative result. [REPO]
3. **Round-2 (+900 unscreened, masked loss) changed a lot.** 50 classes predicted, macro ×4.3, recall 0.35 → 0.54, best epoch 11 — at the cost of precision (0.266 → 0.238) and DRR (0.217 → 0.288). 6 of 18 targets gained non-zero recall; 12 did not; 4 (0:48, 0:16, 0:19, 1:49) have zero predictions in *every* system ever run. [REPO]
4. **The hybrid's verification step is load-bearing; its margin over Liu is small.** Liu + unverified DeBERTa candidates: micro 0.4057. Liu + verified: H3 0.5474 vs. Liu alone 0.5347 (+0.0127); DeepSeek rejected 53.3% of candidate reviews. [REPO]

### 3.3 Evidence status registry

| Claim circulating in the project | Evidence grade |
|---|---|
| "Masked-loss augmented training recovered the tail" | **Weak-moderate**: single seed, confounded (data + loss changed together), tiny per-target dev supports (3–12) |
| "The hybrid beats Liu" | **Weak**: +0.0127 micro in one API pass; documented cross-machine variance for the same Liu config is ±0.004; no CI, no replication |
| "Verification is load-bearing" | **Strong**: within-run ablation with large effect (0.5474 vs. 0.4057) |
| "DeBERTa finds values but not directions" | **Strong**: consistent across diagnosis (DRR 0.24–0.29 vs. 0.02–0.03) and hybrid ablations |
| "Diagnosis-guided targeting works" | **Unsupported**: no comparison against untargeted augmentation at matched budget |
| "Round-1 silver data was useless" | **Overdrawn**: it was useless *under the unchanged trainer*; never retested under masked loss or tuned thresholds [INFERENCE] |

---

## 4. Diagnosis of Current Failure Modes

This section separates **research-hypothesis problems** from **implementation/configuration problems**, as they demand different fixes.

### 4.1 Decision-rule artifact, not (only) data scarcity — *implementation/configuration*

The single most consequential finding of this review. Three repository facts triangulate it:

- `src/train_deberta.py` uses one **global threshold 0.3** and selects checkpoints by **overall dev micro-F1** (lines 471–474), a criterion dominated by head classes. [REPO]
- `pos_weight = sqrt(neg/pos).clamp(1,10)`: a class with 4–35 positives among 3,335 examples has a true neg/pos ratio of 10²–10³; the sqrt+clamp caps its upweighting at 10 — far below what BCE needs to push tail logits over a fixed 0.3 threshold. [REPO] [INFERENCE]
- The hybrid preflight measured DeBERTa v2 candidate recall **0.6134 at threshold 0.30 but 0.951 at 0.10** (`03_deberta_candidate_diagnostics.csv`). The model *ranks* most gold values highly; the decision rule discards them. [REPO]

The long-tail multi-label literature treats exactly this configuration (BCE, global threshold, head-dominated selection) as the canonical failure case, with standard remedies: distribution-balanced loss, asymmetric loss, class-balanced focal variants, logit adjustment, and per-class threshold tuning [LIT: Wu et al. 2020; Huang et al. 2021; Ridnik et al. 2021; Menon et al. 2021]. None was run. The V3 calibration module (`src/calibrate_task1_v3.py`, 12 unit tests) exists but has no run artifacts. [REPO]

**Consequence:** every conclusion of the form "rare labels have zero recall, therefore we need synthetic data" is premature. Zero recall *at threshold 0.3 under micro-F1 selection* is compatible with the signal already being present in the probabilities. This is the cheapest and most urgent thing to test.

### 4.2 Confounded headline result — *experimental control problem*

Augmented v1 → v2 changed simultaneously: (a) +900 records, (b) masked partial-label loss, (c) supervision-mode mixture (450 full / 450 target-only). The 2×2 (data × loss) was never factorized. [REPO]

The masked-loss implementation itself is **correct and well-designed**: `train_deberta_masked_v2.py` masks unknown labels out of both the loss and the pos-weight statistics, and reduces exactly to the original trainer under all-ones masks. [REPO] This matches the single-positive / missing-label literature, where treating unobserved labels as negatives ("assume negative") measurably injects false-negative supervision and masking or robust losses recover much of the loss [LIT: Cole et al. 2021; Liu et al. 2023]. **[INFERENCE]** A plausible reading of v1-vs-v2 is that *the loss correction, not the extra 560 records, is the active ingredient* — v1's 340 single-label silver articles under assume-negative BCE actively taught the model that the other 107 classes are absent, which could even explain v1's slight macro *decline* (0.0305 → 0.0261). This is testable at zero API cost (§9, E2).

### 4.3 Synthetic-to-real distribution shift — *research-hypothesis problem*

Measured directly from the v1 training inputs (`augmented_train_event_base.json` / `..._human_values.json`): [REPO]

| Property (median) | Real articles (n=1228) | Synthetic (n=340) |
|---|---|---|
| Content length (chars) | 3,331 | 811 |
| Actors per article | 3 | 1 |
| Gold labels per article | 13 | 1 |

The synthetic distribution is not a perturbed version of the real one; it is a different task (short, single-actor, single-value vignettes vs. long, multi-actor, ~13-label articles). This matters twice: (i) covariate shift at training time, and (ii) the real articles are truncated at 512 tokens (§4.4) while synthetic ones fit entirely — so the effective supervision signal differs systematically between the two sources. [INFERENCE] The literature on LLM synthetic data reports precisely this pattern: synthetic data helps most in genuinely low-resource regimes but underperforms real data as task subjectivity rises, due to reduced diversity and stylistic regularity [LIT: Li et al. 2023]. Value annotation is a highly subjective task (FEHU labels come with free-text explanations; ValueEval'23 needed three crowdworkers per item [LIT: Kiesel et al. 2023; Mirzakhmedova et al. 2024]).

The four never-predicted targets (0:48, 0:16, 0:19, 1:49) received 50 synthetic records each and still have zero predictions in every system **including the LLMs** (Liu recall 0.0 on all four, `05_historical_18_targets.csv`). [REPO] **[INFERENCE]** When strong LLMs with full context also score zero on a class with dev support 3–6, annotation ambiguity or gold sparsity is at least as likely an explanation as model failure; synthetic data cannot fix that, and these classes should be studied qualitatively before more generation budget is spent on them.

### 4.4 Input truncation and weak actor conditioning — *implementation*

`MAX_LENGTH = 512` with `truncation="only_first"`; median real article ≈ 3.3k chars (≈ 700–900 tokens), mean 4.3k. A large fraction of every long article — and any late-article evidence — is invisible to DeBERTa, while the LLM systems read full articles. Actor identity enters only as the short second segment. [REPO] **[INFERENCE]** This is a plausible independent contributor to the student's recall ceiling and to the value/direction gap (direction judgments often hinge on evidence sentences anywhere in the article). No experiment varied max length, used evidence-sentence selection, or chunked articles.

### 4.5 Dev-set triple duty and macro-F1 fragility — *evaluation methodology*

The 177-article dev set is simultaneously: (a) the early-stopping/model-selection criterion of every DeBERTa run (`eval_dev` on dev micro-F1) [REPO]; (b) an input to round-2 target selection (dev support ≥3, baseline dev recall = 0 conditions, `02_selected_targets_and_allocation.json`) [REPO]; (c) the set on which H2 vs. H3 was chosen and reported [REPO]. The project correctly flagged Liu's dev-fitted ensemble as leakage (`docs/liu_method_pipeline3_audit.md`) — the same standard must be applied to itself. [INFERENCE]

Additionally, macro-F1 over 93 gold-supported classes with 16 classes at support ≤2 means a single lucky prediction moves macro by ~1/93 ≈ 0.011 — the same order as the H2-vs-Liu macro gap. Per-target "recovery" claims ride on supports of 3–12. Without bootstrap CIs or multi-seed runs, differences at the second decimal are not decision-grade. [INFERENCE]

### 4.6 What is *not* broken

- The official evaluator is unmodified and correctly implements gold-supported macro and exclusion-filtered DRR (verified by reading `evaluation.py`). [REPO]
- Pipeline V2/V3's strictness guarantees (no silent failure → empty prediction, identity-bound caches) fixed real V1-era defects and are enforced by tests. [REPO]
- The gold-actors-only construction of dev examples in the trainer is a *near-miss* leakage concern but empirically negligible: 456 of 459 dev actor slots are gold-labeled. [REPO]
- The masked-loss code and the hybrid's audit discipline (hash-pinned inputs, direction-neutral candidates, probabilities withheld from the LLM) are sound. [REPO]

### Failure-mode summary table

| Failure mode | Type | Evidence | Severity |
|---|---|---|---|
| Global threshold + micro-F1 selection kills tail | Implementation/config | Candidate recall 0.951@0.10 vs. 0.613@0.30 | **Critical** — invalidates the premise of the augmentation strand until tested |
| v1→v2 confound (data × loss) | Experimental control | No factorized runs exist | **Critical** for the thesis claim |
| Synthetic distribution shift | Research hypothesis | 811 vs. 3,331 chars; 1 vs. 13 labels | High |
| 512-token truncation | Implementation | `MAX_LENGTH=512` vs. article lengths | High |
| Dev triple duty; no internal validation split | Evaluation methodology | Trainer, target selection, variant choice all on dev | High |
| Single seed / single API pass everywhere | Evaluation methodology | Flagged in every report, never remedied | High |
| Unscreened 900 records in the trained model | Data quality | Screening explicitly paused | Medium (quantifiable via E3) |
| No hybrid ablation with non-augmented student | Experimental control | Missing run | Medium |
| Direction imbalance untreated (2.1:1) | Modeling | Frequency CSV | Medium |
| METHOD_DESIGN "one third ≤35" misstatement | Documentation | Actual: 10/54 | Low |

---

## 5. Assessment of the Current Thesis Direction

**Q6 — Is diagnosis-guided LLM augmentation still defensible?** Yes, *conditionally*. The idea is aligned with current literature on LLM-based data generation for low-resource classes [LIT: Li et al. 2023] and the project's gating/verification machinery is more careful than most published pipelines. But as a *thesis claim* it currently rests on one confounded, single-seed run whose gains may belong to the loss function, and it has never been compared against (a) cheap decision-rule fixes or (b) untargeted augmentation at the same budget. A thesis examiner will ask both questions. Until E1–E4 (§9) are run, the honest statement is: *diagnosis-guided augmentation is a plausible hypothesis with no isolating evidence either way.*

**Q7 — Is masked partial-label learning used appropriately?** The implementation is correct and literature-consistent [LIT: Cole et al. 2021]. What is missing is recognition that it is a *separable contribution*: partial-label supervision from target-only synthetic records is interesting independent of where the records come from, and its effect must be measured alone. Also unexplored: the same assume-negative critique applies to the *silver* 340 (single-label, full supervision) — arguably those should have been target-only masked as well. [INFERENCE]

**Q8 — Do current experiments isolate the augmentation effect?** No. The smoke run (+6) was correctly labeled non-evidentiary; v1 changed only data (clean negative result); v2 changed data and loss together; the hybrid changed student and inference procedure together (no run pairs the Liu verifier with the *baseline* student's candidates).

**Q9 — Is the right objective being optimized?** Partially. The benchmark scores micro-F1, macro-F1, and DRR per task variant [REPO: `evaluation.py`; the official task page does not publish a single ranking metric [LIT: NTCIR-19 FEHU site]]. The project optimizes and selects on **1b micro-F1** everywhere (trainer early stopping, hybrid variant choice), while its research narrative is about the **tail (macro)**. These objectives conflict: micro-F1 selection is part of why tail signal dies (§4.1). If the thesis story is long-tail recovery, model selection should at minimum track macro or a macro/micro compromise on an internal split, and Task-2 (defined by the benchmark, unimplemented here) remains an open scope decision.

**Q10 — Modeling, data, evaluation, or systems problem?** In order of current severity: (1) an **experimental-control/evaluation problem** (confounds, dev triple duty, single seeds); (2) a **modeling/decision-rule problem** (loss, threshold, truncation); (3) a **data problem** (synthetic shift, unscreened records, genuine tail sparsity); (4) least of all a systems problem — the engineering is in good shape. [INFERENCE]

**Q11 — Preserve:** official-evaluator discipline; append-only run culture; label diagnosis tooling; masked-loss trainer; the value/direction decomposition and the verified-hybrid architecture; Pipeline V2/V3 validation machinery; the frozen Liu baseline.

**Q12 — Revise / simplify / abandon:**
- *Revise*: augmentation strand → controlled factorized study (§7 R1); DeBERTa training → long-tail losses, per-class thresholds, longer input, macro-aware selection; evaluation → internal split + bootstrap + ≥3 seeds.
- *Simplify*: stop generating new synthetic rounds until screening of the existing 900 and the E1–E4 ablations are done; retire Pipeline V1-era comparisons (superseded).
- *Abandon (as thesis evidence)*: single-pass hybrid deltas ≤0.02 without replication; the blocked Liu 0.5657/majority-vote comparisons (unauditable artifacts — treat as out of scope rather than "to reproduce").

---

## 6. Literature Review Relevant to the Observed Problems

**Human value detection benchmarks.** FEHU is an NTCIR-19 pilot task on identifying human values (with per-actor direction) in factual news [LIT: NTCIR-19 FEHU site; NTCIR-19 task overview]. Its closest relatives are SemEval-2023 Task 4 (ValueEval; 20 value categories over 9K arguments; best F1 ≈ 0.56 average/0.87 for the top label, with transformer ensembles, entailment formulations, and loss re-weighting among the successful techniques) [LIT: Kiesel et al. 2023] and Touché/CLEF ValueEval'24, which uses the same **54-value multi-level taxonomy** plus an *attainment* (attained/constrained) dimension structurally analogous to FEHU's direction bit [LIT: Touché24; Mirzakhmedova et al. 2024]. Two implications: (i) FEHU's absolute score ranges (best 1b micro ≈ 0.55 here) are in line with what related value-detection tasks achieve — the task is intrinsically hard and noisy; (ii) the ValueEval'24 system papers are the most directly transferable prior art and are currently uncited in the repository. [INFERENCE]

**Long-tail multi-label classification.** Distribution-balanced loss (re-balanced weighting + negative-tolerant regularization) and its text-classification adaptations consistently beat plain BCE on tail macro-F1 [LIT: Wu et al. 2020; Huang et al. 2021]; asymmetric loss decouples positive/negative gradient scales [LIT: Ridnik et al. 2021]; logit adjustment gives a theoretically grounded per-class offset [LIT: Menon et al. 2021]. Standard practice also tunes thresholds per class on validation data. All four directly target the observed failure (head-only prediction under BCE + global threshold).

**Partial-label / missing-label learning.** Cole et al. formalized single-positive multi-label learning and showed assume-negative training measurably degrades performance, with masking, label smoothing, and online label estimation as remedies [LIT: Cole et al. 2021]; later work improves via pseudo-labeling and robust losses [LIT: Liu et al. 2023; Chen et al. 2024]. The project's masked loss is a clean instance of this family — a legitimate, citable methodological component.

**LLM synthetic data and its limits.** Li et al. show LLM-generated synthetic training data helps most in low-resource settings (3–26% gains at ~100 real examples) but degrades with task/instance subjectivity and reduced diversity [LIT: Li et al. 2023]. This predicts both the round-1 null result (silver vignettes for a subjective task) and the observed precision cost in v2.

**LLM annotation/distillation as the alternative supervision channel.** Fine-tuning small classifiers on LLM-generated *labels for real texts* performs comparably to human-label fine-tuning across many tasks [LIT: Pangakis & Wolken 2024; Gilardi et al. 2023] — i.e., annotating real news articles with a strong teacher (the repository already owns a 0.53-F1 teacher in the frozen Liu pipeline) is a literature-supported substitute for generating synthetic articles, and it eliminates the covariate-shift problem by construction.

**Entailment/description-based classification for rare classes.** NLI-style reformulation ("this text expresses the value of X") scores classes independently of their training frequency and is a standard zero/few-shot route for large label spaces [LIT: Yin et al. 2019]; FEHU's official per-value descriptions and gold explanation fields make this directly applicable.

---

## 7. Alternative and Improved Research Routes

Five concrete routes. R1 preserves diagnosis-guided augmentation; R4 and R5 are materially different directions.

### R1 — Controlled DRA: factorized augmentation × partial-label study *(preserves the current thesis)*

- **Core hypothesis:** label-conditioned synthetic data improves tail recall *beyond* what loss/threshold corrections achieve, and semantic screening improves the trade-off.
- **Why it addresses the failure modes:** it converts the confounded v1→v2 comparison into a 2×2×2 design (data: none/340/1240-screened/1240-unscreened × loss: plain/masked × decision rule: fixed/tuned), directly answering §4.1–§4.3.
- **Relationship to current work:** re-uses every existing asset (silver 340, raw 900, masked trainer, diagnosis). The paused Fable-5 screening of the 900 becomes an experimental arm rather than a chore.
- **Data/implementation changes:** none to generation; a config-level grid over existing trainers; screening run for the 900; per-class threshold tuning on an internal split carved from *train* (never dev).
- **Expected evidence:** if augmentation is real, screened-1240 + masked loss beats no-augmentation + tuned thresholds on tail macro at equal seeds; if not, the thesis claim falls and the honest result is "decision-rule correction explains the tail collapse."
- **Main risks:** the cheap baseline wins (a publishable but different thesis); dev supports of 3–12 make per-target claims noisy even with 3 seeds.
- **Minimum ablation:** E1–E4 of §9 (all local GPU, ~10 min/run on the 4090).
- **Thesis suitability:** main contribution *only if* the augmentation arm survives the controls; otherwise supporting chapter.

### R2 — Decision-rule and long-tail training route *(cheapest, highest information)*

- **Core hypothesis:** a large share of the "rare labels have zero recall" phenomenon is an artifact of BCE + global 0.3 threshold + micro-F1 selection, not missing data.
- **Why:** candidate recall 0.951@0.10 [REPO] shows ranked signal exists; the literature remedies are designed for exactly this configuration.
- **Relationship:** modifies only `train_deberta.py`-derived training configs (new run scripts, originals untouched per repo rules); reuses all data.
- **Changes:** distribution-balanced or asymmetric loss; logit-adjusted BCE; per-class thresholds tuned on an internal train-split; macro-aware checkpoint selection; optionally max_length 1024 / evidence-chunking to attack §4.4.
- **Expected evidence:** macro-F1 and distinct-class counts of the *non-augmented* model approach or exceed Augmented v2's 0.1303; if they do not, data scarcity regains standing as the explanation — either outcome sharpens the thesis.
- **Risks:** precision collapse at low thresholds (measurable); DeBERTa-v3 + longer inputs increase VRAM/time modestly.
- **Minimum ablation:** E1 + E5.
- **Thesis suitability:** supporting experiment / mandatory baseline; alone it is solid engineering but a thin thesis.

### R3 — The verified hybrid as primary contribution *(promotes the strongest current result)*

- **Core hypothesis:** decomposing FEHU into high-recall value candidate generation (student, direction-neutral, low threshold) + LLM relevance verification and direction assignment is a robust, replicable architecture that beats the best single LLM.
- **Why:** it is the only strand with a strong within-run ablation (verified vs. unverified: 0.5474 vs. 0.4057) [REPO]; the value/direction decomposition is the project's best-supported empirical finding (A4).
- **Relationship:** formalizes the 07-14 hybrid; adds the missing controls: hybrid with *baseline* student candidates (isolates augmentation's downstream value — A5), candidate threshold sweep (0.10/0.20/0.30 — exploiting the 0.951 recall headroom), ≥3 replicated API passes with bootstrap CIs, and a candidate-source ablation (DeBERTa vs. NLI-scores vs. frequency prior) to prove the student earns its place.
- **Expected evidence:** replicated mean ± CI for H2/H3 vs. Liu; a candidate-recall → final-F1 response curve; demonstration that verification quality, not candidate model identity, drives gains (or the converse).
- **Risks:** gains may vanish under replication (the ±0.004 cross-machine variance concern); API cost (~531–950 calls per full pass); contribution reads as "system" rather than "method" unless the decomposition analysis is rigorous.
- **Minimum ablation:** E6 + E7.
- **Thesis suitability:** strong main-contribution candidate — it is where the state-of-the-art result actually lives, and the decomposition story connects diagnosis, student, and verifier coherently.

### R4 — Entailment/description-based per-(actor, value) scoring *(materially different direction)*

- **Core hypothesis:** casting FEHU-1b as pairwise entailment — premise: actor-focused evidence span; hypothesis: official value description (± direction template) — removes the class-frequency dependence that breaks the 108-way classifier, and sidesteps truncation via evidence retrieval.
- **Why:** NLI reformulation scores tail classes with the same machinery as head classes [LIT: Yin et al. 2019]; ValueEval'23 winners used entailment components [LIT: Kiesel et al. 2023]; FEHU's taxonomy descriptions and gold `explanation` fields provide free supervision for evidence selection.
- **Relationship:** replaces the student's architecture; keeps the hybrid slot (an entailment scorer is a drop-in candidate generator for R3); reuses the diagnosis for error analysis.
- **Changes:** build (article, actor, value, direction) → entail/neutral pairs from gold; fine-tune a cross-encoder (DeBERTa-v3 NLI checkpoint); simple evidence-sentence retrieval per actor; calibrated per-class decision.
- **Expected evidence:** tail macro well above 0.13 without any synthetic data would demonstrate the frequency-independence claim; per-pair scores are also interpretable evidence for the direction bit.
- **Risks:** inference cost (54 × actors pairs per article; prunable); building clean negative pairs from partially-annotated gold reintroduces the missing-label problem (mitigate with the same masking logic); a new codebase strand late in the schedule.
- **Minimum ablation:** E8 (small pilot on the existing splits) before committing.
- **Thesis suitability:** viable main contribution if started promptly; otherwise a strong "alternative formulation" chapter.

### R5 — Teacher-annotation distillation on real news *(materially different supervision channel)*

- **Core hypothesis:** distilling the frozen Liu teacher's annotations of *real* articles (train-set re-annotation with soft/union labels, or external news if permitted) transfers tail knowledge better than generating synthetic articles, because it eliminates covariate shift.
- **Why:** directly answers §4.3; supported by LLM-annotation distillation results [LIT: Pangakis & Wolken 2024; Gilardi et al. 2023]; the teacher already exists and its per-class behavior is measured (`05_historical_18_targets.csv` shows Liu has non-zero recall on 14 of 18 targets where the student had zero).
- **Relationship:** keeps the student, the masked-loss machinery (teacher labels are noisy-positive → partial supervision fits naturally), and the diagnosis (teacher confidence per tail class guides what to distill).
- **Changes:** one teacher inference pass over train articles (~1228 calls, comparable to past runs — *not run now*); a label-merging policy (gold ∪ teacher-above-confidence, teacher-only labels masked-positive); retraining.
- **Expected evidence:** student tail macro approaching teacher tail recall at zero synthetic-data cost; a clean scaling curve in number of distilled articles.
- **Risks:** teacher errors on the head propagate (mitigated by gold priority); "distillation" contribution is less novel methodologically; API cost of the annotation pass.
- **Minimum ablation:** E9 on a 200-article subset first.
- **Thesis suitability:** strong supporting experiment; main contribution only if framed as a systematic study of *generation vs. annotation* as competing LLM supervision channels (which would be a genuinely interesting thesis question given R1's infrastructure).

---

## 8. Ranked Recommendation

Ranking dimensions: scientific justification (SJ), expected performance impact (PI), feasibility in this repo/schedule (F), clarity of thesis contribution (TC), experimental risk (ER, lower = safer). Scores 1–5, [INFERENCE].

| Rank | Route | SJ | PI | F | TC | ER | Overall rationale |
|---|---|---|---|---|---|---|---|
| 1 | **R2 decision-rule/long-tail baselines** | 5 | 3–4 | 5 (hours, local) | 3 | 1 | Must run first regardless of thesis choice; every other route's interpretation depends on it |
| 2 | **R3 hybrid as main contribution** | 4 | 4 | 4 (API budget) | 5 | 2 | Where the best result and the best-supported finding already live; needs replication + missing ablations |
| 3 | **R1 controlled DRA** | 4 | 2–3 | 4 (mostly local + one screening pass) | 4 (conditional) | 3 | Rescues the current thesis if augmentation survives controls; honest fallback narrative if not |
| 4 | **R5 teacher distillation** | 4 | 3 | 3 | 3 | 3 | Best paired *with* R1 as the generation-vs-annotation comparison |
| 5 | **R4 entailment reformulation** | 4 | 3–4 | 2 (new strand, late) | 4 | 4 | Highest upside per novelty, highest schedule risk |

**Recommended composite plan:** run R2's experiments immediately (they are prerequisites, not a thesis); replicate the hybrid (R3) to establish whether the headline result is real; decide the thesis frame based on those two outcomes — either *"diagnosis-guided synthetic supervision under partial-label training"* (R1, if augmentation beats the R2 baselines) or *"a value/direction-decomposed verified hybrid for long-tail human-value recognition"* (R3), with R1 demoted to a chapter. R5 is the natural additional comparison arm inside either frame.

---

## 9. Required Validation Experiments

All are designed to be individually decisive, and none modifies existing artifacts (new run folders per repo convention). "Local" = RTX 4090, ≈10 min/run at current settings.

| ID | Experiment | Distinguishes | Cost | Priority |
|---|---|---|---|---|
| E1 | Baseline (1228, no augmentation): per-class threshold sweep + macro-aware checkpoint selection, 3 seeds | Data scarcity vs. decision-rule artifact (§4.1) | Local | **P0** |
| E2 | 2×2: {official-only, +340} × {plain BCE, masked loss}, fixed decision rule, 3 seeds | Loss correction vs. data as v2's active ingredient (§4.2) | Local | **P0** |
| E3 | Fable-5 semantic screening of the 900 → retrain v2 on screened set, same seeds | Label-noise cost of unscreened records | 1 screening pass + local | P1 |
| E4 | Untargeted augmentation control: 900 records over 18 *random* eligible tail classes (or shuffled allocation) at matched budget | "Diagnosis-guided" vs. "any tail data" | 1 generation pass + local — *defer until E1/E2 justify it* | P1 |
| E5 | Distribution-balanced / asymmetric loss vs. BCE on official data, 3 seeds | Whether standard long-tail losses close the gap for free | Local | P1 |
| E6 | Hybrid re-run ×3 API passes (same config) + article-bootstrap CIs for H2/H3/Liu | Whether +0.0127 exceeds run noise (§4.5) | ~3×177 calls | **P0 for any hybrid claim** |
| E7 | Hybrid with *baseline* DeBERTa candidates; hybrid with candidates at threshold 0.10/0.20 | Whether augmentation matters downstream (A5); recall-headroom value | ~2–3×177 calls | P1 |
| E8 | Entailment cross-encoder pilot: train on gold pairs, evaluate tail macro on internal split | Viability of R4 before committing | Local (1–2 days eng.) | P2 |
| E9 | Teacher-annotation pilot: Liu labels on 200 train articles → masked distillation | Viability of R5; generation-vs-annotation seed comparison | ~200 calls + local | P2 |
| E10 | Qualitative audit of the 4 never-predicted targets (all gold instances + explanations) | Model failure vs. gold ambiguity (§4.3) | Reading only | P1 |

Standing protocol fixes for **all** future runs: (i) carve an internal validation split from *train* for every selection decision (thresholds, checkpoints, variant choices); dev becomes report-only; (ii) ≥3 seeds for training runs, ≥3 passes for API runs; (iii) article-level bootstrap CIs in every metrics report; (iv) correct the METHOD_DESIGN frequency misstatement (§3.1).

---

## 10. Risks, Limitations, and Unresolved Questions

- **This review's own limits.** No new experiments were run; all causal language about *why* v2 improved or whether the hybrid margin is noise is hypothesis, clearly flagged [INFERENCE], to be settled by E1–E6. External-literature effect sizes (e.g., gains from distribution-balanced loss) come from other domains/datasets and may not transfer at FEHU's scale.
- **Dev-set exhaustion.** With 177 articles doing triple duty, even the corrected protocol can only partially undo past selection; the ultimate check is the official test phase, for which no submission run exists yet. [REPO]
- **Gold-label quality on the tail.** Support-≤2 classes and the four all-system-zero targets may reflect annotation sparsity/ambiguity (E10). If so, macro-F1 on dev systematically understates and destabilizes tail progress, and no training method will fix it.
- **Blocked comparisons.** Liu's 0.5657 label-aware ensemble remains unauditable (artifacts absent) and is additionally dev-fitted per the project's own audit; it should be excluded from any thesis comparison table rather than chased. [REPO]
- **API reproducibility.** DeepSeek endpoints are not seed-controllable; replication (E6) bounds but cannot eliminate this. Freezing raw responses (already the repo's practice) is the correct mitigation.
- **Schedule risk.** R4/R5 open new strands; the composite plan in §8 deliberately front-loads the zero-API-cost experiments so a thesis-frame decision can be made within days of compute, not weeks.
- **Unresolved questions.** (1) Should the *silver 340* also be target-only masked? (2) Is Task-2 in scope for the thesis at all? (3) What is the official test-phase ranking metric — micro, macro, or a combination? The public task page does not say [LIT: NTCIR-19 FEHU site]; this materially affects which objective to optimize and should be clarified with the organizers.

---

## 11. Final Conclusion

The repository documents a disciplined but prematurely converging research program. Its best-supported scientific finding is **not** the augmentation thesis it set out to prove — it is the **value/direction decomposition with LLM verification**, established by clean within-run ablations. Its headline augmentation result is real progress in behavior (50 predicted classes, late best epoch) but is causally unattributable as evidence stands: the masked partial-label loss, the extra data, and the decision rule are entangled, and the cheapest competing explanation — that the tail signal was always present and the decision rule discarded it — has never been tested despite the repository containing the strongest single piece of evidence for it (candidate recall 0.951 at threshold 0.10).

The current direction should therefore be **revised, not replaced**: run the decision-rule and factorization experiments first (E1, E2, E6 — days of work, almost no API cost); let their outcome choose between the two viable thesis frames (controlled diagnosis-guided augmentation, or the verified hybrid); and adopt the evaluation-protocol fixes so that whichever frame wins, its evidence survives examination.

---

## 12. References

**Repository evidence** (primary; paths relative to `ntcir19_fehu-master/`): `docs/FEHU_PROJECT_RESEARCH_SUMMARY.md`; `evaluation.py`; `src/train_deberta.py`; `src/task1_v3_ensemble.py`; `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/` (report, `label_frequency_l1.csv`); `output/research_ablation_smoke_runs/20260704_201355/`; `output/research_augmented_deberta_v1/20260712_231751/` (report, `scripts/prepare_augmented_inputs.py`, `inputs/`); `output/research_augmented_deberta_v2_unfiltered/20260714_032758/` (report, `scripts/train_deberta_masked_v2.py`); `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/`; `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/` (report, `03_deberta_candidate_diagnostics.csv`, `05_historical_18_targets.csv`, `scripts/`); `docs/liu_method_pipeline3_audit.md`; `research/fehu_augmentation_v1/METHOD_DESIGN.md`.

**External literature:**

1. NTCIR-19 FEHU task site — https://sites.google.com/view/ntcir19fehu ; NTCIR-19 task overview — https://research.nii.ac.jp/ntcir/ntcir-19/tasks.html ; FEHU pilot-task slides — https://research.nii.ac.jp/ntcir/ntcir-18/NTCIR-18_Conference_closing-materials/NTCIR-19_Pilot-Task_FEHU.pdf
2. Kiesel, J. et al. (2023). *SemEval-2023 Task 4: ValueEval: Identification of Human Values Behind Arguments.* https://aclanthology.org/2023.semeval-1.313.pdf
3. Mirzakhmedova, N. et al. (2024). *The Touché23-ValueEval Dataset for Identifying Human Values behind Arguments.* LREC-COLING 2024. https://aclanthology.org/2024.lrec-main.1402/
4. Touché at CLEF 2024 — Human Value Detection (ValueEval'24). https://touche.webis.de/clef24/touche24-web/human-value-detection.html
5. Li, Z., Zhu, H., Lu, Z., Yin, M. (2023). *Synthetic Data Generation with Large Language Models for Text Classification: Potential and Limitations.* EMNLP 2023. https://aclanthology.org/2023.emnlp-main.647/
6. Cole, E., Mac Aodha, O., Lorieul, T., Perona, P., Morris, D., Jojic, N. (2021). *Multi-Label Learning from Single Positive Labels.* CVPR 2021. https://arxiv.org/abs/2106.09708
7. Liu, B. et al. (2023). *Revisiting Pseudo-Label for Single-Positive Multi-Label Learning.* ICML 2023. https://proceedings.mlr.press/v202/liu23ar/liu23ar.pdf
8. Chen, Y. et al. (2024). *Boosting Single Positive Multi-label Classification with Generalized Robust Loss.* https://arxiv.org/abs/2405.03501
9. Wu, T. et al. (2020). *Distribution-Balanced Loss for Multi-Label Classification in Long-Tailed Datasets.* ECCV 2020. https://arxiv.org/abs/2007.09654
10. Huang, Y. et al. (2021). *Balancing Methods for Multi-label Text Classification with Long-Tailed Class Distribution.* EMNLP 2021. https://arxiv.org/abs/2109.04712
11. Ridnik, T. et al. (2021). *Asymmetric Loss for Multi-Label Classification.* ICCV 2021. https://arxiv.org/abs/2009.14119
12. Menon, A. K. et al. (2021). *Long-Tail Learning via Logit Adjustment.* ICLR 2021. https://arxiv.org/abs/2007.07314
13. Pangakis, N., Wolken, S. (2024). *Knowledge Distillation in Automated Annotation: Supervised Text Classification with LLM-Generated Training Labels.* NLP+CSS @ NAACL 2024. https://aclanthology.org/2024.nlpcss-1.9/
14. Gilardi, F., Alizadeh, M., Kubli, M. (2023). *ChatGPT Outperforms Crowd Workers for Text-Annotation Tasks.* PNAS 120(30). https://arxiv.org/abs/2303.15056
15. Yin, W., Hay, J., Roth, D. (2019). *Benchmarking Zero-shot Text Classification: Datasets, Evaluation and Entailment Approach.* EMNLP 2019. https://arxiv.org/abs/1909.00161

*Note on citation quality: items 1–15 were located via web search during this review; items 11, 12, and 15 are foundational works cited from standard knowledge of the field and were not re-fetched — their identifiers should be spot-checked before inclusion in a thesis bibliography.*
