<!--
Working paper draft for NTCIR-19 FEHU Task 1.

This Markdown file is the prose source. paper_preview.tex mirrors the same
content in the official ACM/NTCIR two-column layout for page-budget checks.

Open items intentionally left for collaborators:
  - Section 3 (WAIPS-01): reserved for Dongyang Liu, target 1.7 A4 pages.
  - Section 7 (Related Work): reserved.
  - References: reserved; the FEHU Task Overview must be cited in the final paper.
  - Author order, affiliations, and e-mail addresses.

Evidence boundary:
  The augmentation experiments establish better score-level separation on the
  selected tail labels. They do not isolate the causal contribution of
  DeBERTa to the final E7-G4 score. Keep this distinction in later revisions.
-->

# WAIPS at NTCIR-19 FEHU Task 1: Label-Aware Prompt Ensembling and Gated Fusion for Human-Value Recognition

**Peiyang Huang, Dongyang Liu, and the WAIPS team**  
*Affiliations and author order to be confirmed*

## Abstract

We present the three WAIPS runs submitted to NTCIR-19 FEHU Task 1, which asks systems to recognize actor-conditioned human values in news and, for fine-grained values, predict direction. Our development experiments exposed a recurring trade-off. Conservative prompt ensembles preserve direction but miss infrequent values; recall-oriented methods recover more labels but add false positives. WAIPS-01 selectively adds labels from a targeted prompt to a conservative majority according to label-wise analysis on development data. WAIPS-03 augments difficult directed labels and tunes DeBERTa-v3-base with LoRA and masked partial-label supervision. The encoder probabilities join heterogeneous prompt jurors in calibrated, frequency-gated veto and addition rules, followed by focused direction verification. WAIPS-03 scores 0.5808 Micro-F1 and 0.3952 Macro-F1 on official Task 1b, the highest Macro-F1 among participant runs. WAIPS-01 has the lowest participant Direction Reverse Rate (DRR), 0.0345. Targeted augmentation improves score separation for 18 low-frequency labels, and E6b supplies direct tail recall. Their combination under conservative gates supports macro performance, although the missing final no-DeBERTa ablation prevents assigning the official gain to one component.

**Keywords:** human values, multi-label classification, long-tail learning, data augmentation, prompt ensemble, calibrated fusion

## Team Name

WAIPS

## Subtasks

Task 1a and Task 1b

## 1 Introduction

Human values are often expressed indirectly in news. A report may describe the same decision as protecting public safety for one actor and restricting freedom for another. Recognizing a value therefore requires more than locating a topical phrase: the system must identify whose action is being judged, which value it bears on, and whether the action aligns with or contradicts that value. The FEHU Task 1 makes these choices explicit. Task 1a asks for directionless Level-2 values for each article--actor pair, while Task 1b evaluates directed Level-1 values. We refer readers to the Task Overview by Wang et al. for the collection construction, taxonomy, and official evaluation protocol.

Three properties of the task shaped our work. First, the output space is strongly imbalanced. A small group of values appears throughout the training set, while many directed Level-1 classes have only a few examples. A system can therefore obtain reasonable Micro-F1 while never predicting several valid labels. Second, increasing recall is unusually expensive: every extra value creates another opportunity for both a false positive and a direction reversal. Third, the available models make different errors. Prompt variants disagree in useful ways, and the encoder can expose weak tail-label evidence that is not reliable enough to use as a final decision by itself.

Rather than forcing these components into a single voting rule, we assigned them different jobs. WAIPS-01, developed by Liu, starts with a conservative prompt majority and selectively restores predictions for labels on which a targeted prompt was demonstrably better. A separate augmentation track diagnoses difficult directed labels, generates focused training cases, and trains a parameter-efficient DeBERTa classifier to supply continuous evidence. WAIPS-03 (E7-G4) uses E6b, a recall-oriented prompt system with self-segmentation, as its primary generator; other prompt runs and the augmented encoder act as jurors. A calibrated gate removes weak frequent-class predictions and admits a small number of supported additions. Direction is then checked only when jurors explicitly disagree.

