# Diagnosis-driven Recall-focused Targeted Augmentation for FEHU Human Value Classification

**Status:** *planning stage*. This document describes the method only. **No augmented samples have been generated. No model has been trained. No API has been called.**

---

## 1. Problem

The FEHU benchmark is a fine-grained, **actor-specific**, **multi-label**, **direction-sensitive** classification task: for each (article, actor) pair the model must predict a subset of 54 human values, and for Task-1b a binary direction (aligned / contradictory) for each value.

The post-audit label-diagnosis (run 2026-06-13) reveals three structural problems that uniform augmentation cannot solve:

1. **Long-tailed label distribution.** Train counts range from 4 ("Be neat and tidy") to 2031 ("Be responsible"). A third of L1 labels have ≤ 35 training instances.

2. **Recall collapses on rare labels for every method except Prompt_DS_Flash.** For the rare tertile (18 labels), the micro `recall_dir` is:

   | Method | Rare-tertile recall_dir |
   |---|---|
   | Prompt_DS_Flash | 0.099 |
   | Prompt_OAI | 0.055 |
   | every other method | 0.000 |

3. **DeBERTa is recall-biased on values but catastrophically wrong on direction.** DRR = 0.2376 with 528 reversals (vs. 47 for Prompt_OAI). Per-label direction-reversal rates reach 0.90 for "Be just" — the model predicts the right value but the wrong direction in 9 out of 10 instances.

4. **A handful of frequent labels are over-predicted by DeBERTa / Hybrid v1.** "Be helpful" precision = 0.227 (recall 0.896); "Be honest" precision = 0.134 (recall 0.551). These bleed into Hybrid v1's verification because the LLM is asked to "keep/remove" and cannot reassign direction.

A teacher model (Prompt_DS_Flash) is strong, but using it as the final answer is not a research contribution. The contribution is **a principled, label-conditioned, diagnosis-driven augmentation pipeline** that lets a smaller student (DeBERTa) approach teacher quality, while reducing direction errors.

---

## 2. Principle

> **Augmentation must be label-conditioned.** What a label needs depends on whether it is rare, over-predicted, direction-flipped, or simply absent.

We define four augmentation types and select them per label based on the diagnosis CSVs. No uniform paraphrase pass; no general "augment every class equally" budget.

---

## 3. Augmentation types

### (A) Label-preserving paraphrase augmentation
- **Source:** existing TRAIN article-level gold samples for the target label.
- **Operation:** rewrite the article (or relevant span) while preserving the actor identity, the L1 label, and the direction.
- **Use:** every label that has at least one seed and benefits from recall improvement; primary baseline.
- **Risk:** semantic drift; the rewritten article may no longer convey the value.
- **Mitigation:** teacher verification step that re-classifies the paraphrase and rejects if direction or value changes.

### (B) Rare-positive generation
- **Source:** the L1 value's definition + 1–3 train seed examples (if available).
- **Operation:** generate a short news-style article in which a named actor's behavior clearly expresses the target L1 value, with the specified direction.
- **Use:** labels in `threshold_group ∈ {zero_train, very_rare, rare}` or `tertile_group = rare` whose `recall_dir < 0.30` across most methods.
- **Risk:** synthetic content may be off-distribution (style, topic). May invent facts.
- **Mitigation:** factuality-free framing ("news-style fiction"), evidence sentence requirement, teacher verification, length cap.

### (C) Hard-negative generation
- **Source:** the target L1 value's definition + a related-but-distinct value.
- **Operation:** generate a sample that is topically related to the target value but should NOT be labeled with that value for the named actor — typically because the *other* value is the right one.
- **Use:** labels in `high_false_positive_labels.csv` (precision < 0.30, FP ≥ 5).
- **Risk:** the generator may produce content that is genuinely ambiguous (would be a positive too).
- **Mitigation:** teacher verification step must explicitly reject the target label and explain why.

### (D) Direction-contrastive generation
- **Source:** the target L1 value's definition.
- **Operation:** generate a **pair** of samples — one aligned, one contradictory — for the same L1 value, ideally on a similar topic so the direction is the discriminating signal.
- **Use:** labels in `high_direction_error_labels.csv` with `direction_reverse_rate_label > 0.30` (top examples from the diagnosis: "Be just" 0.90, "Have a stable society" 0.84, "Have a safe country" 0.76).
- **Risk:** the model may produce two highly similar texts that differ only in surface direction words.
- **Mitigation:** require both samples to come from clearly different actor positions (e.g., authority vs. rule-breaker) and contain different evidence.

---

## 4. Target-label selection

The selection logic lives in `build_augmentation_plan.py`. Inputs:

- `rare_low_recall_labels.csv` (rare + recall_dir < 0.30)
- `high_false_positive_labels.csv` (FP ≥ 5, precision_value < 0.30)
- `high_direction_error_labels.csv` (direction_reverse_count > 0)
- `method_gap_analysis.csv` (cross-method failure)
- `label_frequency_l1.csv` (train counts, tertile/threshold groups)

