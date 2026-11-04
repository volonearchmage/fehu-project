# FEHU Project — Final Audit Report

**Audited:** 2026-06-13 15:14:32
**Auditor:** Claude Code (read-only)
**Constraints honored:** no files modified, no APIs called, no training run, no destructive operations.

---

## 1. Executive Summary

The FEHU project is in **mostly-good** research shape. The data, taxonomy, and prediction-format conventions are clean and internally consistent. The newer scripts (`run_pipeline_deepseek_flash.py`, `hybrid_v2.py`, `regenerate_deberta_predictions.py`, `label_diagnosis.py`) are well-engineered, fully versioned, and reproducible.

However, the **older scripts** (`run_pipeline.py`, `train_deberta.py`, `hybrid_pipeline.py`) share a pre-versioning era of code in which:

- **`output/task1/` is used as a default output folder by two different scripts**, leading to silent overwrites.
- The `cache_dev.json` cache is **not keyed by model**, and `run_pipeline.py`'s `--model` argument is **silently ignored** by the API call.
- `hybrid_pipeline.py` reads the DeBERTa baseline from `output/task1/`, which today contains the **prompt-only** predictions — so its comparison table is wrong if re-run.

Most prediction files on disk are still trustworthy *as data* (every file passes schema validation, guid coverage is complete, no duplicate or invalid items). The risk is in **provenance** — we know what's in each file, but not always how it was produced.

The recently created `research/fehu_label_diagnosis/label_diagnosis.py` is correct: spot-checks against the official evaluator match to four decimal places, and the per-L1 micro-aggregation exactly reproduces the official Task-1b micro-F1.

No API keys were found in source or output files. No `.env` is at rest in the repo. Test predictions have not been generated for any method (only dev).

**Verdict:** Existing dev-set results are **safe to use for research analysis**, but the project cannot be cleanly reproduced from source today without fixing at least the CRITICAL and HIGH items below.

---

## 2. CRITICAL issues

### C1. `run_pipeline.py --model` is silently ignored

- **File:** `src/run_pipeline.py`
- **Lines:** 249 (`call_gpt` uses `MODEL`) vs. 377 (`model_name = args.model` — never used)
- **What happens:** Passing `--model gpt-4o` runs `gpt-4o-mini`. The user sees `Model: {MODEL}` in the printout (also wrong: line 410 prints global `MODEL`).
- **Why it matters:** Any past run that the user *thought* was gpt-4o was actually gpt-4o-mini. The `output/task1/pred_task1*_4omini.json` manual-archive files suggest the user noticed the issue and renamed at least one set.
- **Recommended fix:** Pass `model_name` into `call_gpt`, or replace `MODEL` with `args.model`. **Human review required** because past output folders need to be re-labelled.
- **Auto-fix safe?** NO — fixing the code is safe, but the historical question of *which model produced which file* needs human input.

### C2. `output/task1/` is overwritten by whichever script ran last

- **Files:** `src/run_pipeline.py:54` and `src/train_deberta.py:47` both default to `output/task1/`.
- **Forensic evidence:** `output/task1/pred_task1a.json` is byte-identical to `output/task1_prompt/pred_task1a.json` (md5 `f7d62ca305f4`). DeBERTa's earlier output at this path has been silently overwritten by the prompt-only run (and only later recovered via `regenerate_deberta_predictions.py` to `output/task1_deberta/`).
- **Recommended fix:** Change `run_pipeline.py` to write to `output/task1_prompt/` and `train_deberta.py` to write to `output/task1_deberta/`. **Human review required** for what to do with the existing `output/task1/` folder.
- **Auto-fix safe?** NO — moving/deleting files needs explicit permission.

---

## 3. HIGH issues

### H1. `cache_dev.json` is not keyed by model

- **File:** `src/run_pipeline.py:425`
- **Effect:** Combined with C1, every OpenAI run shares one cache. A run-after-fix would still hit the cache from the buggy era.
- **Auto-fix safe?** Adding model to cache name is safe; deleting old cache is not.

### H2. `evaluation.py` direction docstring/variable names are inverted

- **File:** `evaluation.py:36, 65-72`
- **Authority:** `dataset/hv_categories/direction_mapping.json` says `aligned="1"`, `contradictory="0"`.
- **Effect:** Docstring and variable names (`G_aligned` for `d=="0"`) say the opposite. **DRR mathematically still correct** (symmetric counting), but the names mislead any reader.
- **User constraint:** `evaluation.py` may not be modified. **Hazard noted; no action.**

### H3. `hybrid_pipeline.py` reads DeBERTa baseline from `output/task1/`

