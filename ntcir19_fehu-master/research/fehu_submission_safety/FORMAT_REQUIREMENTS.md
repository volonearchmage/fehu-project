# FEHU Format Requirements

Authoritative reference for **(1) final FEHU prediction files** and **(2) future
augmented training samples**. All producer scripts in this project must
conform to this document. Both guards in this directory reject any deviation.

---

## Part 1 — Final FEHU prediction files (Task-1)

### File names

| File | Contents | Required for |
|---|---|---|
| `pred_task1a.json` | Article-level L2 predictions per actor | Task-1a (dev + test) |
| `pred_task1b.json` | Article-level L1 + direction predictions per actor | Task-1b (dev + test) |

### Top-level structure

Each file is a **JSON array** of article entries:

```json
[
  {
    "guid": "0-4325-2-1",
    "article_human_values": [ ... ]
  },
  ...
]
```

The `guid` set must equal the `guid` set in the corresponding event-base file:
- dev: `dataset/dev/dev_event_base.json`
- test (Task-1): `dataset/test/test_article_event_base.json`

A submission with fewer guids than the event base is a **limit/debug run** and
must not be submitted as a final result.

### Task-1a entry schema

```json
{ "actor": "0-4325-2-1-0", "l2_value": "15" }
```

| Field | Type | Constraint |
|---|---|---|
| `actor` | string | Must appear in `actors` of the matching event_base entry |
| `l2_value` | string | One of `"0".."19"` (20 L2 categories) |

No other fields are allowed in strict mode. Duplicate `(actor, l2_value)`
pairs are forbidden within a single guid.

### Task-1b entry schema

```json
{ "actor": "0-4325-2-1-0", "l1_value": "42", "direction": "1" }
```

| Field | Type | Constraint |
|---|---|---|
| `actor` | string | Must appear in `actors` of the matching event_base entry |
| `l1_value` | string | One of `"0".."53"` (54 L1 values) |
| `direction` | string | Exactly `"0"` or `"1"` |

No other fields are allowed in strict mode. Duplicate
`(actor, l1_value, direction)` tuples are forbidden within a single guid.

### Direction convention (authoritative)

From `dataset/hv_categories/direction_mapping.json`:

| direction | meaning |
|---|---|
| `"0"` | contradictory — the actor's behavior violates / undermines the value |
| `"1"` | aligned — the actor's behavior expresses / upholds the value |

`evaluation.py`'s docstring uses inverted variable names; the **DRR is
mathematically symmetric** so the score is correct either way, but the
authoritative direction names are above.

### Consistency between Task-1a and Task-1b

Both prediction files MUST cover the **same** guid set. A Task-1a file
covering more or fewer guids than Task-1b is a hard error in strict mode.

For a given `(guid, actor)`, the L2 values predicted in Task-1a should be
consistent with the L1 values predicted in Task-1b (i.e. each predicted L1
should map to one of the predicted L2s via
`dataset/hv_categories/level_1_to_level_2.json`). This is checked as a
**warning**, not an error, because Task-1a and Task-1b are evaluated
independently.

### Final-prediction checklist (before submission)

1. Two files exist: `pred_task1a.json`, `pred_task1b.json`.
2. Each is parseable JSON.
3. Each is a top-level array.
4. Each guid in the array is in the event_base.
5. Each `actor` is declared for that guid.
6. Every `l2_value`, `l1_value`, `direction` is in its allowed set.
7. No duplicate predictions within a guid.
8. Task-1a and Task-1b cover the same guid set.
9. Article count matches event_base count (no limit/debug run).
10. `fehu_prediction_format_guard.py` returns exit code 0.

---

## Part 2 — Augmented training samples

### File names

Augmented samples live in JSONL files under a clearly augmentation-specific
folder. **Never write augmented samples into `dataset/`** — they are training
data, not benchmark data.

Recommended location:

