# FEHU Prediction Format Guard Report

**Timestamp:** 2026-07-26T21:19:58
**Mode:** `test`
**Event base:** `dataset/test/test_article_event_base.json`
**Pred Task-1a:** `DS_final/submission/pred_task1a.json`
**Pred Task-1b:** `DS_final/submission/pred_task1b.json`
**Strict mode:** `True`

## Verdict

✅ **All checks passed. Predictions are FEHU-conformant.**

## Summary

| Metric | Task-1a | Task-1b |
|---|---|---|
| articles | 175 | 175 |
| unique guids | 175 | 175 |
| predictions | 1834 | 2260 |
| avg preds/article | 10.48 | 12.91 |
| duplicates | 0 | 0 |
| bad actor | 0 | 0 |
| bad label id | 0 | 0 |
| bad direction | n/a | 0 |
| unknown guid | 0 | 0 |
| extra fields (strict) | 0 | 0 |

**Event base guid count:** 175
**Likely full submission:** True

## Constraints honoured

- No API call.
- No modification of any prediction file.
- No reading of `.env` values.
