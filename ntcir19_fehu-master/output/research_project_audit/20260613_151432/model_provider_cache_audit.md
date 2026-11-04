# Model / Provider / Cache / Secrets Audit

## 1. API key usage

| Script | Reads env var | Reads `.env` | Hard-coded key? |
|---|---|---|---|
| `src/run_pipeline.py` | `OPENAI_API_KEY` | NO | no |
| `src/run_pipeline_deepseek_flash.py` | `DEEPSEEK_API_KEY` | yes (only `DEEPSEEK_API_KEY=` lines) | no |
| `src/hybrid_pipeline.py` | `OPENAI_API_KEY` only | yes (only `OPENAI_API_KEY=` lines) | no |
| `src/hybrid_v2.py` | provider-aware (`DEEPSEEK_API_KEY` if `--provider deepseek`, else `OPENAI_API_KEY`) | yes (provider-aware) | no |

**Finding:** Provider/key separation is correct. No script reads the wrong key.

## 2. DeepSeek base_url

| Script | base_url |
|---|---|
| `src/run_pipeline_deepseek_flash.py` line 459 | `https://api.deepseek.com` |
| `src/hybrid_v2.py` line 703 (when `--provider deepseek`) | `https://api.deepseek.com` |

**Finding:** Correct in both scripts.

## 3. Secret scanning

Project-wide grep was performed for `sk-[a-zA-Z0-9]{16,}` and `api_key\s*=\s*"[a-zA-Z0-9_-]{8,}` patterns across all `.py` files (excluding `__pycache__`).

- **No hard-coded API keys were found in any source file.**
- **No `.env` file is present in the project root** (so no key at rest).
- Cache JSON files in `logs/` were not scanned by exhaustive byte-match, but they only store LLM **response** payloads keyed by guid — the OpenAI/DeepSeek libraries do not echo the key.

## 4. Cache file separation

| Cache | Provider-keyed | Model-keyed | Used by |
|---|---|---|---|
| `logs/cache_dev.json` | NO | **NO** | `src/run_pipeline.py` |
| `logs/cache_dev_deepseek_v4_flash.json` | yes (in name) | yes (in name) | `src/run_pipeline_deepseek_flash.py` |
| `logs/cache_hybrid_dev.json` | NO | **NO** | `src/hybrid_pipeline.py` |
| `logs/cache_hybrid_v2_dev.json` | NO | **NO** | `src/hybrid_v2.py` (LEGACY — current code uses provider+model in path) |
| `logs/cache_hybrid_v2_dev_deepseek_deepseek_v4_pro.json` | yes (in name + entry) | yes | `src/hybrid_v2.py` |
| `logs/cache_hybrid_v2_dev_deepseek_deepseek_v4_flash.json` | yes (in name + entry) | yes | `src/hybrid_v2.py` |
| `logs/cache_test_openai.json` | yes (openai) | unknown | unclear (referenced in `collect_results.py` candidates list) |

### Cache-key hazards

- **`cache_dev.json`** (HIGH) — `run_pipeline.py --model gpt-4o` and `--model gpt-4o-mini` share the same cache file. Whichever ran first determines the predictions; a later run with a different `--model` is silently ignored because (a) cache hit, and (b) `--model` is never used by the API call regardless (see code_correctness_audit.md).
- **`cache_hybrid_dev.json`** (MEDIUM) — same hazard at the v1 hybrid level.
- **`cache_hybrid_v2_dev.json`** (MEDIUM) — orphaned. Current `hybrid_v2.py` writes provider/model-keyed paths, so this old file is no longer touched. Should be archived.

### Caches that are safe

- `run_pipeline_deepseek_flash.py` stores each entry as `{guid, provider, model, result, success, error}` and only reuses cache when `provider` and `model` both match. **Even though the file path mentions deepseek_v4_flash, the per-entry guard prevents cross-model contamination.**
- `hybrid_v2.py` uses cache key `f"{guid}||{candidate_hash}||{provider}||{model}"`, and each cache entry independently records `provider` and `model`. Also defends against changing DeBERTa threshold/top_k via `candidate_hash`. **Best-in-class cache hygiene.**

## 5. Per-script model name handling

| Script | `--model` arg flows to API call? | Default |
|---|---|---|
| `src/run_pipeline.py` | **NO** (BUG — `call_gpt` uses module-level `MODEL`) | `gpt-4o-mini` |
| `src/run_pipeline_deepseek_flash.py` | n/a (no `--model` arg; uses constant `MODEL = "deepseek-v4-flash"`) | n/a |
| `src/hybrid_pipeline.py` | yes (passes `args.model` to `call_llm`) | `gpt-4o-mini` |
| `src/hybrid_v2.py` | yes (passes `args.model` everywhere; defaults switch with provider) | `gpt-4o-mini` (openai) / `deepseek-v4-pro` (deepseek) |

## 6. Severity summary

| Severity | Item |
|---|---|
| HIGH | `cache_dev.json` is shared across all OAI models in `run_pipeline.py` |
| HIGH | `run_pipeline.py --model` argument is silently ignored |
| MEDIUM | `cache_hybrid_dev.json` is not LLM-model-keyed |
| MEDIUM | Orphan `cache_hybrid_v2_dev.json` should be archived |
| LOW | No secret leakage detected |