This division of labour is also how we interpret the results. E6b supplies much of the direct tail recall, the DeBERTa track improves representation of selected low-frequency labels and contributes an auxiliary probability signal, and the fusion layer controls the precision cost of combining them. We report both F1 and DRR throughout because the official runs occupy visibly different points on that trade-off.

## 2 Task Setting and Submitted Runs

For each actor listed in an article, Task 1b requires a set of `(Level-1 value, direction)` pairs. We treat the two directions of each of 54 Level-1 values as 108 atomic classes. Task 1a is obtained by mapping the predicted Level-1 values to their Level-2 parents and discarding direction. Development experiments use the official 177-article development set. The frozen inference pipelines were then applied to 175 test articles containing 479 released article--actor pairs; no test labels or Task-2 annotations were used.

We follow the official evaluator and the Task Overview in treating Micro-F1 as the primary ranking measure. Macro-F1 is averaged over labels that occur at least once in the test gold data, which makes it a useful but support-dependent view of tail behavior. DRR counts opposite-direction predictions for gold actor--value pairs with a unique direction. A missed value does not count as a reversal, so a low DRR must be read together with F1 rather than as a standalone accuracy measure.

The three submissions were deliberately different. WAIPS-01 is Liu's label-aware prompt ensemble, described in Section 3. WAIPS-02 uses a three-way majority vote over DeepSeek Pro prompt variants and uses a Flash prediction, when available, to arbitrate direction. WAIPS-03 is the E7-G4 heterogeneous fusion described in Sections 5 and 6. This paper focuses on WAIPS-01 and WAIPS-03 because they embody the two main methodological lines; WAIPS-02 is retained as a useful prompt-only reference point.

| Run | Short description | Role in the paper |
|---|---|---|
| WAIPS-01 | Label-aware prompt ensemble | Direction-stable, selectively recovers difficult labels |
| WAIPS-02 | Three-way prompt majority + direction arbitration | Prompt-only comparison |
| WAIPS-03 | E7-G4 gated heterogeneous fusion | Highest WAIPS Task-1b Micro/Macro-F1 |

WAIPS-02 provides a useful middle point between the other two submissions. One DeepSeek Pro prompt is the baseline, one is compact and strict, and one uses targeted balanced few-shot examples; all run at temperature zero. A label is retained when at least two runs emit the same actor, value, and direction. The Flash run is then consulted only for direction: when it predicts the same actor and value with the opposite direction, the majority direction is replaced. Task 1a is deterministically projected from the resulting Task-1b set. Unlike E7-G4, this run has no learned calibrator, encoder features, frequency gate, or per-cell QA call.

## 3 Label-Aware Prompt Ensembling (WAIPS-01)

> **Reserved for Dongyang Liu — target length: approximately 1.7 A4 pages in the official two-column template.**
>
> The reserved section should retain Liu's standalone method rather than describe only the Liu juror used in E7-G4. The agreed scope is: the baseline/compact/compact-strict majority base; per-label diagnosis; the ten selected directed labels; selective additions from `targeted_more_shot_balanced`; the controlled development comparison; and the official WAIPS-01 result. The LaTeX preview reserves the corresponding physical space without inventing prose or implementation details.

<!--
Suggested subsection boundaries for Liu:
3.1 Prompt variants and majority base
3.2 Label-level diagnosis and ten-label selection
3.3 Selective-addition algorithm
3.4 Development and official results

Development table already verified in the outline:
Majority:     micro .5359, macro .3532, P .6350, R .4636, DRR .0180
Targeted:     micro .5387, macro .3679, P .5750, R .5067, DRR .0302
Label-aware:  micro .5657, macro .3870, P .6149, R .5238, DRR .0279
-->

