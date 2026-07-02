# Reproducibility Audit

## Overall verdict

| Method | Trustworthy today | Reproducible without code changes |
|---|---|---|
| Prompt OAI gpt-4o-mini | Yes (likely-from-cache) | Partial — output folder collides with DeBERTa training |
| Prompt OAI gpt-4o | UNKNOWN | NO — `--model` arg is silently ignored in `run_pipeline.py` |
| Prompt DS Flash | Yes | Yes |
| DeBERTa-only | Yes | Yes (regenerate_deberta_predictions.py reads checkpoint) |
| Hybrid v1 gpt-4o-mini | Yes | Partial — cache not model-keyed; DeBERTa baseline path stale |
| Hybrid v2 OAI gpt-4o-mini | DEGRADED — orphan folder, canonical path missing | NO — would need re-run |
| Hybrid v2 DS Pro | Yes | Yes |
| Hybrid v2 DS Flash | Yes | Yes |
| Label diagnosis | Yes | Yes (no API; timestamped output) |
| Audit | Yes | Yes (this file) |

See `reproducibility_matrix.csv` for the per-method matrix.

## Per-method narrative

### Prompt OAI

- **Script:** `src/run_pipeline.py`
- **Command:** `python src/run_pipeline.py --mode dev`
- **Key required:** `OPENAI_API_KEY` (env or `--api_key`)
- **Output:** writes to `output/task1/` (NOT `output/task1_prompt/`); `output/task1_prompt/` exists only because `src/collect_results.py` later converts `logs/cache_dev.json` into the canonical folder.
- **Cache:** `logs/cache_dev.json` — keyed only by `mode`. Catastrophic if anyone passes a different `--model` (which is silently ignored anyway).
- **Reproducible?** Partial. Re-running with `gpt-4o-mini` should produce identical predictions (cache hit). Re-running with `gpt-4o` requires editing `MODEL = ...` at the top of the file because the `--model` flag is not wired into `call_gpt`.

### Prompt DeepSeek V4 Flash

- **Script:** `src/run_pipeline_deepseek_flash.py`
- **Command:** `python src/run_pipeline_deepseek_flash.py --mode dev`
- **Key required:** `DEEPSEEK_API_KEY`
- **Output:** `output/task1_prompt_deepseek_v4_flash/` (canonical)
- **Cache:** `logs/cache_dev_deepseek_v4_flash.json`, with per-entry `provider` + `model` + `success` guard. Safe.
- **Reproducible?** Yes. `run_config.json` + `metrics.json` + `comparison_table.txt` all present and consistent.

### DeBERTa-only

- **Training:** `python src/train_deberta.py` (writes checkpoint to `checkpoints/best_model/`; writes preds to `output/task1/` which conflicts with run_pipeline.py).
- **Inference re-run:** `python src/regenerate_deberta_predictions.py` writes canonical `output/task1_deberta/`.
- **Reproducible?** Yes from the checkpoint. **Training itself** is reproducible only by reading hardcoded hyperparameters (`LR=2e-4`, `MAX_EPOCHS=15`, etc.) inside the file.

### Hybrid v1

- **Script:** `src/hybrid_pipeline.py`
- **Reads DeBERTa preds from:** `DEBERTA_OUT = output/task1` (LINE 46) — **but `output/task1/` no longer holds DeBERTa preds**. If anyone re-runs Hybrid v1's evaluation step, the "DeBERTa-only baseline" row is actually the prompt-only preds.
- **Cache:** `logs/cache_hybrid_dev.json`, not LLM-model-keyed.
- **Reproducible?** Partial — the hybrid output itself is reproducible from the cache; the comparison table will be silently wrong.

### Hybrid v2

- **Script:** `src/hybrid_v2.py` (single file handles OpenAI + DeepSeek with `--provider`).
- **Hybrid v2 OAI:** canonical path is `output/task1_hybrid_v2_openai_gpt_4o_mini/` (per `HYBRID_V2_DIRS`). That folder **does not exist on disk**; `output/task1_hybrid_v2/` exists instead but is not the canonical name. **The orphan folder's provenance is undocumented.** Re-running `--provider openai` would *create* the canonical folder but would not delete the orphan.
- **Hybrid v2 DS Pro/Flash:** clean; full provenance (`run_config.json`, `metrics.json`, `comparison_metrics.json`, `comparison_table.txt`, `filtering_stats.json`, `candidates_dev.json`).

### Label diagnosis

- **Script:** `research/fehu_label_diagnosis/label_diagnosis.py`
- **Command:** `python research/fehu_label_diagnosis/label_diagnosis.py`
- **Output:** `output/research_label_diagnosis/{YYYYMMDD_HHMMSS}/` (timestamped, never overwritten).
- **No API key required.**
- **Reproducible?** Yes. Two recent runs (`20260613_145549/` and `20260613_145847/`) both completed successfully; numbers independently verified.

## Reproducibility gaps to fix (suggested, not done)

1. Add `run_config.json` writer to:
   - `src/run_pipeline.py` → `output/task1_prompt/` (with model, cache_path, timestamp, limit)
   - `src/train_deberta.py` → next to its output (with all hyperparameters)
   - `src/regenerate_deberta_predictions.py` → record THRESHOLD and checkpoint dir

2. Add `requirements.txt` or `pyproject.toml` with at least:
   - `openai`, `transformers`, `peft`, `torch`, `tqdm`, `matplotlib` (for diagnosis)

3. Pin a HuggingFace model revision in `train_deberta.py` (`MODEL_NAME = "microsoft/deberta-v3-base"` currently floats to upstream HEAD).

4. Add a `versioned_paths.py` module so all scripts agree on canonical folder names.

(These are suggestions only — no changes were applied during this audit.)
