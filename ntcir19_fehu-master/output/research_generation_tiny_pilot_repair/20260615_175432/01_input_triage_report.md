# 01_input_triage_report.md

**Input folder:** output/research_generation_tiny_pilot/20260615_171954

## Triage Classification

### A. KEEP_FOR_HUMAN_VERIFICATION

These samples from the initial pilot are structurally valid (PASS or WARN).
They proceed directly to human verification.

- `prev_dir_contrast_12_002_aligned_ce1da19f54` — PASS
- `prev_dir_contrast_38_003_contradictory_e969e14138` — WARN
- `prev_rare_positive_32_001_83df110175` — WARN

### B. DETERMINISTIC_REPAIR_CANDIDATE

Parsed sample exists with correct labels/direction but evidence_sentence is 
a truncated prefix of a complete sentence in content.
Deterministic repair: expand evidence_sentence to the full sentence.

- `prev_dir_contrast_38_003_aligned_e969e14138` — evidence_sentence is a substring of a full content sentence

### C. TARGETED_REGENERATION_REQUIRED

These failed due to finish_reason=length (reasoning exhausted max_tokens=1800).
Solution: regenerate with max_tokens=4096 and stricter brevity constraints.

- `prev_dir_contrast_12_002_contradictory_ce1da19f54` — JSON decode error: Unterminated string starting at: line 3 column 14 (char 93)
- `prev_rare_positive_24_004_98671d8d01` — Empty content from model