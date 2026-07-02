# DRA-FEHU AI-Assisted Semantic Verification Dashboard
**Date:** 2026-06-26  
**Verification Folder:** output/research_ai_verification/20260626_214148/

---

## Current Stage

AI-assisted semantic verification of the 6 repaired unified candidates from the DRA-FEHU tiny pilot. This stage applies rule-based reasoning to assess value/direction consistency, actor centrality, evidence quality, content naturalness, and training risk. No LLM API was called. Verdicts are suggestions for human review — not final training approval.

---

## Input Files Read

| File | Purpose |
|------|---------|
| .../20260615_175432/07_unified_candidate_samples.jsonl | Candidate content and validation |
| .../20260615_175432/08_unified_validation_table.csv | Structural validation summary |
| .../20260615_175432/09_human_verification_sheet_REPAIRED.csv | Human review template (confirmed blank) |
| .../20260615_175432/10_research_interpretation.md | Prior pipeline interpretation |
| .../20260626_212044/00_RESUME_DASHBOARD.md | Project state |
| .../20260626_212044/03_candidate_readiness_report.md | Candidate inventory |
| .../20260626_212044/05_next_step_recommendation.md | Verification criteria |
| dataset/hv_categories/*.json | Taxonomy verification |

---

## Candidate Count

**6 candidates verified** (expected: 6). All 6 expected candidate IDs confirmed present.

---

## Original Rule-Based Validation

| Status | Count |
|--------|-------|
| PASS | 3 |
| WARN | 3 |
| FAIL | 0 |

All WARN cases were due to `evidence_mentions_actor = WARN` (evidence sentence uses generic reference instead of actor name). No hard-rule failures.

---

## AI Semantic Verification Results

| Verdict | Count |
|---------|-------|
| ACCEPT_SUGGESTED | 3 |
| REVIEW_SUGGESTED | 3 |
| REJECT_SUGGESTED | 0 |

### ACCEPT_SUGGESTED (HIGH confidence)
| Candidate ID | Value | Direction |
|-------------|-------|-----------|
| prev_dir_contrast_12_002_aligned_ce1da19f54 | Have success (L1=12) | 1 aligned |
| prev_dir_contrast_38_003_aligned_e969e14138 | Be honest (L1=38) | 1 aligned |
| prev_rare_positive_24_004_98671d8d01 | Be neat and tidy (L1=24) | 1 aligned |

### REVIEW_SUGGESTED (MEDIUM confidence)
| Candidate ID | Value | Direction | Primary Concern |
|-------------|-------|-----------|-----------------|
| prev_rare_positive_32_001_83df110175 | Be behaving properly (L1=32) | 1 aligned | Evidence uses "The group" not actor name — confirm referent |
| prev_dir_contrast_38_003_contradictory_e969e14138 | Be honest (L1=38) | 0 contradictory | Evidence uses "The company"; article is only 4 sentences |
| prev_dir_contrast_12_002_contradictory_ce1da19f54 | Have success (L1=12) | 0 contradictory | Mixed framing: positive season narrative surrounds championship loss — HIGH training risk |

---

## Safety Checks

| Check | Result |
|-------|--------|
| Any candidate marked training_ready = true | **NO** — all 6 remain false |
| Any human_decision filled | **NO** — all remain blank |
| Any LLM API called | **NO** |
| Any training run | **NO** |
| Any ablation run | **NO** |
| Official data modified | **NO** |
| Candidate content modified | **NO** |
| Secrets read or printed | **NO** |

---

## Conclusion

This output is **AI-assisted verification suggestions only.** It is **not final approval for training.**

Three candidates (all aligned-direction samples) scored well across all semantic dimensions and are suggested for acceptance pending routine human confirmation. Three candidates (all containing the WARN flag from rule-based validation) require human judgment on specific questions documented in `07_review_and_reject_notes.md`.

The most complex case is `prev_dir_contrast_12_002_contradictory_ce1da19f54`: its positive season framing creates a training risk that is not resolvable by AI alone — a human must decide whether the championship loss is sufficient to label this as contradictory to "Have success" despite the overwhelmingly positive context.

**Immediate next action:** Human spot-check using `05_human_review_sheet_AI_ASSISTED.csv` and `07_review_and_reject_notes.md`. Training must wait for human approval.