## 4 Diagnosis-Guided Augmentation for Rare-Label Evidence

### 4.1 From label diagnosis to generation targets

Our initial DeBERTa classifier used a 108-dimensional sigmoid head and a single global threshold. Per-label analysis showed that this model had effectively learned no usable ordering for many low-frequency directed labels. We therefore selected targets at the directed Level-1 class evaluated by Task 1b, rather than augmenting undirected values uniformly. A class was eligible when its official training count was at most 130 and its development support was at least three. Ranking the eligible classes by diagnostic evidence produced 18 frozen targets: 14 contradictory and four aligned classes, spanning 12 Level-2 groups.

The data were constructed in two rounds. Round 1 covered six Level-1 values in both directions. DeepSeek V4 Pro generated 422 candidates; deterministic checks and an independent LLM semantic screen retained 340 silver records. These records were machine-screened, not manually verified. Round 2 concentrated on the 18 directed targets and allocated exactly 50 records to each target. Its 900 records mix targeted in-context generation, direction contrast cases, situation transformations, and hard negatives (Table 2). The hard-negative group includes 36 explicitly known negative labels. All Round-2 records passed schema, taxonomy, actor mention, direction, and duplicate checks, but they did not receive semantic LLM screening or human review. We keep this provenance distinction because it limits what can be claimed about data quality.

| Round-2 strategy | Records | Supervision supplied | Purpose |
|---|---:|---|---|
| Targeted in-context generation | 450 | Full multi-label (2--5 labels) | Place the target in varied news contexts and retain co-occurring values |
| Direction-contrastive generation | 180 | Target-only (90 pairs) | Distinguish aligned from contradictory realizations of the same value |
| Situation transformation | 180 | Target-only | Re-express a value through a different actor, action, or setting |
| Hard-negative generation | 90 | Target-only; 36 known negatives | Separate the target from topically close but incorrect values |

Generation was deliberately more constrained than free-form paraphrasing. Each request fixed the actor, target identity, direction, and a news-style evidence requirement. Local validators rejected malformed mappings, absent actors, unsupported evidence sentences, forbidden meta-language, and duplicates before a record could enter a training input. The generation gates rejected and regenerated 67 Round-1 and 472 Round-2 candidates; the later Round-1 semantic screen separately excluded 82 of 422 records. The distinction between structural gates and semantic review is important: the former establishes format and internal consistency, not that every synthetic label is correct.

### 4.2 Partial-label training

The final training set contains 1,228 official articles, 340 Round-1 records, and 900 Round-2 records: 2,468 articles and 4,575 actor examples in total. Synthetic news vignettes are often only partially annotated. Treating every unlisted class as negative would create hundreds of false-negative training signals, especially for the single-target records. We therefore mark 3,785 examples as fully supervised and 790 as `target_only`. For a target-only example, binary cross entropy is evaluated only on its known positive entries and any explicitly known negatives; the remaining label positions receive a zero loss mask.

We fine-tune `microsoft/deberta-v3-base` with LoRA adapters on the query and value projections (`r=16`, `alpha=32`, dropout 0.1) and a 108-way classification head. Inputs pair the article text with the actor name, use a maximum length of 512, and are optimized with class-weighted binary cross entropy. The positive weight for each class is `sqrt(n_negative / n_positive)`, clipped to `[1, 10]` and computed over supervised entries only. Models are selected by development Task-1b Micro-F1 and decoded at a global threshold of 0.30. In E7-G4 the encoder never assigns the final direction: we export all 108 sigmoid probabilities and use them only as continuous jury features.

For example `i` and directed class `k`, let `m_ik` be one for an observed label decision and zero for an unknown entry. Training minimizes

`L = sum(i,k) m_ik w_k BCE(y_ik, z_ik) / sum(i,k) m_ik`.