```
output/research_augmentation_data/YYYYMMDD_HHMMSS/
├── augmented_samples.jsonl          # validated samples
├── augmented_samples_rejected.jsonl # samples that failed verification
├── generation_run_config.json
└── verification_summary.json
```

### Per-sample schema

Authoritative: `research/fehu_augmentation_v1/augmentation_schema.json`.

Required fields:

- `augmentation_id` (unique, pattern-matched)
- `augmentation_type` ∈ {`paraphrase`, `rare_positive`, `hard_negative`, `direction_contrastive`}
- `source_label_id` (string in `"0".."53"`)
- `source_label_name`
- `l2_value_id` (string in `"0".."19"`, must map from `source_label_id`)
- `l2_value_name`
- `direction` (`"0"` or `"1"`)
- `direction_name` (`"contradictory"` or `"aligned"`, must match `direction`)
- `title`, `content`, `actor_name`, `actor_id`
- `evidence_sentence` (must appear in `content`, or be prefixed `[derived] `)
- `explanation`
- `is_positive` (boolean)

Conditional fields:

- `hard_negative` samples require `negative_target_label_id`.
- `direction_contrastive` samples require `paired_augmentation_id`.

Optional metadata:

- `seed_guid`, `seed_actor_id` (TRAIN seed provenance)
- `generation_model`, `generation_prompt_id`, `verifier_model`
- `verification_status` ∈ {`pending`, `accepted`, `rejected`, `needs_human_review`}
- `content_hash`, `created_at`

### Hard rules

- **Source must not be `official_gold`.** Augmented samples are synthetic; if
  any sample claims `source: "official_gold"`, the guard rejects it.
- **No dev/test guids.** A sample's `seed_guid`, if present, must be a TRAIN
  guid. Dev and test guids are reserved.
- **No API keys.** No sample field may contain `sk-…`-style tokens or any
  similar key pattern.
- **No conflicting labels for the same content.** Two samples with the same
  `content_hash` may not declare different `(l1_value, direction)` pairs.

### Augmented-data checklist (before training on it)

1. JSONL is parseable.
2. Each sample passes the schema validator.
3. Each sample passes L1↔L2 / direction-name consistency.
4. Each sample's `actor_name` appears in `content`.
5. Each sample's `evidence_sentence` is in `content` (or marked `[derived]`).
6. No duplicate `augmentation_id`.
7. No conflicting-label content collisions.
8. No dev/test `seed_guid`.
9. `generation_model` recorded.
10. `augmented_training_data_guard.py` returns exit code 0.

---

## Part 3 — File separation requirements

| Pool | Folder | Mutability |
|---|---|---|
| Official TRAIN gold | `dataset/gold_labels/train/train_human_values.json` | **NEVER MODIFY** |
| Official DEV gold | `dataset/gold_labels/dev/dev_human_values.json` | **NEVER MODIFY** |
| Official TEST input | `dataset/test/*` | **NEVER MODIFY** |
| Augmented training samples | `output/research_augmentation_data/<TS>/augmented_samples.jsonl` | New writes per TS |
| Combined train set used for training | `output/research_augmentation_data/<TS>/combined_train_set.json` | Derived; never overwrites official gold |
| Final FEHU predictions | `output/task1_<method>_<provider>_<model>_<version>/pred_task1*.json` | New writes per version |

The training script must read from `combined_train_set.json` (or equivalent
explicit path); it must **never** load `dataset/gold_labels/train/...` and
silently mix in augmented data.

---

## Part 4 — Reserved guards

| Tool | Authoritative for |
|---|---|
| `research/fehu_submission_safety/fehu_prediction_format_guard.py` | Part 1 (final predictions) |
| `research/fehu_submission_safety/augmented_training_data_guard.py` | Part 2 (augmented samples) |
| `research/fehu_augmentation_v1/validate_augmented_data.py` | redundant schema check at planning stage |
| `research/fehu_augmentation_v1/augmentation_schema.json` | JSON Schema source of truth |

Run the guards in CI for every new submission and every new augmented batch.
