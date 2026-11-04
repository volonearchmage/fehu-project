# FEHU Project Inventory

**Generated:** 2026-06-13 15:14:32
**Auditor:** Claude Code (read-only inspection)

## Top-level layout

```
ntcir19_fehu-master/
├── evaluation.py                      # official evaluator (do not modify)
├── README.md
├── CLAUDE.md
├── HYBRID_ROADMAP.md                  # ad-hoc roadmap doc
├── .gitignore                         # has duplicate entries (LOW)
├── checkpoints/best_model/            # trained DeBERTa LoRA checkpoint
├── dataset/                           # FEHU official data + taxonomy
│   ├── train/                         # train_event_base.json
│   ├── dev/                           # dev_event_base.json
│   ├── test/                          # article + subevent test base files
│   ├── gold_labels/                   # train + dev gold
│   ├── hv_categories/                 # L1/L2/dir mappings
│   └── evaluation_test_data_examples/ # format reference
├── src/                               # all training & inference scripts
├── research/                          # diagnostic + audit modules
├── output/                            # all prediction & analysis output
└── logs/                              # caches
```

## Core official files

| Path | Exists | Type | Purpose | Risk | Notes |
|---|---|---|---|---|---|
| `evaluation.py` | yes | file | Official scorer | HIGH | Direction labels inverted in docstring/vars; DRR math still correct |
| `dataset/train/train_event_base.json` | yes | file | Train articles (1228) | LOW | 16905 article_human_value items |
| `dataset/dev/dev_event_base.json` | yes | file | Dev articles (177) | LOW | 2390 article_human_value items |
| `dataset/test/test_article_event_base.json` | yes | file | Test for Task-1 (175) | LOW | no `subevents` field |
| `dataset/test/test_subevent_event_base.json` | yes | file | Test for Task-2 (175) | LOW | |
| `dataset/gold_labels/train/train_human_values.json` | yes | file | Train gold | LOW | guids match train articles |
| `dataset/gold_labels/dev/dev_human_values.json` | yes | file | Dev gold | LOW | guids match dev articles |
| `dataset/hv_categories/human_value_level1_values.json` | yes | file | 54 L1 names→ids | LOW | |
| `dataset/hv_categories/human_value_level2_values.json` | yes | file | 20 L2 names→ids | LOW | |
| `dataset/hv_categories/level_1_to_level_2.json` | yes | file | L1→L2 mapping | LOW | |
| `dataset/hv_categories/direction_mapping.json` | yes | file | `{aligned:"1", contradictory:"0"}` | LOW | Authoritative direction semantics |

## Core scripts

| Path | Exists | Type | Purpose | Risk | Notes |
|---|---|---|---|---|---|
| `src/run_pipeline.py` | yes | script | Prompt-only OAI pipeline | HIGH | `--model` arg ignored (bug); cache not keyed by model; writes to `output/task1/` |
| `src/run_pipeline_deepseek_flash.py` | yes | script | Prompt-only DeepSeek pipeline | MEDIUM | Cache & paths correct; comparison filters by limit |
| `src/train_deberta.py` | yes | script | DeBERTa-v3 LoRA training + final inference | HIGH | Writes pred to `output/task1/` (same dir as run_pipeline.py — collision) |
| `src/hybrid_pipeline.py` | yes | script | Hybrid v1 (DeBERTa cand + LLM verify) | HIGH | `DEBERTA_OUT = output/task1` (wrong now); cache not model-keyed |
| `src/hybrid_v2.py` | yes | script | Hybrid v2 (value-only cands + LLM direction) | MEDIUM | Well-versioned; cache & output dir include provider+model |
| `src/collect_results.py` | yes | script | Aggregate results + cache→submission convert | MEDIUM | Reads `cache_dev_openai.json` or `cache_dev.json` → writes `output/task1_prompt/` |
| `src/regenerate_deberta_predictions.py` | yes | script | Regenerate DeBERTa preds in `output/task1_deberta/` | LOW | Clean; reuses train_deberta functions |
| `src/prompts.py` | yes | file | Prompt module | LOW | Dead code — duplicated by run_pipeline.py; never imported by other scripts |
| `research/fehu_label_diagnosis/label_diagnosis.py` | yes | script | Per-label diagnosis | LOW | Computations verified against official evaluator |
| `research/fehu_label_diagnosis/README.md` | yes | doc | Usage doc | LOW | |
| `research/fehu_project_audit/README.md` | yes | doc | Audit landing page | LOW | This audit's home |

## Output folders

