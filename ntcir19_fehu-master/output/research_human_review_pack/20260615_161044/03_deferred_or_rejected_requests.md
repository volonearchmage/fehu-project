# Deferred or Rejected Requests

11 of the 18 v2 preview requests are **not** in the DRAFT candidate manifest. Each is classified as:

- **DEFER** — potentially usable later after manual review, prompt adjustment, or once we have confidence from a successful first pilot.
- **REJECT** — not suitable for the augmentation research at all.

In this pack, **all 11 are DEFER** (none REJECT). The reasoning is conservative-by-design for the first tiny pilot; the underlying preview design is still valid.

## All 4 paraphrase requests — DEFER (truncated seed)

| Request ID | L1 | Label | Risk | Reason |
|---|---:|---|---|---|
| `prev_paraphrase_32_001_735dc24587` | 32 | Be behaving properly | HIGH (4) | truncated seed excerpt (paraphrase relies on seed as primary content); long parenthetical actor name (Identitarian + 200+ chars); abstract/confusable label |
| `prev_paraphrase_51_002_e5406084c6` | 51 | Have the wisdom to accept others | HIGH (4) | truncated seed; sensitive label (tolerance / minority context); abstract/confusable label |
| `prev_paraphrase_7_003_97e379f741` | 7 | Have an exciting life | MEDIUM (3) | truncated seed; abstract/confusable label |
| `prev_paraphrase_24_004_fc69036780` | 24 | Be neat and tidy | MEDIUM (2) | truncated seed |

**Why DEFER, not REJECT.** The smart-truncation flag is honest and the prompt does warn the generator. A future pack could (a) use a longer seed window, (b) hand-curate a 1500-char excerpt for these four, (c) accept that the rewrite may legitimately drop seed details. Any of those would clear the truncation penalty.

## Direction-contrastive 29 pair — DEFER (sensitive content)

| Request ID | L1 | Label | Risk | Reason |
|---|---:|---|---|---|
| `prev_dir_contrast_29_001_aligned_0991b57a47` | 29 | Be holding religious faith | LOW (1) | **sensitive label** (religion / protected belief) — held back from first tiny pilot |
| `prev_dir_contrast_29_001_contradictory_0991b57a47` | 29 | Be holding religious faith | LOW (1) | same; kept together with pair partner |

**Why DEFER, not REJECT.** The pair is structurally well-formed (low risk on every other axis). The sensitivity policy can be relaxed once we have evidence from the first tiny pilot that the generator handles non-sensitive direction-contrastive pairs cleanly.

## All 4 hard-negative requests — DEFER

| Request ID | L1 | Label | Risk | Reason |
|---|---:|---|---|---|
| `prev_hard_negative_32_001_caf1a3dfb5` | 32 | Be behaving properly | HIGH (4) | hard_negative is structurally hardest type; abstract/confusable label |
| `prev_hard_negative_51_002_10a7cdd970` | 51 | Have the wisdom to accept others | HIGH (7) | `alternative_label_id = null`; sensitive label; abstract/confusable label |
| `prev_hard_negative_7_003_d2ddea18f0` | 7 | Have an exciting life | HIGH (4) | hard_negative; abstract/confusable label |
| `prev_hard_negative_29_004_6883966fd8` | 29 | Be holding religious faith | HIGH (6) | `alternative_label_id = null`; sensitive label |

**Why DEFER, not REJECT.** Hard-negatives are research-valuable; they just need a successful baseline first. After the rare-positive + direction-contrastive pilot succeeds, a second pack can include hard-negatives with `alternative_label_id` manually filled.

## rare_positive 51 — DEFER (sensitive label)

| Request ID | L1 | Label | Risk | Reason |
|---|---:|---|---|---|
| `prev_rare_positive_51_002_6796672415` | 51 | Have the wisdom to accept others | LOW (1) | scored LOW on every other axis, but held back because the label can touch protected-group context depending on actor framing |

**Why DEFER, not REJECT.** Worth revisiting after the first pilot. Label is legitimate FEHU research target.

## Summary by deferral reason

| Primary reason | Count |
|---|---:|
| Truncated seed for paraphrase | 4 |
| Sensitive label (religion / tolerance / equality) | 4 (29 dir-contrast pair, 51 hard-neg, 51 rare-pos, 29 hard-neg) |
| `hard_negative` is structurally hardest type (deferred to second wave) | 4 (the four hard-negatives) |
| Null `alternative_label_id` (subset of above) | 2 (51, 29) |

(Reasons may overlap; one request can have multiple reasons. The score column in `01_request_review_table.csv` lists all triggered rules.)

## No request was REJECTED

The v2 preview itself is sound — these deferrals are about **first-pilot ordering**, not preview correctness. Every deferred request is a candidate for a later pack.
