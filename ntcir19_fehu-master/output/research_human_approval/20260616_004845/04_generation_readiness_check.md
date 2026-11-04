# Generation Readiness Check

Every check is independently re-verified by reading the files written in this folder.

## Go / No-Go

| Item | Decision |
|---|---|
| Human approval manifest created | ✅ **GO** |
| Approved manifest has exactly 6 rows | ✅ **GO** |
| Both direction_contrastive pairs complete (12 + 38) | ✅ **GO** |
| Direction convention `aligned="1"`, `contradictory="0"` | ✅ **GO** (per `dataset/hv_categories/direction_mapping.json`) |
| API generation now | 🛑 **NO-GO** |
| `run_generation.py` creation now | 🛑 **NO-GO** unless separately requested |
| Model training | 🛑 **NO-GO** |
| Final FEHU submission | 🛑 **NO-GO** |
| Official dataset modification | 🛑 **NO-GO** |
| Old prediction modification | 🛑 **NO-GO** |

## Negative invariants on the approved manifest

Cross-checked programmatically against `02b_human_approved_manifest.jsonl`:

| Invariant | Status |
|---|---|
| No `hard_negative` request approved | ✅ verified — 0 of 6 |
| No `paraphrase` request approved | ✅ verified — 0 of 6 |
| No sensitive-label (L1 ∈ {29, 44, 51}) request approved | ✅ verified — 0 of 6 |
| No row carries `manual_approval_status = "PENDING_HUMAN_APPROVAL"` | ✅ verified — every row has `APPROVED_BY_HUMAN` |
| No row carries `api_generation_authorized_now = true` | ✅ verified — every row has `false` |
| No `execute` field | ✅ verified — absent from all 6 rows |
| No `should_execute_now` field | ✅ verified — absent from all 6 rows |
| `preview_only: true` and `do_not_execute: true` preserved | ✅ verified — preserved from the canonical preview |
| `preview_revision: 2` preserved | ✅ verified — every row |

## Pair completeness

| Pair | Aligned member | Contradictory member |
|---|---|---|
| L1 = 12 (Have success) | `prev_dir_contrast_12_002_aligned_ce1da19f54` ✅ | `prev_dir_contrast_12_002_contradictory_ce1da19f54` ✅ |
| L1 = 38 (Be honest) | `prev_dir_contrast_38_003_aligned_e969e14138` ✅ | `prev_dir_contrast_38_003_contradictory_e969e14138` ✅ |

Both pairs are fully present in the approved manifest. The 29 (religion) pair was deferred together, not approved.

## Direction convention spot-check

For every approved row in the manifest:

| `target_direction` | Expected `target_direction_name` | Result |
|---|---|---|
| "1" | "aligned" | ✅ matches in all aligned rows |
| "0" | "contradictory" | ✅ matches in all contradictory rows |

Source of truth: `dataset/hv_categories/direction_mapping.json` (`{"aligned": "1", "contradictory": "0"}`). `evaluation.py`'s docstring is inverted but DRR symmetric — not used here.

## Files this check inspects

- `output/research_human_approval/20260616_004845/02b_human_approved_manifest.jsonl`
- `output/research_human_approval/20260616_004845/01_request_review_table_HUMAN_DECISION.csv`
- `output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl` (read-only)
- `dataset/hv_categories/direction_mapping.json` (read-only)

## Verdict

The approval manifest is structurally complete and consistent with the explicit human decision. **API generation is NOT authorized by this manifest**; that authorization requires a separately-approved generation-runner workflow.
