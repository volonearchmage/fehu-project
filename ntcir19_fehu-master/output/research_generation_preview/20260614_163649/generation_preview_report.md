# Generation Preview Report (tiny pilot v1)

**Timestamp:** 20260614_163649  
**Profile:** `tiny_pilot_v1`  
**Source plan:** `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_augmentation_plan/20260614_131524`  
**Max requests:** 20  

> No API was called. Every request object has `"preview_only": true` and `"do_not_execute": true`.

## Totals

- Preview requests written: **18**
- TRAIN seeds used: 8
- Requests with a seed: 8
- Requests without a seed (definition-only): 10
- Direction-contrastive pairs: 3

## Requests by augmentation type

| Type | Target | Actual |
|---|---|---|
| paraphrase | 4 | 4 |
| rare_positive | 4 | 4 |
| hard_negative | 4 | 4 |
| direction_contrastive | 8 | 6 |

## Requests by L1 label

| L1 | Label | Requests |
|---|---|---|
| 29 | Be holding religious faith | 3 |
| 32 | Be behaving properly | 3 |
| 51 | Have the wisdom to accept others | 3 |
| 7 | Have an exciting life | 3 |
| 12 | Have success | 2 |
| 24 | Be neat and tidy | 2 |
| 38 | Be honest | 2 |

## What this preview does

1. Reads the existing plan and selects target labels per type by priority.
2. Picks one TRAIN seed instance per `paraphrase` and (optionally) per `rare_positive`.
3. Builds a complete request object — system prompt, user prompt,    expected output schema, quality checklist, rejection rules — but does not    call any API.
4. Writes a human review sheet in CSV form with `review_status = pending`    for every request.
5. Writes a small set of figures summarising the preview.

## What this preview does NOT do

- Does not call any LLM.
- Does not produce any augmented sample.
- Does not modify any existing file or output folder.
- Does not write into `dataset/`, `output/task1*/`, or `logs/`.

## Suggested next steps (for the human reviewer)

1. Open `human_review_sheet.csv` and verify the request set.
2. Inspect any non-trivial prompt by reading the matching line in    `generation_requests_preview.jsonl`.
3. When ready, the next phase will be `run_generation.py` (not yet created),    which consumes the preview file, dispatches calls, and writes    `augmented_samples.jsonl` validated against    `research/fehu_augmentation_v1/augmentation_schema.json` and the    FEHU-specific augmented-data guard.

## Constraints honoured

- No API call.
- No model training.
- No reading of `.env` values.
- TRAIN seeds only; no dev/test article content used.
- All output written to a new timestamped folder; nothing overwritten.