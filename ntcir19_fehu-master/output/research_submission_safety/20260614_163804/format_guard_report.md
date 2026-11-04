# FEHU Prediction Format Guard Report

**Timestamp:** 2026-06-14T16:38:04
**Mode:** `dev`
**Event base:** `dataset/dev/dev_event_base.json`
**Pred Task-1a:** `output/task1_prompt_deepseek_v4_flash/pred_task1a.json`
**Pred Task-1b:** `output/task1_prompt_deepseek_v4_flash/pred_task1b.json`
**Strict mode:** `False`

## Verdict

✅ **All checks passed. Predictions are FEHU-conformant.**

## Summary

| Metric | Task-1a | Task-1b |
|---|---|---|
| articles | 177 | 177 |
| unique guids | 177 | 177 |
| predictions | 1500 | 1736 |
| avg preds/article | 8.47 | 9.81 |
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
