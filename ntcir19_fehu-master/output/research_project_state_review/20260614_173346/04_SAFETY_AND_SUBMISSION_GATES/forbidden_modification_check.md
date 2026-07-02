# Forbidden-Modification Check

Each "must not touch" category is checked against the filesystem at audit time. The bar for "touched" is **any file modification after 2026-06-14 00:00** (i.e. on the day of this audit).

| Category | Path glob | Files touched today | Verdict |
|---|---|---:|---|
| Official dataset | `dataset/**` | 0 | ✅ untouched |
| Official evaluator | `evaluation.py` | 0 (unchanged vs git HEAD) | ✅ untouched |
| Legacy predictions | `output/task1*/**` | 0 | ✅ untouched |
| Logs / caches | `logs/cache_*.json` | 0 | ✅ untouched |
| Trained checkpoint | `checkpoints/best_model/**` | 0 | ✅ untouched |
| Previous preview folder | `output/research_generation_preview/20260614_163649/**` | 0 | ✅ untouched |
| Other research outputs (older than today) | `output/research_*/{older}` | 0 | ✅ untouched |

**Files modified by this audit:** only the new audit folder
`output/research_project_state_review/20260614_173346/**` (created fresh).

**Files created outside the audit folder:** none.

**Files deleted:** none.

**Files renamed/moved:** none.

## Independent verification commands used

```bash
git diff --quiet HEAD -- evaluation.py && echo unchanged
find dataset -type f -newermt '2026-06-14 00:00'   # empty
find output/task1* -type f -newermt '2026-06-14 00:00'  # empty
find logs -name 'cache_*.json' -newermt '2026-06-14 00:00'  # empty
find checkpoints -type f -newermt '2026-06-14 00:00'  # empty
stat output/research_generation_preview/20260614_163649/generation_requests_preview.jsonl  # 2026-06-14 16:36
```

All commands were read-only.
