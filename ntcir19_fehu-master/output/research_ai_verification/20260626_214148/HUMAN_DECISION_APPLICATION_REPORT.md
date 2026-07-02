# Human Decision Application Report

## Files
- **Input CSV:** `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_ai_verification/20260626_214148/05_human_review_sheet_AI_ASSISTED.csv`
- **Output CSV:** `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_ai_verification/20260626_214148/05_human_review_sheet_AI_ASSISTED_HUMAN_DECIDED.csv`
- **Original CSV overwritten:** No (SHA-256 unchanged: `606f60432fc5a621a405ff638d0d85fbba33a627a25a10b03db0e132ba24db71`)

## Processing Summary
- **Rows processed:** 6
- **Fields modified:** `human_decision`, `human_notes` only

## Decision Counts
- **ACCEPT:** 5
- **REJECT:** 1

### ACCEPT candidate IDs
- `prev_rare_positive_32_001_83df110175`
- `prev_dir_contrast_12_002_aligned_ce1da19f54`
- `prev_dir_contrast_38_003_contradictory_e969e14138`
- `prev_dir_contrast_38_003_aligned_e969e14138`
- `prev_rare_positive_24_004_98671d8d01`

### REJECT candidate IDs
- `prev_dir_contrast_12_002_contradictory_ce1da19f54`

## Invariant Confirmations
- `training_ready` remains **false** for all 6 rows: Yes
- `final_training_approval` remains **blank** for all 6 rows: Yes
- Candidate content, evidence_sentence, labels, directions, candidate_id, semantic_verdict unchanged: Yes
- Original AI-assisted CSV was **not** overwritten: Yes

## Process Confirmations
- No API was called: Confirmed
- No training was run: Confirmed
- No ablation was run: Confirmed
- No official dataset or `evaluation.py` modified: Confirmed
- No prediction files generated: Confirmed
- No `verified_augmented_candidates.jsonl` or augmented training set created: Confirmed

## Next Step Recommendation
The next step is to create `verified_augmented_candidates.jsonl` from the **ACCEPT rows only**.
This should be done in a **separate, explicit task** after this human-decided CSV is confirmed.
