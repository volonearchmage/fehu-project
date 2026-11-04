# FEHU Prediction Format Guard Report

**Timestamp:** 2026-07-26T20:17:37
**Mode:** `dev`
**Event base:** `dataset/dev/dev_event_base.json`
**Pred Task-1a:** `/var/folders/wl/fnn0v6f143gg6rd52bfdfzgr0000gn/T/tmp.c2TYM1vgoP/pred_task1a.json`
**Pred Task-1b:** `/var/folders/wl/fnn0v6f143gg6rd52bfdfzgr0000gn/T/tmp.c2TYM1vgoP/pred_task1b.json`
**Strict mode:** `True`

## Verdict

✅ **All checks passed. Predictions are FEHU-conformant.**

## Summary

| Metric | Task-1a | Task-1b |
|---|---|---|
| articles | 177 | 177 |
| unique guids | 177 | 177 |
| predictions | 1724 | 2161 |
| avg preds/article | 9.74 | 12.21 |
| duplicates | 0 | 0 |
| bad actor | 0 | 0 |
| bad label id | 0 | 0 |
| bad direction | n/a | 0 |
| unknown guid | 0 | 0 |
| extra fields (strict) | 0 | 0 |

**Event base guid count:** 177
**Likely full submission:** True

## Constraints honoured

- No API call.
- No modification of any prediction file.
- No reading of `.env` values.
