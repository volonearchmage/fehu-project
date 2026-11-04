# WAIPS at the NTCIR-19 FEHU Task 1
## Revised Paper Outline for Professor Review

**Working title**

> **WAIPS at the NTCIR-19 FEHU Task 1: Label-Aware Prompt Ensembling and Gated Heterogeneous Fusion for Human-Value Recognition**

**Team name:** WAIPS  
**Subtasks:** Task 1a and Task 1b  
**Target length:** no more than 8 pages, including references  
**Purpose of this document:** agree on the paper story, contribution boundaries, evidence, and writing allocation before drafting the participant paper.

---

## 1. Paper Positioning

The paper presents two complementary, but distinct, contributions for article-level human-value recognition in FEHU Task 1:

1. **Label-aware prompt ensembling (Liu Dongyang).** A standalone prompt-only method that uses label-level diagnosis to combine a conservative majority-vote base with selective recovery from a targeted prompt.
2. **Gated heterogeneous fusion (joint WAIPS system).** A later integration of multiple prompt components and rare-label auxiliary evidence, designed and evaluated as WAIPS-03 / E7-G4.

The paper must distinguish these contributions clearly. Liu's complete label-aware ensemble is a standalone method; it is not interchangeable with the particular Liu prompt component used in E7-G4.

The central research question is:

> How can complementary prompt behaviors and rare-label evidence be combined to improve actor-conditioned human-value recognition while making the precision-recall-direction trade-off explicit?

---

## 2. Official Context and Result Positioning

WAIPS participated in **Task 1 only**. Task 1a predicts directionless Level-2 values for each article-actor pair; Task 1b predicts directed Level-1 values. Detailed task construction, data statistics, output format, and evaluation definitions will be cited from the official FEHU Task Overview paper rather than repeated in full.

The official Task 1 results are summarized below. Values are rounded from the organizer's Overview paper.

| System | Task 1a Micro / Macro F1 | Task 1b Micro / Macro F1 | Task 1b DRR |
|---|---:|---:|---:|
| WAIPS-01 | 0.6589 / 0.5366 | 0.5543 / 0.3277 | **0.0345** |
| WAIPS-02 | **0.6930** / 0.5646 | 0.5496 / 0.3580 | 0.0395 |
| WAIPS-03 / E7-G4 | 0.6862 / **0.5705** | **0.5808 / 0.3952** | 0.0477 |

Accurate interpretation:

- WAIPS-03 is the strongest **WAIPS** run on Task-1b Micro-F1 and Macro-F1.
- WAIPS-03 achieves the highest Task-1b Macro-F1 among participant runs.
- WAIPS-01 achieves the lowest Task-1b DRR among participant runs.
- No single WAIPS run dominates every measure; the results expose different precision, recall, macro-F1, and direction-stability trade-offs.

The paper must not claim that WAIPS-03 is the best overall Task-1b participant system: IIUoT-01 has the highest participant Task-1b Micro-F1. The organizer baseline is an unranked reference system and must be labeled as such if reported.

---

## 3. Proposed Structure and Page Budget

| Section | Content | Pages | Primary owner |
|---|---|---:|---|
| Abstract | Problem, two complementary contributions, principal development and official findings | 0.20 | Joint |
| 1. Introduction and Task | FEHU Task 1 motivation, difficulties, contributions | 0.55 | Joint |
| 2. Label-aware Prompt Ensembling | Liu's standalone method, results, and analysis | **2.00** | Liu Dongyang |
| 3. Rare-label Diagnosis and Augmentation | Huang's targeted augmentation and auxiliary evidence | 0.75 | Huang Peiyang |
| 4. Gated Heterogeneous Fusion | E7-G4 integration, ablation, and official results | 3.35 | Huang / joint |
| 5. Related Work | Focused related work | 0.25 | Joint |
| 6. Conclusion | Findings and limitations | 0.15 | Joint |
| References | Including FEHU overview paper | 0.45 | Joint |
| **Total** |  | **7.70** |  |

If space is tight, reduce Section 4 detail before reducing Section 2. Liu's two-page method section is required to represent the standalone contribution accurately.

---

## 4. Detailed Outline

### Abstract

- Introduce FEHU as actor-conditioned, multi-label human-value recognition in factual news.
- State that the paper studies label-aware prompt ensembling, rare-label augmentation, and gated heterogeneous fusion.
- Report development results with explicit split labels.
- Report the official Task-1 result accurately: WAIPS-03 achieves 0.5808 Task-1b Micro-F1 and 0.3952 Macro-F1; WAIPS-01 achieves the lowest participant DRR, 0.0345.
- State the key conclusion: complementary sources can improve value recovery, but the gain must be interpreted jointly with direction stability.

