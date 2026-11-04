# Safety Audit Report
**Audit Date:** 2026-06-26

---

## evaluation.py

| Check | Result |
|-------|--------|
| File exists | YES |
| Last modified | 2026-05-17 17:39 |
| Modified during DRA-FEHU work (after 2026-06-13) | **NO** |
| Verdict | SAFE — not touched |

---

## dataset/** Files

| Check | Result |
|-------|--------|
| dataset/gold_labels/dev/dev_human_values.json last modified | 2026-05-17 17:39 |
| dataset/gold_labels/train/train_human_values.json last modified | 2026-05-17 17:39 |
| Any dataset/ file modified after 2026-05-17 | **NO** (`find -newer` returned no results) |
| Verdict | SAFE — no dataset files modified |

---

## logs/cache_* Files

| File | Last Modified |
|------|--------------|
| cache_dev.json | 2026-05-17 17:39 |
| cache_test_openai.json | 2026-05-17 17:39 |
| cache_hybrid_dev.json | 2026-05-17 22:05 |
| cache_hybrid_v2_dev.json | 2026-05-18 20:18 |
| cache_hybrid_v2_dev_deepseek_deepseek_v4_pro.json | 2026-05-18 21:03 |
| cache_dev_deepseek_v4_flash.json | 2026-05-19 20:22 |
| cache_hybrid_v2_dev_deepseek_deepseek_v4_flash.json | 2026-05-19 19:39 |

All cache files were last modified before June 13, 2026 (the start of DRA-FEHU work).  
**No cache files were modified during the DRA-FEHU pipeline.** SAFE.

---

## output/task1*/ Files

| Check | Result |
|-------|--------|
| output/task1/pred_task1a.json last modified | 2026-05-17 22:11 |
| output/task1/pred_task1b.json last modified | 2026-05-17 22:11 |
| Any new pred_task1a/b.json created since June 13 | **NO** |
| Verdict | SAFE — original prediction files untouched since May 2026 |

---

## Previous Output Folders

| Check | Result |
|-------|--------|
| research_generation_preview/20260614_171644/ overwritten | NO — file dates confirm original creation |
| research_human_review_pack/20260615_161044/ overwritten | NO |
| research_human_approval/20260616_004845/ overwritten | NO |
| research_generation_dry_run/20260616_013343/ overwritten | NO |
| research_generation_tiny_pilot/20260615_171954/ overwritten | NO |
| research_generation_tiny_pilot_repair/20260615_175432/ overwritten | NO |
| Verdict | SAFE — no previous output folders appear overwritten |

---

## Suspicious Generated Training Files

| Check | Result |
|-------|--------|
| Files named *augmented_training* or *train_augmented* | Found 1: `research/fehu_submission_safety/augmented_training_data_guard.py` |
| Is this a training data file? | **NO** — it is a guard/safety script, not a training data file |
| Any .jsonl or .json file named "augmented_train*" or "*_training_data*" | NONE FOUND |
| Verdict | SAFE — no augmented training data file created |

---

## Final Prediction Files Accidentally Created

| Check | Result |
|-------|--------|
| pred_task1a.json in output/task1/ | YES — created 2026-05-17 (baseline run, not during DRA-FEHU) |
| pred_task1b.json in output/task1/ | YES — created 2026-05-17 (baseline run, not during DRA-FEHU) |
| New pred_task1a.json or pred_task1b.json anywhere in project | **NO new ones found** |
| Verdict | SAFE — no accidental final prediction files created during DRA-FEHU work |

---

## API Keys in Generated Reports

| Check | Result |
|-------|--------|
| Actual `sk-…` token values in repair folder reports | NONE FOUND |
| Actual DeepSeek key values in any report | NONE FOUND |
| References to API key pattern strings in dry-run report | YES — but only descriptive text ("tokens of shape `sk-…`") and env var names (`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`), not actual values |
| `.env` file read or contents in any report | NO evidence |
| Verdict | SAFE — no actual API key values exposed in any generated report |

---

## Summary

| Boundary | Status |
|----------|--------|
| evaluation.py not modified | SAFE |
| dataset/** not modified | SAFE |
| dataset/gold_labels/** not modified | SAFE |
| output/task1*/ not modified (since DRA-FEHU began) | SAFE |
| logs/cache_* not modified (since DRA-FEHU began) | SAFE |
| Previous output folders not overwritten | SAFE |
| No augmented training data file created | SAFE |
| No new final prediction files created | SAFE |
| No API keys in generated reports | SAFE |

**All safety boundaries are intact.**
