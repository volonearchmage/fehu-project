# 06_validation_report.md — Validation Report

## Summary

- Total attempted: 6
- Parsed successfully: 4
- Failed (API or parse): 2
- Validation PASS: 1
- Validation WARN: 2
- Validation FAIL: 1

## Per-Request Validation

### prev_dir_contrast_12_002_aligned_ce1da19f54
- augmentation_type: direction_contrastive
- label: L1=12 (Have success)
- direction: 1 (aligned)
- parse_status: PASS
- validation_status: PASS
- recommended_action: REVIEW: structural checks pass; verify content quality

### prev_dir_contrast_12_002_contradictory_ce1da19f54
- augmentation_type: direction_contrastive
- label: L1=12 (Have success)
- direction: 0 (contradictory)
- parse_status: FAIL
- validation_status: FAIL
- recommended_action: JSON parse failed: JSON decode error: Unterminated string starting at: line 3 column 14 (char 93)

### prev_dir_contrast_38_003_aligned_e969e14138
- augmentation_type: direction_contrastive
- label: L1=38 (Be honest)
- direction: 1 (aligned)
- parse_status: PASS
- validation_status: FAIL
- recommended_action: REJECT: structural validation failed; review and discard

### prev_dir_contrast_38_003_contradictory_e969e14138
- augmentation_type: direction_contrastive
- label: L1=38 (Be honest)
- direction: 0 (contradictory)
- parse_status: PASS
- validation_status: WARN
- recommended_action: REVIEW: content warnings present; human judgment required

### prev_rare_positive_24_004_98671d8d01
- augmentation_type: rare_positive
- label: L1=24 (Be neat and tidy)
- direction: 1 (aligned)
- parse_status: FAIL
- validation_status: FAIL
- recommended_action: JSON parse failed: Empty content from model

### prev_rare_positive_32_001_83df110175
- augmentation_type: rare_positive
- label: L1=32 (Be behaving properly)
- direction: 1 (aligned)
- parse_status: PASS
- validation_status: WARN
- recommended_action: REVIEW: content warnings present; human judgment required

## Detailed Validation Results

### prev_dir_contrast_12_002_aligned_ce1da19f54

- [PASS] field 'title' exists
- [PASS] field 'content' exists
- [PASS] field 'actor_name' exists
- [PASS] field 'actor_mention' exists
- [PASS] field 'evidence_sentence' exists
- [PASS] field 'explanation' exists
- [PASS] field 'l1_value_id' exists
- [PASS] field 'l1_value_name' exists
- [PASS] field 'l2_value_id' exists
- [PASS] field 'l2_value_name' exists
- [PASS] field 'direction' exists
- [PASS] field 'direction_name' exists
- [PASS] field 'is_positive' exists
- [PASS] field '_type_specific_rule' exists
- [PASS] title non-empty
- [PASS] content non-empty
- [PASS] actor_name non-empty
- [PASS] actor_mention non-empty
- [PASS] actor_mention verbatim in content
- [PASS] evidence_sentence non-empty
- [PASS] evidence_sentence verbatim in content
- [PASS] l1_value_id matches request — expected '12', got '12'
- [PASS] l1_value_name matches request — expected 'Have success', got 'Have success'
- [PASS] l2_value_id matches request — expected '4', got '4'
- [PASS] l2_value_name matches request — expected 'Achievement', got 'Achievement'
- [PASS] direction matches request — expected '1', got '1'
- [PASS] direction_name matches request — expected 'aligned', got 'aligned'
- [PASS] is_positive matches request — expected True, got True
- [PASS] direction convention (aligned=1, contradictory=0) — direction='1', direction_name='aligned'
- [PASS] content does not contain 'as an AI'
- [PASS] content does not mention FEHU or NTCIR
- [PASS] content does not mention synthetic data
- [PASS] content length (50–1500 chars) — 1034 chars
- [PASS] evidence_sentence mentions actor (superficial)
- [PASS] no obvious unsupported severe accusation
- [PASS] sample marked PENDING_HUMAN_VERIFICATION — Set by runner

### prev_dir_contrast_38_003_aligned_e969e14138

- [PASS] field 'title' exists
- [PASS] field 'content' exists
- [PASS] field 'actor_name' exists
- [PASS] field 'actor_mention' exists
- [PASS] field 'evidence_sentence' exists
- [PASS] field 'explanation' exists
- [PASS] field 'l1_value_id' exists
- [PASS] field 'l1_value_name' exists
- [PASS] field 'l2_value_id' exists
- [PASS] field 'l2_value_name' exists
- [PASS] field 'direction' exists
- [PASS] field 'direction_name' exists
- [PASS] field 'is_positive' exists
- [PASS] field '_type_specific_rule' exists
- [PASS] title non-empty
- [PASS] content non-empty
- [PASS] actor_name non-empty
- [PASS] actor_mention non-empty
- [PASS] actor_mention verbatim in content
- [PASS] evidence_sentence non-empty
- [FAIL] evidence_sentence verbatim in content — evidence_sentence not found verbatim in content
- [PASS] l1_value_id matches request — expected '38', got '38'
- [PASS] l1_value_name matches request — expected 'Be honest', got 'Be honest'
- [PASS] l2_value_id matches request — expected '14', got '14'
- [PASS] l2_value_name matches request — expected 'Benevolence: caring', got 'Benevolence: caring'
- [PASS] direction matches request — expected '1', got '1'
- [PASS] direction_name matches request — expected 'aligned', got 'aligned'
- [PASS] is_positive matches request — expected True, got True
- [PASS] direction convention (aligned=1, contradictory=0) — direction='1', direction_name='aligned'
- [PASS] content does not contain 'as an AI'
- [PASS] content does not mention FEHU or NTCIR
- [PASS] content does not mention synthetic data
- [PASS] content length (50–1500 chars) — 534 chars
- [PASS] evidence_sentence mentions actor (superficial)
- [PASS] no obvious unsupported severe accusation
- [PASS] sample marked PENDING_HUMAN_VERIFICATION — Set by runner

