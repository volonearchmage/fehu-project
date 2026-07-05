# Expanded Raw Generation Report — DeepSeek V4 Pro

**Created at:** 2026-07-04T22:22:49 (completed 2026-07-04T23:0x)
**Run folder:** `output/research_expanded_raw_generation/20260704_222249`
**Branch:** `main`

## Git status before/after
Identical (verified): the pre-existing dirty set only (`src/hybrid_pipeline.py`, `src/run_pipeline.py`,
`src/train_deberta.py` modified; `HYBRID_ROADMAP.md`, `research/`, 4 untracked `src/*.py`). The prior
`.env.bak.20260704_215926` file was confirmed **absent** before generation started. No file outside this
run folder changed (output/ is gitignored).

## Files read
Planning trio (03_expanded_generation_plan.json, 04_generation_batch_spec.md,
02_target_label_priority_table.csv), verified pool (6 records), hv_categories taxonomy including
direction_mapping.json ({aligned:"1", contradictory:"0"}), and `.env` (config presence only — the API
key value was never printed, logged, or stored).

## Files written (this folder only)
01_generation_run_config.json, 02_generation_batch_plan_used.json, 03_raw_generated_candidates.jsonl,
04_generation_validation_table.csv, 05_candidate_quality_summary.csv, 06_generation_report.md,
logs/ (stdout/stderr incl. preserved attempt1 logs, api_call_summary.json), scripts/ (3 helper scripts,
allowed inside this folder only).

## API / provider / model
- Provider: **DeepSeek**; model: **DeepSeek V4 Pro** (API-reported id: `deepseek-v4-pro`).
- 28 successful API calls total (24 main + 4 repair), all `finish_reason=stop`, ~93k tokens total.
- **Recorded failure & fix:** the very first attempt requested 9 articles in one response and the JSON
  truncated mid-article → the script stopped loudly (attempt1 logs preserved). Fix: chunk every call to
  ≤3 articles and abort on `finish_reason=length`. Same endpoint/model — batching fix, not a fallback.
- **Recorded repair round 1:** 10 candidates failed local validation (evidence sentence not verbatim /
  actor mention missing — the model named the actor only in the extracted field while the article said
  "The company…"). Exactly those 10 were regenerated with tightened constraints
  (batch_02_aligned ×5, batch_03_contradictory ×3, batch_05_contradictory ×2); replaced IDs are listed
  in `logs/api_call_summary.json → repair_round_1`.

## Totals
**72 raw candidates**, per label/direction exactly as planned:

| L1 | Label | aligned | contradictory |
|----|-------|---------|---------------|
| 22 | Have good health | 9 | 9 |
| 30 | Be compliant | 6 | 6 |
| 38 | Be honest | 6 | 6 |
| 12 | Have success | 6 | 6 |
| 5 | Have freedom of action | 6 | 6 |
| 46 | Have a world at peace | 3 | 3 |

## Local validation summary (after repair round)
**67 PASS / 5 REVIEW / 0 FAIL** (per-candidate statuses in 05_candidate_quality_summary.csv; full check
matrix in 04_generation_validation_table.csv). All run-level checks pass: 72 records, unique IDs,
per-batch counts match plan, L1/L2 mappings valid against hv_categories, direction codes consistent with
1=aligned/0=contradictory, no forbidden meta-terms (FEHU/NTCIR/AI/synthetic/annotation), all workflow
flags clean (training_ready=false, verified_for_candidate_pool=false, empty verdicts/decisions).

REVIEW items (5): 4 candidates whose evidence sentence uses a generic actor reference
(3× L1=22-contradictory, 1× L1=38-aligned) — historically resolvable in human review; 1 candidate
(exp_38_aligned_03) flagged for actor/content similarity with the existing verified pool
(NovaTech-style disclosure story) — the semantic verification stage should check it for redundancy.

## Duplicate checks
No duplicate candidate IDs; no near-duplicate titles/contents within the run (actor names forced
distinct across chunks); 1 verified-pool similarity flagged as REVIEW (above).

## Quality-risk summary
All 72 remain **semantically unverified**. Highest-risk groups for the next stage: the 5 REVIEW items;
L1=5 contradictory samples (ban/blocking events risk drifting into compliance framing); L1=22 samples
(must stay on the actor's own health, not others').

## API key leak scan
`grep` scan of the entire run folder for key-like strings (`sk-…`, `Bearer …`): **NO_LEAK**. The
api_call_summary records `api_key_value_stored: false`; HTTP error bodies were redacted before logging.

## Statement
These are raw generated candidates only. They are not semantically verified, not human accepted, not in
the verified pool, and not training-ready.

## Next step
Run local candidate filtering and AI-assisted semantic verification, then human ACCEPT/REJECT review.
