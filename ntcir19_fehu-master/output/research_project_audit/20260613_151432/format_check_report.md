# FEHU Format Check Report

## 1. Direction encoding (CRITICAL semantic check)

**Authoritative source:** `dataset/hv_categories/direction_mapping.json`
```json
{"aligned": "1", "contradictory": "0"}
```

| Source | "0" means | "1" means | Consistent with authority? |
|---|---|---|---|
| `dataset/hv_categories/direction_mapping.json` | contradictory | aligned | ✓ (authoritative) |
| `CLAUDE.md` | contradictory | aligned | ✓ |
| gold label data (sample inspection) | contradictory | aligned | ✓ |
| `evaluation.py` line 36 docstring | aligned (wrong) | contradictory (wrong) | ✗ INVERTED |
| `evaluation.py` lines 65-72 variable names (`G_aligned` for d=="0") | aligned (wrong) | contradictory (wrong) | ✗ INVERTED |
| `evaluation.py` DRR mathematical correctness | n/a (symmetric) | n/a (symmetric) | ✓ DRR count is correct regardless of labels |
| `src/run_pipeline.py` line 328 (`if direction_str == "contradictory": direction = "0"`) | contradictory | aligned | ✓ |
| `src/run_pipeline_deepseek_flash.py` line 303 | contradictory | aligned | ✓ |
| `src/train_deberta.py` docstring + label_index logic | contradictory | aligned | ✓ |
| `src/hybrid_pipeline.py` system prompt | contradictory | aligned | ✓ |
| `src/hybrid_v2.py` (`"1" if dir_word == "aligned" else "0"`) | contradictory | aligned | ✓ |
| `research/fehu_label_diagnosis/label_diagnosis.py` (`DIR_NAME = {"1":"aligned", "0":"contradictory"}`) | contradictory | aligned | ✓ |

**Finding (HIGH):** `evaluation.py`'s comments and variable names contradict the authoritative direction mapping. The DRR computation is *mathematically* still correct (because it counts any direction flip symmetrically), but anyone reading the code will misinterpret the semantics of the variables. Nothing else in the project is affected.

**User constraint:** evaluation.py must not be modified. This is therefore a documented hazard only.

## 2. Dataset schema

### Article schema (event_base.json)

```python
{
  "guid":     str,             # unique article id
  "title":    str,
  "content":  str,             # full text
  "actors":   List[Dict[str, str]],   # [{actor_name: actor_id_str}, ...]
  "subevents": List[Dict],     # only in non-test (and test_subevent_event_base.json)
}
```

| File | Has subevents? | n articles |
|---|---|---|
| `dataset/train/train_event_base.json` | yes | 1228 |
| `dataset/dev/dev_event_base.json` | yes | 177 |
| `dataset/test/test_article_event_base.json` | NO (Task-1 test) | 175 |
| `dataset/test/test_subevent_event_base.json` | yes (Task-2 test) | 175 |

### Gold label schema

```python
{
  "guid":   str,
  "article_human_values": [
    {"actor": str, "l1_value": str, "l2_value": str, "direction": str, "explanation": str},
    ...
  ],
  "subevents_human_values": [...]   # not used by Task-1 scripts
}
```

| File | n items | guid coverage matches articles? | distinct directions |
|---|---|---|---|
| `dataset/gold_labels/train/train_human_values.json` | 1228 | yes (1228/1228) | "0"=5449, "1"=11456 |
| `dataset/gold_labels/dev/dev_human_values.json` | 177 | yes (177/177) | "0"=793, "1"=1597 |

**Both gold files have direction values strictly in {"0", "1"} — no anomalies.**

## 3. Prediction schema (observed)

### Task-1a (article-level L2, no direction)

```python
{
  "guid": str,
  "article_human_values": [
    {"actor": str, "l2_value": str},
    ...
  ]
}
```

### Task-1b (article-level L1 + direction)

```python
{
  "guid": str,
  "article_human_values": [
    {"actor": str, "l1_value": str, "direction": str},   # direction in {"0","1"}
    ...
  ]
}
```

## 4. Per-prediction file validation

Every existing `pred_task1a.json` and `pred_task1b.json` was scanned for:
- `l2_value` ∈ {"0".."19"}
- `l1_value` ∈ {"0".."53"}
- `direction` ∈ {"0", "1"}
- `actor` ∈ actor IDs declared in `dev_event_base.json`
- Duplicate `(guid, actor, l2_value)` in Task-1a

| Folder | n articles | bad l2 | bad l1 | bad dir | bad actor | dup 1a |
|---|---|---|---|---|---|---|
| `output/task1/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_prompt/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_prompt_deepseek_v4_flash/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_prompt_deepseek_v4_flash_limit5/` | 5 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_deberta/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_hybrid/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_hybrid_v2/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_hybrid_v2_limit20/` | 20 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` | 177 | 0 | 0 | 0 | 0 | 0 |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/` | 177 | 0 | 0 | 0 | 0 | 0 |

**All prediction files are syntactically and semantically valid.** Every full-dev folder covers exactly the 177 dev guids.

## 5. Risk assessment

| Severity | Item |
|---|---|
| HIGH | `evaluation.py` direction docstring/variable names contradict `direction_mapping.json`. The DRR is still numerically correct (the function is symmetric in the two directions), but this is a documentation hazard. |
| LOW | All prediction files conform to the expected schema with no malformed items. |
