# Recommended Next Steps (Staged)

Each stage gates the next. Do not skip ahead.

## Stage 1 — Human review of v2 preview (CURRENT GO)

- Open `output/research_generation_preview/20260614_171644/human_review_sheet.csv` in a spreadsheet tool.
- For each of the 18 rows, set `review_status` ∈ {`approved`, `rejected`, `needs_changes`} and add brief `reviewer_notes`.
- Optionally re-read the matching line of `generation_requests_preview.jsonl` for the full system + user prompt:
  ```bash
  python3 -c "import json; [print(json.dumps(r,indent=2,ensure_ascii=False)[:1500],'\n---') for r in (json.loads(l) for l in open('output/research_generation_preview/20260614_171644/generation_requests_preview.jsonl')) if r['request_id']=='<PUT_ID_HERE>']"
  ```
- Use this audit's `03_PREVIEW_V2_AUDIT/preview_v2_request_matrix.csv` as a companion: it pre-flags `medium`-priority requests (no seed, smart-truncated excerpt, missing alternative_label_id).

**Owner:** human reviewer (researcher).
**Output:** human-edited copy of `human_review_sheet.csv` (a new file with the approval column filled).
**Time budget:** 30–45 minutes for 18 rows.

## Stage 2 — Approve 6–8 low-risk requests for the tiny pilot

Out of the 18, **target approving only 6–8**. Suggested mix:

| Type | Suggested approvals | Why |
|---|---:|---|
| paraphrase | 2 | Lowest risk: seed-grounded, identity-stable |
| rare_positive | 2 | Tests generator on rare labels (e.g. 24 "Be neat and tidy" — 4 train examples) |
| hard_negative | 1 | Tests near-miss prompt; consider a request that has `alternative_label_id` already set |
| direction_contrastive | 1 pair (2 requests) | Validates pair design |
| **Total** | **7** | Fits inside the cost guard rail in `MODEL_SELECTION_AND_COST_STRATEGY.md` |

**Output:** a `pilot_approved_requests.csv` (list of approved `request_id`s).
**Owner:** human reviewer.

## Stage 3 — Design `run_generation.py` (DRY-RUN FIRST)

Only after Stage 2 produces an approved manifest:

- Author `research/fehu_augmentation_v1/run_generation.py`.
- **Default mode = dry-run**: read approved manifest, build the actual HTTP payload, write it to disk, print "would call X model with Y tokens", but **do not** send the request.
- `--execute` flag required to actually call the API.
- On execute, the script must:
  - Refuse to run on a request where `do_not_execute` is true unless an approved manifest is provided.
  - Record `generation_model`, `generation_prompt_hash`, `preview_revision`, `created_at`.
  - Stream-write each sample to `output/research_augmentation_data/<TS>/augmented_samples.jsonl`.
  - Tag rejections to `augmented_samples_rejected.jsonl`.
  - Run `augmented_training_data_guard.py --strict` automatically at the end.

**Owner:** assistant, after explicit user approval.
**Safety:** still **no API** at this stage — only the script exists, dry-run-first.

## Stage 4 — Tiny-pilot API generation

- Confirmed via `--execute` on the approved manifest only.
- Recommended model: `deepseek-v4-pro` (per `MODEL_SELECTION_AND_COST_STRATEGY.md` Tier 1).
- Cost cap: ≤ 7 generation calls + 7 verifier calls = 14 calls. Hard upper bound: 20.
- All output to `output/research_augmentation_data/<TS>/` (a fresh timestamped folder).

**Owner:** human (runs the command after confirming budget).

## Stage 5 — Local validation + teacher/human verification

- `python research/fehu_submission_safety/augmented_training_data_guard.py --input <samples>.jsonl --strict` MUST return exit 0.
- Human spot-check at least 3 of the 7 samples (read content + evidence sentence; compare to direction + L1).
- Optional: run a second-pass LLM verifier with the verification prompt template.

**Owner:** human + assistant.
**No augmented data enters training data until exit code is clean AND spot-check passes.**

## Stage 6 — Ablation training (only after Stage 5 passes)

- Author the training-data combiner (`combined_train_set.json = train_gold + approved augmented`).
- Re-run `src/train_deberta.py --version aug_pilot_v1` (training is local, no API).
- Re-run `python research/fehu_label_diagnosis/label_diagnosis.py` to measure rare-label recall change vs. the existing diagnosis baseline.

**Owner:** human + assistant.

---

## What we are explicitly NOT doing in the current session

- Authoring `run_generation.py`.
- Calling any LLM.
- Producing `augmented_samples.jsonl`.
- Producing `pred_task1*.json` for any test or dev set.
- Modifying any existing prediction or cache file.
- Re-running `evaluation.py`.
