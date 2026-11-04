# Risk Scoring Rules — Human Review Pack v1

This document describes the rules used to compute `risk_score` and `risk_level` for every request in `01_request_review_table.csv`. Scoring is deterministic and reproducible from the rules below.

## Base

Every request starts at `risk_score = 0`.

## Additive penalties

| Rule | Trigger | Δ |
|---|---|---:|
| Truncated seed (paraphrase) | `seed_excerpt_truncated == True` AND `augmentation_type == "paraphrase"` | **+2** |
| Truncated seed (rare_positive) | `seed_excerpt_truncated == True` AND `augmentation_type == "rare_positive"` | **+0**¹ |
| Type = hard_negative | `augmentation_type == "hard_negative"` | **+2** |
| hard_negative with null alt | `hard_negative` AND `alternative_label_id ∈ {null, "", None}` | **+2** |
| hard_negative evidence | `augmentation_type == "hard_negative"` (intrinsically harder evidence req) | **+1** |
| Direction-contrastive missing pair | `direction_contrastive` AND `paired_request_id` empty | **+2** |
| Long / unnatural actor mention | `len(canonical_actor_name) > 120` OR long parenthetical (`(…)` plus length > 80) OR contains `including` and length > 80 | **+1** |
| Abstract / confusable label | `target_l1_value_id ∈ {32, 51, 7, 38}`² | **+1** |
| Sensitive content | `target_l1_value_id ∈ {29, 44, 51}`³ | **+1** |
| Strong factual specificity required | `augmentation_type ∈ {hard_negative, direction_contrastive}` OR (`rare_positive` AND no `seed_guid`) | **+1** |

¹ For paraphrase, the seed text is the **primary source** of content; truncating it materially raises the risk that the rewrite invents facts. For rare_positive, the seed excerpt is a **style reference only** (≤300 chars), and the LLM generates fresh content — truncation does not materially raise risk. The flag is still recorded for transparency but does not add to the score.

² Labels with overlapping definitions inside FEHU's L2 families. Empirically, these labels also show direction or precision issues in `output/research_label_diagnosis/20260613_145847/`.

³ Sensitive-content list is conservative-by-design for the first tiny pilot. It can be relaxed in a later pack once we have direct evidence that the generator handles them safely.

## Subtractive credits

| Rule | Trigger | Δ |
|---|---|---:|
| Complete identity + label + non-blocking truncation + clear evidence req | `canonical_actor_name` non-empty (or invented-actor type) AND both `target_l1_value_id` and `target_l2_value_id` set AND (no seed truncation OR type ≠ paraphrase) AND `evidence_requirement` non-empty | **−1** |
| Paraphrase with self-contained seed | `paraphrase` AND seed exists AND not truncated | **−1** |
| Rare_positive with grounded seed + non-sensitive | `rare_positive` AND seed exists AND `target_l1_value_id ∉ SENSITIVE` | **−1** |

## Risk level

| Score | Level |
|---|---|
| ≤ 1 | **LOW** |
| 2 – 3 | **MEDIUM** |
| ≥ 4 | **HIGH** |

## Decision policy applied this pass (DRAFT only)

The script proposes `recommended_decision` from the score plus a few overrides — **the human reviewer remains the final authority**.

| Condition | Proposed decision |
|---|---|
| `risk_level == HIGH` | `DEFER` |
| `risk_level == MEDIUM` | `DEFER` (conservative first pilot) |
| `risk_level == LOW` | `DRAFT_CANDIDATE` |
| `augmentation_type == hard_negative` AND `alternative_label_id` is null | force `DEFER` |
| `target_l1_value_id ∈ SENSITIVE_L1` | force `DEFER` |
| Direction-contrastive pair where one side is `DEFER` | force the other side to `DEFER` (keep pairs together) |

## Notes on transparency

- The `reason` column in `01_request_review_table.csv` lists every triggered rule for every request, so any reviewer can re-derive the score.
- No request is marked `APPROVED` automatically. The DRAFT manifest carries `manual_approval_status = "PENDING_HUMAN_APPROVAL"`.
- Words like `approved`, `approved_manifest`, `ready_for_generation`, `execute`, `should_execute_now` do not appear anywhere in the pack.
