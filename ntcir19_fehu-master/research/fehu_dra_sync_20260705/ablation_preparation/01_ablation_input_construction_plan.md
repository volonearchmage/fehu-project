# Ablation Input Construction Plan — DRA-FEHU (Task-1)

**Created at:** 2026-07-02T16:56:50
**Status:** PLANNING ONLY. No augmented data created, no training, no ablation.

## Research objective
Diagnosis-driven Recall-focused Augmentation for FEHU (DRA-FEHU): test whether adding a small,
auditable, verify-first set of augmented actor-level examples (targeting rare labels and direction
consistency) improves Task-1 recognition — especially rare-label recall and direction correctness —
without harming overall micro/macro-F1. This plan defines how baseline vs augmented inputs will be
constructed later; it does not build them.

## Current verified pool status
Source: `output/research_verified_candidates/20260702_165107/01_verified_augmented_candidates.jsonl`
- 6 verified candidates; all human_decision=ACCEPT; all verified_for_candidate_pool=true; all training_ready=false.
- L1=38 "Be honest" direction pair COMPLETE (['0 contradictory', '1 aligned']).
- L1=12 "Have success" direction pair COMPLETE (['0 contradictory', '1 aligned']).
- No duplicate candidate_id.
- Every candidate's L1->L2 mapping validated against dataset/hv_categories: consistent = True.

## Condition A — Baseline
- Train: official train only.
- Eval: official dev via `evaluation.py`.
- No augmented candidates.

## Condition B — DRA-FEHU verified augmentation
- Train: official train + the 6 verified augmented candidates (as derived copies under `output/`).
- Eval: official dev (identical to A) via `evaluation.py`.
- Same model, prompt, and training configuration as baseline. **The only changed factor is the
  inclusion of the augmentation data.**

### Hard invariants (both conditions)
- Official train/dev/test files must **never** be overwritten.
- Augmented data is created later as a **derived copy under `output/`**, never under `dataset/`.
- Every synthetic record is traceable back to `candidate_id` and `source_files`.
- `training_ready` remains **false** until a later explicit approval step.
- No official gold labels are changed.

## Candidate-to-data conversion design (to be executed in a LATER task)
Observed official schema (read-only inspection):
- event_base record keys: `guid, content, title, actors, subevents`; `actors` is a list of
  single-key objects `{"Actor Name": "actor_id"}`; `subevents` is a list of `{"id","subevent"}`.
- gold record keys: `guid, article_human_values, subevents_human_values`; each article_human_values
  entry: `{actor, l1_value, l2_value, direction, explanation}`; `direction` is the string `"1"` or `"0"`.

1. **Synthetic guid naming rule:** `aug_<candidate_id>` (e.g. `aug_repl_dir_contrast_12_002_contradictory_3cfa8093d2`).
2. **Actor id naming rule:** `aug_<candidate_id>-0` (single actor per synthetic article).
3. **event_base structure (derived):**
   - `guid` = `aug_<candidate_id>`
   - `title` = candidate-derived short title (or first sentence)
   - `content` = candidate `content` verbatim
   - `actors` = `[{ <actor_name>: "aug_<candidate_id>-0" }]`
   - `subevents` = `[]` (Task-1 is article-level; subevents are optional and left empty for synthetic articles)
4. **gold label structure (derived):**
   - `guid` = same synthetic guid
   - `article_human_values` = one entry: `{ "actor": "aug_<candidate_id>-0", "l1_value": target_l1_value_id,
     "l2_value": target_l2_value_id, "direction": DIR_MAP[target_direction], "explanation": evidence_sentence }`
   - `subevents_human_values` = `[]`
5. **Direction mapping consistency:** preserve the project convention `{'1 aligned': '1', '0 contradictory': '0'}` (1=aligned, 0=contradictory).
   Directions are **never silently inverted**; the mapping is explicit and validated.
6. **Level-1 / Level-2 consistency:** validated against `dataset/hv_categories`:
   L1=12 "Have success" -> L2=4 (Achievement); L1=38 "Be honest" -> L2=14 (Benevolence: caring);
   L1=32 "Be behaving properly" -> L2=11; L1=24 "Be neat and tidy" -> L2=8. Every derived label's
   (l1_value, l2_value) pair must equal the canonical hv_categories mapping or the build stops.
7. **Traceability:** every synthetic record carries `candidate_id` in a metadata field, and a separate
   manifest maps synthetic guid -> candidate_id -> source_files.
8. **No dataset pollution:** derived augmented files are written **only** under
   `output/research_ablation_inputs/<timestamp>/`, never under `dataset/`. No synthetic guid may
   collide with an official guid.

## Evaluation metrics to compare (A vs B, on official dev)
- **Task-1b micro-F1**
- **Task-1b macro-F1** (gold-supported)
- **Direction Reverse Rate (DRR)** — primary direction-consistency metric
- **Rare-label recall** — per-class recall for the augmented rare labels (L1=12, 38, 32, 24) if
  available from the label-diagnosis analysis; report per-label recall deltas.

## What NOT to claim before ablation
- Do not claim any F1 / DRR / recall improvement until both conditions are actually run.
- Do not claim statistical significance from 6 augmented examples; treat results as a directional,
  small-sample signal, not proof.
- Do not claim generalization beyond the targeted rare labels/directions.

## Exact next implementation step
After human review of this plan, create derived baseline/augmented input files under
`output/research_ablation_inputs/<timestamp>/` (event_base + gold + manifest), following the
conversion design above, **without modifying official data** and **without flipping training_ready**.
