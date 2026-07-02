# Proposed Patch Plan (NOT APPLIED)

This document describes patches recommended by the audit. **None of these have been applied.** Each item lists the affected file, the proposed change, its risk, and whether human approval is required.

---

## Patch P1 — fix `run_pipeline.py --model` ignored (CRITICAL)

- **issue_id:** C1 / H1
- **affected_file:** `src/run_pipeline.py`
- **proposed_change:**
  1. Replace line 249 `model=MODEL,` inside `call_gpt` with `model=args.model,` (and thread `args.model` through into `call_gpt(client, system_prompt, user_prompt, article_guid, args.model)`).
  2. Replace line 410 `print(f"Model: {MODEL}")` with `print(f"Model: {args.model}")`.
  3. Replace line 425 `cache_path = ... f"cache_{args.mode}.json"` with `cache_path = ... f"cache_{args.mode}_openai_{args.model.replace('-', '_')}.json"` to prevent cross-model contamination.
- **risk_level:** MEDIUM
- **modifies existing code?** YES
- **human approval required?** YES — also requires deciding what to do with the existing `logs/cache_dev.json` (which holds results from when `--model` was ignored).

---

## Patch P2 — fix `train_deberta.py` output collision (CRITICAL)

- **issue_id:** C2
- **affected_file:** `src/train_deberta.py`
- **proposed_change:** Line 47, change `OUTPUT_DIR = BASE_DIR / "output" / "task1"` to `OUTPUT_DIR = BASE_DIR / "output" / "task1_deberta"`. Also add a `run_config.json` writer in the final inference block recording `MODEL_NAME`, `THRESHOLD`, `MAX_EPOCHS`, `LR`, `BATCH_SIZE`, `GRAD_ACCUM`, `WARMUP_RATIO`, `WEIGHT_DECAY`, `PATIENCE`, `CHECKPOINT_DIR`, and timestamp.
- **risk_level:** LOW (training is not auto-rerun)
- **modifies existing code?** YES
- **human approval required?** YES — also requires deciding what to do with the now-redundant `output/task1/` folder (currently a duplicate of `output/task1_prompt/`).

---

## Patch P3 — fix `hybrid_pipeline.py` DeBERTa baseline path (HIGH)

- **issue_id:** H3
- **affected_file:** `src/hybrid_pipeline.py`
- **proposed_change:** Line 46, change `DEBERTA_OUT = BASE_DIR / "output/task1"` to `DEBERTA_OUT = BASE_DIR / "output/task1_deberta"`.
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES — does not invalidate existing hybrid v1 predictions (only affects its comparison table on re-run).

---

## Patch P4 — fix `run_pipeline.py` limit-mode evaluation (HIGH)

- **issue_id:** H4
- **affected_file:** `src/run_pipeline.py`
- **proposed_change:** In `run_dev_evaluation` (lines 492-526), follow the pattern from `run_pipeline_deepseek_flash.py:323-337`:
  ```python
  processed_guids = {x["guid"] for x in json.load(open(pred_1a_path))}
  def _filter(d, guids): return {k: v for k, v in d.items() if k[0] in guids}
  gold_1a = _filter(parse_task1a(DEV_LABELS), processed_guids)
  pred_1a = _filter(parse_task1a(pred_1a_path), processed_guids)
  ```
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES.

---

## Patch P5 — fix `hybrid_pipeline.py` cache key (HIGH)

- **issue_id:** M1
- **affected_file:** `src/hybrid_pipeline.py`
- **proposed_change:** Line 438, change `cache_path = LOGS_DIR / f"cache_hybrid_{args.mode}.json"` to `cache_path = LOGS_DIR / f"cache_hybrid_{args.mode}_{args.model.replace('-', '_')}.json"`. Also store `{"llm_model": args.model, ...}` per cache entry and guard cache hits on model match (mirror `hybrid_v2.py`).
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES.

---