All mask entries are one for official and full-multilabel records. On target-only records, only the intended positives and explicitly supplied hard negatives contribute. This does not rebalance the dataset to 50:50; it prevents missing synthetic annotations from becoming certain negatives. The distinction matters in a 108-class problem, where a single partially annotated example would otherwise create more than one hundred negative loss terms.

### 4.3 What the augmentation did—and did not—establish

The most informative comparison is score-level separation on the 18 targets. With official data only, mean target AUC was 0.536 and mean per-target oracle F1 was 0.053. The augmented v2 checkpoint raised these values to 0.697 and 0.112; AUC improved for 14 of 18 targets and oracle F1 for 16 of 18. Thus the generated supervision changed how target positives were ranked, rather than merely pushing an unchanged score distribution across the 0.30 threshold.

| Tail-label diagnostic (development) | Official-only | Augmented v2 |
|---|---:|---:|
| Mean AUC over 18 targets | 0.536 | **0.697** |
| Mean per-target oracle F1 | 0.053 | **0.112** |
| Targets with AUC at or below 0.55 | 11/18 | **3/18** |

The three-seed comparison isolates the 900 Round-2 records. It gives a second view of the same effect: the official-only condition remains close to chance (mean target AUC 0.513), whereas the 900 records raise AUC to 0.624 with assume-negative supervision and 0.577 with masking. Both improvements have the same sign for all three matched seeds. With the complete 340+900 data, masked supervision was retained because it had the better mean full-data result and protected the sparsely annotated Round-1 records; its mean target AUC was 0.632, but with a standard deviation of 0.105.

| Three-seed target analysis | Mean target AUC | Mean target oracle F1 |
|---|---:|---:|
| Official only | 0.513 ± 0.030 | 0.048 ± 0.010 |
| +900, assume-negative | **0.624 ± 0.011** | **0.095 ± 0.014** |
| +900, masked | 0.577 ± 0.028 | 0.080 ± 0.019 |
| +340+900, masked | 0.632 ± 0.105 | 0.111 ± 0.049 |

The gain is useful but not a claim of a solved tail classifier. Three full-data seeds showed substantial variance: target true positives were 0, 0, and 37, and overall Macro-F1 ranged from 0.022 to 0.182. This is why the encoder is an auxiliary source rather than a submitted standalone model. It is also why we describe the final macro result as a joint effect of tail-oriented generation, E6b's direct recall, and gated fusion. A clean final-fusion ablation without DeBERTa is not available, so the official E7-G4 gain cannot be assigned causally to augmentation alone.

## 5 E7-G4: Frequency-Gated Heterogeneous Fusion

### 5.1 Members with deliberately different roles

E7-G4 starts from E6b, a prompt pipeline that first segments an article into six to nine coherent developments and then predicts values for each actor using a fixed few-shot scaffold. This granularity constraint is small but consequential. Its predecessor E6 produced a median of 12 segments and achieved high recall with many false positives. Asking the segmenter to merge closely related sentences reduced the median to eight. On development data, E6b improved over E6 from 0.5412 to 0.5496 Micro-F1 and from 0.4079 to 0.4124 Macro-F1. Relative to the earlier E1 prompt run, its Micro-F1 changed only slightly (0.5480 to 0.5496), but Macro-F1 rose by 0.0405. We therefore use E6b as the primary generator: it already carries the broad coverage that a later fusion stage cannot manufacture.

The jurors serve different roles. E1 uses a balanced article-level prompt. E6 instead uses finer self-segmentation to favor recall. E6c runs DeepSeek Pro without thinking over the E6b segments. It has the strongest individual Task-1a development result (0.6774) but weak direction behavior; we therefore use it as value evidence, not as a direction authority. The local Liu component is one `targeted_more_shot_balanced` prompt run and is distinct from the complete label-aware WAIPS-01 method in Section 3. Finally, the augmented DeBERTa model contributes continuous probabilities rather than discrete predictions.

