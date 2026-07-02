# 10_research_interpretation.md — Research Interpretation

## What the Initial Tiny Pilot Showed

The initial tiny pilot (6 requests, max_tokens=1800) produced:
- 1 fully valid (PASS) sample: `prev_dir_contrast_12_002_aligned_ce1da19f54`
- 2 structurally valid WARN samples: `prev_dir_contrast_38_003_contradictory_e969e14138`,
  `prev_rare_positive_32_001_83df110175`
- 1 validation FAIL (evidence verbatim issue): `prev_dir_contrast_38_003_aligned_e969e14138`
- 2 parse failures (token budget exhaustion): `prev_dir_contrast_12_002_contradictory_ce1da19f54`,
  `prev_rare_positive_24_004_98671d8d01`

The 3 KEEP samples demonstrated that the pipeline CAN produce actor-specific,
label-consistent, direction-consistent outputs. The 3 failures were technical rather
than semantic.

## Why Parse Failures Occurred

`deepseek-v4-pro` is a reasoning model. Its internal chain-of-thought tokens count against
the `max_tokens` limit. With `max_tokens=1800`:
- `prev_dir_contrast_12_002_contradictory`: 1772/1800 tokens consumed by reasoning;
  only ~28 tokens available for JSON output → truncated mid-string.
- `prev_rare_positive_24_004_98671d8d01`: all 1800 tokens consumed by reasoning →
  content field was empty string.

The fix: use `max_tokens=4096` for regeneration, giving the model sufficient budget for
both reasoning and JSON output.

The evidence verbatim failure for `prev_dir_contrast_38_003_aligned_e969e14138` was
different: the model's evidence_sentence field contained a truncated version of a complete
sentence in content. This is a minor formatting issue amenable to deterministic repair.

## Why Targeted Regeneration Is Better Than Rerunning All 6 Requests

Rerunning all 6 requests would:
1. Waste API tokens on 3 requests that already produced acceptable candidates.
2. Risk replacing a PASS/WARN sample with a worse regeneration.
3. Violate the principle of minimal intervention — if a sample is structurally valid,
   it should proceed to human verification, not be discarded.

Targeted regeneration applies only to the 2 requests that definitively failed
(finish_reason=length). The 1 deterministic repair case (evidence_sentence expansion)
is handled without any API call at all.

## Why Deterministic Evidence_Sentence Repair Is Acceptable

The evidence_sentence repair is a metadata field update, not a content change:
- The content, title, actor_name, actor_mention, labels, and direction are unchanged.
- The repair replaces a truncated sentence fragment with the complete sentence that
  already exists verbatim in content.
- The full sentence still supports the target actor, value, and direction.
- The repair is fully reversible (original_evidence_sentence is preserved).

However, this repair does NOT constitute automatic training approval. The repaired
sample still requires human verification to confirm the full sentence is semantically
appropriate as an evidence sentence.

## How Many Candidates Are Now Available for Human Verification

Unified candidates after repair/regeneration: 6
- For human verification (PASS + WARN): 6
- Excluded (FAIL): 0

## What This Proves

1. **Pipeline infrastructure works end-to-end.** The DeepSeek V4 runner successfully
   produces actor-specific, schema-conformant outputs when given sufficient token budget.
2. **Label and direction control is feasible.** All successfully parsed samples had
   correct l1_value_id, l2_value_id, direction, and is_positive fields.
3. **Output schema still needs strict constraints.** The initial pilot required strict
   brevity instructions to prevent reasoning from consuming the full token budget.
   The revised prompt (120–180 word content limit) should mitigate this.
4. **Deterministic repair is viable for minor verbatim-inclusion mismatches.** When the
   content is correct and only the evidence_sentence field is truncated, deterministic
   repair preserves the original generation while fixing the structural issue.

## What This Does NOT Prove

- **No model performance improvement.** Neither the initial pilot nor this repair step
  provides evidence that adding these samples to training will improve Macro-F1 or reduce
  DRR. An ablation experiment is required.
- **No training readiness.** All candidates remain PENDING_HUMAN_VERIFICATION. Human
  reviewers must confirm factual plausibility, semantic appropriateness, and annotation
  consistency before any sample enters a training candidate pool.
- **No final FEHU score improvement.** Score improvement requires (1) human-verified
  samples, (2) an augmented training run, and (3) evaluation on the dev or test set.

## Connection to FEHU Research Goals

**rare_positive targets** (L1=24 "Be neat and tidy", L1=32 "Be behaving properly"):
- Both values have mean_recall_dir=0.000 in the current model.
- Providing positive examples may shift the classifier's decision boundary to produce
  non-zero recall for these labels.
- Impact on Macro-F1 (gold-supported) depends on how frequently these labels appear
  in gold labels.

**direction_contrastive targets** (L1=12 "Have success", L1=38 "Be honest"):
- Both have low precision due to over-prediction (mean_prec≈0.13).
- Paired aligned/contradictory samples for the SAME domain but DIFFERENT actors provide
  direction-discriminating signal that single-direction training data lacks.
- Expected to reduce DRR (Direction Reverse Rate) for these values if training succeeds.

## Recommended Next Steps

1. **Human verification of 09_human_verification_sheet_REPAIRED.csv**
   Review all PASS and WARN samples. For each row, record:
   - human_decision: ACCEPT or REJECT
   - human_notes: specific concerns or confirmations

2. **Create a small verified augmented candidate set (not official gold):**
   Collect only human-ACCEPT samples into a candidate augmentation pool.
   Do NOT add to the official training dataset directly.

3. **Run ablation experiment:**
   - Baseline: train with official training data only.
   - Augmented: train with official data + verified augmented candidates.
   - Compare: Macro-F1, per-class recall for L1=24/32, DRR for L1=12/38.
   - Report delta only; note any regressions.

4. **Expand only if ablation is positive:**
   If the ablation shows meaningful improvement without regressions, expand to more
   rare-label and direction-contrastive requests with a larger approved manifest.