## Patch P6 — add `run_config.json` writers (MEDIUM)

- **issue_id:** M5
- **affected_files:**
  - `src/run_pipeline.py` → write to `output/task1_prompt/run_config.json` (NOT `output/task1/`)
  - `src/regenerate_deberta_predictions.py` → write to `output/task1_deberta/run_config.json`
- **proposed_change:** Each script writes `{mode, provider, model, threshold (if applicable), cache_path, limit, timestamp, notes}` to a `run_config.json` next to its prediction files.
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES.

---

## Patch P7 — document the orphan `output/task1_hybrid_v2/` folder (HIGH provenance)

- **issue_id:** H5
- **affected_file:** none (just add a README)
- **proposed_change:** Add `output/task1_hybrid_v2/PROVENANCE.md` explaining that this folder predates the provider-aware naming scheme in `hybrid_v2.py`, and that the canonical OAI Hybrid v2 location is `output/task1_hybrid_v2_openai_gpt_4o_mini/`. If the user wants this folder treated as the OAI baseline going forward, rename it.
- **risk_level:** LOW
- **modifies existing code?** NO (only adds a new doc file in an existing output dir, which the audit rules permit only as a research artifact — defer to user)
- **human approval required?** YES — even adding a file in `output/` deserves a sign-off.

---

## Patch P8 — clean up `.gitignore` duplicates (LOW)

- **issue_id:** L1
- **affected_file:** `.gitignore`
- **proposed_change:** Deduplicate entries for `output/`, `logs/`, `checkpoints/`, `__pycache__/`, `*.pyc`, `.env`.
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES.

---

## Patch P9 — add `requirements.txt` (MEDIUM)

- **issue_id:** M8
- **affected_file:** new file `requirements.txt`
- **proposed_change:** Pin versions for: `openai>=1.0`, `transformers>=4.40`, `peft>=0.10`, `torch>=2.1`, `tqdm`, `matplotlib`, `pandas` (optional, for diagnosis ergonomics).
- **risk_level:** LOW
- **modifies existing code?** NO (new file)
- **human approval required?** YES.

---

## Patch P10 — remove the dead `src/prompts.py` (LOW)

- **issue_id:** M3
- **affected_file:** `src/prompts.py`
- **proposed_change:** Either delete it, or refactor `run_pipeline.py` and `run_pipeline_deepseek_flash.py` to `from prompts import build_system_prompt, build_user_prompt`.
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES.

---

## Patch P11 — fix `hybrid_pipeline.py` deprecated `datetime.utcnow()` (LOW)

- **issue_id:** M4
- **affected_file:** `src/hybrid_pipeline.py:523`
- **proposed_change:** Replace `datetime.utcnow().isoformat() + "Z"` with `datetime.now(timezone.utc).isoformat()`. Add `from datetime import timezone` to imports.
- **risk_level:** LOW
- **modifies existing code?** YES
- **human approval required?** YES.

---

## What this plan does NOT propose

- **No deletion** of any existing prediction file, cache file, or output folder. The user must explicitly authorize any removal.
- **No edits to `evaluation.py`** — even though its direction docstring is misleading, the user constraint forbids changing this file.
- **No re-runs** of any pipeline (no API calls, no training).

---

## Summary table

| Patch | Severity | Modifies code? | Auto-fix safe? | Approval required |
|---|---|---|---|---|
| P1 | CRITICAL | yes | NO | yes |
| P2 | CRITICAL | yes | NO | yes |
| P3 | HIGH | yes | mostly | yes |
| P4 | HIGH | yes | yes | yes |
| P5 | HIGH | yes | yes | yes |
| P6 | MEDIUM | yes | yes | yes |
| P7 | HIGH | adds new file | NO | yes |
| P8 | LOW | yes | yes | yes |
| P9 | MEDIUM | adds new file | yes | yes |
| P10 | LOW | yes | yes | yes |
| P11 | LOW | yes | yes | yes |
