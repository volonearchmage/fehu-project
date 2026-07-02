# Prediction Consistency Check

## Per-folder summary

| Folder | Arts | 1a count | 1b count | avg 1a/art | avg 1b/art | bad l2 | bad l1 | bad dir | bad actor | dup 1a | full-dev |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| `task1/` | 177 | 929 | 1027 | 5.25 | 5.80 | 0 | 0 | 0 | 0 | 0 | yes |
| `task1_prompt/` | 177 | 929 | 1027 | 5.25 | 5.80 | 0 | 0 | 0 | 0 | 0 | yes |
| `task1_prompt_deepseek_v4_flash/` | 177 | 1500 | 1736 | 8.47 | 9.81 | 0 | 0 | 0 | 0 | 0 | yes |
| `task1_prompt_deepseek_v4_flash_limit5/` | 5 | 46 | 52 | 9.20 | 10.40 | 0 | 0 | 0 | 0 | 0 | NO |
| `task1_deberta/` | 177 | 1786 | 3378 | 10.09 | 19.08 | 0 | 0 | 0 | 0 | 0 | yes |
| `task1_hybrid/` | 177 | 2417 | 3117 | 13.66 | 17.61 | 0 | 0 | 0 | 0 | 0 | yes |
| `task1_hybrid_v2/` | 177 | 1040 | 1098 | 5.88 | 6.20 | 0 | 0 | 0 | 0 | 0 | yes (orphan) |
| `task1_hybrid_v2_limit20/` | 20 | 136 | 151 | 6.80 | 7.55 | 0 | 0 | 0 | 0 | 0 | NO |
| `task1_hybrid_v2_deepseek_deepseek_v4_pro/` | 177 | 1069 | 1202 | 6.04 | 6.79 | 0 | 0 | 0 | 0 | 0 | yes |
| `task1_hybrid_v2_deepseek_deepseek_v4_flash/` | 177 | 1078 | 1270 | 6.09 | 7.18 | 0 | 0 | 0 | 0 | 0 | yes |

## Observations

### Format compliance — all clean
Every prediction file passed every validation check:
- All `l2_value` ∈ {"0".."19"}
- All `l1_value` ∈ {"0".."53"}
- All `direction` ∈ {"0", "1"}
- All actor IDs are present in `dataset/dev/dev_event_base.json`
- No duplicate `(guid, actor, l2_value)` entries in any Task-1a file
- Task-1a and Task-1b guid sets are identical within each folder

### Volume distribution

| Method family | Avg predictions per article (Task-1b) |
|---|---|
| Prompt OAI (gpt-4o-mini) | 5.80 |
| Prompt DS Flash | 9.81 |
| DeBERTa-only (thresh=0.3) | 19.08 |
| Hybrid v1 | 17.61 |
| Hybrid v2 OAI (orphan) | 6.20 |
| Hybrid v2 DS Pro | 6.79 |
| Hybrid v2 DS Flash | 7.18 |

This breakdown is consistent with the architectural intent:
- **Prompt-only** methods are conservative.
- **DeBERTa-only** at threshold 0.3 over-predicts (highest volume).
- **Hybrid v1** keeps most DeBERTa candidates after LLM "keep/remove" — high volume.
- **Hybrid v2** lets the LLM assign direction → moderate volume similar to prompt-only.

### Limit runs are properly named and easy to detect

Both limit folders (`_limit5/`, `_limit20/`) cover fewer than 177 guids and their `run_config.json` records the limit value. The label diagnosis script correctly excludes both from the main full-dev comparison.

### Suspicious files

| File | Concern |
|---|---|
| `output/task1/pred_task1a.json` | Same bytes as `output/task1_prompt/pred_task1a.json`. Probably overwritten by the prompt-only run. |
| `output/task1/pred_task1a_4omini.json` | Manually-named archive (no script writes this name); no run_config or metrics file alongside. |
| `output/task1/pred_task1b_4omini.json` | Same caveat. |
| `output/task1_hybrid_v2/` | Orphan — does not match the script's current canonical OAI v2 path. |

### Anomalies — none beyond the above

No empty files, no truncated files, no schema drift.

## Risk summary

| Severity | Item |
|---|---|
| HIGH | `output/task1/` is a duplicate of `output/task1_prompt/`; not a separate result |
| MEDIUM | `output/task1_hybrid_v2/` is an orphan; its provenance is undocumented |
| MEDIUM | `output/task1/pred_task1a_4omini.json` and `pred_task1b_4omini.json` are manual archives — should be moved to a clearly named folder |
| LOW | All other folders pass every schema check |
