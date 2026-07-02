# Candidate Readiness Report
**Audit Date:** 2026-06-26  
**Source:** output/research_generation_tiny_pilot_repair/20260615_175432/

---

## Number of Candidates

**6 candidates** (matches expectation of 6).

---

## Candidate Detail Table

| # | Candidate ID | Augmentation Type | L1 Value ID | L1 Value Name | L2 Value ID | L2 Value Name | Direction | Direction Name | Validation Status | Source Stage | Candidate Status | Training Ready |
|---|-------------|------------------|-------------|--------------|------------|--------------|-----------|---------------|------------------|-------------|-----------------|---------------|
| 1 | prev_rare_positive_32_001_83df110175 | rare_positive | 32 | Be behaving properly | 11 | Conformity: rules | 1 | aligned | WARN | initial_tiny_pilot_warn | PENDING_HUMAN_VERIFICATION | false |
| 2 | prev_dir_contrast_12_002_aligned_ce1da19f54 | direction_contrastive | 12 | Have success | 4 | Achievement | 1 | aligned | PASS | initial_tiny_pilot_pass | PENDING_HUMAN_VERIFICATION | false |
| 3 | prev_dir_contrast_38_003_contradictory_e969e14138 | direction_contrastive | 38 | Be honest | 14 | Benevolence: caring | 0 | contradictory | WARN | initial_tiny_pilot_warn | PENDING_HUMAN_VERIFICATION | false |
| 4 | prev_dir_contrast_38_003_aligned_e969e14138 | direction_contrastive | 38 | Be honest | 14 | Benevolence: caring | 1 | aligned | PASS | deterministic_repair | PENDING_HUMAN_VERIFICATION | false |
| 5 | prev_dir_contrast_12_002_contradictory_ce1da19f54 | direction_contrastive | 12 | Have success | 4 | Achievement | 0 | contradictory | WARN | targeted_regeneration | PENDING_HUMAN_VERIFICATION | false |
| 6 | prev_rare_positive_24_004_98671d8d01 | rare_positive | 24 | Be neat and tidy | 8 | Security: personal | 1 | aligned | PASS | targeted_regeneration | PENDING_HUMAN_VERIFICATION | false |

---

## Taxonomy Verification

L1→L2 mappings were verified against `dataset/hv_categories/level_1_to_level_2.json` and `human_value_level2_values.json`:

| L1 ID | L1 Name | Expected L2 Name | Candidate L2 ID | Candidate L2 Name | Match |
|-------|---------|----------------|----------------|------------------|-------|
| 12 | Have success | Achievement | 4 | Achievement | CORRECT |
| 24 | Be neat and tidy | Security: personal | 8 | Security: personal | CORRECT |
| 32 | Be behaving properly | Conformity: rules | 11 | Conformity: rules | CORRECT |
| 38 | Be honest | Benevolence: caring | 14 | Benevolence: caring | CORRECT |

All L1→L2 mappings are confirmed correct per the FEHU taxonomy.

Note: "Be honest" mapping to "Benevolence: caring" (not "Universalism") may appear counterintuitive but is correct per the FEHU schema — honesty is positioned within the Benevolence motivational type in this taxonomy.

---

## PASS / WARN / FAIL Counts

| Status | Count | Expected | Match |
|--------|-------|----------|-------|
| PASS | 3 | 3 | YES |
| WARN | 3 | 3 | YES |
| FAIL | 0 | 0 | YES |

---

## WARN Reason Analysis

All three WARN candidates (1, 3, 5) failed only the `evidence_mentions_actor` check:

> **WARN: actor_mention not found in evidence_sentence**

This means the evidence sentence does not literally contain the actor's name string. This is a **style/surface check** — the evidence sentence may still semantically describe the actor's action. It does not indicate a value mismatch, factuality error, or schema error. All other checks passed for these candidates.

The WARN status is appropriate: these candidates should receive careful human review focused on whether the evidence sentence is semantically adequate despite not naming the actor directly.

Additional note for candidate 5 (prev_dir_contrast_12_002_contradictory_ce1da19f54): the automatic_notes in the CSV include "Regenerated with max_tokens=4096; verify against approved manifest" — this is a procedural note, not a content warning.

Additional note for candidate 6 (prev_rare_positive_24_004_98671d8d01): same procedural note about max_tokens regeneration; no content concern.

---

## Candidate Status Verification

| Requirement | All 6 Candidates | Pass |
|-------------|-----------------|------|
| `candidate_status` = "PENDING_HUMAN_VERIFICATION" | YES | SAFE |
| `training_ready` = false | YES | SAFE |
| `human_decision` field blank in verification sheet | YES | CORRECT |

No candidate is incorrectly marked as training-ready. No candidate has been pre-approved for training without human review.

---

## JSONL vs CSV Consistency Check

Comparing `07_unified_candidate_samples.jsonl` (6 lines) with `08_unified_validation_table.csv` (6 data rows) and `09_human_verification_sheet_REPAIRED.csv` (6 data rows):

| Candidate ID | In JSONL | In Validation CSV | In Human Sheet |
|-------------|---------|------------------|---------------|
| prev_rare_positive_32_001_83df110175 | YES | YES | YES |
| prev_dir_contrast_12_002_aligned_ce1da19f54 | YES | YES | YES |
| prev_dir_contrast_38_003_contradictory_e969e14138 | YES | YES | YES |
| prev_dir_contrast_38_003_aligned_e969e14138 | YES | YES | YES |
| prev_dir_contrast_12_002_contradictory_ce1da19f54 | YES | YES | YES |
| prev_rare_positive_24_004_98671d8d01 | YES | YES | YES |

**No mismatch detected.** All 6 candidates appear consistently across all three files.

---

## Expected Candidates Verification

| Expected Candidate ID | Found | Notes |
|----------------------|-------|-------|
| prev_dir_contrast_12_002_aligned_ce1da19f54 | YES | PASS |
| prev_dir_contrast_12_002_contradictory_ce1da19f54 | YES | WARN |
| prev_dir_contrast_38_003_aligned_e969e14138 | YES | PASS (deterministic repair) |
| prev_dir_contrast_38_003_contradictory_e969e14138 | YES | WARN |
| prev_rare_positive_24_004_98671d8d01 | YES | PASS (regenerated) |
| prev_rare_positive_32_001_83df110175 | YES | WARN |

All 6 expected candidates are present.

---

## Candidates That Should Be Excluded From Verification

**None.** All 6 candidates passed the schema, label consistency, and safety checks. The 3 WARN candidates should be verified with extra care (evidence_mentions_actor) but should not be excluded outright.
