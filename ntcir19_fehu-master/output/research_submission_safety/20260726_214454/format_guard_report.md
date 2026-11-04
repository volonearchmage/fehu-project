# FEHU Prediction Format Guard Report

**Timestamp:** 2026-07-26T21:44:54
**Mode:** `test`
**Event base:** `dataset/test/test_article_event_base.json`
**Pred Task-1a:** `/Users/lloydhuang/Downloads/task1/pred_task1a.json`
**Pred Task-1b:** `/Users/lloydhuang/Downloads/task1/pred_task1b.json`
**Strict mode:** `True`

## Verdict

✅ **All checks passed. Predictions are FEHU-conformant.**

## Summary

| Metric | Task-1a | Task-1b |
|---|---|---|
| articles | 175 | 175 |
| unique guids | 175 | 175 |
| predictions | 1811 | 2058 |
| avg preds/article | 10.35 | 11.76 |
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