| Member | 1b Micro / Macro-F1 | DRR | Assigned role in E7 |
|---|---:|---:|---|
| E1 | 0.5480 / 0.3719 | 0.0347 | Balanced article-level juror |
| E6 | 0.5412 / 0.4079 | 0.0504 | Fine-segmentation, recall-oriented juror |
| **E6b** | **0.5496 / 0.4124** | 0.0459 | Primary generator |
| E6c | 0.5343 / 0.3725 | 0.0657 | Value-evidence and disagreement juror |
| Local Liu component | 0.5347 / 0.3385 | **0.0230** | Precision-oriented juror |
| Augmented DeBERTa | probabilities only | -- | Continuous exact/value evidence |

```
article + actor
      |
      +--> E6b primary predictions --------------------+
      |                                                |
      +--> E1 / E6 / E6c / Liu prompt jurors          |
      +--> augmented DeBERTa probabilities             |
                                                       v
                         calibrated veto and additions (G3)
                                                       |
                         disagreement-triggered direction QA
                                                       |
                                             Task-1b predictions
                                                       |
                                      deterministic L1-to-L2 projection
                                                       v
                                             Task-1a predictions
```

### 5.2 Calibrated veto and additions

For an actor and directed value cell `c`, the removal score combines exact-direction votes, value-only votes, and the encoder's directionless value score:

`s_remove(c) = n_exact(c) + 0.25 n_value-only(c) + p_DeBERTa(value(c)).`

For a candidate not emitted by E6b, the addition score is stricter:

`s_add(c) = n_exact(c) + p_DeBERTa(c).`

Pool-adjacent-violators calibration maps each monotone score to an empirical probability of being gold. During development, calibration is two-fold cross-fitted by article, so an article's own labels do not determine its mapping. For test inference, the mapping is fitted once on the full development set and applied unchanged. The decision threshold follows the plug-in expected-F1 rule, `tau = F1_primary / 2`; the frozen full-development value is 0.27479.

The rules are intentionally asymmetric. A primary cell is removed only when its calibrated probability is below `tau`, it belongs to one of 38 frequent directed classes (official training count greater than 130), and the actor retains at least one label. A non-primary cell can be added only when it was proposed by a juror, its calibrated probability reaches `tau`, it is in the same frequent tier, and E6b does not already hold the value in either direction. Additions are capped at two per actor. The frequency gate matters: removing weak tail predictions reduced Macro-F1 sharply in the ungated development control. It also means that the 18 augmentation targets are not directly switched on or off by the G3 actions; the encoder supplies broader score evidence, while E6b remains the main direct source of tail labels.

### 5.3 Focused direction repair

The last stage addresses a different error. A fused prediction is sent to direction QA only if at least one juror predicts the same value in the opposite direction and the fused set does not already contain both directions. DeepSeek Flash then receives the article, actor, and one value and returns only `aligned` or `contradictory`. On development data, 176 cells were flagged and 46 were flipped; seven failed all retries and were retained with explicit failure records. On test, 207 cells were flagged, 77 were flipped, and five failed and were retained. Because this stage never introduces a new value, it can repair direction without reopening the value-selection problem.

### 5.4 Frozen development-to-test transfer

The complete test path was executed as a fit--apply procedure. All prompt members read only `test_article_event_base.json`; E6 and E6b generated their own segmentations because official test subevents were unavailable. The removal and addition calibrators were fitted on all development data and loaded unchanged for test. We also froze the frequency tier, score weights, threshold, maximum of two additions, and QA trigger. Every empty API response or parsing failure was retried and then either caused the stage to fail or, for the predeclared QA behavior, was logged while retaining the original direction.

Before submission, both files were checked for complete article coverage, valid actor membership, taxonomy ranges, duplicate tuples, and deterministic Task-1a projection. The final WAIPS-03 output contained 2,764 directed labels, covering 93 of the 108 classes and all 54 Level-1 values. These counts cannot substitute for test labels, but the removal/addition profile was close to development and gave no operational indication of a broken transfer pipeline.

