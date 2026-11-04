# Next Step Recommendation
**Audit Date:** 2026-06-26

---

## Readiness Decisions

### Is the project ready for final human spot-check?
**YES.**

The AI-assisted verification is complete. Three candidates are ACCEPT_SUGGESTED with HIGH confidence. Three candidates are REVIEW_SUGGESTED. The human review sheet (`05_human_review_sheet_AI_ASSISTED.csv`) contains specific questions for each REVIEW candidate, making the human's job concrete and bounded. The human reviewer needs to make 3 quick confirmations and 1 harder judgment call (candidate 5, the mixed-framing case).

### Is the project ready to create verified_augmented_candidates?
**Not yet — human spot-check must come first.**

The AI-assisted verdicts are suggestions, not final approvals. At minimum:
1. The 3 ACCEPT_SUGGESTED candidates need human confirmation.
2. The 3 REVIEW_SUGGESTED candidates need explicit human decisions (ACCEPT or REJECT).
3. Only after all 6 human decisions are recorded in the review sheet can `verified_augmented_candidates.jsonl` be created.

### Is the project ready for training?
**NO.**

Training requires `verified_augmented_candidates.jsonl` to exist, and that file requires completed human final approval. Training before human approval risks adding the L1=12 contradictory candidate (with high training risk) to the training set without scrutiny.

### Is the project ready for ablation?
**NO.**

Ablation requires at least one training run with augmented data, which requires verified candidates.

### Should we scale generation now?
**NO — not until human spot-check is complete.**

Before scaling:
1. The human rejection rate for this batch must be known. If the contradictory L1=12 candidate is rejected, this is a 1/6 = 17% rejection rate — which informs how many raw generations are needed per desired verified sample.
2. Two systematic issues should be fixed in future generation prompts: (a) evidence sentences must name the actor explicitly; (b) minimum article length should be specified (~150 words).
3. The value/direction distribution for the next batch should be chosen based on which current candidates pass.

---

## Why Not Train Yet (Detailed)

1. **No human-verified samples exist.** All 6 candidates are AI-suggested, not human-approved.
2. **Candidate 5 has high training risk.** The L1=12 contradictory candidate's positive-framing-around-a-loss could teach the model incorrect direction associations. If this candidate enters training unreviewed, it may harm rather than help DRR for L1=12.
3. **Sample count is still small.** Even with all 6 approved, 6 synthetic samples is a modest intervention. The training signal must be verified before scaling.
4. **No training-format conversion done.** Candidates are in generation format, not FEHU training format.

---

## Files to Create After Human Decisions

The following files should be created in the next session, after the human reviewer fills in `05_human_review_sheet_AI_ASSISTED.csv`:

| File | Description | Location |
|------|-------------|---------- |
| `verified_augmented_candidates.jsonl` | Only human-ACCEPT candidates, in verified format | `output/research_verified_candidates/<TIMESTAMP>/` |
| `verified_candidate_summary.csv` | Per-candidate final status (ACCEPT/REJECT, reason) | Same folder |
| `verification_final_decision_report.md` | Summary of human decisions, rejected candidate analysis, lessons learned for next generation round | Same folder |

**Constraints for those files:**
- `training_ready` must remain `false` in `verified_augmented_candidates.jsonl`.
- A separate explicit step should convert verified candidates to FEHU training format, with its own safety check.
- `verification_final_decision_report.md` should recommend whether a replacement contradictory L1=12 sample is needed.

---

## Recommended Immediate Next Action

Give the human reviewer `05_human_review_sheet_AI_ASSISTED.csv` and `07_review_and_reject_notes.md`. The reviewer needs to:

1. **For ACCEPT_SUGGESTED (candidates 2, 4, 6):** Quick review; confirm the specific question noted in `recommended_human_action`. Fill `human_decision = ACCEPT` if confirmed.

2. **For REVIEW_SUGGESTED (candidates 1, 3):** Read the specific question. Likely to result in ACCEPT after confirmation. Fill `human_decision = ACCEPT` or `REJECT`.

3. **For REVIEW_SUGGESTED (candidate 5 — the mixed-framing case):** Careful review. Read the article and ask: does this story present a failure to have success, or a successful season with one shortfall? Fill `human_decision = ACCEPT` or `REJECT` with a note.

Once all 6 human decisions are recorded, run the next Claude Code session to create `verified_augmented_candidates.jsonl`.
