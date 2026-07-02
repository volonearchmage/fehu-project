# 09_research_interpretation.md — Research Interpretation

## Why This Tiny Pilot Was Run

The FEHU Task-1 evaluation reveals two persistent, measurable problems:
(1) Rare labels suffer from near-zero recall, dragging down Macro-F1 (gold-supported).
(2) Direction-contrastive label pairs suffer from elevated Direction Reverse Rate (DRR),
    indicating the classifier confounds aligned and contradictory instances.

Both problems are plausibly attributable to training data sparsity and distributional
imbalance. This tiny pilot tests whether a controlled, human-approved LLM-based
augmentation pipeline can generate article-level training candidates that are:
  - Actor-specific (target actor is the grammatical subject of the value-bearing action)
  - Label-consistent (l1_value_id, l2_value_id match the approved request)
  - Direction-consistent (aligned="1", contradictory="0" per direction_mapping.json)
  - Evidence-grounded (evidence_sentence appears verbatim in content and supports the
    actor-value-direction relationship)

## Why Only 6 Requests Were Used

Six requests represent the smallest viable test of the end-to-end pipeline:
  - 2 rare_positive requests test generation on underrepresented label classes
    (L1=24 "Be neat and tidy", L1=32 "Be behaving properly")
  - 4 direction_contrastive requests (2 complete pairs) test whether the pipeline
    can produce direction-discriminating pairs without conflating aligned/contradictory

Starting with exactly 6 requests reduces API budget risk, limits safety exposure, and
ensures every generated sample can receive thorough human verification. All 6 requests
received explicit human approval by name before this script was run.

## Why rare_positive and direction_contrastive Were Selected First

These two augmentation types address the most directly measurable FEHU weaknesses:

  **rare_positive:** L1=24 and L1=32 both have mean_recall_dir=0.000 in the current
  model evaluation. Zero recall means the classifier never predicts these labels;
  even a small number of targeted training examples may shift the decision boundary
  and produce non-zero recall.

  **direction_contrastive:** L1=12 (Have success) and L1=38 (Be honest) have low
  precision due to over-prediction (mean_prec≈0.13). Paired contrastive samples —
  one aligned, one contradictory, same domain, different actors — provide direction-
  discriminating signal that is absent from single-direction training data. The
  hypothesis is that direction-contrastive augmentation should reduce DRR for these
  values.

## Why paraphrase, hard_negative, and sensitive-label Requests Were Deferred

  **paraphrase:** Adds density but not new class coverage or direction signal.
  Low marginal value at the pilot stage.

  **hard_negative:** Higher risk of confusing the model's decision boundary. Requires
  careful validation of what the "wrong" label is before use.

  **sensitive-label:** Requires additional ethical review before deployment as
  training data. Deferred to a later stage with specialist oversight.

## What This Generation Result Can Prove

If samples pass structural validation:
  - The pipeline produces schema-conformant, structurally valid JSON outputs.
  - The DeepSeek V4 model can follow the actor_mention/evidence_sentence verbatim
    inclusion constraint.
  - Label and direction fields can be mechanically verified against the approved
    manifest.
  - The pipeline is safe: it does not modify official data, evaluation code, or
    prediction files.

## What It Cannot Prove

  - It does NOT prove that adding these samples to training improves Macro-F1 or
    reduces DRR. An ablation experiment is required for that claim.
  - It does NOT prove that generated content is factually accurate or free from bias.
  - It does NOT prove that samples are annotation-consistent with the FEHU gold labels.
  - It does NOT prove that human verifiers will approve any sample for training use.

## Relationship to Rare-Label Recall, Macro-F1, and Direction Reverse Rate

  **Rare-label recall:** If human-verified samples for L1=24 and L1=32 are added to
  training, the classifier may begin predicting these labels. Increased recall for
  rare labels raises Macro-F1 (gold-supported), which averages F1 only over labels
  present in gold.

  **Macro-F1:** Currently near-zero recall for rare labels (L1=24, L1=32) drags the
  macro average below what the raw frequency distribution would suggest. Even one
  correct prediction per label moves recall from 0 to non-zero and may have outsized
  effect on the macro average.

  **Direction Reverse Rate (DRR):** Paired direction-contrastive samples for L1=12
  and L1=38 provide explicit contrastive signal for direction classification. The
  hypothesis is that they reduce DRR; this is to be tested in an ablation experiment,
  not assumed from generation quality.

## Why Generated Samples Are Not Training-Ready Until Human Verification

Human verifiers must confirm:
  1. Content is plausible and newsworthy, not hallucinated or misleading.
  2. actor_mention and evidence_sentence are factually appropriate for the scenario.
  3. The label and direction assignments match the article's semantic intent, not
     just the lexical surface of the evidence sentence.
  4. No defamatory, sensitive, factually incorrect, or ethically problematic content.
  5. The generated sample is distinct enough from training data to add value.

Only after human approval should samples enter a candidate augmentation set — and
even then, an ablation experiment is required to confirm impact before use in
official submissions.

## Recommended Next Experimental Steps

1. **Human verification first:** Review all samples in 08_human_verification_sheet.csv.
   For each sample with overall_validation_status = PASS or WARN, record a human
   decision (ACCEPT / REJECT) and notes.

2. **Create a small verified training candidate set:** Only human-ACCEPT samples
   should be collected into a candidate augmentation file. This is NOT the official
   training dataset; it is a controlled candidate pool.

3. **Run ablation experiment:** Fine-tune (or retrain) the classifier with and without
   the verified augmented samples. Measure delta in:
     - Macro-F1 (gold-supported) on dev set
     - Per-class recall for L1=24, L1=32
     - DRR for L1=12, L1=38

4. **Report delta only; do not claim general improvement:** Document which labels
   improve, which are unaffected, and any regressions introduced.

5. **Expand if ablation is positive:** If the ablation shows meaningful improvement,
   expand to more rare-label and direction-contrastive requests using a larger
   approved manifest — with the same human-approval gating.
