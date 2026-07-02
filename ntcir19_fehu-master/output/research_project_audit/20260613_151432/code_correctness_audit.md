# Code Correctness Audit

## 1. Syntax checks (`py_compile`)

```
OK    evaluation.py
OK    src/run_pipeline.py
OK    src/run_pipeline_deepseek_flash.py
OK    src/train_deberta.py
OK    src/hybrid_pipeline.py
OK    src/hybrid_v2.py
OK    src/collect_results.py
OK    src/regenerate_deberta_predictions.py
OK    src/prompts.py
OK    research/fehu_label_diagnosis/label_diagnosis.py
```

All scripts compile without errors.

## 2. Static-inspection findings

### `evaluation.py`

| Severity | Line | Issue |
|---|---|---|
| HIGH | 36, 65-72 | Direction docstring/variable naming inverts the authoritative semantics (`"0"` is called `aligned`, but `direction_mapping.json` says `aligned="1"`). DRR math is symmetric, so the numeric output is still correct — but the names lie. |
| INFO | 262-272 | `DEBUG = True` block forces fake `/tmp/ntcir19_fehu/...` paths if `evaluation.py` is run as `__main__`. This only matters if anyone runs `python evaluation.py` directly; importing functions is safe. |

### `src/run_pipeline.py`

| Severity | Line | Issue |
|---|---|---|
| CRITICAL | 249, 377 | `call_gpt` uses module-level constant `MODEL` instead of `args.model`. `--model gpt-4o` is silently ignored. |
| HIGH | 425 | Cache path `logs/cache_{args.mode}.json` is not model-keyed. Combined with the above bug, every run reuses the cache from whatever model ran first. |
| HIGH | 54, 462-466 | Writes predictions to `output/task1/` — collides with `train_deberta.py`'s output path. |
| HIGH | (whole) | `run_dev_evaluation` does not filter gold when `--limit N` is used → recall is deflated. |
| MEDIUM | 9-16 docstring | References `--provider gemini` flag that does not exist in `argparse`. |
| MEDIUM | 410 | `print(f"Model: {MODEL}")` uses global constant, not `args.model` (reflects the same bug). |
| LOW | 92-152 | `load_few_shot_examples` reads `l1_name_to_id` as a global before `main()` sets it. If anyone imports this function in isolation it will raise `NameError`. |

### `src/run_pipeline_deepseek_flash.py`

| Severity | Line | Issue |
|---|---|---|
| LOW | 42-45 | `MODEL = "deepseek-v4-flash"` is hard-coded — no `--model` flag to swap to DeepSeek V4 Pro etc. Acceptable because the file is named after the model. |
| LOW | 266-273 | `except json.JSONDecodeError` then `except Exception` swallows everything else; final `print("[FAIL]...")` makes recovery visible. Acceptable. |
| LOW | (overall) | Otherwise clean. Cache & limit handling correct. |

### `src/train_deberta.py`

| Severity | Line | Issue |
|---|---|---|
| HIGH | 47 | `OUTPUT_DIR = output/task1` — collides with `run_pipeline.py`. |
| MEDIUM | 264-289 | `eval_dev` writes to a TemporaryDirectory each epoch — fine for correctness, but **per-epoch writes are not retained**. Useful diagnostics lost. |
| LOW | 30-44 | All hyperparameters are module-level constants (no CLI). Reproducibility relies on reading the file. |
| LOW | 312 | Auto-detects CUDA without a `--device` flag. Acceptable. |

### `src/hybrid_pipeline.py` (v1)

| Severity | Line | Issue |
|---|---|---|
| HIGH | 46 | `DEBERTA_OUT = output/task1` — the DeBERTa-only baseline now reads prompt-only predictions if anyone re-runs this. |
| HIGH | 438 | Cache `logs/cache_hybrid_dev.json` is not LLM-model-keyed. |
| MEDIUM | 523 | `datetime.utcnow().isoformat()+"Z"` — `utcnow()` is deprecated in Python 3.12+. Use `datetime.now(timezone.utc)`. |
| LOW | 277-282 | Catches `Exception` then sleeps + retries; final return is `[]`. Acceptable. |

