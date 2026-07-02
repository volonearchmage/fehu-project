# 03 — Rejected Candidates Report

## Number of Rejected Candidates
**1**

## Rejected Candidate IDs
- `prev_dir_contrast_12_002_contradictory_ce1da19f54`

## Per-Candidate Detail

### `prev_dir_contrast_12_002_contradictory_ce1da19f54`
| Field | Value |
|---|---|
| augmentation_type | direction_contrastive |
| target value | Have success (L1=12) |
| target direction | 0 contradictory |
| actor name | Oakridge High School |
| semantic verdict | REVIEW_SUGGESTED |
| human_decision | REJECT |

**human_notes:**
> Rejected. Although the article includes a championship loss, the overall framing is
> strongly positive, including the best record in a decade, MVP honors, scholarship
> offers, and a turning point for the program. This may indicate Have success aligned
> and creates direction-label noise for the contradictory label.

**Why it was excluded from the verified pool:**
This candidate was labeled `direction=0` (contradictory) for **Have success**, but the
article's overall framing is strongly positive. While the team lost the regional
championship (the single failure signal), the surrounding narrative emphasizes:
- a **22–6 record, the best in a decade**,
- **tournament MVP honors** for the senior point guard,
- **college scholarship offers** for several players,
- the season described as a **turning point for the program**.

A model trained on this article as a `contradictory` example risks learning to associate
strong success signals (records, awards, scholarships) with the contradictory direction —
i.e., **direction-label noise**. Because the annotator intuition plausibly leans toward
**Have success aligned**, the candidate was rejected to protect direction-label purity.
It is therefore excluded from `01_verified_augmented_candidates.jsonl` and
`02_verified_candidate_summary.csv`.

## Consequence
Rejecting this candidate leaves the **L1=12 Have success** direction_contrastive pair
**incomplete** (aligned accepted, contradictory missing). See
`04_pair_completeness_and_rerequest_plan.md` for the replacement plan.
