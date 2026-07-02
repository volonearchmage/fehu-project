# FEHU Submission Safety

Two local-only guards that protect FEHU submissions and training data.

## fehu_prediction_format_guard.py

Validates final `pred_task1a.json` / `pred_task1b.json` files against the FEHU
prediction format. Runs no API and never modifies the prediction files.

```bash
# dev
python research/fehu_submission_safety/fehu_prediction_format_guard.py \
    --event_base dataset/dev/dev_event_base.json \
    --pred_task1a output/task1_prompt_deepseek_v4_flash/pred_task1a.json \
    --pred_task1b output/task1_prompt_deepseek_v4_flash/pred_task1b.json \
    --mode dev

# test
python research/fehu_submission_safety/fehu_prediction_format_guard.py \
    --event_base dataset/test/test_article_event_base.json \
    --pred_task1a output/<your_method>/pred_task1a.json \
    --pred_task1b output/<your_method>/pred_task1b.json \
    --mode test
```

Output (timestamped, never overwrites previous):

```
output/research_submission_safety/YYYYMMDD_HHMMSS/
├── format_guard_report.md
├── format_guard_summary.json
└── invalid_entries.csv      # only if any entries failed
```

Checks performed:

1. Both prediction files exist and are valid JSON.
2. Every entry has a `guid` and a list of `article_human_values`.
3. Every guid is present in the event_base.
4. Every `actor` is declared for that guid in the event_base.
5. Task-1a entries contain only `actor` + `l2_value`; `l2_value ∈ {"0","19"}`.
6. Task-1b entries contain only `actor` + `l1_value` + `direction`;
   `l1_value ∈ {"0","53"}`, `direction ∈ {"0","1"}`.
7. No duplicate predictions within a guid (same `(actor, l2_value)` or
   `(actor, l1_value, direction)`).
8. Strict mode flags any extra fields not in the official schema.
9. Task-1a and Task-1b cover the same guid set.
10. Limit / debug runs are flagged (article count < event_base count).

Exit code: 0 = clean, 2 = at least one issue found.

## augmented_training_data_guard.py

Validates a future `augmented_samples.jsonl` against
`research/fehu_augmentation_v1/augmentation_schema.json` plus FEHU-specific
semantic checks. Runs no API.

```bash
python research/fehu_submission_safety/augmented_training_data_guard.py \
    --input path/to/augmented_samples.jsonl
```

If `--input` is omitted, the script prints usage and exits cleanly with code 0.

Checks performed:

1. JSONL parseability.
2. All required schema fields present and well-typed.
3. `augmentation_type ∈ {paraphrase, rare_positive, hard_negative, direction_contrastive}`.
4. `source` field (when present) is NOT `official_gold`.
5. L1↔L2 mapping consistent with `dataset/hv_categories/level_1_to_level_2.json`.
6. `direction ∈ {"0","1"}` and matches `direction_name`.
7. `actor_name` and `content` are non-empty.
8. `evidence_sentence` is present in `content` (or marked `[derived] `).
9. No duplicate `augmentation_id`.
10. No two samples with identical `content_hash` but conflicting `(l1_value, direction)`.
11. `verification_status` present in strict mode.
12. `generation_model` recorded.
13. No `sk-`-style tokens or other API-key shapes appear in any sample field.
14. `seed_guid` does NOT refer to any guid in `dataset/dev/` or `dataset/test/`.

## FORMAT_REQUIREMENTS.md

Authoritative quick reference for both prediction files and augmented training
samples. Read this before writing any new producer of either kind of file.

## Safety assumptions

- Strictly read-only on every file inspected.
- No environment variable read for API keys.
- No HTTP library imported.
- All outputs go to fresh timestamped folders; no existing file is ever overwritten.
