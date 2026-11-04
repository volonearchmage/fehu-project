# Human Approval Dashboard

**Current stage:** human approval manifest created. **No generation has been performed. No API has been called.**

## Inputs

| File | Role |
|---|---|
| `output/research_human_review_pack/20260615_161044/01_request_review_table.csv` | 18-row review table (read-only) |
| `output/research_human_review_pack/20260615_161044/02_low_risk_candidate_manifest_DRAFT.jsonl` | 7-row DRAFT (read-only) |
| `output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl` | Canonical 18-row preview with full prompts (read-only) |

## Output folder

```
output/research_human_approval/20260616_004845/
├── 00_APPROVAL_DASHBOARD.md                       ← this file
├── 01_request_review_table_HUMAN_DECISION.csv     (18 rows: 6 APPROVE, 12 DEFER, 0 REJECT)
├── 02b_human_approved_manifest.jsonl              (6 rows; `manual_approval_status = "APPROVED_BY_HUMAN"`)
├── 03_deferred_requests_after_human_decision.md   (12 deferrals grouped by reason)
├── 04_generation_readiness_check.md               (Go/No-Go + negative invariants)
└── 05_session_report.md                           (safety attestations)
```

## Counts

| Decision | Count |
|---|---:|
| APPROVE | **6** |
| DEFER | **12** |
| REJECT | 0 |
| **Total** | **18** |

## Approved requests (6)

| # | Request ID | Type | L1 | Label | Direction |
|---|---|---|---:|---|---|
| 1 | `prev_rare_positive_24_004_98671d8d01` | rare_positive | 24 | Be neat and tidy | 1 (aligned) |
| 2 | `prev_rare_positive_32_001_83df110175` | rare_positive | 32 | Be behaving properly | 1 (aligned) |
| 3 | `prev_dir_contrast_12_002_aligned_ce1da19f54` | direction_contrastive (pair A) | 12 | Have success | 1 (aligned) |
| 4 | `prev_dir_contrast_12_002_contradictory_ce1da19f54` | direction_contrastive (pair A) | 12 | Have success | 0 (contradictory) |
| 5 | `prev_dir_contrast_38_003_aligned_e969e14138` | direction_contrastive (pair B) | 38 | Be honest | 1 (aligned) |
| 6 | `prev_dir_contrast_38_003_contradictory_e969e14138` | direction_contrastive (pair B) | 38 | Be honest | 0 (contradictory) |

Each approved row carries:

- `manual_approval_status: "APPROVED_BY_HUMAN"`
- `approved_for: "future_tiny_pilot_generation"`
- `api_generation_authorized_now: false`
- `requires_separate_generation_runner_approval: true`
- `approval_scope: "approval_manifest_only_no_execution"`
- `approved_by: "human_user_explicit_request_ids"`
- `approval_note: "Approved for first conservative tiny pilot manifest. This does not authorize API generation."`

Original preview metadata is preserved: `system_prompt`, `user_prompt`, `expected_output_schema`, `evidence_requirement`, `preview_only: true`, `do_not_execute: true`, `preview_revision: 2`, etc.

## Deferred summary (12)

| Reason cluster | Distinct requests |
|---|---:|
| Truncated seed (paraphrase) | 4 |
| Hard-negative (structurally hardest; 2 also null-alt) | 4 |
| Sensitive label (29 religion / 51 tolerance) | 4 unique (with overlap above) |
| Generic-content risk (rare_positive L1=7) | 1 |
| **Total** | **12** |

Detail in `03_deferred_requests_after_human_decision.md`.

## Safety attestations

| Question | Answer |
|---|---|
| Any API called? | **No.** No HTTP / LLM client imported by this session. |
| Any model trained? | **No.** |
| Was `.env` read? | **No** (file does not exist). |
| Was `evaluation.py` modified? | **No** (byte-identical to git HEAD `c37a775`). |
| Was `dataset/**` modified? | **No.** |
| Was `output/task1*/` modified? | **No.** |
| Were `logs/cache_*` modified? | **No.** |
| Were old preview folders modified? | **No.** |
| Were prior state-review folders modified? | **No.** |
| Was the original human review pack modified? | **No** (read-only access only). |
| Was any request marked APPROVE that is not on the explicit human list? | **No** (verified by set-equality check). |

## Go / No-Go

| Item | Decision |
|---|---|
| Human approval manifest created | ✅ GO |
| API generation | 🛑 NO-GO |
| `run_generation.py` creation | 🛑 NO-GO (unless separately requested) |
| Model training | 🛑 NO-GO |
| Final FEHU submission | 🛑 NO-GO |

## Final recommendation

> **Human approval manifest created. API generation is still not authorized.**