### prev_dir_contrast_38_003_contradictory_e969e14138

- [PASS] field 'title' exists
- [PASS] field 'content' exists
- [PASS] field 'actor_name' exists
- [PASS] field 'actor_mention' exists
- [PASS] field 'evidence_sentence' exists
- [PASS] field 'explanation' exists
- [PASS] field 'l1_value_id' exists
- [PASS] field 'l1_value_name' exists
- [PASS] field 'l2_value_id' exists
- [PASS] field 'l2_value_name' exists
- [PASS] field 'direction' exists
- [PASS] field 'direction_name' exists
- [PASS] field 'is_positive' exists
- [PASS] field '_type_specific_rule' exists
- [PASS] title non-empty
- [PASS] content non-empty
- [PASS] actor_name non-empty
- [PASS] actor_mention non-empty
- [PASS] actor_mention verbatim in content
- [PASS] evidence_sentence non-empty
- [PASS] evidence_sentence verbatim in content
- [PASS] l1_value_id matches request — expected '38', got '38'
- [PASS] l1_value_name matches request — expected 'Be honest', got 'Be honest'
- [PASS] l2_value_id matches request — expected '14', got '14'
- [PASS] l2_value_name matches request — expected 'Benevolence: caring', got 'Benevolence: caring'
- [PASS] direction matches request — expected '0', got '0'
- [PASS] direction_name matches request — expected 'contradictory', got 'contradictory'
- [PASS] is_positive matches request — expected True, got True
- [PASS] direction convention (aligned=1, contradictory=0) — direction='0', direction_name='contradictory'
- [PASS] content does not contain 'as an AI'
- [PASS] content does not mention FEHU or NTCIR
- [PASS] content does not mention synthetic data
- [PASS] content length (50–1500 chars) — 427 chars
- [WARN] evidence_sentence mentions actor (superficial) — actor_mention not in evidence_sentence (may still be semantically valid)
- [PASS] no obvious unsupported severe accusation
- [PASS] sample marked PENDING_HUMAN_VERIFICATION — Set by runner

### prev_rare_positive_32_001_83df110175

- [PASS] field 'title' exists
- [PASS] field 'content' exists
- [PASS] field 'actor_name' exists
- [PASS] field 'actor_mention' exists
- [PASS] field 'evidence_sentence' exists
- [PASS] field 'explanation' exists
- [PASS] field 'l1_value_id' exists
- [PASS] field 'l1_value_name' exists
- [PASS] field 'l2_value_id' exists
- [PASS] field 'l2_value_name' exists
- [PASS] field 'direction' exists
- [PASS] field 'direction_name' exists
- [PASS] field 'is_positive' exists
- [PASS] field '_type_specific_rule' exists
- [PASS] title non-empty
- [PASS] content non-empty
- [PASS] actor_name non-empty
- [PASS] actor_mention non-empty
- [PASS] actor_mention verbatim in content
- [PASS] evidence_sentence non-empty
- [PASS] evidence_sentence verbatim in content
- [PASS] l1_value_id matches request — expected '32', got '32'
- [PASS] l1_value_name matches request — expected 'Be behaving properly', got 'Be behaving properly'
- [PASS] l2_value_id matches request — expected '11', got '11'
- [PASS] l2_value_name matches request — expected 'Conformity: rules', got 'Conformity: rules'
- [PASS] direction matches request — expected '1', got '1'
- [PASS] direction_name matches request — expected 'aligned', got 'aligned'
- [PASS] is_positive matches request — expected True, got True
- [PASS] direction convention (aligned=1, contradictory=0) — direction='1', direction_name='aligned'
- [PASS] content does not contain 'as an AI'
- [PASS] content does not mention FEHU or NTCIR
- [PASS] content does not mention synthetic data
- [PASS] content length (50–1500 chars) — 600 chars
- [WARN] evidence_sentence mentions actor (superficial) — actor_mention not in evidence_sentence (may still be semantically valid)
- [PASS] no obvious unsupported severe accusation
- [PASS] sample marked PENDING_HUMAN_VERIFICATION — Set by runner

## Usability Assessment

Some samples have structural issues. Review failed checks before proceeding.

> **Generated samples are not training-ready until human verification.**