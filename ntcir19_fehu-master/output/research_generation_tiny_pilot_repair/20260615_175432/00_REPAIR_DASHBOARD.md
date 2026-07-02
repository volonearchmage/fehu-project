# FEHU Tiny Pilot Repair and Regeneration — Dashboard

**Stage:** Targeted repair and regeneration
**Timestamp:** 2026-06-15T18:14:51.359192+00:00
**Input tiny pilot folder:** output/research_generation_tiny_pilot/20260615_171954
**Output repair folder:** output/research_generation_tiny_pilot_repair/20260615_175432

## Initial Pilot Result Summary

| Category | Count | Request IDs |
|----------|-------|-------------|
| KEEP (PASS/WARN from pilot) | 3 | prev_dir_contrast_12_002_aligned_ce1da19f54; prev_dir_contrast_38_003_contradictory_e969e14138; prev_rare_positive_32_001_83df110175 |
| DETERMINISTIC_REPAIR | 1 | prev_dir_contrast_38_003_aligned_e969e14138 |
| TARGETED_REGENERATION | 2 | prev_dir_contrast_12_002_contradictory_ce1da19f54; prev_rare_positive_24_004_98671d8d01 |

## Deterministic Repair

**Result:** SUCCEEDED
- Repaired: `prev_dir_contrast_38_003_aligned_e969e14138`
- original_evidence: 'NovaTech Solutions proactively notified all affected users about the security incident.'
- repaired_evidence: 'NovaTech Solutions proactively notified all affected users about the security incident and offered free credit monitoring.'

## Targeted Regeneration

- Requests sent: 2
- Raw responses saved: 2
- Parsed successfully: 2
- Failed: 0

## Unified Candidates

- Total unified candidates: 6
- Validation PASS: 3
- Validation WARN: 3
- Validation FAIL: 0

## Human Verification Sheet

- Path: output/research_generation_tiny_pilot_repair/20260615_175432/09_human_verification_sheet_REPAIRED.csv
- Contains: 6 samples (PASS + WARN only)

## Safety Summary

- Official data modified? NO
- evaluation.py modified? NO
- Original tiny pilot folder modified? NO
- API key logged? NO
- Training run? NO

## Final Recommendation

Complete human verification of 09_human_verification_sheet_REPAIRED.csv before any further steps.

> **Candidates remain PENDING_HUMAN_VERIFICATION and are not training-ready.**