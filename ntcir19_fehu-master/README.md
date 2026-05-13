**Note (March 20, 2026):** Versions before commit `af52dcb` (as of March 20, 2026) are incorrect: `dataset/gold_labels/dev/dev_human_values.json` and `dataset/gold_labels/train/train_human_values.json` contained actor misalignment caused by a code bug. This has been corrected in the current version.

# NTCIR-19 FEHU (Fact-based Event-centric Human Value Understanding)

This repository provides the **NTCIR-19 FEHU** benchmark resources and evaluation code for **human value recognition** in **factual news articles** and their **subevents**.

FEHU focuses on identifying **human values expressed by each actor** at:
- **Article level** (Task-1)
- **Subevent level** (Task-2)

## Repository Structure
```
ntcir19_fehu/
├─ dataset/
│  ├─ train/
│  │  ├─ train_event_base.json
│  │  └─ train_human_values.json
│  ├─ dev/
│  │  ├─ dev_event_base.json
│  │  └─ (dev labels may be provided under dataset/gold_labels/dev/)
│  ├─ test/
│  │  ├─ test_article_event_base.json
│  │  └─ test_subevent_event_base.json
│  ├─ gold_labels/
│  │  ├─ train/
│  │  │  └─ train_human_values.json
│  │  └─ dev/
│  │     └─ dev_human_values.json
│  ├─ hv_categories/
│  │  ├─ direction_mapping.json
│  │  ├─ human_value_level1_values.json
│  │  ├─ human_value_level2_values.json
│  │  ├─ human_value_taxonomy.json
│  │  ├─ level_1_to_level_2.json
│  │  └─ level_2_to_level_1.json
│  └─ evaluation_test_data_examples/
│     └─ pred/
│        ├─ task1/
│        │  ├─ pred_task1a.json
│        │  └─ pred_task1b.json
│        └─ task2/
│           ├─ pred_task2a.json
│           └─ pred_task2b.json
├─ evaluation.py
└─ README.md
```

---


## Tasks Overview

### Task-1: Article-level Human Value Recognition
- **Task-1a (Level-2, no direction)**
  Identify **Level-2** human values for each **actor** in the article.
- **Task-1b (Level-1 + direction)**
  Identify **Level-1** human values for each **actor**, and assign the **direction**:
  - `direction = 1` → **aligned**
  - `direction = 0` → **contradictory**

**Evaluation unit (instance)**: `(guid, actor)`

---

### Task-2: Subevent-level Human Value Recognition
- **Task-2a (Level-2, no direction)**
  Identify **Level-2** human values for each **actor** in each **subevent**.
- **Task-2b (Level-1 + direction)**
  Identify **Level-1** human values for each **actor** in each **subevent**, with direction:
  - `direction = 1` → **aligned**
  - `direction = 0` → **contradictory**

**Evaluation unit (instance)**: `(guid, subevent_id, actor)`

---

## Human Value Label Set (`dataset/hv_categories/`)

This benchmark provides a two-level human value label set, plus taxonomy and mappings.

- `human_value_level1_values.json`
  Level-1 human value labels with ID mappings (`"0"`–`"53"`).

- `human_value_level2_values.json`
  Level-2 human value labels with ID mappings (`"0"`–`"19"`).

- `human_value_taxonomy.json`
  Overall human value taxonomy (Level-1 to higher-level categories).

- `level_1_to_level_2.json`
  Mapping from Level-1 → Level-2.

- `level_2_to_level_1.json`
  Mapping from Level-2 → Level-1.

- `direction_mapping.json`
  Direction ID mapping:
  - `1` = aligned
  - `0` = contradictory

---

## Event Dataset (Articles + Subevents)

### Event Base Files
Located in:
- `dataset/train/train_event_base.json`
- `dataset/dev/dev_event_base.json`
- `dataset/test/test_article_event_base.json`
- `dataset/test/test_subevent_event_base.json`

**Common fields (schema):**
- `guid`: article ID
- `title`: news title
- `content`: factual news content
- `actors`: list of actors in the article
- `subevents`: list of subevents (may be empty for article-only test)

**Subevent fields:**
- `id`: subevent ID (string or integer-like string)
- `subevent`: subevent text/content

**Test split note:**
- `test_article_event_base.json` contains **article-level** information only.
- `test_subevent_event_base.json` contains **article + subevents** for subevent-level evaluation.