### 1. Introduction and Task Setting

- Define Task 1a and Task 1b concisely; cite the FEHU Task Overview for the full task design and evaluation protocol.
- Motivate the three practical difficulties: actor-specific evidence, fine-grained long-tail labels, and direction disagreement.
- State the three contributions:
  1. a label-aware prompt ensemble guided by per-label development analysis;
  2. diagnosis-guided augmentation for selected rare/difficult labels;
  3. a gated fusion framework combining heterogeneous evidence.
- State up front that the paper reports both F1 and DRR because high recall can introduce direction errors.

### 2. Label-Aware Prompt Ensembling (Liu Dongyang) — 2.00 pages

This section is a full standalone method section. It must not be compressed into the description of one E7-G4 jury member.

#### 2.1 Prompt-only Pipeline and Complementary Variants — 0.35 page

- Describe the end-to-end Task-1 prompt-only pipeline: input processing, LLM inference, structured Task-1a/Task-1b prediction, and official evaluation.
- Introduce the DeepSeek V4 Flash baseline and the role of three variants:
  - **baseline:** recall-oriented A0-style prompt;
  - **compact:** concise structured output with actor-specific evidence requirements;
  - **compact strict:** conservative variant with stronger evidence requirements and a precision-oriented behavior.
- Introduce **targeted-more-shot-balanced** as a separate high-recall source with targeted guidance for difficult labels.

#### 2.2 Label-Level Diagnosis — 0.40 page

- Evaluate Task-1b at the unit of `(direction, Level-1 value)`, not only by aggregate scores.
- Compute per-label TP, FP, FN, precision, recall, and F1; group labels by frequency.
- Show the key finding: ordinary majority vote stabilizes common labels and lowers false positives, but loses true positives for some difficult or infrequent labels.
- Include one compact frequency-group table or figure. The central dev result is that the average F1 for infrequent labels rises from 0.2168 under majority vote to 0.3025 under the label-aware ensemble.

#### 2.3 Exact Label-Aware Ensemble Algorithm — 0.65 page

Let `B`, `C`, and `S` denote the Task-1b prediction sets from the baseline, compact, and compact-strict prompt variants. Each prediction is an atomic actor-value-direction tuple.

1. Construct a majority-vote base `M` by retaining a tuple predicted by at least two of `B`, `C`, and `S`.
2. Let `T` be the prediction set from the targeted-more-shot-balanced prompt.
3. Select a fixed set of ten direction:Level-1 labels using development-set label-level comparison.
4. Create the final Task-1b set by adding to `M` only tuples in `T` whose direction:Level-1 identity is in the selected set.
5. Use the targeted-more-shot-balanced Task-1a output for Task 1a.

The selected Task-1b identities are:

```text
contradictory: Be creative
contradictory: Have good health
contradictory: Have a stable society
contradictory: Have equality
contradictory: Have harmony with nature
aligned: Be capable
aligned: Have good health
aligned: Have a stable society
aligned: Be humble
aligned: Have a world at peace
```

This method is not a blind union, weighted vote, calibrated fusion, or fine-tuning method. Direction is part of the voted tuple; no separate direction-repair rule is claimed for this standalone ensemble.

#### 2.4 Development Results, Label Cases, and Ablation — 0.40 page

Report the controlled full-development comparison:

| Method | Task-1b Micro F1 | Macro F1 | Precision | Recall | DRR |
|---|---:|---:|---:|---:|---:|
| Majority vote | 0.5359 | 0.3532 | 0.6350 | 0.4636 | 0.0180 |
| Targeted-more-shot-balanced | 0.5387 | 0.3679 | 0.5750 | 0.5067 | 0.0302 |
| **Label-aware ensemble** | **0.5657** | **0.3870** | 0.6149 | **0.5238** | 0.0279 |

- Explain the improvement over majority vote: +0.0298 Micro-F1, +0.0338 Macro-F1, and +0.0602 recall.
- Give representative recovered labels, for example `contradictory: Have a stable society` and `aligned: Have good health`.
- Include the smaller selected-label ablation briefly: the original 10-label configuration is score-oriented; the `small_low_drr` alternative reaches 0.5613 Micro-F1 and 0.0230 DRR.

#### 2.5 Official WAIPS-01 Result and Limitation — 0.20 page

- Identify WAIPS-01 as the formal Task-1 submission based on the label-aware prompt ensemble.
- Report the official Task-1b result: 0.5543 Micro-F1, 0.3277 Macro-F1, and the lowest participant DRR of 0.0345.
- Interpret this as a direction-stable alternative, not as evidence that the method dominates all other runs.
- State the limitation: the selected direction:Level-1 set was chosen on development data, so development gains may be optimistic; dev and test results are not a controlled ablation because the article sets differ.

