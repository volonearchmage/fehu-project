# FEHU Project Research Summary

**Document date:** 2026-07-19
**Repository:** `fehu-project` (project root: `ntcir19_fehu-master/`)
**Branch / HEAD at time of writing:** `sync-safe-fehu-dra-20260705` / `6b6f4cc` (working tree clean)
**Scope:** This document summarizes only work that is already designed, implemented, run, evaluated, or explicitly documented in this repository. It contains no future plans or feasibility analysis. All file paths are relative to `ntcir19_fehu-master/` unless stated otherwise. All quantitative claims cite the run folder or report from which they are taken; results from different runs and model variants are never merged.

---

## 1. Executive Summary

This repository hosts research on the **NTCIR-19 FEHU (Fact-based Event-centric Human Value Understanding)** benchmark: recognizing the human values expressed by each actor in factual news articles, including a binary *direction* (aligned vs. contradictory) per value. The work to date covers four interlocking research strands, all evaluated on the official 177-article dev set with the unmodified official evaluator (`evaluation.py`):

1. **Prompt-only LLM pipelines** — the original GPT baseline (`src/run_pipeline.py`), a DeepSeek Flash adaptation, and two re-engineered pipelines: Pipeline V2 (strict-validation, zero-shot taxonomy-grounded; `src/run_pipeline_prompt_v2.py`) and Pipeline V3 (two-variant prompt ensemble + precision verifier; `src/run_pipeline_prompt_v3.py`), with 124 unit tests.
2. **A DeBERTa-v3-base + LoRA student classifier** (`src/train_deberta.py`) over the 108-class direction-aware label space (54 L1 values × 2 directions).
3. **DRA-FEHU: diagnosis-driven, label-conditioned data augmentation** — a per-label diagnosis of all methods, followed by two rounds of DeepSeek-generated synthetic data (round 1: 340 AI-filtered "silver" records; round 2: 900 structurally-validated but semantically *unscreened* records), and two augmented DeBERTa training experiments, the second using a masked-loss trainer.
4. **Inference-time hybrids** — culminating in a DeBERTa×LLM hybrid in which the Augmented DeBERTa v2 model supplies direction-neutral candidate values and DeepSeek V4 Flash (running a reference method by Liu, `liu_method/`) verifies value relevance and assigns/corrects direction.