For each L1 label `v` we compute four sub-scores in [0, 1]:

```
rare_score          = 1 - clip(train_count_v / max_train_count, 0, 1)
low_recall_score    = 1 - mean_recall_dir_across_methods_v
direction_error_score = mean_direction_reverse_rate_v_across_methods   (normalized)
false_positive_score = mean(1 - precision_value_v_across_methods over FP-flagged rows)
```

Combined priority:

```
priority_score(v) = 0.40 * rare_score
                  + 0.25 * low_recall_score
                  + 0.20 * direction_error_score
                  + 0.15 * false_positive_score
```

The top-`--max_labels` labels by `priority_score` are kept. For each kept label, we attach the **augmentation type(s)** that triggered its inclusion:

- in `rare_low_recall_labels.csv` → `{rare_positive, paraphrase}`
- in `high_false_positive_labels.csv` → `{hard_negative}`
- in `high_direction_error_labels.csv` → `{direction_contrastive}`

A label may receive more than one type.

---

## 5. Budget policy

Three pre-defined profiles parameterise *how many* augmented samples a label receives. Only `pilot` runs in this first phase.

| Profile | rare_positive | paraphrase | hard_negative | direction_contrastive |
|---|---|---|---|---|
| `pilot` | 3 / label | ≤ 3 / seed, max 9 / label | 3 / label | 2 pairs / label |
| `medium` | 8 / label | ≤ 20 / label | 8 / label | 5 pairs / label |
| `full` | 20 / label | ≤ 50 / label | 20 / label | 10 pairs / label |

The total budget for `pilot` is small by design — it lets us iterate on prompt engineering and the verification filter before committing API spend.

---

## 6. Filtering and validation

Every augmented sample (when it is eventually generated) must pass:

1. **Format validation** — strict JSON Schema (see `augmentation_schema.json`).
2. **Label validity** — `l1_value_id ∈ [0, 53]`, `l2_value_id ∈ [0, 19]`, `direction ∈ {"0", "1"}`, `l2_value_id` matches the L1→L2 mapping for `l1_value_id`.
3. **Actor-specific evidence** — the named actor must appear by name in `content`, and the `evidence_sentence` must reference behavior consistent with the labeled direction.
4. **Duplicate / near-duplicate filter** — exact `content` hash + token-set Jaccard threshold across the pool.
5. **Teacher verification** — an independent LLM call with the verification template (see `augmentation_prompt_blueprints.md`) returns `accept` or `reject` with a reason.
6. **Optional human spot-check** — 5–10 samples per type sampled for manual review before scaling.

`validate_augmented_data.py` implements steps 1–4 locally (no API).

---

## 7. Planned ablation

We will compare these student configurations downstream:

| Configuration | Train data |
|---|---|
| DeBERTa baseline | original train only |
| DeBERTa + paraphrase | original + label-preserving paraphrases |
| DeBERTa + rare positives | original + rare-positive generation |
| DeBERTa + rare positives + hard negatives | original + rare positives + hard negatives |
| DeBERTa + rare positives + hard negatives + direction-contrastive pairs | full augmentation pool |
| Hybrid v2 (DS Pro) on the augmented student | replaces the student in Hybrid v2 candidate generation |

The primary metric is Task-1b direction-aware macro-F1 (because the augmentation targets rare classes that micro-F1 ignores). The secondary metric is DRR — the direction-contrastive set is expected to lower it.

---

## 8. Risks and threats to validity

- **Teacher-student data leakage.** Synthetic positives generated by Prompt_DS_Flash could simply teach DeBERTa to mimic Prompt_DS_Flash on those labels rather than learn the underlying concept. Mitigation: the prompt blueprints intentionally avoid feeding Prompt_DS_Flash's predictions; instead they use the L1 definition + training seeds + behavior schemas.
- **Distribution shift.** Augmented articles will be shorter and more focused than real news. We will monitor length distributions and topical coverage.
- **Over-augmentation of rare classes.** If a rare label receives 20× more synthetic than real positives, the model may over-predict it. The budget profiles cap synthetic volume relative to the real volume.
- **Direction shortcut learning.** A direction-contrastive pair that differs only in lexical direction cues (e.g., "supports vs. violates") could let the model learn the surface rather than the semantics. Mitigation: paired generation must come from different actor positions.

---

## 9. What this stage actually delivers

- A reproducible target-label selection algorithm with documented weights.
- A pilot budget that fits a small API call quota.
- A seed-instance pool extracted **only from TRAIN gold** (Dev gold is never used as content, only as a diagnosis signal for *which* labels to target).
- Prompt blueprints for all four augmentation types + a teacher verifier.
- A strict JSON Schema for any future augmented sample.
- A local-only validator that can be run before any API call.

**No samples are generated at this stage.** The next stage (`research/fehu_augmentation_v1/run_generation.py`, not yet created) will consume `selected_seed_instances.jsonl` and the blueprints to produce real augmented data — at which point the constraints in this document become checks, not promises.
