# Model Selection & Cost Strategy for FEHU Augmentation

**Status:** *strategy only*. No model has been called. No cost has been incurred.

This document specifies which LLM should be used for generation and which for
verification at each scale of the augmentation pipeline. It complements
`research/fehu_augmentation_v1/METHOD_DESIGN.md` (which covers *what* to
augment) by specifying *with what* to do it.

## Why model selection matters

The label diagnosis shows that **Prompt_DS_Flash** is the strongest external
"teacher" in the current project (Task-1b µF1 = 0.4964, DRR = 0.0279). But:

- Using it as the final classifier is not a research contribution.
- Using it as the *generator* is acceptable; using it as the *verifier* of
  its own generations is **not** acceptable (it would simply reaffirm its own
  biases).
- For verification we want a model at least as strong as the generator, with
  no shared optimisation history.

The strategy below balances three constraints: quality, cost, and verifier
independence.

---

## Tier 1 — Tiny pilot (≤ 20 generation requests)

**Goal:** sanity-check prompts, examine failure modes, refine rejection
rules before scaling.

| Role | Recommended model | Reason |
|---|---|---|
| Generator | `deepseek-v4-pro` | At small volume the cost difference between Pro and Flash is negligible (~20 calls × ~2k tokens). Pro produces fewer format errors and stays on-task with our strict-JSON instructions. |
| Verifier | `deepseek-v4-pro` *or* manual review | At 20 samples a single human reviewer can read every output in 30 minutes. If the human review is the bottleneck, run Pro as an automated pre-filter and review only `needs_human_review`. |

**Budget signal.** If pilot rejection rate > 30 %, fix prompts *before*
scaling. If rejection is concentrated in one augmentation type, revise its
blueprint specifically.

## Tier 2 — Medium pilot (≤ 200 generation requests)

**Goal:** validate that the pipeline scales without prompt regressions.

| Role | Recommended model | Reason |
|---|---|---|
| Generator | `deepseek-v4-flash` | ~10× cheaper than Pro at similar JSON-following quality once prompts are stable. Slight loss in coherence is acceptable for short news-style text. |
| Verifier | `deepseek-v4-pro` | Independent of the generator's biases (different model size); strong at instruction-following on the verification template. |

**Budget signal.** If Pro rejects > 50 % of Flash output, the generator
prompt is under-specified — patch the prompt, do not just raise the
acceptance threshold.

## Tier 3 — Full augmentation (full plan budget, ~500–1500 samples)

**Goal:** produce the entire pilot/medium/full augmentation pool.

| Role | Recommended model | Reason |
|---|---|---|
| Generator | `deepseek-v4-flash` | Cost is the dominant constraint at this scale. |
| Verifier | `deepseek-v4-pro` (sampled) **or** `gpt-4o` (full) | Either Pro on a sample (≥ 20 % per type per label) plus manual spot checks, or a stronger external model on every sample if budget allows. Use stronger model for `direction_contrastive` samples specifically — direction faithfulness is the highest-stakes property. |

---

## Required metadata on every generated sample

Every augmented sample (Tier 1, 2, or 3) must record the following provenance
fields — `augmented_training_data_guard.py` enforces these:

| Field | Required |
|---|---|
| `augmentation_id` | yes |
| `augmentation_type` | yes |
| `source_label_id`, `direction` | yes |
| `generation_model` | yes (e.g. `"deepseek:deepseek-v4-pro"`) |
| `generation_prompt_id` | yes (refers to a blueprint section) |
| `generation_prompt_hash` | yes (md5 of the prompt sent) |
| `source_plan_dir` | yes (path of the augmentation plan that selected this label) |
| `created_at` | yes (UTC ISO-8601) |
| `verifier_model` | required if `verification_status` is set |
| `verification_status` | required in strict mode |
| `verification_reason` | required if `verification_status ∈ {rejected, needs_human_review}` |

This makes every sample traceable to (a) the prompt template, (b) the model
that produced it, (c) the planning run that selected its target label.

---

## Quality control cadence

| Stage | Mechanism | Trigger |
|---|---|---|
| Schema validation | `validate_augmented_data.py` (local; no API) | Every batch |
| Teacher verification | LLM verifier prompt (Tier 2 / 3) | Every sample in Tier 2; sampled in Tier 3 |
| Duplicate filtering | content-hash + (later) embedding-distance Jaccard | Every batch |
| Human spot check | Manual review of N samples per type | Always Tier 1; ≥ 20 per type Tier 2; ≥ 10 per type Tier 3 |
| Rejection-rate reporting | Per-type, per-label rejection bar chart | After every batch |
| Per-label volume cap | Cap synthetic positives at `min(4 × train_count, 50)` per label | Always |

The last cap is critical: it prevents the model from learning that rare
labels are now "common" because of augmentation.

---

## Cost guard rails (suggested, not enforced)

| Tier | Max generations | Max verifications | Suggested daily cap |
|---|---|---|---|
| Tiny pilot | 20 | 20 | 50 calls |
| Medium pilot | 200 | 200 | 500 calls |
| Full | per the `full` budget profile in `BUDGET_PROFILES` | per Tier-3 verification policy | 5 000 calls |

These caps are policy, not technical limits. They should be checked by the
operator (the human running the generator) before each session.

---

## What this strategy does NOT do

- Does not implement the runner. (`research/fehu_augmentation_v1/run_generation.py`
  is the future, not-yet-created script that will consume request previews
  and dispatch them.)
- Does not specify a particular API key, billing plan, or rate limit.
- Does not lock the project to DeepSeek. If `Hybrid_v2_DS_Pro` and
  `Hybrid_v2_DS_Flash` later show divergent direction-accuracy patterns, the
  verifier may be switched to `gpt-4o` for direction-contrastive samples
  specifically.

---

## Status statement

> **No augmentation generation has been performed.** This document describes
> the planned model strategy. The next phase (request review →
> tiny-pilot generation) requires explicit user approval and a billing decision.