### `src/hybrid_v2.py`

| Severity | Line | Issue |
|---|---|---|
| LOW | 81 | `HYBRID_V2_DIRS["Hybrid v2 OAI"] = output/task1_hybrid_v2_openai_gpt_4o_mini` — folder is currently MISSING; an undated `output/task1_hybrid_v2/` exists instead. Cosmetic mismatch in comparison table. |
| LOW | 640 | `OUT_DIR = f"output/task1_hybrid_v2_{provider}_{slug}"` — produces double-"deepseek" in the path when `--provider deepseek --model deepseek-v4-pro`. Cosmetic only. |
| INFO | 419-432 | `extra_body={"thinking": {"type": "disabled"}}` correctly disables DeepSeek chain-of-thought to keep JSON parseable. |

### `src/collect_results.py`

| Severity | Line | Issue |
|---|---|---|
| MEDIUM | 32-35 | `PROMPT_CACHE_PATHS` falls back to `logs/cache_dev.json` which is not model-keyed; the converted predictions in `output/task1_prompt/` therefore have unrecorded model identity. |
| LOW | 125-160 | Does not filter gold/pred when working with partial-dev predictions. Same risk pattern as `run_pipeline.py`. |
| LOW | 304 | Hard-coded preference order: `hybrid > deberta_only > prompt_only`. Acceptable. |

### `src/regenerate_deberta_predictions.py`

No issues found beyond LOW-severity lack of run_config persistence (the script does not write a run_config.json next to the predictions).

### `src/prompts.py`

| Severity | Line | Issue |
|---|---|---|
| LOW | (whole file) | Dead module. The `build_system_prompt` and `build_user_prompt` functions are duplicated verbatim into `run_pipeline.py` and `run_pipeline_deepseek_flash.py`; `prompts.py` itself is imported by nothing. Either delete it or have the pipelines `from prompts import ...`. |

### `research/fehu_label_diagnosis/label_diagnosis.py`

| Severity | Line | Issue |
|---|---|---|
| LOW | (whole file) | Per-method, per-label, and 108-class metrics independently verified against the official evaluator (Prompt_DS_Flash: µF1 = 0.4964, P = 0.5899, R = 0.4285 — exact match). |
| LOW | 215-225 | Limit-detection in inventory: any folder with `limit != null` and `limit < 177` is excluded from the full-dev table with a `notes` entry. Correct. |

## 3. Hard-coded paths

All scripts compute `BASE_DIR = Path(__file__).parent.parent` (or `os.path.dirname(...)`), so relative paths are derived from the source-file location rather than the user's CWD. **No absolute hard-coded paths were found** outside the in-source DEBUG block of `evaluation.py:266-271`.

## 4. Broad-except swallowing

| Script | Locations | Risk |
|---|---|---|
| `run_pipeline.py` | `call_gpt` `except Exception` (line 283) | LOW — message + retry |
| `run_pipeline_deepseek_flash.py` | `call_llm` `except Exception` (line 271) | LOW |
| `hybrid_pipeline.py` | `call_llm` `except Exception` (line 278) | LOW |
| `hybrid_v2.py` | `call_llm` `except Exception` (line 438) | LOW (captures `err = str(e)` and returns) |

None of these swallow errors silently — they print and retry, with a final failure mode.

## 5. Wrong label / actor / direction mapping

No scripts mix L1 and L2 IDs (each one has explicit `l1_id_to_l2_id` maps). Direction encoding is consistent everywhere except `evaluation.py`'s docstring/variable names (see HIGH issue above).

## 6. Severity summary

| Severity | Count |
|---|---|
| CRITICAL | 1 (`run_pipeline.py` ignores `--model`) |
| HIGH     | 6 (output collisions, model-blind caches, hybrid_pipeline DEBERTA_OUT, limit-recall in run_pipeline, evaluation.py direction names, run_pipeline limit eval) |
| MEDIUM   | 5 |
| LOW      | many (mostly style/dead-code) |
| INFO     | 2 |
