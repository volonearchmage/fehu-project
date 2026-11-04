# Expected Output Schema (Future Generated Sample)

> This documents the **future** generated-response schema. **No sample has been generated.**

Every future generated sample (one per approved request) must conform to this schema before
entering any training pool. The augmented-training-data guard at
`research/fehu_submission_safety/augmented_training_data_guard.py` enforces these rules.

## Required JSON fields

| Field | Type | Description |
|---|---|---|
| `title` | string | News-style headline, ≤ 200 chars |
| `content` | string | News-style body, 50–1500 chars |
| `actor_name` | string | Canonical actor identifier — must equal the request's `canonical_actor_name` (or, for invented-actor types, the name the generator picked) |
| `actor_mention` | string | The actual surface form used inside `content`. **MUST appear verbatim in `content`.** May be the canonical name, the primary mention, an alias, or any natural surface form |
| `evidence_sentence` | string | **MUST appear verbatim in `content`**, MUST describe the target actor's action/stance/decision/behavior, MUST support the target value+direction (for hard_negative: must support the ALTERNATIVE value) |
| `explanation` | string | One-sentence justification of (actor, value, direction). For hard_negative: WHY the target label does not apply |
| `l1_value_id` | string | One of `"0".."53"` |
| `l1_value_name` | string | Must match `l1_value_id` per `dataset/hv_categories/human_value_level1_values.json` |
| `l2_value_id` | string | One of `"0".."19"` |
| `l2_value_name` | string | Must match `l2_value_id` per `dataset/hv_categories/human_value_level2_values.json` |
| `direction` | `"0"` / `"1"` / `null` | `"1"` = aligned, `"0"` = contradictory; `null` only for hard_negative |
| `direction_name` | `"aligned"` / `"contradictory"` / `null` | Must match `direction` |
| `is_positive` | boolean | `True` for paraphrase / rare_positive / direction_contrastive; `False` for hard_negative |
| `_type_specific_rule` | string | Echo of the type-specific rule the generator agreed to |

## Future validation rules

The augmented-data guard will enforce, at minimum:

1. **Schema validity** — every required field present, correct type, correct enum / pattern.
2. **`evidence_sentence` verbatim in `content`** (or, if marked `[derived] `, semantically derived).
3. **`actor_mention` verbatim in `content`**.
4. **L1↔L2 mapping** matches `dataset/hv_categories/level_1_to_level_2.json`.
5. **Direction / direction_name consistency** per `dataset/hv_categories/direction_mapping.json`
   (`"1"` = aligned, `"0"` = contradictory). The `evaluation.py` docstring inverts this; the
   guard does NOT use `evaluation.py` for direction semantics.
6. **L1 / direction / is_positive must match the approved request**. A request asking for
   `(l1=12, direction="1", is_positive=true)` and a response carrying
   `(l1=12, direction="0", …)` is automatically rejected.
7. **No more salient non-target value** — generated content must not make any other human
   value more salient than the target value for the target actor.
8. **No defamation or unsupported factual accusations** about real, identifiable individuals.
9. **No dev/test article content** used as seed (`seed_guid` must not be in dev or test
   event_base files).
10. **No secret-shaped strings** (no API-key tokens) in any field.

## Path forward

Once samples exist, run:

```bash
python research/fehu_submission_safety/augmented_training_data_guard.py \
    --input output/research_augmentation_data/<future_TS>/augmented_samples.jsonl \
    --strict
```

A clean exit-0 is required before any training-data integration. **No such file exists yet.**
