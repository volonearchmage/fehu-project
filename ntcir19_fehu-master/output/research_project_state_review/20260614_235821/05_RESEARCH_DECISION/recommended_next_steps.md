# Recommended Next Steps (Staged)

Each stage gates the next. Do not skip ahead.

## Stage 1 — Human review of v2 preview (CURRENT GO)

- Open `output/research_generation_preview/20260614_171644/human_review_sheet.csv` in a spreadsheet tool.
- For each of the 18 rows, set `review_status` ∈ {`approved`, `rejected`, `needs_changes`} and add brief `reviewer_notes`.
- For the full system + user prompts of any specific request:
  ```bash
  python3 - <<'PY'
  import json
  rid = "PUT_REQUEST_ID_HERE"
  for line in open("output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl"):
      r = json.loads(line)
      if r["request_id"] == rid:
          print(json.dumps(r, indent=2, ensure_ascii=False)[:2000])
          break
  PY
  ```
- Use this audit's `03_PREVIEW_V2_AUDIT/preview_v2_request_matrix.csv` as a companion. It pre-flags `medium` priority rows.

**Owner:** human reviewer.
**Output:** approval column filled.
**Time budget:** 30–45 min for 18 rows.

## Stage 2 — Approve 6–8 low-risk requests for the tiny pilot

| Type | Suggested approvals | Why |
|---|---:|---|
| paraphrase | 2 | Lowest risk: seed-grounded, identity-stable |
| rare_positive | 2 | Tests generator on rare labels (e.g. 24 "Be neat and tidy" — 4 train examples) |
| hard_negative | 1 | Tests near-miss prompt; prefer a request with `alternative_label_id` already set |
| direction_contrastive | 1 pair (2 requests) | Validates pair design |
| **Total** | **7** | Fits inside the cost guard rail in `MODEL_SELECTION_AND_COST_STRATEGY.md` |

**Output:** `pilot_approved_requests.csv` (list of approved `request_id`s).
**Owner:** human reviewer.

## Stage 3 — Design `run_generation.py` (DRY-RUN FIRST)

Author after Stage 2 produces an approved manifest:

- Author `research/fehu_augmentation_v1/run_generation.py`.
- **Default mode = dry-run**: build the actual HTTP payload, write it to disk, print "would call X model with Y tokens", but do not send.
- `--execute` flag required to actually call the API.
- On execute:
  - Refuse to run on a request where `do_not_execute` is true unless an approved manifest is provided.
  - Record `generation_model`, `generation_prompt_hash`, `preview_revision`, `created_at`.
  - Stream-write each sample to `output/research_augmentation_data/<TS>/augmented_samples.jsonl`.
  - Route rejections to `augmented_samples_rejected.jsonl`.
  - Auto-run `augmented_training_data_guard.py --strict` at end.

**Owner:** assistant, after explicit user approval.
**Safety:** still no API at this stage — script exists, dry-run-first.

## Stage 4 — Tiny-pilot API generation

- Confirmed via `--execute` on the approved manifest only.
- Recommended model: `deepseek-v4-pro` (Tier 1 per `MODEL_SELECTION_AND_COST_STRATEGY.md`).
- Cost cap: ≤ 7 generation + 7 verifier = 14 calls. Hard upper bound: 20.
- Output to `output/research_augmentation_data/<TS>/` (fresh timestamped folder).

**Owner:** human (runs the command after confirming budget).

## Stage 5 — Local validation + teacher/human verification

- `augmented_training_data_guard.py --input <samples>.jsonl --strict` MUST exit 0.
- Human spot-check ≥ 3 of the 7 samples.
- Optional: second-pass LLM verifier with the verification prompt template.

**Owner:** human + assistant.

## Stage 6 — Ablation training (only after Stage 5 passes)

- Author training-data combiner (`combined_train_set.json = train_gold + approved augmented`).
- Run `src/train_deberta.py --version aug_pilot_v1` (local; no API).
- Re-run `python research/fehu_label_diagnosis/label_diagnosis.py` to measure rare-label recall change.

**Owner:** human + assistant.

---

## What this current session is NOT doing

- Authoring `run_generation.py`.
- Calling any LLM.
- Producing `augmented_samples.jsonl`.
- Producing any `pred_task1*.json`.
- Modifying any existing prediction or cache file.
- Re-running `evaluation.py`.