**Headline verified result** (run `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/`): the hybrid variant **H3** reaches Task-1b micro-F1 **0.5474** and the variant **H2** reaches Task-1b macro-F1 **0.3603** on dev, both exceeding the strongest single system (Liu's `targeted_more_shot_balanced` DeepSeek Flash run, locally frozen and reproduced at micro-F1 **0.5347** / macro **0.3385**), while keeping Direction Reverse Rate near Liu's level (0.031–0.036 vs. 0.023). Ablations in the same run show that the LLM verification step is load-bearing: adding the same DeBERTa candidates unverified collapses micro-F1 to 0.4057.

Key documented caveats: all training/API results are single-seed / single-run; the 900 round-2 augmentation records are semantically unscreened; two of Liu's reported reference numbers (0.5387 and 0.5657) could not be reproduced or evaluated locally (artifacts absent) and are explicitly marked BLOCKED; and DRR deltas in early augmentation runs were shown to lie within single-model trajectory variance.

---

## 2. FEHU Task Definition

Source: `README.md`, `CLAUDE.md`.

FEHU asks systems to identify the human values expressed by **each actor** in factual news articles. The benchmark defines two tasks, each with two variants:

| Task | Variant | Label space | Evaluation unit |
|---|---|---|---|
| Task-1 (article level) | **1a** | Level-2 values (20 categories) | `(article_guid, actor_id)` |
| Task-1 (article level) | **1b** | Level-1 values (54) **+ direction** | `(article_guid, actor_id)` |
| Task-2 (subevent level) | **2a** | Level-2 values (20) | `(article_guid, subevent_id, actor_id)` |
| Task-2 (subevent level) | **2b** | Level-1 values (54) + direction | `(article_guid, subevent_id, actor_id)` |

- **Direction semantics** (`dataset/hv_categories/direction_mapping.json`): `"1"` = **aligned** (actor's behavior expresses/supports the value), `"0"` = **contradictory** (actor's behavior violates/undermines the value).
- For Task-1b/2b the evaluator internally encodes each label as `"{direction}:{l1_value}"` (e.g., `"1:42"`), yielding a **108-class direction-aware space** (54 × 2). This encoding (e.g., `0:28` = "Be respecting traditions", contradictory) is used throughout the repository's experiment reports.
- All experimental work in this repository targets **Task-1**; the baseline pipeline and every subsequent experiment produce `pred_task1a.json` / `pred_task1b.json` only. Task-2 is defined by the benchmark but has no implemented system here.

---

## 3. Dataset and Label Structure

Source: `README.md`, `CLAUDE.md`, `dataset/`, per-run reports.

| Split | File | Size (as used in experiments) |
|---|---|---|
| Train | `dataset/train/train_event_base.json` + `dataset/gold_labels/train/train_human_values.json` | **1228 articles**, 3335 actor-level examples (per `output/research_augmented_deberta_v1/20260712_231751/report/`) |
| Dev | `dataset/dev/dev_event_base.json` + `dataset/gold_labels/dev/dev_human_values.json` | **177 articles**; 458 gold `(guid, actor)` instances per the evaluator (`output/task1_prompt_v2/20260713_111745_.../metrics.json`; the DeBERTa training loader reports 456 dev actor examples); 2390 gold direction-aware Task-1b labels |
| Test | `dataset/test/test_article_event_base.json`, `dataset/test/test_subevent_event_base.json` | articles without gold labels (Task-1 / Task-2 inputs) |

- **Taxonomy** (`dataset/hv_categories/`): 54 Level-1 values (IDs `"0"`–`"53"`), 20 Level-2 categories (IDs `"0"`–`"19"`), L1↔L2 mappings, direction mapping, and `human_value_taxonomy.json` with official per-value descriptions. There is **no official "not-to-be-confused-with" resource**; the closest artifact is project-authored confusion notes in the round-2 generation cards (documented in `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/01_preflight_artifact_audit.md` §4).
- **Long-tail structure** (label diagnosis, `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/diagnosis_report.md`; `research/fehu_augmentation_v1/METHOD_DESIGN.md`): train L1 counts range from 4 ("Be neat and tidy") to 2031 ("Be responsible"); roughly a third of L1 labels have ≤35 training instances. This long tail is the central motivation for the augmentation strand.
- **Upstream data-bug history** (`README.md`, `CLAUDE.md`): dataset versions before upstream commit `af52dcb` (March 20, 2026) contained actor misalignment in the train/dev gold labels caused by a data-processing bug. The dataset in this repository is the corrected version.

---

## 4. Evaluation Protocol

Source: `evaluation.py` (official scorer, never modified; imported programmatically by experiment scripts), `README.md`.

| Metric | Definition |
|---|---|
| **micro-F1** | Precision/recall over all label instances (per task variant). |
| **macro-F1 (gold-supported)** | F1 averaged only over labels appearing ≥1 time in gold. |
| **Direction Reverse Rate (DRR)** — Task-1b/2b only | Fraction of gold Level-1 values (with a unique gold direction) predicted with the **opposite** direction. Gold cases where the same `l1_value` carries **both** directions within one instance are filtered out. On the dev set the DRR denominator is **2222** gold-exclusive values (84 ambiguous gold values filtered), a constant across all reports here. Lower is better. |

Standing evaluation conventions used across experiments:

- All comparisons are on the official **dev** set (177 articles) with the unchanged `evaluation.py`.
- Task-1a predictions are, in the V2/V3 pipelines and DeBERTa-derived systems, **deterministically derived** from Task-1b via the L1→L2 mapping (documented per run; e.g., hybrid variants H1/H3 report Task-1a "derived solely from their Task-1b mapping").
- One documented protocol caveat: Pipeline V2/V3 metrics files evaluate on "successful guids only" (gold filtered to schema-valid articles); in the cited complete runs this equals all 177 articles, so no filtering was actually in effect (`run_status.json` in each run).

---

## 5. Repository Architecture

| Path | Role |
|---|---|
| `README.md`, `CLAUDE.md` | Benchmark description, task/schema/metric reference, baseline usage. |
| `evaluation.py` | Official scorer (micro/macro F1, DRR). **Never modified**; a repeated invariant in every experiment report. |
| `dataset/` | Official train/dev/test data, gold labels, taxonomy, example prediction formats. |
| `src/run_pipeline.py`, `src/prompts.py` | Original GPT-4o(-mini) few-shot baseline (Pipeline V1). |
| `src/run_pipeline_deepseek_flash.py` | DeepSeek Flash adaptation of the V1 prompt (produced the strong `Prompt_DS_Flash` baseline). |
| `src/train_deberta.py` | DeBERTa-v3-base + LoRA (r=16, α=32) trainer, 108-class multi-label head, BCE loss with sqrt pos-weight, threshold 0.3. |
| `src/hybrid_pipeline.py`, `src/hybrid_v2.py` | Hybrid v1 (LLM keep/remove verification of DeBERTa candidates) and Hybrid v2 (value-only candidates; LLM assigns direction). |
| `src/run_pipeline_prompt_v2.py`, `src/prompts_task1_v2.py`, `src/task1_v2_schema.py`, `src/task1_v2_taxonomy.py` | Pipeline V2: strict all-or-nothing validation, no silent failure→empty-prediction conversion, identity-bound cache (provider/model/prompt hash/taxonomy hash/article hash/success status), L1+direction-only output with 1a derived. |
| `src/run_pipeline_prompt_v3.py`, `src/prompts_task1_v3.py`, `src/task1_v3_ensemble.py`, `src/calibrate_task1_v3.py` | Pipeline V3: two prompt variants (A concise balanced, B targeted recall with TRAIN-only demos), compact verifier for uncertain `(actor, l1)` pairs, deterministic ensemble stages, optional frozen label-aware policy; calibration script (implemented and unit-tested; **no calibration run artifacts exist in `output/`**). |
| `src/regenerate_deberta_predictions.py`, `src/collect_results.py` | Checkpoint re-inference with provenance; results collection. |
| `liu_method/run_pipeline.py`, `liu_method/label_aware_ensemble.py` | Liu's reference method (read-only reference code; audited in `docs/liu_method_pipeline3_audit.md`). |
| `research/` | Method-design and tooling modules: label diagnosis, augmentation method design (`fehu_augmentation_v1/METHOD_DESIGN.md`), generation model/cost strategy, experiment registry & output naming, submission-safety format guards, tiny-pilot scripts, and the mirrored safe-sync artifact set `research/fehu_dra_sync_20260705/`. |
| `output/` | All experiment outputs, one timestamped folder per run, **never overwritten** (standing rule documented in `output/research_handoffs/20260704_after_raw_generation_handoff.md`). `output/research_*` folders are research experiments; `output/task1*` folders are pipeline prediction sets. |
| `tests/` | 124 unit tests: `test_task1_prompt_v2.py` (45), `test_task1_prompt_v3.py` (34), `test_task1_v3_ensemble.py` (33), `test_task1_v3_calibration.py` (12). |
| `docs/` | `liu_method_pipeline3_audit.md` (audit of Liu's method vs. Pipeline V3) and this summary. |
| `HYBRID_ROADMAP.md` | Historical design note: diagnosis of Hybrid v1 failure and the v2 design (value-only candidates + LLM direction). |

Standing working principles (recorded in `output/research_handoffs/20260704_after_raw_generation_handoff.md` and repeated in run reports): no fallback implementations; no silent model/provider switching; official dataset files and `evaluation.py` are never modified; every run in a fresh timestamped folder; API keys read from `.env` at call time only and never printed or stored in outputs (leak scans documented per generation run).

---

## 6. Research Methodology

Four strands, in the order they entered the project:

### 6.1 Prompt-only LLM classification
The V1 baseline (`src/run_pipeline.py`) builds a few-shot system prompt (54 L1 values, domain patterns, 2 train demonstrations) and asks GPT-4o(-mini) for per-actor L1+direction JSON. A DeepSeek Flash port of this prompt became the strongest early system. Pipeline V2 rebuilt this as a zero-shot, taxonomy-grounded, strictly validated pipeline whose core guarantees (from the module docstring of `src/run_pipeline_prompt_v2.py`) are: failures are never converted into empty predictions; all-or-nothing schema validation with no silent repair or direction normalization; fully identity-bound caching; model outputs L1+direction only. Pipeline V3 added a two-generator prompt ensemble (variant A precision-leaning, variant B recall-leaning with TRAIN-only demonstrations), a compact verifier call for uncertain pairs, deterministic ensemble stages (`variant_a`, `variant_b`, `union`, `intersection`, `verified`, `final`), and treats deterministic HTTP 4xx errors as configuration errors that abort the run.

### 6.2 DeBERTa student classifier
`src/train_deberta.py`: `microsoft/deberta-v3-base` with LoRA (r=16, α=32, dropout 0.1, query/value projections; 589,824 trainable params = 0.32%), a 108-way multi-label sigmoid head, BCEWithLogits with `sqrt(neg/pos)` pos-weight clamped to [1,10], AdamW lr 2e-4, cosine schedule with 10% warmup, batch 8 × grad-accum 4, ≤15 epochs, early stopping patience 4 on dev Task-1b micro-F1, inference threshold 0.3, seed 42.

### 6.3 DRA-FEHU: diagnosis-driven, label-conditioned augmentation
Method design in `research/fehu_augmentation_v1/METHOD_DESIGN.md`: augmentation must be label-conditioned — rare, over-predicted, direction-flipped, and absent labels need different treatments. The workflow, executed over June–July 2026, was: per-label diagnosis → human-gated candidate generation (DeepSeek V4 Pro) → deterministic structural validation → AI-assisted semantic verification (with Fable 5 / Claude Code as screener in round 1) → human ACCEPT decisions for the small verified pool → controlled A/B training runs. Model roles were fixed in advance by `research/fehu_generation_model_strategy/MODEL_SELECTION_AND_COST_STRATEGY.md` (generator vs. independent verifier; the strongest teacher must not verify its own generations).

### 6.4 Inference-time hybrids
Hybrid v1 (DeBERTa candidates + LLM keep/remove) failed and its failure analysis (`HYBRID_ROADMAP.md`) produced the guiding decomposition used for the rest of the project: **DeBERTa is good at finding which values are relevant (recall) but catastrophically bad at direction (DRR ≈ 0.24); prompt-LLMs are precise on direction (DRR ≈ 0.02)**. Hybrid v2 therefore passes direction-neutral value candidates to the LLM, which decides relevance and assigns direction. The final hybrid (July 14) instantiates this with the Augmented DeBERTa v2 model as candidate supplier and Liu's strongest prompt running on DeepSeek V4 Flash as the frozen base, verifier, and direction assigner.

---

## 7. Research Timeline

Reconstructed from git history (`git log`), timestamped output folders, and per-run reports.

| Date (2026) | Milestone | Evidence |
|---|---|---|
| 05-13 | Initial commit (benchmark code + baseline). | commit `c37a775` |
| 05-17 | DeBERTa LoRA training + hybrid verification pipeline added; V1 baseline runs. | commit `4142f10`; `output/task1*/` |
| 05-18 | Hybrid v1 failure diagnosed; Hybrid v2 design written. | `HYBRID_ROADMAP.md` |
| 06-13 | **Label diagnosis** over 7 methods (professor-requested per-label recall/precision, frequent→rare); project audit (2 CRITICAL, 4 HIGH engineering issues). | `output/research_label_diagnosis/…`, `output/research_project_audit/20260613_151432/` |
| 06-14 | Repair session: provenance/cache/output-collision fixes to `src/` scripts; experiment registry + output naming convention; augmentation METHOD_DESIGN. | `research/fehu_repair_and_augmentation_v1/FINAL_SUMMARY.md`, `output/research_experiment_registry/20260614_123732/` |
| 06-16 → 07-02 | Human-gated candidate chain: human approval of generation requests, tiny pilot generation/repair, AI verification, L1=12 replacement, **verified pool of 6 human-ACCEPTed candidates**. | `output/research_human_approval/20260616_004845/`, `output/research_ai_verification/20260626_214148/`, `output/research_verified_candidates/20260702_165107/` |
| 07-04 | **Controlled smoke run** (A/B: official train vs. +6 verified candidates); expansion planning (pool 6→30); DeepSeek API readiness; **72 raw candidates** generated (DeepSeek V4 Pro). | `output/research_ablation_smoke_runs/20260704_201355/`, `output/research_expanded_augmentation_planning/20260704_214251/`, `output/research_expanded_raw_generation/20260704_222249/`, handoff doc |
| 07-05 | Semantic verification of the 72; **safe research state synced** to branch `sync-safe-fehu-dra-20260705`, artifacts mirrored in `research/fehu_dra_sync_20260705/`. | commit `ee5add9`, `output/research_semantic_verification_expanded/20260705_005015/` |
| 07-12 | **Round-1 AI-filtered silver dataset** (350 new + 72 previous → 340 retained); **Augmented DeBERTa v1** trained and evaluated (negative result). | `output/research_first_round_ai_filtered_augmentation/20260712_214315/`, `output/research_augmented_deberta_v1/20260712_231751/` |
| 07-13 | **Pipeline V2** full dev run (DeepSeek Flash); **Pipeline V3** full dev run with ablation stages; Liu-method audit; **round-2 label-aware generation** (18 direction:L1 targets, 900 raw records, structural stage only — semantic screening not run). | `output/task1_prompt_v2/20260713_111745_…`, `output/task1_prompt_v3/20260713_143858_…`, `docs/liu_method_pipeline3_audit.md`, `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/` |
| 07-14 | **Augmented DeBERTa v2-Unfiltered** (masked loss, 2468 articles); **DeBERTa v2 × Liu Flash hybrid** (H0–H3 + ablations) — the current best dev results. | `output/research_augmented_deberta_v2_unfiltered/20260714_032758/`, `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/` |
| 07-19 | Research state committed: prompt v2–v3, Liu method, calibration, tests, documentation. | commit `6b6f4cc` |

---

## 8. Experimental Data and Augmentation Process

### 8.1 Data assets produced (chronological)

| Asset | Size | Status | Evidence |
|---|---|---|---|
| Verified pool | **6** candidates (incl. complete L1=12 and L1=38 aligned/contradictory pairs) | Human `ACCEPT`; `verified_for_candidate_pool=true`; `training_ready=false` | `output/research_verified_candidates/20260702_165107/01_verified_augmented_candidates.jsonl`; handoff doc |
| Expanded raw candidates | **72** (6 L1 targets × 2 directions) | Raw only; DeepSeek V4 Pro; 28 calls, ~93k tokens; local validation 67 PASS / 5 REVIEW / 0 FAIL | `output/research_expanded_raw_generation/20260704_222249/` |
| Round-1 silver dataset | **340** retained of 422 (350 new + 72 previous) | **AI-filtered synthetic silver** — machine-generated + machine-screened (Fable 5), not human-verified; `training_ready=false`, `eligible_for_preliminary_training=true` | `output/research_first_round_ai_filtered_augmentation/20260712_214315/08_final_ai_filtered_silver_candidates.jsonl` |
| Round-2 label-aware records | **900** raw (all structurally valid) | **Unscreened**: structural validation only; Fable 5 semantic screening explicitly NOT run | `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/04_new_900_raw_candidates.jsonl` |
| Combined unfiltered set | **1240** = 340 + 900 | Mixed provenance as above | same run, `06_unfiltered_combined_340_plus_valid.jsonl` |

### 8.2 Round-1 generation and screening (run `20260712_214315`)

- Generator: DeepSeek V4 Pro (confirmed by API `model` field; no fallback model). 152 successful calls, 740,979 tokens; 67 model-side candidates rejected by deterministic checks and regenerated. Allocation: 6 L1 targets (22, 30, 38, 12, 5, 46) × 2 directions = 175 aligned + 175 contradictory.
- Deterministic local validation on the merged 422: 3798 per-candidate checks, **0 FAIL / 1 WARN** (a known actor collision, resolved by DROP).
- Fable 5 semantic screening of all 422: **337 KEEP_AS_IS, 3 LIGHT_REPAIR, 82 DROP → 340 retained (80.6%)**. Dominant drop reason: template redundancy (65 of 82). The 3 repairs were evidence-sentence reselection only (no change to labels, direction, actor, or article text).
- Final label balance: 167 aligned / 173 contradictory across the six L1 targets (largest: L1=22 with 87; smallest: L1=46 with 29).

### 8.3 Round-2 label-aware generation (run `20260713_163751`)

- **Target selection (frozen, deterministic)** (`02_selected_targets_and_allocation.json`): from a 51-class candidate universe, a class became a target iff train gold count ≤130 **and** dev support ≥3, ranked by evidence strength; top 18 kept with two documented swaps (0:6 out, 0:28 in for 1:20). The **18 direction:L1 targets**: `0:31, 0:48, 0:53, 1:31, 0:16, 1:10, 0:19, 0:20, 1:49, 0:13, 0:37, 0:29, 1:4, 0:2, 0:33, 0:32, 0:40, 0:28` (14 contradictory / 4 aligned, spanning 12 of 20 L2 groups).
- **Allocation:** exactly 18 × 50 = 900 records across four strategies: `targeted_icl` 450 (full multilabel supervision, 2–5 labels each), `contrastive` 180 (90 direction pairs), `transformation` 180, `hard_negative` 90 (36 of which carry a known-negative class). Supervision modes: 450 `full_multilabel` + 450 `target_only`.
- Generation: DeepSeek V4 Pro, 948 calls (273 retries), 4,333,725 tokens, 472 candidates rejected at generation time by structural gates. All 900 final records passed structural validation (0 invalid).
- **Semantic screening was not performed** (documented scope note in `07_structural_stage_report.md`); the combined 1240-record set is explicitly labeled *unfiltered*.

### 8.4 Training-set constructions

| Training set | Composition | Used by |
|---|---|---|
| Official baseline | 1228 articles / 3335 actor examples | DeBERTa baseline (`output/research_ablation_smoke_runs/20260704_201355/baseline/`) |
| Smoke-run augmented | 1228 + 6 verified = 1234 articles / 3341 actor examples | Smoke run condition B |
| Augmented v1 | 1228 + 340 silver = **1568 articles** (24/24 integrity checks PASS; real generated headline used as title to avoid label leakage) | `output/research_augmented_deberta_v1/20260712_231751/` |
| Augmented v2 | 1228 + 340 + 900 = **2468 articles** / 4575 actor examples; per-example 108-dim loss masks (3785 fully supervised, 790 `target_only` masked); 18/18 input checks PASS | `output/research_augmented_deberta_v2_unfiltered/20260714_032758/` |

---

## 9. Completed Experiments (registry)

Status legend: **Verified** = complete run with metrics from the official evaluator; **Partial** = run incomplete or metrics on a subset; **Blocked** = planned comparison that could not be executed (documented reason); **Prep-only** = data/tooling stage with no model evaluation.

| # | Experiment | Run folder | Status |
|---|---|---|---|
| 1 | V1 prompt baselines (GPT-4o-mini / GPT-4o; DeepSeek Flash port) | `output/task1_prompt/`, `output/task1_prompt_deepseek_v4_flash/` | Verified (metrics via diagnosis run) |
| 2 | DeBERTa-only (original) | `output/task1_deberta/` | Verified (via diagnosis run) |
| 3 | Hybrid v1; Hybrid v2 (DS Pro / DS Flash / OAI) | `output/task1_hybrid/`, `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/`, `..._v4_flash/`, `output/task1_hybrid_v2/` | Verified (via diagnosis run) |
| 4 | Label diagnosis (7 methods, per-label, 108-class) | `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/` (+ two 20260613 runs) | Verified (diagnostic) |
| 5 | Controlled smoke run A/B (+6 verified candidates) | `output/research_ablation_smoke_runs/20260704_201355/` | Verified (explicitly labeled smoke run, not a thesis result) |
| 6 | Round-1 silver dataset preparation | `output/research_first_round_ai_filtered_augmentation/20260712_214315/` | Prep-only (dataset complete) |
| 7 | Augmented DeBERTa v1 | `output/research_augmented_deberta_v1/20260712_231751/` | Verified (negative result) |
| 8 | Pipeline V2 full dev run (DeepSeek Flash) | `output/task1_prompt_v2/20260713_111745_deepseek_deepseek_v4_flash/` | Verified (COMPLETE, 177/177) |
| 9 | Pipeline V2 other runs (DS Pro; GPT-5.6-sol; GPT-4o) | `output/task1_prompt_v2/20260713_003652_…` (174/177), `20260713_012432_…` (169/177), `20260713_001308_openai_gpt_4o` (limit 3, test mode) | Partial (INCOMPLETE runs / smoke; metrics only on succeeded subsets — not comparable to full runs) |
| 10 | Pipeline V3 full dev run + stage ablation | `output/task1_prompt_v3/20260713_143858_dev_deepseek_deepseek_v4_flash/` | Verified (COMPLETE, 177/177, 531 API calls) |
| 11 | Pipeline V3 calibration (`src/calibrate_task1_v3.py`) | — | Not executed (script + 12 unit tests exist; no run artifacts in `output/`) |
| 12 | Round-2 label-aware generation (structural stage) | `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/` | Prep-only; semantic screening stage **not run** |
| 13 | Augmented DeBERTa v2-Unfiltered (masked loss) | `output/research_augmented_deberta_v2_unfiltered/20260714_032758/` | Verified (single seed) |
| 14 | Liu targeted run (local frozen) | `output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000/` | Verified (re-evaluated exactly: 0.534750) |
| 15 | Liu majority-vote and label-aware-ensemble comparisons | — | **Blocked** (required artifacts absent from repo; see §12) |
| 16 | DeBERTa v2 × Liu Flash hybrid (H0–H3 + 3 ablations) | `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/` | Verified (single API pass, temperature 0.1) |

---

## 10. Experimental Results

All numbers below are Task-1 dev results from the official evaluator, quoted from the named run folder. Tables are kept separate per run; do not mix rows across tables when citing.

### 10.1 Early-system diagnosis (run `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/`)

| Method | 1a µF1 | 1a MaF1 | 1b µF1 | 1b MaF1 | 1b P | 1b R | DRR (reversals) |
|---|---|---|---|---|---|---|---|
| Prompt_OAI (V1, GPT) | 0.4810 | 0.2740 | 0.3424 | 0.1496 | 0.5696 | 0.2448 | 0.0212 (47) |
| **Prompt_DS_Flash** | 0.6331 | 0.4578 | **0.4964** | 0.3003 | 0.5899 | 0.4285 | 0.0279 (62) |
| DeBERTa_only (original) | 0.5056 | 0.1342 | 0.2989 | 0.0328 | 0.2552 | 0.3607 | 0.2376 (528) |
| Hybrid_v1 | 0.4652 | 0.1958 | 0.2390 | 0.0334 | 0.2111 | 0.2753 | 0.0743 (165) |
| Hybrid_v2_DS_Pro | 0.5720 | 0.2504 | 0.4488 | 0.1258 | 0.6705 | 0.3372 | 0.0252 (56) |
| Hybrid_v2_DS_Flash | 0.5410 | 0.2291 | 0.4153 | 0.1119 | 0.5984 | 0.3180 | 0.0257 (57) |
| Hybrid_v2_OAI_old | 0.4750 | 0.1922 | 0.3331 | 0.0822 | 0.5291 | 0.2431 | 0.0293 (65) |

Key diagnostic findings (same report; `research/fehu_augmentation_v1/METHOD_DESIGN.md`): rare-tertile direction-aware recall is 0.099 for Prompt_DS_Flash, 0.055 for Prompt_OAI, and **0.000 for every other method**; DeBERTa's per-label direction-reversal rate reaches 0.90 on "Be just"; Hybrid v1 is worse than both parents because the keep/remove-only verifier cannot fix DeBERTa's wrong directions.

### 10.2 Controlled smoke run (run `output/research_ablation_smoke_runs/20260704_201355/`)

Baseline (1228 articles) vs. +6 verified candidates, identical everything else, seed 42:

| Metric | Baseline | Augmented (+6) | Δ |
|---|---|---|---|
| 1b micro-F1 | 0.3023 | 0.3060 | +0.0037 |
| 1b macro-F1 | 0.0305 | 0.0309 | +0.0004 |
| DRR | 0.2165 (481) | 0.1620 (360) | −0.0545 |
| L1=12 / L1=38 recall | 0 / 0 | 0 / 0 | 0 |

Documented corrected interpretation (handoff `output/research_handoffs/20260704_after_raw_generation_handoff.md`): the DRR drop mostly came from L1=45 "Be just," which the 6 candidates never touched, so it is a **training-trajectory effect, not an augmentation effect**. Rare-label recall goal not achieved; single seed; not a thesis result.

### 10.3 Augmented DeBERTa v1 (run `output/research_augmented_deberta_v1/20260712_231751/`)

1568 articles (1228 + 340 silver), unmodified trainer, seed 42, threshold 0.3. **Negative result, no improvement claimed** (per the run report):

| Metric | Baseline (1228) | Augmented v1 (1568) |
|---|---|---|
| 1a micro-F1 / macro-F1 | 0.5090 / 0.1351 | 0.5091 / 0.1351 |
| 1b micro-F1 / macro-F1 | 0.3023 / 0.0305 | 0.3009 / 0.0261 |
| DRR | 0.2165 | 0.1364 |
| Distinct predicted 1b classes | 6 | 5 |

All six round-1 target L1 values remain at exactly zero recall (TP=0, FP=0). Both conditions saved their best checkpoint at **epoch 1**. The DRR "improvement" lies inside the model's own epoch-to-epoch DRR range (0.1314–0.2151) and is explicitly not claimed. The report's documented diagnosis: model selection by overall micro-F1 plus the fixed 0.3 threshold plausibly destroys any rare-label signal before it can surface.

### 10.4 Pipeline V2 and V3 (prompt-only, DeepSeek V4 Flash)

Pipeline V2 full run (`output/task1_prompt_v2/20260713_111745_deepseek_deepseek_v4_flash/`, COMPLETE 177/177, 177 API calls): 1a micro 0.5195 / macro 0.3974; **1b micro 0.3976 / macro 0.2247**, P 0.5171, R 0.3230, DRR 0.0288 (64). Note: this strict zero-shot pipeline scores below the older few-shot `Prompt_DS_Flash` baseline (0.4964) on 1b micro-F1 but far above every V1-era system on 1b macro-F1 except Prompt_DS_Flash.

Pipeline V3 full run with stage ablation (`output/task1_prompt_v3/20260713_143858_dev_deepseek_deepseek_v4_flash/ablation_summary.md`, COMPLETE 177/177, 531 calls):

| Stage | 1a µF1 | 1b µF1 | 1b MaF1 | 1b P | 1b R | DRR |
|---|---|---|---|---|---|---|
| variant_a (concise balanced) | 0.4439 | 0.3361 | 0.2108 | 0.4534 | 0.2669 | 0.0252 |
| **variant_b (targeted recall)** | 0.5954 | **0.4628** | **0.3031** | 0.4986 | 0.4318 | 0.0360 |
| union | 0.6006 | 0.4549 | 0.3036 | 0.4391 | 0.4720 | 0.0446 |
| intersection | 0.4111 | 0.3287 | 0.1923 | 0.5969 | 0.2268 | 0.0167 |
| verified (= final) | 0.5487 | 0.4455 | 0.2465 | 0.5437 | 0.3774 | 0.0225 |

The recall-oriented variant B is the strongest single stage; the verifier stage trades micro/macro-F1 for precision and DRR.

### 10.5 Augmented DeBERTa v2-Unfiltered (run `output/research_augmented_deberta_v2_unfiltered/20260714_032758/`)

Masked-loss trainer (`scripts/train_deberta_masked_v2.py`, a copy of `src/train_deberta.py` with per-example loss masks; original not modified), 2468 articles, seed 42, threshold 0.3, best epoch **11** (vs. epoch 1 in all previous DeBERTa runs), training 10m31s on an RTX 4090:

| Metric | Baseline | Augmented v1 | **Augmented v2-Unfiltered** |
|---|---|---|---|
| 1a micro / macro F1 | 0.5090 / 0.1351 | 0.5091 / 0.1351 | **0.5405 / 0.3420** |
| 1b micro / macro F1 | 0.3023 / 0.0305 | 0.3009 / 0.0261 | **0.3306 / 0.1303** |
| 1b precision / recall | 0.2664 / 0.3494 | 0.3061 / 0.2958 | 0.2381 / **0.5406** |
| DRR | 0.2165 (481) | 0.1364 (303) | 0.2880 (640) |
| Distinct 1b classes predicted | 8 | 6 | **50** |

Per-target (of the 18 round-2 targets; recall was 0.0 for all 18 in baseline and v1): **recovered with non-zero recall:** 0:2 (0.4286), 0:29 (0.2857), 0:28 (0.2381), 1:10 (0.2000), 0:33 (0.0833); 0:32 is predicted (18 predictions) but with 0 recall; the other 12 targets have zero predictions. Documented caveats: single seed; precision −11% relative and DRR worsened to 0.2880; the 900 unscreened records' label noise is now in the model; no threshold sweep.

### 10.6 Liu reference method (frozen local run)

`output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000/`, re-evaluated exactly in the hybrid preflight audit (`output/research_hybrid_deberta_v2_liu_flash/20260714_184515/01_preflight_artifact_audit.md`): **1b micro 0.534750**, P 0.5677, R 0.5054, macro 0.3385, DRR 0.0230 (51/2222); 1a micro 0.6447, macro 0.4777; 88 distinct 1b classes.

Three reported Liu numbers, audited:

| Number | Status |
|---|---|
| 0.5347 | **Reproduced exactly** from the frozen local run (hash-pinned). |
| 0.5387 (Liu's slides, same variant) | Not locally reproducible; attributed to run-to-run API variance on a different machine/cache. Never mixed with local numbers. |
| 0.5657 (label-aware ensemble) | **BLOCKED**: `liu_method/label_aware_ensemble.py` requires a majority-vote base run whose predictions and producing script are absent from the repository. |

### 10.7 Final hybrid: DeBERTa v2 × Liu Flash (run `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/`)

Inference-time only (no training; SHA256-verified that no existing artifact changed). One DeepSeek V4 Flash call per article carries Liu's exact prompt plus a review section with (A) Liu's frozen predictions, (B) DeBERTa v2 **direction-neutral** L1 candidates at threshold 0.30 (candidate recall 0.6134 of gold directed labels; 0.951 at threshold 0.10), and (C) official definitions plus project-authored confusion notes. DeepSeek verifies value relevance, assigns direction (DeBERTa's directional probabilities never shown), and may keep/flip/remove Liu predictions.

| System | 1b µF1 | 1b MaF1 | 1b P | 1b R | DRR (rev.) | classes | 1a µF1 | 1a MaF1 |
|---|---|---|---|---|---|---|---|---|
| DeBERTa baseline (official-only) | 0.3023 | 0.0305 | 0.2664 | 0.3494 | 0.2165 (481) | 8 | 0.5090 | 0.1351 |
| Augmented DeBERTa v2-Unfiltered | 0.3306 | 0.1303 | 0.2381 | 0.5406 | 0.2880 (640) | 50 | 0.5405 | 0.3420 |
| **H0 Liu targeted (local frozen)** | 0.5347 | 0.3385 | 0.5677 | 0.5054 | 0.0230 (51) | 88 | 0.6447 | 0.4777 |
| H1 closed verifier (DeBERTa candidates only) | 0.4921 | 0.2240 | 0.5420 | 0.4506 | 0.0293 (65) | 60 | 0.6102 | 0.3753 |
| **H2 Liu + verified additions** | 0.5433 | **0.3603** | 0.5038 | **0.5895** | 0.0356 (79) | 89 | 0.6598 | **0.5038** |
| **H3 full revision** | **0.5474** | 0.3382 | 0.5480 | 0.5469 | 0.0311 (69) | 85 | **0.6617** | 0.5032 |
| Ablation: raw union | 0.3859 | 0.2703 | 0.2654 | 0.7067 | 0.2975 | 88 | 0.5722 | 0.4311 |
| Ablation: intersection (actor:L1) | 0.4250 | 0.1711 | 0.4502 | 0.4025 | 0.2066 | 55 | 0.5775 | 0.3224 |
| Ablation: Liu + **unverified** DeBERTa | 0.4057 | 0.2793 | 0.2887 | 0.6820 | 0.1107 | 88 | 0.5722 | 0.4311 |

Verified findings from the run report:

- **H3 beats Liu** on 1b micro (+0.0127), recall (+0.0415), 1a micro (+0.0170) and 1a macro (+0.0255) at −0.0197 precision and +18 reversals; **H2 is the macro/recall point** (macro +0.0218, recall +0.0841 vs. Liu).
- **Verification is load-bearing**: the same DeBERTa additions unverified collapse precision to 0.289; DeepSeek rejected 2264 of 4251 candidate reviews (53.3%).
- Direction discipline held: DeepSeek flipped only 12 of Liu's 2128 predictions and removed 161; hybrid DRR stays ≤0.036 vs. 0.288 for DeBERTa v2 alone.
- Complementarity (of 2390 gold directed labels): Liu-only 397, DeBERTa-only 481, both 811, neither 701. H2 recovered 201 Liu-missed gold labels (adding 468 false positives); H3 recovered 143, lost 44, added 158 FPs.
- **18-target effect**: H2 lifts 6 targets above Liu (e.g., 0:2 recall 0.143→0.429, 0:28 0.048→0.143) and never drops a target below Liu. **Four targets have zero predictions in every system: 0:48, 0:16, 0:19, 1:49.**
- Best current dev prediction files (as designated in the report): `15_pred_task1a_h3.json` + `16_pred_task1b_h3.json` (micro/1a optimum), with `13/14_…_h2.json` as the macro/recall alternative.
- Stated limitations: single API pass at temperature 0.1 with no seed replication; the Liu label-aware (0.5657) and majority-vote comparisons remain BLOCKED.

---

## 11. Bugs, Corrections, and Documented Research Decisions

### 11.1 Data and upstream bugs
- **Actor-alignment bug in gold labels** (upstream, fixed before this project's experiments): versions before upstream commit `af52dcb` (2026-03-20) had misaligned actors in train/dev gold labels. Current data is corrected (`README.md`, `CLAUDE.md`).

### 11.2 Engineering issues found by the 2026-06-13 audit and repaired on 2026-06-14
(`research/fehu_repair_and_augmentation_v1/FINAL_SUMMARY.md`; audit in `output/research_project_audit/20260613_151432/`)
- `--model` did not reach the API in `src/run_pipeline.py` (CRITICAL C1) — fixed.
- Output-directory collision between pipeline and DeBERTa outputs (CRITICAL C2) — fixed via `output/task1_deberta/` default and per-run `run_config.json`.
- Cache files not keyed by provider/model; `--limit` runs scored against full gold; missing provenance metadata — all fixed; overwrite-safe timestamped outputs introduced.

### 11.3 Pipeline V1-era defects motivating Pipeline V2
(docstring of `src/run_pipeline_prompt_v2.py`; `docs/liu_method_pipeline3_audit.md`)
- Old pipelines converted API/parse failures into empty predictions and cached them as valid; caches were not bound to prompt content; silent JSON repair and direction normalization could alter predictions. Pipeline V2's invariants (no silent failures; all-or-nothing validation; identity-bound cache; failed entries never reused) were designed specifically against these defects and are enforced by 45 unit tests (`tests/test_task1_prompt_v2.py`).

### 11.4 Defects documented in Liu's reference code (audited, deliberately not copied)
(`docs/liu_method_pipeline3_audit.md`)
- Parser silently coerces any direction other than `"contradictory"` (including absent) to aligned; all-retries-failed articles are cached as empty predictions; cache has no prompt/article hash.
- Few-shot demonstrations truncate gold outputs to the first 4 items, teaching under-prediction.
- The label-aware ensemble add-list is **dev-fitted** (selected by scoring on the same 177 reporting articles) — identified as partial dev leakage; the majority-vote producer script is absent, making that number unauditable.

### 11.5 Corrected interpretations and mid-run fixes
- **Smoke-run DRR misattribution corrected**: the −25% DRR delta was traced mainly to L1=45 ("Be just"), untouched by the 6 added candidates; recorded as a trajectory effect (`output/research_handoffs/20260704_after_raw_generation_handoff.md`).
- **Augmented-v1 DRR delta not claimed**: within the model's own epoch-to-epoch DRR variance (report §10, §14).
- **Label-leak avoidance in silver conversion**: the 2026-07-02 pool used constructed marker titles containing the target label name; reusing them would have leaked labels into model input, so Augmented v1 conversion uses the candidates' real generated headlines (`output/research_augmented_deberta_v1/.../report/` §4).
- **Evidence-quote mismatch fix during round-1 generation**: the first launch was aborted after ~13 calls because DeepSeek quoted evidence with typographic-quote/whitespace variants; a deterministic exact-sentence recovery step was added and the rejection rate dropped (`10_first_round_report.md` §2).
- **DeepSeek Flash thinking-token cap**: in the hybrid run, 4 articles exceeded the 8000-token output cap on provider-default reasoning alone; thinking was explicitly disabled for only those 4 articles, documented in `21_structural_validation.md`.
- **The "128 cutoff" is a legacy description, not a coded rule**: no code used 128; the diagnosis used ≤120 and the frozen round-2 selector used ≤130 + ranking; 128 is simply the maximum observed train support among the 18 selected targets. The literal rule would select 39 classes (a strict superset); the divergence is documented, with a sensitivity analysis, in `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/` (`06_target_rule_sensitivity.csv`, report §4).
- **Local vs. external result separation**: Liu's 0.5387 (his machine) is never mixed into local tables; only the locally frozen, hash-pinned 0.5347 run is compared against.

### 11.6 Standing methodological decisions (documented, still in force)
- Verifier independence: the generation model must not verify its own outputs (`research/fehu_generation_model_strategy/MODEL_SELECTION_AND_COST_STRATEGY.md`).
- Every dataset artifact carries explicit status flags (`verified_for_candidate_pool`, `training_ready`, `eligible_for_preliminary_training`); no synthetic record has ever been marked human `training_ready`.
- All experiment folders are append-only and timestamped; protected inputs are SHA256-verified before/after each experiment (e.g., 26-artifact hash inventory in the hybrid run's `audit/artifact_hashes.json`).

---

## 12. Current Research State

As of HEAD `6b6f4cc` (2026-07-19):

**Established (verified on dev, single-run):**
- Best overall system: hybrid **H3** (1b micro 0.5474, 1a micro 0.6617); best macro/recall point: **H2** (1b macro 0.3603, recall 0.5895). Both from `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/`.
- Best single LLM system: Liu targeted (frozen) 0.5347. Best in-house prompt pipeline stage: V3 variant B, 0.4628.
- Augmented DeBERTa v2-Unfiltered is the first DeBERTa run in the project whose training moved rare classes (50 predicted classes; 5 of 18 targets with non-zero recall) and whose best checkpoint came late (epoch 11).
- The value/direction decomposition (DeBERTa for value recall, LLM for direction and relevance filtering) is empirically supported by the hybrid ablations.

**Incomplete / partial:**
- Pipeline V2 runs on DeepSeek Pro (174/177) and GPT-5.6-sol (169/177) are INCOMPLETE; their metrics cover only succeeded articles and are not comparable to full runs. Two additional GPT-5.6-sol folders and one early Flash folder contain no metrics (aborted/superseded).
- The V3 calibration module (`src/calibrate_task1_v3.py`) is implemented and unit-tested but has no recorded run artifacts.

**Blocked (documented reasons):**
- Liu majority-vote and label-aware-ensemble (0.5657) comparisons: required prediction artifacts and the majority-vote script are absent from the repository.

**Explicitly not done (recorded as such, not proposed here):**
- Fable 5 semantic screening of the 900 round-2 records (paused by instruction; the trained v2 model therefore contains any label noise from those records).
- Multi-seed replication of any training or API experiment (every report flags single-seed status).
- Threshold sweeps for the DeBERTa models beyond the fixed 0.3.
- Any Task-2 system; any test-set submission run.

**Open empirical facts:** four round-2 targets (0:48, 0:16, 0:19, 1:49) have zero predictions in every system evaluated to date.

---

## 13. Reproducibility and Important File Locations

### 13.1 Environment
- Python project, no build step; conda env `fehu` used for training (`/home/szf-4090/miniconda3/envs/fehu/bin/python` recorded in run scripts); GPU: single RTX 4090.
- API keys are supplied via a git-ignored `.env` (OpenAI / Gemini / DeepSeek variables). Keys are read at call time only; generation runs include leak-scan confirmations. **No key material appears in any tracked file or output.**

### 13.2 Reference commands (as recorded in the repository)

```bash
# V1 baseline
python src/run_pipeline.py --mode dev

# Pipeline V2 / V3 (dev, DeepSeek Flash)
python src/run_pipeline_prompt_v2.py --mode dev --provider deepseek --model deepseek-v4-flash
python src/run_pipeline_prompt_v3.py   # see module docstring for options

# Label diagnosis
python research/fehu_label_diagnosis/label_diagnosis.py

# Augmented DeBERTa v2 (masked loss) — exact frozen script
bash output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_augmented_deberta_v2.sh

# Official evaluation
python evaluation.py \
  --gold_task1 dataset/gold_labels/dev/dev_human_values.json \
  --pred_task1a <pred_task1a.json> --pred_task1b <pred_task1b.json>

# Tests
python -m pytest tests/
```

Fixed experimental constants across DeBERTa runs: seed 42, threshold 0.3, LoRA r=16/α=32, lr 2e-4, ≤15 epochs, patience 4. LLM runs: temperature 0.1; DeepSeek `max_tokens` 8000; JSON-object response format (V2/V3 and Liu configurations documented per run).

### 13.3 Key artifact map

| Artifact | Path |
|---|---|
| Best dev predictions (H3 / H2) | `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/15_pred_task1a_h3.json`, `16_pred_task1b_h3.json` (H2: `13`/`14`) |
| Hybrid experiment report | `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/report/deberta_liu_hybrid_report.md` |
| Augmented DeBERTa v2 checkpoint (best, epoch 11) | `output/research_augmented_deberta_v2_unfiltered/20260714_032758/checkpoint/` |
| Masked-loss trainer | `output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_deberta_masked_v2.py` |
| Round-1 silver dataset (340) | `output/research_first_round_ai_filtered_augmentation/20260712_214315/08_final_ai_filtered_silver_candidates.jsonl` |
| Round-2 raw records (900) + frozen targets | `output/research_label_aware_low_frequency_augmentation_v2/20260713_163751/04_new_900_raw_candidates.jsonl`, `02_selected_targets_and_allocation.json` |
| Verified pool (6, human-ACCEPTed) | `output/research_verified_candidates/20260702_165107/01_verified_augmented_candidates.jsonl` |
| Liu frozen run + cache | `output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000/`, `logs/cache_dev_deepseek_…_max8000.json` |
| Liu method audit | `docs/liu_method_pipeline3_audit.md` |
| Label diagnosis (canonical) | `output/research_label_diagnosis/baseline_diagnosis_full_dev_v1/diagnosis_report.md` |
| DeBERTa official-only baseline (comparison anchor) | `output/research_ablation_smoke_runs/20260704_201355/baseline/` |
| Safe-sync mirror of DRA artifacts | `research/fehu_dra_sync_20260705/` |
| Post-generation handoff (rules + state) | `output/research_handoffs/20260704_after_raw_generation_handoff.md` |
| Output naming convention / registry | `research/fehu_experiment_management/OUTPUT_NAMING.md`, `experiment_registry.py` |
| Submission format guards | `research/fehu_submission_safety/` |

---

*This summary was compiled exclusively from the repository contents listed above. No source code, dataset, experiment artifact, or prior report was modified in its preparation.*
