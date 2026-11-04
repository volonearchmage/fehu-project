# FEHU Prediction Format Guard Report

**Timestamp:** 2026-07-26T20:14:25
**Mode:** `test`
**Event base:** `dataset/test/test_article_event_base.json`
**Pred Task-1a:** `DS_final/outputs/pred_task1a.json`
**Pred Task-1b:** `DS_final/outputs/pred_task1b.json`
**Strict mode:** `True`

## Verdict

❌ **354 issue(s) found. See `invalid_entries.csv` for details.**

## Summary

| Metric | Task-1a | Task-1b |
|---|---|---|
| articles | 177 | 177 |
| unique guids | 177 | 177 |
| predictions | 1724 | 2164 |
| avg preds/article | 9.74 | 12.23 |
| duplicates | 0 | 0 |
| bad actor | 0 | 0 |
| bad label id | 0 | 0 |
| bad direction | n/a | 0 |
| unknown guid | 177 | 177 |
| extra fields (strict) | 0 | 0 |

**Event base guid count:** 175
**Likely full submission:** False
> ⚠ Article count is less than event_base guid count — this looks like a **limit/debug** run. Do NOT submit as a final result.

## Constraints honoured

- No API call.
- No modification of any prediction file.
- No reading of `.env` values.