---

## Gold Human Value Labels (Train/Dev)

Gold labels are provided for training/dev.
**Important:** In the current scorer, gold labels are **merged** per level:
- **Task-1 gold file** contains everything needed for **Task-1a and Task-1b**
- **Task-2 gold file** contains everything needed for **Task-2a and Task-2b**

Typical locations:
- Train: `dataset/gold_labels/train/train_human_values.json`
- Dev: `dataset/gold_labels/dev/dev_human_values.json`

### Task-1 Gold (Article-level labels)
Each record includes:
- `guid`
- `article_human_values`: list of actor-centric labels

Each item in `article_human_values` typically includes:
- `actor`
- `l2_value` (Level-2 ID, `"0"`–`"19"`) **[used by Task-1a]**
- `l1_value` (Level-1 ID, `"0"`–`"53"`) **[used by Task-1b]**
- `direction` (`"1"` aligned / `"0"` contradictory) **[used by Task-1b]**
- `explanation` (optional rationale text)

### Task-2 Gold (Subevent-level labels)
Each record includes:
- `guid`
- `subevents_human_values`: list of subevents

Each item in `subevents_human_values` includes:
- `subevent_id`
- `subevent_human_values`: list of actor-centric labels within that subevent

Each item in `subevent_human_values` typically includes:
- `actor`
- `l2_value` **[used by Task-2a]**
- `l1_value` + `direction` **[used by Task-2b]**
- `explanation` (optional)

---

## Submission Output Formats (Predictions)

Example prediction files are provided in:
- `dataset/evaluation_test_data_examples/pred/task1/`
- `dataset/evaluation_test_data_examples/pred/task2/`

Participants should generate prediction files following the official JSON formats:
- `pred_task1a.json` (Task-1a, Level-2, no direction)
- `pred_task1b.json` (Task-1b, Level-1 + direction)
- `pred_task2a.json` (Task-2a, Level-2, no direction)
- `pred_task2b.json` (Task-2b, Level-1 + direction)

For Task-1b / Task-2b evaluation, the scorer internally encodes labels in a **direction-aware label space**:
- `"{direction}:{l1_value}"` (e.g., `"1:42"`)
  - `direction ∈ {"1","0"}` (1 aligned, 0 contradictory)
  - `l1_value ∈ {"0"... "53"}`

---

## Evaluation

The official scorer is provided in `evaluation.py`.

### Metrics
- **micro-F1**
- **macro-F1 (gold-supported)**
  Macro-F1 is averaged over labels that appear at least once in **gold**.
- **Task-1b / Task-2b only: Direction Reverse Rate (DRR)**
  Measures how often a gold **Level-1** value (with a unique direction) is predicted with the **opposite direction** (aligned ↔ contradictory).
  Ambiguous gold cases where the same `l1_value` appears with **both directions** within the same instance are **filtered out** for DRR.

### Run the evaluator (example)

> Gold is merged per level:
> - `--gold_task1` is used for Task-1a and Task-1b
> - `--gold_task2` is used for Task-2a and Task-2b

```bash
python evaluation.py \
  --gold_task1 dataset/gold_labels/dev/dev_human_values.json \
  --pred_task1a dataset/evaluation_test_data_examples/pred/task1/pred_task1a.json \
  --pred_task1b dataset/evaluation_test_data_examples/pred/task1/pred_task1b.json \
  --gold_task2 dataset/gold_labels/dev/dev_human_values.json \
  --pred_task2a dataset/evaluation_test_data_examples/pred/task2/pred_task2a.json \
  --pred_task2b dataset/evaluation_test_data_examples/pred/task2/pred_task2b.json
# ntcir19_fehu
```

### Contact Information:
- **Yao Wang: oh.gyou.tkb_gf@u.tsukuba.ac.jp**
- **Zhuochen Liu: s2426082@u.tsukuba.ac.jp**
- **Jiankang Chen: s2526100@u.tsukuba.ac.jp**
- **Xin Liu: https://staff.aist.go.jp/xin.liu/**
- **Kyoungsook Kim: https://staff.aist.go.jp/ks.kim/**
- **Adam Jatowt:  https://ds-informatik.uibk.ac.at/doku.php?id=contact**
- ***Haitao Yu: https://ii-research-yu.github.io/**
