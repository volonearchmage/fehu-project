# FEHU Output Naming Convention

This document is the **single source of truth** for what every `output/*` folder
means. It is the post-audit replacement for the inconsistent state in which
`output/task1/` was used by two different scripts.

## 1. Canonical CURRENT results

Use these as inputs to any new experiment or analysis.

| Folder | Method | Provider | Model | Provenance |
|---|---|---|---|---|
| `output/task1_prompt/` | Prompt-only (legacy) | OpenAI | likely gpt-4o-mini | Partial (no run_config; content matches `output/task1/`) |
| `output/task1_prompt_deepseek_v4_flash/` | Prompt-only | DeepSeek | deepseek-v4-flash | Full (run_config + metrics) |
| `output/task1_deberta/` | DeBERTa-only | — | microsoft/deberta-v3-base + LoRA | Partial → patched regenerator now writes run_config |
| `output/task1_hybrid/` | Hybrid v1 | OpenAI | gpt-4o-mini | Partial (run_config has llm_model) |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` | Hybrid v2 | DeepSeek | deepseek-v4-pro | Full |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/` | Hybrid v2 | DeepSeek | deepseek-v4-flash | Full |

## 2. NON-canonical / legacy — do NOT use as a method source

| Folder | Why |
|---|---|
| `output/task1/` | Legacy ambiguous. Was written by both `run_pipeline.py` (prompt-only) and `train_deberta.py` (DeBERTa). Current contents are byte-identical to `output/task1_prompt/`. After the audit fix neither script writes here by default. |
| `output/task1_hybrid_v2/` | Orphan from before `hybrid_v2.py` adopted provider-aware naming. The canonical OAI v2 path would be `output/task1_hybrid_v2_openai_gpt_4o_mini/` (currently missing). |
| `output/task1/pred_task1*_4omini.json` | Manual archive files with no run_config. Provenance unclear. |
| `output/task1_prompt_deepseek_v4_flash_limit5/` | Limit (debug) run — never compare against full-dev runs. |
| `output/task1_hybrid_v2_limit20/` | Limit (debug) run — never compare against full-dev runs. |

## 3. Naming convention for FUTURE results

```
output/{task}_{method}_{provider}_{model}_{version_or_tag}/
```

Every component is lowercase, with `-` / `.` / `/` / `:` collapsed to `_`.

Examples:

```
output/task1_prompt_openai_gpt_4o_mini/
output/task1_prompt_openai_gpt_4o/
output/task1_prompt_deepseek_v4_flash/
output/task1_deberta_lora_v1/
output/task1_deberta_lora_aug_pilot_v1/
output/task1_hybrid_v2_deepseek_deepseek_v4_pro/
output/task1_hybrid_v2_deepseek_v4_pro_aug_pilot_v1/
```

Research-analysis outputs use timestamped folders that never collide:

```
output/research_label_diagnosis/YYYYMMDD_HHMMSS/
output/research_project_audit/YYYYMMDD_HHMMSS/
output/research_experiment_registry/YYYYMMDD_HHMMSS/
output/research_visualization_dashboard/YYYYMMDD_HHMMSS/
output/research_augmentation_plan/YYYYMMDD_HHMMSS/
```

## 4. Mandatory files for every NEW method output folder

Every prediction folder MUST contain:

| File | Purpose |
|---|---|
| `pred_task1a.json` | Task-1a predictions (always) |
| `pred_task1b.json` | Task-1b predictions (always) |
| `run_config.json` | Provenance — see schema below |
| `metrics.json` | Dev metrics (dev mode only) |

### Minimum `run_config.json` schema

```json
{
  "script":         "src/run_pipeline.py",
  "method":         "prompt_only" | "deberta_lora" | "hybrid_v1" | "hybrid_v2",
  "provider":       "openai" | "deepseek" | null,
  "model":          "gpt-4o-mini",
  "model_slug":     "gpt_4o_mini",
  "version":        null,
  "mode":           "dev" | "test",
  "limit":          null,
  "is_limit_run":   false,
  "output_dir":     "output/...",
  "cache_path":     "logs/...",
  "timestamp":      "2026-06-13T15:14:32+00:00",
  "git_commit":     "4142f10c00b2fb...",
  "command_line":   "python src/run_pipeline.py --mode dev",
  "dataset_paths":  {"train_articles": "...", ...},
  "prompt_template_hash": "abc123...",
  "taxonomy_hash":        "def456...",
  "notes":          "..."
}
```

Optional:
- `lora_config`, `hyperparameters` (DeBERTa)
- `deberta_threshold`, `top_k`, `max_candidates_per_actor` (Hybrid)

## 5. Cache-path convention

```
logs/cache_{mode}_{provider}_{model_slug}.json                 # prompt-only
logs/cache_hybrid_v1_{mode}_{provider}_{model_slug}.json       # hybrid v1
logs/cache_hybrid_v2_{mode}_{provider}_{model_slug}.json       # hybrid v2
```

Each cache **entry** should also store `{guid, provider, model, result, success, error}`, and code should reuse a cached entry only if `provider` and `model` both match. This double-key guard means even a folder-level mistake won't cross-contaminate runs.

## 6. Forbidden patterns going forward

- ❌ Writing to `output/task1/` (ambiguous legacy path)
- ❌ Cache files that do not include the model in the filename
- ❌ Method folders that lack `run_config.json`
- ❌ Mixing limit runs and full-dev runs in the same comparison without filtering both to the same guid set
- ❌ Hardcoded model names inside an `args.model` flow (any use of a `MODEL` global where `args.model` exists)

## 7. Quick checklist before merging a new pipeline

1. Does the script accept `--model`? Does it actually use it in the API call?
2. Does the script accept `--limit`? Does it filter the dev gold to the same guids before scoring?
3. Does the script write a `run_config.json` next to its predictions?
4. Does the script write a `metrics.json` in dev mode?
5. Is the cache file named with provider + model?
6. Is the default output folder one of the canonical names above (and NOT `output/task1/`)?
7. If `--output_dir` and the target already contains predictions, does the script refuse to overwrite without `--force_overwrite` (or write to a timestamped sibling)?