- **File:** `src/hybrid_pipeline.py:46`
- **Effect:** Re-running `hybrid_pipeline.py --mode dev` would print a "DeBERTa-only" comparison row using the prompt-only predictions in `output/task1/` — wrong baseline.
- **Auto-fix safe?** Changing path string to `output/task1_deberta` is safe.

### H4. `run_pipeline.py` does not filter gold when `--limit N` is used

- **File:** `src/run_pipeline.py:495-526`
- **Effect:** `limit=5` predictions get compared against full 177-article gold → recall deflated.
- **Auto-fix safe?** Yes — same pattern as `run_pipeline_deepseek_flash.py`.

### H5. `output/task1_hybrid_v2/` is orphaned

- The canonical Hybrid v2 OAI folder per `hybrid_v2.py:81` is `output/task1_hybrid_v2_openai_gpt_4o_mini/`, which does not exist.
- `output/task1_hybrid_v2/` predates that naming scheme; its `run_config.json` lacks `provider`.
- **Auto-fix safe?** NO — renaming would alter history. Recommend documenting the orphan.

### H6. `output/task1/` is a duplicate of `output/task1_prompt/`

- Same bytes; same content. Either of them is enough; keeping both invites confusion.
- **Auto-fix safe?** NO — deletion needs human approval.

### H7. `output/task1/pred_task1a_4omini.json`, `pred_task1b_4omini.json` are manual archives

- No script writes these filenames. They are a different content from the unsuffixed files (probably gpt-4o-mini before a re-run replaced the unsuffixed files with something else, but provenance is unclear).
- **Auto-fix safe?** NO — see C1.

---

## 4. MEDIUM issues

| ID | File | Issue |
|---|---|---|
| M1 | `src/hybrid_pipeline.py:438` | `cache_hybrid_dev.json` not LLM-model-keyed |
| M2 | `src/run_pipeline.py` docstring (lines 9-16) | References `--provider gemini` flag that does not exist in `argparse` |
| M3 | `src/prompts.py` | Dead code — duplicated in `run_pipeline.py` and `run_pipeline_deepseek_flash.py`; never imported |
| M4 | `src/hybrid_pipeline.py:523` | Uses deprecated `datetime.utcnow()` |
| M5 | `output/task1/`, `output/task1_prompt/`, `output/task1_deberta/` | Lack `run_config.json` — provenance loss |
| M6 | `src/train_deberta.py` | Hyperparameters are module-level constants only (no CLI) — reproducibility relies on reading source |
| M7 | `logs/cache_hybrid_v2_dev.json` | Orphan cache predating provider-keyed naming |
| M8 | `requirements.txt` / `pyproject.toml` | Absent — no pinned dependency versions |

---

## 5. LOW issues

| ID | Item |
|---|---|
| L1 | `.gitignore` has duplicate entries for `output/`, `logs/`, `checkpoints/`, `__pycache__/`, `*.pyc`, `.env` |
| L2 | Cosmetic double-"deepseek" in `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` etc. |
| L3 | `label_diagnosis.py`'s `direction_reverse_rate_label` uses a per-label denominator approximation, not directly comparable to the global DRR |
| L4 | `evaluation.py` has `DEBUG=True` block that hardcodes `/tmp/` paths if run as `__main__` |
| L5 | Untracked-but-present files in `src/` (`collect_results.py`, `hybrid_v2.py`, etc.) — not in git index |

---

## 6. INFO

| ID | Item |
|---|---|
| I1 | `logs/cache_test_openai.json` exists — test set has been attempted with OAI but no test predictions in `output/` |
| I2 | The most frequent L1 label is `42 "Be responsible"` (2031 train occurrences) |
| I3 | Two recent diagnosis runs (`20260613_145549/` and `20260613_145847/`) both successful; latter has figures |

---

## 7. Files that appear SAFE (no action needed)

- `dataset/` — fully intact, validated
- `evaluation.py` — used correctly (only direction naming is misleading)
- `src/run_pipeline_deepseek_flash.py`
- `src/hybrid_v2.py`
- `src/regenerate_deberta_predictions.py`
- `research/fehu_label_diagnosis/label_diagnosis.py`
- `output/task1_prompt_deepseek_v4_flash/`
- `output/task1_deberta/` (content fine; provenance weak)
- `output/task1_hybrid/`
- `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/`
- `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/`
- `output/research_label_diagnosis/`

## 8. Files that need HUMAN review

- `src/run_pipeline.py` (C1, H1, H4, M2)
- `src/train_deberta.py` (C2)
- `src/hybrid_pipeline.py` (H3, M1, M4)
- `output/task1/` (C2, H6, H7)
- `output/task1_hybrid_v2/` (H5)

---

## 9. Trustworthiness of existing results (by method)

