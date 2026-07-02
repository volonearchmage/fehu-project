# Human Review Pack — Dashboard

**Stage:** human review preparation only. **No API has been called. No augmented sample has been generated.**

## Inputs

| File | Purpose |
|---|---|
| `output/research_generation_preview/20260614_171644/human_review_sheet.csv` | The original 18-row review sheet (pending) |
| `output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl` | Full per-request prompts + metadata (18 lines) |
| `output/research_project_state_review/20260614_235821/03_PREVIEW_V2_AUDIT/preview_v2_request_matrix.csv` | Per-request pass/warn/fail matrix from prior audit |
| `output/research_project_state_review/20260614_235821/03_PREVIEW_V2_AUDIT/preview_v2_warning_items.csv` | 6 design-justified warnings |
| `output/research_project_state_review/20260614_235821/04_SAFETY_AND_SUBMISSION_GATES/direction_mapping_audit.md` | Direction mapping verdict (PASS) |
| `output/research_project_state_review/20260614_235821/05_RESEARCH_DECISION/go_no_go_decision.md` | Prior GO/NO-GO summary |

## Output folder

`output/research_human_review_pack/20260615_161044/`

```
00_REVIEW_DASHBOARD.md                       ← this file
01_request_review_table.csv                  (18 rows · 23 cols · reviewer_decision blank)
02_low_risk_candidate_manifest_DRAFT.jsonl   (7 rows · manual_approval_status = PENDING_HUMAN_APPROVAL)
03_deferred_or_rejected_requests.md          (11 deferrals classified)
04_manual_review_instructions.md             (step-by-step for the human reviewer)
05_risk_scoring_rules.md                     (transparent scoring rules)
06_session_report.md                         (what this session did / did not do)
```

## Cross-file consistency

| Source | Distinct request IDs | Match with JSONL |
|---|---:|---|
| `generation_requests_preview.jsonl` | 18 | ✅ canonical |
| `human_review_sheet.csv` | 18 | ✅ match |
| `preview_v2_request_matrix.csv` | 18 | ✅ match |

**PASS** — proceeded with candidate selection.

## Counts by augmentation type

| Type | Total | DRAFT candidate | DEFER |
|---|---:|---:|---:|
| paraphrase | 4 | 0 | 4 |
| rare_positive | 4 | 3 | 1 |
| hard_negative | 4 | 0 | 4 |
| direction_contrastive | 6 | 4 (2 pairs) | 2 (1 pair) |
| **Total** | **18** | **7** | **11** |

## Counts by risk level

| Level | Total | DRAFT candidate | DEFER |
|---|---:|---:|---:|
| LOW | 10 | 7 | 3 (sensitive label or pair-coherence) |
| MEDIUM | 2 | 0 | 2 |
| HIGH | 6 | 0 | 6 |
| **Total** | **18** | **7** | **11** |

## DRAFT candidate manifest (7 requests)

> `manual_approval_status = "PENDING_HUMAN_APPROVAL"` on every row. Nothing here is approved.

| # | Request ID | Type | L1 | Label | Direction | Risk |
|---|---|---|---:|---|---|---|
| 1 | `prev_rare_positive_24_004_98671d8d01` | rare_positive | 24 | Be neat and tidy | 1 (aligned) | LOW (-1) |
| 2 | `prev_rare_positive_32_001_83df110175` | rare_positive | 32 | Be behaving properly | 1 (aligned) | LOW (-1) |
| 3 | `prev_rare_positive_7_003_49cbb6617c` | rare_positive | 7 | Have an exciting life | 1 (aligned) | LOW (-1) |
| 4 | `prev_dir_contrast_12_002_aligned_ce1da19f54` | direction_contrastive (pair A) | 12 | Have success | 1 (aligned) | LOW (0) |
| 5 | `prev_dir_contrast_12_002_contradictory_ce1da19f54` | direction_contrastive (pair A) | 12 | Have success | 0 (contradictory) | LOW (0) |
| 6 | `prev_dir_contrast_38_003_aligned_e969e14138` | direction_contrastive (pair B) | 38 | Be honest | 1 (aligned) | LOW (1) |
| 7 | `prev_dir_contrast_38_003_contradictory_e969e14138` | direction_contrastive (pair B) | 38 | Be honest | 0 (contradictory) | LOW (1) |

## Deferred / rejected requests (11)

| Cluster | Count | Primary reason |
|---|---:|---|
| All 4 paraphrase | 4 | seed_excerpt_truncated (paraphrase uses seed as primary content) |
| All 4 hard_negative | 4 | structurally hardest type; 2 also have `alternative_label_id = null`; some also sensitive |
| direction_contrastive 29 pair | 2 | sensitive label (religion / protected belief) — held for first pilot |
| rare_positive 51 | 1 | sensitive label (tolerance / minority context) — held for first pilot |

See `03_deferred_or_rejected_requests.md` for the per-request rationale.

## Warnings

- All 4 paraphrase requests carry `seed_excerpt_truncated: True` — design-honest flag from the v2 smart-cut. Deferred from this pilot; can be revisited with longer seed windows.
- 2 hard-negative requests (`prev_hard_negative_51_…`, `prev_hard_negative_29_…`) have `alternative_label_id = null`. Even after the sensitivity filter, these would still be DEFER candidates because the generator would need to invent the alternative L1 from scratch.
- `evaluation.py` direction docstring is inverted vs `direction_mapping.json`, but the metric is symmetric (scores correct). The reviewer should rely on `direction_mapping.json`, not on `evaluation.py` comments. This pack uses `"1"` = aligned, `"0"` = contradictory everywhere.

## Go / No-Go

| Action | Decision |
|---|---|
| Human review of v2 preview | ✅ **GO** (this pack supports it) |
| API generation | 🛑 **NO-GO** (no manifest is approved yet) |
| Create `run_generation.py` | 🛑 **NO-GO** |
| Model training | 🛑 **NO-GO** |
| Final FEHU submission | 🛑 **NO-GO** |

## Final recommendation

> **Proceed to human review only. API generation is still not authorized.**

After review, produce a successor manifest (e.g. `02b_human_approved_manifest.jsonl`) listing only the IDs the reviewer marked `APPROVE`. The DRAFT here remains as a record of what the scoring proposed.
