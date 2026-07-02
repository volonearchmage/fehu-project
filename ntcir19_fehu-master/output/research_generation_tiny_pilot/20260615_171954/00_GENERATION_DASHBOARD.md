# FEHU DeepSeek V4 Tiny Pilot Generation — Dashboard

**Stage:** DeepSeek V4 tiny pilot generation
**Status:** PARTIAL
**Timestamp:** 2026-06-15T17:34:56.568003+00:00
**Model:** deepseek-v4-pro
**Execute Mode:** True
**Manifest:** output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl
**Output Folder:** output/research_generation_tiny_pilot/20260615_171954

## Counts

| Metric | Value |
|--------|-------|
| Approved requests | 6 |
| Attempted | 6 |
| Raw responses saved | 6 |
| Parsed successfully | 4 |
| Failed (API or parse) | 2 |
| Validation PASS | 1 |
| Validation WARN | 2 |
| Validation FAIL | 1 |

## Results Table

| request_id | augmentation_type | label | direction | parse_status | validation_status | recommended_human_action |
|------------|-------------------|-------|-----------|--------------|-------------------|--------------------------|
| prev_dir_contrast_12_002_aligned_ce1da19f54 | direction_contrastive | L1=12 (Have success) | 1 (aligned) | PASS | PASS | REVIEW: structural checks pass; verify content quality |
| prev_dir_contrast_12_002_contradictory_ce1da19f54 | direction_contrastive | L1=12 (Have success) | 0 (contradictory) | FAIL | FAIL | JSON parse failed: JSON decode error: Unterminated string starting at: line 3 column 14 (char 93) |
| prev_dir_contrast_38_003_aligned_e969e14138 | direction_contrastive | L1=38 (Be honest) | 1 (aligned) | PASS | FAIL | REJECT: structural validation failed; review and discard |
| prev_dir_contrast_38_003_contradictory_e969e14138 | direction_contrastive | L1=38 (Be honest) | 0 (contradictory) | PASS | WARN | REVIEW: content warnings present; human judgment required |
| prev_rare_positive_24_004_98671d8d01 | rare_positive | L1=24 (Be neat and tidy) | 1 (aligned) | FAIL | FAIL | JSON parse failed: Empty content from model |
| prev_rare_positive_32_001_83df110175 | rare_positive | L1=32 (Be behaving properly) | 1 (aligned) | PASS | WARN | REVIEW: content warnings present; human judgment required |

---

> **Generated samples are candidates only and are not training-ready until human verification.**

## Research Statement

This tiny pilot tests whether the controlled FEHU augmentation pipeline can produce actor-specific, label-consistent, direction-consistent, evidence-grounded samples from a human-approved manifest. It does not yet claim model performance improvement.