## 6 Experiments and Results

### 6.1 Development results

Table 2 follows the construction of E7-G4. The first comparison is important for the paper's macro-F1 interpretation: E6b already raises Macro-F1 by 0.0405 over E1. The calibrated veto (G1) mainly restores precision. Re-enabling supported additions (G3) provides the largest single fusion increment, and direction QA (G4) produces a smaller but consistent improvement in Micro-F1, Macro-F1, and DRR.

| Development system | 1b Micro-F1 | P / R | 1b Macro-F1 | 1a Micro-F1 | DRR | Target-18 F1 |
|---|---:|---:|---:|---:|---:|---:|
| E1 | 0.5480 | .541 / .556 | 0.3719 | 0.6574 | 0.0347 | 0.2460 |
| E6b primary | 0.5496 | .502 / .608 | 0.4124 | 0.6621 | 0.0459 | 0.3145 |
| G1: calibrated veto | 0.5608 | .559 / .563 | 0.4146 | 0.6587 | **0.0374** | 0.3145 |
| G3: veto + additions | 0.5790 | .539 / .626 | 0.4266 | 0.6874 | 0.0450 | 0.3145 |
| **G4: G3 + direction QA** | **0.5817** | **.542 / .629** | **0.4308** | **0.6874** | 0.0419 | **0.3264** |

The G4--E6b Micro-F1 difference is 0.0321. A paired article bootstrap with 10,000 resamples gives a 95% interval of `[0.0209, 0.0433]`. This interval measures article-sampling variation; it does not measure nondeterminism across LLM calls. Operationally, G1 removed 484 predictions on development data and G3 admitted 364. The test pipeline was frozen before inference and produced a similar action profile: 529 removals and 365 additions. These counts are useful sanity checks, not test-set quality estimates.

Two controls clarify why the final rule is gated. Removing Liu from the veto jury changes Micro-F1 only from 0.5608 to 0.5619, so Liu is not load-bearing for removals; its precision profile is more useful when additions are considered. Conversely, allowing vetoes on all classes gives 0.5703 Micro-F1 but only 0.3900 Macro-F1. This is the failure mode the frequency gate was designed to prevent: a weak auxiliary score can look useful in aggregate by suppressing difficult labels that macro-F1 is intended to expose.

### 6.2 Where the macro gain enters

The development path makes the macro story more specific than the final run comparison alone. Moving from E1 to E6b raises Macro-F1 from 0.3719 to 0.4124 (+0.0405) while changing Micro-F1 by only +0.0016. The frequent-class veto then adds +0.0022 Macro-F1, supported additions add a further +0.0120, and direction QA adds +0.0042. The 18-target Micro-F1 is 0.3145 for E6b and remains unchanged through G1 and G3; direction QA raises it to 0.3264.

This decomposition matches the assigned roles. E6b is the component that directly emits most of the additional tail labels. Augmentation makes the DeBERTa score space less blind to rare labels and contributes a continuous confidence signal, but the frequent-class gate prevents G3 from directly adding the 18 selected targets. Its support for the final macro-oriented system is therefore indirect and shared with the prompt jury. We regard the official macro advantage as consistent with the combined design, not as a demonstration that augmented DeBERTa alone caused it.

### 6.3 Official results

The Task Overview reports four evaluated run packages from two teams: three from WAIPS and one from IIUoT. The results show different trade-offs rather than one uniformly dominant run. WAIPS-02 gives our highest Task-1a Micro-F1, WAIPS-03 gives our strongest Task-1b Micro- and Macro-F1, and WAIPS-01 gives the lowest DRR among all participant runs. Across teams, IIUoT-01 leads the primary Micro-F1 ranking on Tasks 1a and 1b, while WAIPS-03 has the highest participant Task-1b Macro-F1. The organizer baseline is an unranked reference and exceeds every participant run on Task-1b Micro- and Macro-F1. We therefore state the macro result as a participant comparison, not as overall task dominance.

