# Deferred Requests After Human Decision

12 of 18 v2 preview requests are deferred from the first conservative tiny pilot. **All 12 are DEFER, not REJECT** — they remain available for later waves once the first pilot is validated.

## Group 1 — All paraphrase requests (4)

Deferred because **all 4 paraphrase candidates have `seed_excerpt_truncated=True`** in the v2 preview. Paraphrase is the only request type that uses the seed text as the primary content source (rather than as a style reference); a truncated seed therefore raises the risk that the rewrite either drops material context or invents details to fill the gap.

| Request ID | L1 | Label | Direction |
|---|---:|---|---|
| `prev_paraphrase_32_001_735dc24587` | 32 | Be behaving properly | 0 (contradictory) |
| `prev_paraphrase_51_002_e5406084c6` | 51 | Have the wisdom to accept others | 0 (contradictory) |
| `prev_paraphrase_7_003_97e379f741` | 7 | Have an exciting life | 0 (contradictory) |
| `prev_paraphrase_24_004_fc69036780` | 24 | Be neat and tidy | 1 (aligned) |

**Path forward:** revisit in a later wave with a longer seed window or a hand-curated 1500-char excerpt.

## Group 2 — All hard_negative requests (4)

Deferred because hard_negative is structurally the hardest type (it has to produce a near-miss that is topic-relevant but actor-specific value-negative, plus an explanation that points to the actor's stance rather than topic difference). Two of the four also have `alternative_label_id = null`, which means the generator would have to invent the alternative L1 from scratch.

| Request ID | L1 | Label | `alternative_label_id` |
|---|---:|---|---|
| `prev_hard_negative_32_001_caf1a3dfb5` | 32 | Be behaving properly | 31 (set) |
| `prev_hard_negative_51_002_10a7cdd970` | 51 | Have the wisdom to accept others | null |
| `prev_hard_negative_7_003_d2ddea18f0`  | 7  | Have an exciting life | 8 (set) |
| `prev_hard_negative_29_004_6883966fd8` | 29 | Be holding religious faith | null |

**Path forward:** add hard-negatives in a second wave with `alternative_label_id` manually pre-filled, once the first pilot succeeds.

## Group 3 — Sensitive-label requests (3)

Deferred from the first conservative pilot because the labels can touch protected-group or religious context. The requests themselves are structurally well-formed; the deferral is policy-driven, not quality-driven.

| Request ID | Type | L1 | Label |
|---|---|---:|---|
| `prev_paraphrase_51_002_e5406084c6` | paraphrase | 51 | Have the wisdom to accept others (also covered in Group 1) |
| `prev_rare_positive_51_002_6796672415` | rare_positive | 51 | Have the wisdom to accept others |
| `prev_hard_negative_51_002_10a7cdd970` | hard_negative | 51 | Have the wisdom to accept others (also in Group 2) |
| `prev_hard_negative_29_004_6883966fd8` | hard_negative | 29 | Be holding religious faith (also in Group 2) |
| `prev_dir_contrast_29_001_aligned_0991b57a47` | direction_contrastive | 29 | Be holding religious faith |
| `prev_dir_contrast_29_001_contradictory_0991b57a47` | direction_contrastive | 29 | Be holding religious faith |

**Path forward:** revisit once the first pilot has demonstrated that the generator handles non-sensitive requests cleanly. Sensitive-label generation will need extra verifier scrutiny.

## Group 4 — `rare_positive` "Have an exciting life" (1)

Deferred because the label is abstract enough that synthetic generation may produce generic/non-news-like content ("they pursued thrills…"). The seed is grounded but the L1 itself overlaps with `Have a varied life` and `Be daring`, so the model may drift.

| Request ID | L1 | Label | Direction |
|---|---:|---|---|
| `prev_rare_positive_7_003_49cbb6617c` | 7 | Have an exciting life | 1 (aligned) |

**Path forward:** revisit after the first pilot; consider adding a tighter actor-archetype hint and an explicit "do not produce generic adventure-tourism copy" instruction.

## Group 5 — Other (none in this pack)

No further deferrals beyond Groups 1–4. The first pilot is intentionally conservative: 2 rare_positive (non-sensitive, non-abstract) + 2 complete direction_contrastive pairs (non-sensitive).

## Summary

| Reason cluster | Distinct requests |
|---|---:|
| Truncated seed (paraphrase) | 4 |
| Hard-negative (structurally hardest; 2 also null-alt) | 4 |
| Sensitive label (29 religion / 51 tolerance) | 4 unique (some overlap with above) |
| Generic-content risk (rare_positive 7) | 1 |
| **Total deferred** | **12** |

All 12 deferred requests retain `preview_revision: 2`, `preview_only: true`, `do_not_execute: true`. They are still available, untouched, in `output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl`.