### 3. Rare-Label Diagnosis and Data Augmentation (Huang Peiyang) — 0.75 page

- Describe the diagnosis of 18 task-specific low-frequency or zero-recall Task-1b targets.
- Describe targeted synthetic data generation, LoRA fine-tuning of DeBERTa-v3-large, and masked partial-label supervision.
- State only verified standalone findings and distinguish auxiliary evidence from final predictions.
- Do not claim that data augmentation alone caused the final E7-G4 gain unless a no-DeBERTa fusion ablation is available.

### 4. E7-G4 Gated Heterogeneous Fusion — 3.35 pages

#### 4.1 System Overview and Member Roles — 0.45 page

- Present one system figure: primary prompt output plus prompt jurors and rare-label auxiliary evidence, followed by veto, additions, and direction QA.
- Describe E1, E6b, E6c, the Liu prompt component, and DeBERTa evidence by their verified roles.
- Explicitly distinguish the Liu component used in E7-G4 from Liu's complete standalone label-aware ensemble in Section 2.

#### 4.2 Gated Fusion and Direction QA — 0.95 page

- Describe the exact rule for veto, additions, and direction conflict resolution.
- State which components provide exact-direction votes, value-only evidence, or probability support.
- Explain how development data is used to select/freeze rules before applying the test pipeline.
- Include calibration method, thresholds, and constraints only after they are verified against the final code and run report.

#### 4.3 Development Comparison and Ablation — 0.70 page

- Compare E6b, each verified gating stage, and E7-G4 with Task-1b Micro-F1, Macro-F1, precision, recall, and DRR.
- Include uncertainty estimates only if their implementation and sampling procedure are documented and reproducible.
- Do not reuse official test results to tune the gating configuration.

#### 4.4 Official Results and Error Analysis — 0.65 page

- Report WAIPS-03 / E7-G4 official results: Task-1b 0.5808 Micro-F1, 0.3952 Macro-F1, 0.0477 DRR; Task-1a 0.6862 Micro-F1, 0.5705 Macro-F1.
- Compare the three WAIPS runs using the qualified interpretation in Section 2.
- Discuss false positives from recall-oriented additions and unresolved direction conflicts as the two principal error patterns.

#### 4.5 Contribution Boundary — 0.60 page

- Explain that E7-G4 is a joint fusion system.
- Attribute the standalone label-aware prompt ensemble to Liu, the rare-label augmentation and DeBERTa evidence to Huang, and the gated integration to the joint system as documented by its implementation.
- Avoid attributing the full E7-G4 gain to any individual component without ablation evidence.

### 5. Related Work — 0.25 page

- Prompt ensembling, self-consistency, and voting.
- Long-tail multi-label classification and targeted data augmentation.
- Calibration/confidence-aware ensemble fusion.
- Human-value extraction and the FEHU / NEVU task resources.

Each citation must be tied directly to one paper contribution; internal reports are evidence for experiments, not substitutes for scholarly references.

### 6. Conclusion — 0.15 page

- Liu's label-aware prompt ensemble shows that per-label diagnosis can balance a conservative base with targeted recall recovery.
- The rare-label track provides auxiliary signal for selected targets.
- E7-G4 improves Task-1b F1 through heterogeneous fusion, while WAIPS-01 demonstrates the lowest participant DRR.
- The paper will report the resulting performance trade-offs rather than claim that one run is best on every metric.

---

## 5. Required References and NTCIR Elements

The final paper will:

1. cite the NTCIR-19 FEHU Task Overview paper supplied by the organizers;
2. cite the underlying human-value taxonomy / NEVU resource;
3. cite relevant prompt ensembling, long-tail multi-label learning, data augmentation, DeBERTa-v3, LoRA, and any calibration method actually used;
4. include the required **Team Name** and **Subtasks** fields before the Introduction;
5. label all development and official-test results by split;
6. stay within the NTCIR maximum of eight pages including references.

---

## 6. Items to Confirm Before Drafting the Full Paper

1. Which exact Liu run is used as the E7-G4 prompt component, and how is it transformed or reproduced in the E7 pipeline?
2. Which E7-G4 calibration, threshold, bootstrap, and gating claims have final code and reproducible logs?
3. Is there a no-DeBERTa E7-G4 ablation that supports a causal statement about augmentation?
4. Confirm final author order and individual author-contribution wording.

Until these items are verified, the paper should describe them as planned E7-G4 details rather than settled claims.