| System / run | Task-1a Micro / Macro-F1 | Task-1b Micro / Macro-F1 | Task-1b DRR |
|---|---:|---:|---:|
| Organizer baseline (unranked) | 0.6782 / 0.5405 | 0.6284 / 0.4402 | 0.0386 |
| IIUoT-01 | **0.7042 / 0.5808** | **0.5979** / 0.3930 | 0.0613 |
| WAIPS-01 | 0.6589 / 0.5366 | 0.5543 / 0.3277 | **0.0345** |
| WAIPS-02 | 0.6930 / 0.5646 | 0.5496 / 0.3580 | 0.0395 |
| **WAIPS-03 (E7-G4)** | 0.6862 / 0.5705 | 0.5808 / **0.3952** | 0.0477 |

The development and official results tell a consistent, if not perfectly tidy, story. Broad value recovery helps macro-F1, but it increases exposure to direction mistakes. WAIPS-01 is the conservative end of this spectrum. E7-G4 accepts a higher DRR in exchange for more labels and higher Task-1b F1. Its targeted direction QA reduces the development reversal rate after additions, but does not erase the underlying coverage--direction trade-off on the official test set.

### 6.4 Error patterns and limitations

Two errors remain common. The first is over-generation of plausible values for a nearby actor or for the article in general. Self-segmentation makes more local evidence visible, but a value can still be attached to an actor who is mentioned rather than responsible. The calibrated veto repairs some of these errors only in frequent classes. The second is direction ambiguity. Jurors often agree that a value is relevant while disagreeing about whether the actor supports or undermines it; focused QA helps, but ambiguous reporting and multiple actions by one actor remain difficult.

There are also limits to the evidence behind our interpretation. The fusion weights, frequency gate, and threshold family were designed through development-era analysis, even though calibration was cross-fitted and the test pipeline was frozen. The Round-2 synthetic data were structurally checked but not semantically screened, and masked DeBERTa training has high seed variance. Most importantly, the final fusion was not rerun in a controlled no-DeBERTa condition, so the augmentation track's causal share of the official macro result is unknown. We can safely say that it improves low-frequency score separation and provides auxiliary evidence; E6b and the LLM jury remain essential. Finally, results from two participating teams should not be read as a broad leaderboard conclusion.

## 7 Related Work

> **Reserved.** Keep this section short (approximately 0.25--0.35 page): prompt voting/self-consistency; long-tail multi-label learning and targeted synthetic augmentation; DeBERTa-v3 and LoRA; confidence calibration; and human-value recognition. Each citation should support a concrete design choice rather than repeat the FEHU Task Overview.

## 8 Conclusion

Our Task-1 systems were built by treating label recovery, precision control, and direction assignment as separate problems. Liu's WAIPS-01 method uses label-level diagnosis to recover selected misses without abandoning a conservative prompt majority. The augmentation track gives a LoRA-tuned DeBERTa encoder substantially better score-level separation on selected rare directed labels, while E6b supplies strong direct tail recall through granularity-controlled self-segmentation. E7-G4 combines these heterogeneous signals with calibrated, frequency-gated veto and addition rules and repairs direction only where jurors disagree. The official results reflect the intended trade-off: WAIPS-03 reaches 0.5808 Micro-F1 and 0.3952 Macro-F1 on Task 1b, while WAIPS-01 remains more direction-stable. A clean component ablation and more stable tail training are the clearest next steps.

## References

> **Reserved for the camera-ready draft.** The final list must at least contain the NTCIR-19 FEHU Task Overview, the human-value taxonomy/resource paper, DeBERTa-v3, LoRA, relevant prompt-ensemble work, long-tail multi-label learning, synthetic-data augmentation, and the calibration method actually described above.