| Method | Number trustworthy? | Provenance trustworthy? | Comments |
|---|---|---|---|
| Prompt OAI (in `task1_prompt/`) | Yes | Partial | Model identity not recorded; `--model` arg was ignored anyway |
| Prompt DS Flash | Yes | Yes | Full provenance |
| DeBERTa-only | Yes | Partial | No run_config, but THRESHOLD=0.3 is hard-coded in `train_deberta.py` and `regenerate_deberta_predictions.py` matches that |
| Hybrid v1 | Yes | Partial | provider field missing in run_config |
| Hybrid v2 OAI (in `task1_hybrid_v2/`) | Yes as data | UNCLEAR | Orphan folder; canonical name missing |
| Hybrid v2 DS Pro | Yes | Yes | Best provenance |
| Hybrid v2 DS Flash | Yes | Yes | Same |
| Label diagnosis (latest) | Yes | Yes | Numbers verified against official scorer |

---

## 10. Answers to specific questions

### Q: Does `Prompt_DS_Flash` result appear valid?
**Yes.** Independent recomputation reproduces µF1=0.4964, P=0.5899, R=0.4285, DRR=0.0279 exactly. Folder has complete run_config + metrics.

### Q: Do `Hybrid v2 DS Pro` / `DS Flash` results appear valid?
**Yes.** Both folders have full provenance (run_config, metrics, comparison metrics, filtering stats, candidates). No schema issues.

### Q: Does `DeBERTa-only` result appear valid?
**Yes as data.** Predictions cover all 177 dev guids; no schema issues; volume (avg 19.08 task-1b/article) is consistent with `threshold=0.3` and `top_k`-style behaviour. Provenance is weaker (no run_config) but `regenerate_deberta_predictions.py` makes it cleanly reproducible.

### Q: Does the label-diagnosis result appear valid?
**Yes.** Per-label, 108-class, and frequency-group metrics independently verified. Sanity check: per-L1 direction-aware micro-aggregation exactly reproduces the official Task-1b micro-F1.

### Q: Are outputs mixed, overwritten, or mislabeled?
- `output/task1/` and `output/task1_prompt/` are **identical duplicates** (H6).
- DeBERTa's predictions that *used to* live in `output/task1/` were **overwritten** by the prompt-only run (C2).
- `output/task1_hybrid_v2/` is **orphaned/mislabeled** relative to the canonical naming scheme (H5).
- `output/task1/pred_task1*_4omini.json` are **manually archived** with no script-generated metadata.

### Q: Any API keys / secrets exposed?
**No.** Project-wide grep for `sk-[a-zA-Z0-9]{16,}` and `api_key\s*=\s*"…"` finds nothing in source. No `.env` at rest. Cache JSON files contain LLM responses only, not keys.

### Q: Is the codebase ready for the next research phase?
**Conditionally yes.** The data, diagnosis module, DeepSeek prompt pipeline, and Hybrid v2 (DS Pro/Flash) are research-grade. Recommended actions before augmentation:

1. Fix C1 (run_pipeline.py --model bug) so future OAI baselines are runnable.
2. Add `run_config.json` writers to legacy folders (M5).
3. Decide what to do with the orphan `output/task1/` and `output/task1_hybrid_v2/` folders.
4. Pin dependencies (`requirements.txt`).

The diagnosis-driven research conclusions already published are **safe to act on** — augmentation planning can begin using `rare_low_recall_labels.csv`, `high_direction_error_labels.csv`, etc.

---

## 11. Recommended next actions (in priority order)

1. **Patch C1 + H4** in `run_pipeline.py` (small surface; one local change each).
2. **Patch C2** in `train_deberta.py` (change default `OUTPUT_DIR` to `output/task1_deberta/`).
3. **Patch H3** in `hybrid_pipeline.py` (one path string).
4. **Patch H1, M1** by adding model name to the legacy cache paths.
5. Add `run_config.json` writers to `run_pipeline.py`, `train_deberta.py`, `regenerate_deberta_predictions.py`.
6. Decide: archive or delete `output/task1/`, `output/task1_hybrid_v2/`, `logs/cache_hybrid_v2_dev.json`.
7. Add `requirements.txt` with versions for: openai, transformers, peft, torch, tqdm, matplotlib.
8. Consider patching `evaluation.py`'s direction comment **only if** the user explicitly authorizes (the audit rule was to not modify it).
9. Then proceed to augmentation research as planned.

All proposed changes are summarized — and explicitly NOT applied — in `proposed_patch_plan.md`.

---

## 12. Severity totals

| Severity | Count |
|---|---:|
| CRITICAL | 2 |
| HIGH     | 7 |
| MEDIUM   | 8 |
| LOW      | 5 |
| INFO     | 3 |

---

**This audit was performed without modifying any project files.**
**All proposed changes are documented in `proposed_patch_plan.md` and require human review before application.**
