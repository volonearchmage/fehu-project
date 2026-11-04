# Manifest Validation Report

**Manifest:** `human_user_explicit_request_ids` source — see `00_DRY_RUN_DASHBOARD.md`.
**Rows loaded:** 6
**Expected rows:** 6
**Verdict:** PASS

## Checks performed

1. Manifest has exactly 6 rows.
2. Every row has `manual_approval_status == 'APPROVED_BY_HUMAN'`.
3. Every row has `api_generation_authorized_now == False`.
4. Every row has `requires_separate_generation_runner_approval == True`.
5. No row has `manual_approval_status == 'PENDING_HUMAN_APPROVAL'`.
6. No row has any field named `execute` or `should_execute_now`.
7. No `hard_negative` request is included.
8. No `paraphrase` request is included.
9. No sensitive-label request (L1 ∈ {29, 44, 51}) is included.
10. Both required direction_contrastive pairs are present:
    - prev_dir_contrast_12_002_aligned_… / contradictory_…
    - prev_dir_contrast_38_003_aligned_… / contradictory_…
11. Direction convention `'1'` = aligned, `'0'` = contradictory consistent on every row.
12. No secret-shaped tokens (`sk-…`, `ds-…`, `anthropic-…`) in the manifest payload.

## Result

✅ **All checks passed.**

| Row | request_id | type | L1 | direction |
|---|---|---|---|---|
| 1 | `prev_dir_contrast_12_002_aligned_ce1da19f54` | direction_contrastive | 12 | 1 |
| 2 | `prev_dir_contrast_12_002_contradictory_ce1da19f54` | direction_contrastive | 12 | 0 |
| 3 | `prev_dir_contrast_38_003_aligned_e969e14138` | direction_contrastive | 38 | 1 |
| 4 | `prev_dir_contrast_38_003_contradictory_e969e14138` | direction_contrastive | 38 | 0 |
| 5 | `prev_rare_positive_24_004_98671d8d01` | rare_positive | 24 | 1 |
| 6 | `prev_rare_positive_32_001_83df110175` | rare_positive | 32 | 1 |

## What this validation does NOT do

- Does not call any API.
- Does not read `.env`.
- Does not authorise execution.
- Does not modify the manifest or any other existing file.