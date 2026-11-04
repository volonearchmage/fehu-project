# Evaluation Logic Audit

For each script, this report records:
1. Whether it imports official functions from `evaluation.py` (vs. duplicating).
2. Whether it calls `evaluation.py:main()` (which forces fake `/tmp/` paths via `DEBUG=True`).
3. How Task-1a / Task-1b are computed.
4. Whether it filters gold when `--limit` is used.
5. Whether it uses the correct universe.

## Per-script audit

### `src/run_pipeline.py`

- **Imports:** `parse_task1a`, `parse_task1b`, `evaluate`, `l2_universe`, `l1_dir_universe`, `direction_reverse_rate_gold_excl` (correct).
- **Calls `main()`?** No.
- **Universe usage:** `l2_universe()` for Task-1a, `l1_dir_universe()` for Task-1b — correct.
- **Limit handling:** When `--limit N` is used, only N predictions are written, but evaluation compares against the FULL dev gold (`gold_1a = parse_task1a(DEV_LABELS)`). This silently **mixes limit predictions with full-dev gold**, deflating recall.
- **Severity:** HIGH (limit-mode evaluation produces wrong numbers).

### `src/run_pipeline_deepseek_flash.py`

- **Imports:** Same official functions — correct.
- **Calls `main()`?** No.
- **Universe usage:** Correct.
- **Limit handling:** Uses `processed_guids` and an internal `_filter` helper to restrict gold to the same N articles when `--limit` is set. **Correct behavior**.
- **Comparison table:** Also filters comparison results (`Prompt OAI`, `DeBERTa-only`, `Hybrid v1`, `Hybrid v2 DS Pro/Flash`) to the same `filter_guids`. Correct.
- **Severity:** LOW.

### `src/train_deberta.py`

- **Imports:** Correct.
- **Calls `main()`?** No (imports inside `eval_dev`).
- **Universe usage:** Correct.
- **L1×direction encoding:** Trains a 108-class binary head with `label_index = int(l1_value)*2 + int(direction)`. Inverse: `(l1, dir) = (idx // 2, idx % 2)`. Mathematically consistent, and matches direction_mapping ("0"=contradictory, "1"=aligned).
- **Limit handling:** N/A (training).
- **Severity:** LOW for evaluation logic; HIGH for output path (see versioning audit).

### `src/hybrid_pipeline.py` (Hybrid v1)

- **Imports:** Correct.
- **Calls `main()`?** No.
- **Universe usage:** Correct.
- **Limit handling:** Hybrid v1's own evaluation is filtered by `processed_guids` (correct). But the **DeBERTa comparison** uses `processed_guids if args.limit else None` — fine.
- **DeBERTa comparison source:** `DEBERTA_OUT = output/task1` (line 46). After the prompt-only run overwrote `output/task1/`, this comparison would silently evaluate the **PROMPT-ONLY predictions as if they were DeBERTa**.
- **Severity:** HIGH.

### `src/hybrid_v2.py`

- **Imports:** Correct.
- **Calls `main()`?** No.
- **Universe usage:** Correct.
- **Limit handling:** Uses `processed_guids if args.limit else None` everywhere (own metrics + comparisons). Correct.
- **Comparison sources:** `COMPARE_DIRS["DeBERTa-only"] = output/task1_deberta` ✓, `COMPARE_DIRS["Prompt-only"] = output/task1_prompt` ✓. These now exist and are correct.
- **Severity:** LOW.

### `src/collect_results.py`

- **Imports:** Correct.
- **Calls `main()`?** No.
- **Universe usage:** Correct.
- **Limit handling:** No filtering — assumes pred files cover the full dev split. If you ever feed it limit-run prediction files, recall will be deflated (matches FEHU per-article guid set, but full gold).
- **Cache discovery:** Tries `logs/cache_dev_openai.json` first, then `logs/cache_dev.json`. Neither file is keyed by model — so this script *cannot distinguish* a gpt-4o cache from a gpt-4o-mini cache.
- **Severity:** MEDIUM (only matters when caches collide across model changes).

### `src/regenerate_deberta_predictions.py`

- **Imports:** Correct.
- **Calls `main()`?** No.
- **Universe usage:** Correct.
- **Limit handling:** N/A (runs full dev).
- **Severity:** LOW.

### `research/fehu_label_diagnosis/label_diagnosis.py`

- **Imports:** Correct (uses `parse_task1a`, `parse_task1b`, `evaluate`, `l2_universe`, `l1_dir_universe`, `direction_reverse_rate_gold_excl`, `safe_div`).
- **Calls `main()`?** No.
- **Universe usage:** Correct.
- **Limit handling:** Has explicit limit-detection in `build_method_inventory` — folders with `limit != null` and `limit < 177` are excluded from full-dev analysis with a notes line in `method_inventory.csv`. Correct.
- **Per-label aggregation:** Direction-aware micro-aggregation reproduces the official Task-1b micro exactly (verified for `Prompt_DS_Flash`: per-L1 µF1 = 0.4964 = official µF1). The aggregation is mathematically valid (sum-of-disjoint-sets across labels).
- **Direction semantics:** Uses authoritative `{"1":"aligned", "0":"contradictory"}` — consistent with `direction_mapping.json`.
- **Severity:** LOW.

## Cross-cutting issues

### Issue E1 (HIGH): `run_pipeline.py` does not filter gold when `--limit` is used

```python
# in run_pipeline.py / run_dev_evaluation
gold_1a = parse_task1a(DEV_LABELS)      # FULL dev (177 articles)
pred_1a = parse_task1a(pred_1a_path)    # only N articles when --limit N
results_1a = evaluate(gold_1a, pred_1a, l2_universe())
```

Because `evaluate()` takes `instances = set(gold) | set(pred)`, every missing prediction becomes a False Negative — recall is deflated and the comparison to other full-dev runs is misleading. **Same risk in `collect_results.py`.**

`run_pipeline_deepseek_flash.py`, `hybrid_pipeline.py`, `hybrid_v2.py`, and `label_diagnosis.py` all handle this correctly.

### Issue E2 (HIGH): `hybrid_pipeline.py` compares to a moved DeBERTa output

```python
DEBERTA_OUT = BASE_DIR / "output/task1"   # line 46
```

`output/task1/` no longer contains DeBERTa predictions (the prompt-only run overwrote them — see versioning audit). If `hybrid_pipeline.py` re-runs, its DeBERTa-only baseline column will report prompt-only-as-DeBERTa numbers.

### Issue E3 (HIGH): `evaluation.py` direction names

Documented in `format_check_report.md`. Mathematically harmless for DRR; semantically misleading for any reader.

### Issue E4 (LOW): Diagnosis micro-aggregation correctly reproduces official metrics

Sanity check (verified):
- Official Task-1b micro for Prompt_DS_Flash: µF1 = 0.4964, P = 0.5899, R = 0.4285.
- Diagnosis per-L1 direction-aware micro-aggregation: µF1 = 0.4964, P = 0.5899, R = 0.4285.
- Match exact to 4 decimal places.