| Path | Has pred_1a/1b | run_config | Likely method | Likely full-dev | Risk | Notes |
|---|---|---|---|---|---|---|
| `output/task1/` | yes | no | Prompt-only OAI (currently) | yes | HIGH | Identical to `task1_prompt/` (md5 match). DeBERTa results overwritten here by later prompt-only run. Also holds `pred_task1a_4omini.json` (manual archive). |
| `output/task1_prompt/` | yes | no | Prompt-only OAI gpt-4o-mini | yes | MEDIUM | Identical content to `output/task1/`; no run_config so model identity not recorded |
| `output/task1_prompt_deepseek_v4_flash/` | yes | yes | DeepSeek V4 Flash prompt-only | yes | LOW | Full run config + metrics; trustworthy |
| `output/task1_prompt_deepseek_v4_flash_limit5/` | yes | yes | DeepSeek V4 Flash, limit=5 | NO | INFO | Clearly marked as limit run |
| `output/task1_deberta/` | yes | no | DeBERTa-only (regenerated) | yes | MEDIUM | Predictions present; no run_config so checkpoint/threshold not recorded |
| `output/task1_hybrid/` | yes | yes | Hybrid v1 (gpt-4o-mini) | yes | LOW | run_config has llm_model; no provider field |
| `output/task1_hybrid_v2/` | yes | yes | Old Hybrid v2 OAI | yes | HIGH | ORPHANED — predates provider-aware naming; canonical OAI v2 dir `task1_hybrid_v2_openai_gpt_4o_mini/` is MISSING |
| `output/task1_hybrid_v2_limit20/` | yes | yes | Hybrid v2 OAI, limit=20 | NO | INFO | Clearly marked as limit run |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` | yes | yes | Hybrid v2 DeepSeek V4 Pro | yes | LOW | Full metrics; trustworthy |
| `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/` | yes | yes | Hybrid v2 DeepSeek V4 Flash | yes | LOW | Full metrics; trustworthy |
| `output/research_label_diagnosis/20260613_145549/` | n/a | yes | First diagnosis run (no figures) | n/a | LOW | matplotlib missing on first run |
| `output/research_label_diagnosis/20260613_145847/` | n/a | yes | Second diagnosis run (with figures) | n/a | LOW | Complete; numbers verified |
| `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/` | n/a | yes | Earlier baseline diagnosis | n/a | INFO | Untouched by recent diagnosis runs |
| `output/per_category_analysis.json` | yes | n/a | From collect_results.py | n/a | LOW | |
| `output/results_comparison.json` | yes | n/a | From collect_results.py | n/a | LOW | |
| `output/results_comparison_table.txt` | yes | n/a | From collect_results.py | n/a | LOW | |

## Logs / caches

| Path | Purpose | Risk | Notes |
|---|---|---|---|
| `logs/cache_dev.json` | run_pipeline.py dev cache | HIGH | Not keyed by model — may mix gpt-4o-mini and gpt-4o results |
| `logs/cache_dev_deepseek_v4_flash.json` | DeepSeek Flash prompt-only cache | LOW | Provider+model-keyed |
| `logs/cache_hybrid_dev.json` | Hybrid v1 cache | MEDIUM | Not keyed by LLM model |
| `logs/cache_hybrid_v2_dev.json` | Old Hybrid v2 cache | MEDIUM | Orphaned — pre-provider-keyed |
| `logs/cache_hybrid_v2_dev_deepseek_deepseek_v4_pro.json` | Hybrid v2 DS Pro cache | LOW | Provider+model-keyed |
| `logs/cache_hybrid_v2_dev_deepseek_deepseek_v4_flash.json` | Hybrid v2 DS Flash cache | LOW | Provider+model-keyed |
| `logs/cache_test_openai.json` | Test-set OAI cache | INFO | Test run was attempted; no test predictions in output/ |

## Project metadata

| Path | Exists | Notes |
|---|---|---|
| `README.md` | yes | Project README |
| `CLAUDE.md` | yes | Coding guidance |
| `HYBRID_ROADMAP.md` | yes | Roadmap doc (untracked file) |
| `.gitignore` | yes | Has duplicate entries (LOW) |
| `pyproject.toml` | NO | absent |
| `requirements.txt` | NO | absent — no pinned deps |
| `.env` | NO | absent (good — no key file at rest) |

## Untracked files (per git status)

```
HYBRID_ROADMAP.md
src/collect_results.py
src/hybrid_v2.py
src/regenerate_deberta_predictions.py
src/run_pipeline_deepseek_flash.py
```

These are committed-in-fact (work files present) but missing from git index.
