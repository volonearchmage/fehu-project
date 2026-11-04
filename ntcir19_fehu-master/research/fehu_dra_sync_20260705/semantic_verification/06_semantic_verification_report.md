# Semantic Verification Report — Expanded Raw Candidates (72)

**Created at:** 2026-07-05T00:50:15
**Verifier:** AI-assisted semantic verification by Claude Code / Fable 5 (all 72 article texts read and
judged individually; no external API). Final decisions remain human.

## Totals
- Candidates reviewed: **72**
- **ACCEPT_SUGGESTED: 67**
- **REVIEW_SUGGESTED: 4**
- **REJECT_SUGGESTED: 1**

## Per-label summary (verdict counts; recommended-accept slots per plan in brackets)
| L1 | Label | aligned | contradictory | ACCEPT | REVIEW | REJECT | plan target |
|----|-------|---------|---------------|--------|--------|--------|-------------|
| 22 | Have good health | 9 | 9 | 18 | 0 | 0 | [3+3] |
| 30 | Be compliant | 6 | 6 | 12 | 0 | 0 | [2+2] |
| 38 | Be honest | 6 | 6 | 9 | 2 | 1 | [2+2] |
| 12 | Have success | 6 | 6 | 12 | 0 | 0 | [2+2] |
| 5 | Have freedom of action | 6 | 6 | 10 | 2 | 0 | [2+2] |
| 46 | Have a world at peace | 3 | 3 | 6 | 0 | 0 | [1+1] |

Every label/direction slot has at least as many ACCEPT_SUGGESTED candidates as its plan target
(the tightest is L1=38 aligned: 4 ACCEPT for a 2-slot target).

## Per-direction summary
- Aligned (36): 33 ACCEPT / 2 REVIEW / 1 REJECT — issues concentrate in L1=38 aligned.
- Contradictory (36): 34 ACCEPT / 2 REVIEW / 0 REJECT — this round's contradictory samples are clean;
  the L1=12 contradictory batch in particular fully applies the Oakridge lesson (dominant failure, no
  counter-signals).

## Top recurring problems
1. **Quote-as-evidence (L1=38 aligned):** 3 candidates use a value-statement quote as the evidence
   sentence instead of the corrective act itself (MEDIUM risk, still ACCEPT_SUGGESTED).
2. **Surname-only evidence naming (L1=22 contradictory):** 3 candidates name the actor by surname only
   in the evidence sentence; referents unambiguous (MEDIUM, ACCEPT_SUGGESTED).
3. **Compliance confound (L1=5 contradictory):** bans caused by the actor's own violations create a
   Be-compliant(30) confound; one case (BitValley) is co-dominant → REVIEW.
4. **Template near-duplicates:** two Swiss-pharma fabrication stories (38-contradictory) and two
   African safari-license restorations (5-aligned) — keep at most one of each pair.

## Candidates needing human attention (16 flagged; 5 decisive)
- **REJECT_SUGGESTED — `exp_38_aligned_03_db5558f393`:** reuses the verified pool's actor
  "BrightPath Analytics" (recorded there as a data fabricator, L1=38 contradictory) for an
  opposite-direction honesty story → same fictional actor would carry both directions of the same value
  across the training set. Recommend reject/regenerate with a fresh actor.
- **REVIEW — `exp_38_aligned_05_7a89a29c5c`:** actor's admitted past fabrication + present honest
  correction = both directions of Be honest in one article (pool precedent labels confessions of
  fabrication as contradictory evidence). High direction-ambiguity.
- **REVIEW — `exp_38_contradictory_r1_00_d42bf6d43c`:** near-duplicate of Meridian Therapeutics story.
- **REVIEW — `exp_5_aligned_03_628fc4fa5e`:** near-duplicate of GreenPath safari-license story.
- **REVIEW — `exp_5_contradictory_05_0ef024ccef`:** AML non-compliance co-dominant with the freedom
  loss; could be L1=30 contradictory instead.
- Plus 11 MEDIUM-risk ACCEPT_SUGGESTED candidates (surname evidence, quote evidence, mild confounds)
  listed in 03_semantic_verification_table.csv with `required_human_attention=True`.

## Redundancy findings
Within-run: 2 near-duplicate pairs (38-contradictory pharma; 5-aligned safari). Against verified pool:
1 actor-identity conflict (BrightPath, above). No verbatim duplicates.

## Recommendation
- **Send all 72 to human review** (04_candidate_review_sheet.csv), attention-flagged rows first.
- **Recommended target: accept 24** (per plan: 22→3+3, 30→2+2, 38→2+2, 12→2+2, 5→2+2, 46→1+1),
  preferring LOW-risk/HIGH-utility candidates and avoiding both members of each near-duplicate pair.
  The 24-target is comfortably feasible: every slot has enough clean ACCEPT_SUGGESTED candidates.

## Statement
These are AI-assisted semantic verification suggestions only. No final human decisions were made, no
candidate was added to the verified pool, and no candidate is training-ready.

## Next step
Human review of 04_candidate_review_sheet.csv, then create a new verified candidate pool from accepted
candidates only.
