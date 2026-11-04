# Shortlist Report — 24-Candidate Human Review Shortlist

Generated: 2026-07-05T10:54:04.751007
Output folder: `output/research_human_review_shortlist/20260705_105211/`

## Scope

Selection and review-packet preparation only. No human decisions were made,
no verified-pool update occurred, no `training_ready`/`verified_for_candidate_pool`
flags were written, no API was called, no source code / official data /
evaluation.py / raw generation / semantic verification files were modified.

## Inputs

- Semantic judgments: `output/research_semantic_verification_expanded/20260705_005015/02_semantic_judgments.jsonl` (72 candidates: 67 ACCEPT_SUGGESTED, 4 REVIEW_SUGGESTED, 1 REJECT_SUGGESTED)
- Raw candidates: `output/research_expanded_raw_generation/20260704_222249/03_raw_generated_candidates.jsonl` (72)
- Existing verified pool: `output/research_verified_candidates/20260702_165107/01_verified_augmented_candidates.jsonl` (6, unchanged)

## Selection outcome

- Selected: **24 / 24 planned** — the target is fully feasible.
- Every selected candidate is **ACCEPT_SUGGESTED**.
- 22 of 24 are LOW risk with HIGH suggested training utility.
- 2 of 24 are the L1=38 aligned slot-fillers where clean supply was thin:
  `exp_38_aligned_04` (LOW/HIGH) and `exp_38_aligned_00` (MEDIUM/MEDIUM,
  evidence sentence is a value-statement quote — flagged for the human reviewer).
- No REVIEW_SUGGESTED or REJECT_SUGGESTED candidate was selected.

## Per-slot coverage

| Label | Direction | Planned | Selected | Backups |
|---|---|---|---|---|
| 5 Have freedom of action | aligned (1) | 2 | 2 | 3 |
| 5 Have freedom of action | contradictory (0) | 2 | 2 | 3 |
| 12 Have success | aligned (1) | 2 | 2 | 3 |
| 12 Have success | contradictory (0) | 2 | 2 | 4 |
| 22 Have good health | aligned (1) | 3 | 3 | 5 |
| 22 Have good health | contradictory (0) | 3 | 3 | 3 |
| 30 Be compliant | aligned (1) | 2 | 2 | 4 |
| 30 Be compliant | contradictory (0) | 2 | 2 | 4 |
| 38 Be honest | aligned (1) | 2 | 2 | 1 |
| 38 Be honest | contradictory (0) | 2 | 2 | 3 |
| 46 Have a world at peace | aligned (1) | 1 | 1 | 2 |
| 46 Have a world at peace | contradictory (0) | 1 | 1 | 2 |

Backups available in total: 37 (see `05_excluded_candidate_notes.csv`, `viable_backup=yes`).

## Instruction-mandated exclusions honored

- `exp_38_aligned_03` — excluded (BrightPath Analytics reused in an
  opposite-direction honesty story already in the verified pool; also
  REJECT_SUGGESTED / HIGH risk / POOL_CONFLICT).
- `exp_38_aligned_05` — not selected (REVIEW_SUGGESTED, HIGH risk,
  BOTH_DIRECTIONS counter-signal: past fabrication + present honesty).
- `exp_5_contradictory_05` — not selected (REVIEW_SUGGESTED; AML
  non-compliance may dominate the freedom-of-action signal).

## Other notable exclusions

- All three PARTIAL actor-grounding candidates for L1=22 contradictory
  (`exp_22_contradictory_06/07/08`) and `exp_38_aligned_02` were avoided.
- In-run near-duplicates were collapsed to one representative each:
  `exp_38_contradictory_r1_00` (dup of `exp_38_contradictory_00`),
  `exp_5_aligned_03` (dup of `exp_5_aligned_00`),
  `exp_22_contradictory_04/07` pair,
  `exp_12_contradictory_05` (theme dup of `exp_12_contradictory_01`).
- For L1=12 contradictory, all six candidates had `counter_signal_status=NONE`;
  the two selected were additionally chosen for distinct failure types
  (delivery shortfall vs. competition loss).

## Next step (human)

Review `04_human_review_packet.md`, then fill `human_decision`
(ACCEPT / REJECT / REVIEW_MORE), `human_notes`, and
`final_training_approval` in `02_recommended_24_shortlist.csv`.
Only human-ACCEPTed candidates may later be added to a **new**
verified candidate pool folder (target: ~24 new + 6 existing = 30).
