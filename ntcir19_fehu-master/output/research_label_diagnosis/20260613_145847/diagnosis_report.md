# FEHU Label Diagnosis Report

**Generated:** 20260613_145847  
**Project:** NTCIR-19 FEHU — Task-1 Diagnostic Analysis  

---

## 1. Purpose

This analysis responds to the professor's suggestions for a recall-focused and label-wise
diagnostic evaluation **before** any data augmentation work.

Key questions addressed:

- Which labels are frequent vs. rare?
- Which labels have low recall / low precision per method?
- Which labels have high direction reversal errors (high DRR)?
- Are methods behaving as recall-focused or precision-focused?
- Recall/precision from frequent to rare labels (the professor's main ask)?

> **Constraint**: This report is purely diagnostic. No augmentation, no training, no API calls.

---

## 2. Data and Methods

**Gold labels used:**
- `dataset/gold_labels/train/train_human_values.json` — for label frequency analysis
- `dataset/gold_labels/dev/dev_human_values.json`   — for metric evaluation

**Methods analyzed (7):**
- `Prompt_OAI`
- `Prompt_DS_Flash`
- `DeBERTa_only`
- `Hybrid_v1`
- `Hybrid_v2_DS_Pro`
- `Hybrid_v2_DS_Flash`
- `Hybrid_v2_OAI_old`

**Methods skipped (1):**
- `Hybrid_v2_OAI_mini`: directory does not exist

---

## 3. Overall Results

| Method | 1a µF1 | 1a MaF1 | 1a P | 1a R | 1b µF1 | 1b MaF1 | 1b P | 1b R | DRR | RevCnt |
|---|---|---|---|---|---|---|---|---|---|---|
| Prompt_OAI | 0.4810 | 0.2740 | 0.7223 | 0.3606 | 0.3424 | 0.1496 | 0.5696 | 0.2448 | 0.0212 | 47 |
| Prompt_DS_Flash | 0.6331 | 0.4578 | 0.7093 | 0.5717 | 0.4964 | 0.3003 | 0.5899 | 0.4285 | 0.0279 | 62 |
| DeBERTa_only | 0.5056 | 0.1342 | 0.5162 | 0.4954 | 0.2989 | 0.0328 | 0.2552 | 0.3607 | 0.2376 | 528 |
| Hybrid_v1 | 0.4652 | 0.1958 | 0.4117 | 0.5347 | 0.2390 | 0.0334 | 0.2111 | 0.2753 | 0.0743 | 165 |
| Hybrid_v2_DS_Pro | 0.5720 | 0.2504 | 0.7839 | 0.4503 | 0.4488 | 0.1258 | 0.6705 | 0.3372 | 0.0252 | 56 |
| Hybrid_v2_DS_Flash | 0.5410 | 0.2291 | 0.7375 | 0.4272 | 0.4153 | 0.1119 | 0.5984 | 0.3180 | 0.0257 | 57 |
| Hybrid_v2_OAI_old | 0.4750 | 0.1922 | 0.6625 | 0.3702 | 0.3331 | 0.0822 | 0.5291 | 0.2431 | 0.0293 | 65 |

> `µF1` = micro-F1, `MaF1` = macro-F1 (gold-supported), `P` = micro-precision, `R` = micro-recall.  
> `DRR` = Direction Reverse Rate (lower is better). `RevCnt` = raw direction reversals.

**Best Task-1b Micro-F1:** `Prompt_DS_Flash` = 0.4964  
**Lowest DRR (best direction accuracy):** `Prompt_OAI` = 0.0212  
**Best rare-label avg direction-recall:** `Prompt_DS_Flash` = 0.1197

---

## 4. Label Frequency Distribution

Total L1 label classes: **54**  
Total L1 × direction classes: **108**  

**Tertile groups (18 labels each, by train gold count):**
- Frequent (top-18):   18 labels
- Medium (middle-18):  18  labels
- Rare (bottom-18):    18 labels

**Threshold groups (by raw count):**
- `zero_train` (0):     0 labels
- `very_rare`  (1–5):   1 labels
- `rare`       (6–15):  3 labels
- `medium`     (16–40): 7 labels
- `frequent`   (>40):   43 labels

The distribution is **strongly long-tailed**: a handful of labels dominate training data,
while many rare labels receive very limited supervision.

---

## 5. Per-Label Precision/Recall Findings

*(Sample for method `Prompt_OAI`; see `per_label_l1_metrics.csv` for all methods.)*

### High-Recall Labels

| L1 Value | Rec (dir) | Prec (dir) | F1 (dir) | Train Count |
|---|---|---|---|---|
| Be helpful | 0.6321 | 0.5726 | 0.6009 | 682 |
| Be responsible | 0.5638 | 0.6598 | 0.6080 | 2031 |
| Be just | 0.5194 | 0.6687 | 0.5847 | 1538 |
| Have the wisdom to accept others | 0.5000 | 0.2000 | 0.2857 | 36 |
| Be curious | 0.3889 | 0.5385 | 0.4516 | 122 |

### Low-Recall Labels (with dev gold > 0)

| L1 Value | Rec (dir) | Prec (dir) | F1 (dir) | Train | Dev |
|---|---|---|---|---|---|
| Have a stable society | 0.0000 | 0.0000 | 0.0000 | 1590 | 229 |
| Be capable | 0.0000 | 0.0000 | 0.0000 | 389 | 55 |
| Be broadminded | 0.0000 | 0.0000 | 0.0000 | 311 | 43 |
| Have influence | 0.0000 | 0.0000 | 0.0000 | 243 | 36 |
| Have the own family secured | 0.0000 | 0.0000 | 0.0000 | 174 | 21 |

### Rare + Low-Recall Labels (top-10, suggested for augmentation)

*(method: `Prompt_OAI`)*

| L1 Value | Rec (dir) | Train | Dev | Suggested Action |
|---|---|---|---|---|
| Have loyalty towards friends | 0.0000 | 90 | 13 | `rare_positive_augmentation` |
| Be behaving properly | 0.0000 | 60 | 10 | `rare_positive_augmentation` |
| Have the right to command | 0.0000 | 47 | 2 | `rare_positive_augmentation` |
| Have pleasure | 0.0000 | 45 | 9 | `rare_positive_augmentation` |
| Have a world of beauty | 0.0000 | 44 | 6 | `rare_positive_augmentation` |
| Have a varied life | 0.0000 | 35 | 3 | `rare_positive_augmentation` |
| Be self-disciplined | 0.0000 | 34 | 11 | `rare_positive_augmentation` |
| Be forgiving | 0.0000 | 30 | 3 | `rare_positive_augmentation` |
| Have harmony with nature | 0.0000 | 28 | 4 | `rare_positive_augmentation` |
| Be humble | 0.0000 | 25 | 3 | `rare_positive_augmentation` |

---

## 6. Method-Level Interpretation

### Prompt-only Models

Check `task1b_precision` vs `task1b_recall` in the overall table.
Models with recall > precision are in 'recall-focused' mode; the opposite indicates conservatism.
LLM model choice (OAI vs. DeepSeek Flash) may shift the recall–precision balance on rare labels.

### DeBERTa-only

DeBERTa is trained on actual gold labels with binary classifiers.
Its behavior on frequent labels may differ significantly from rare/zero-train labels.
Check `frequency_group_summary.csv` group-level `micro_recall_dir` and `micro_precision_dir`.
High recall on frequent labels combined with low recall on rare labels would confirm class-imbalance effects.

### Hybrid Methods (v1, v2 DS Pro, v2 DS Flash)

Hybrid methods use DeBERTa for candidate generation and an LLM for verification.
They should reduce direction errors (lower DRR) vs. prompt-only methods.
Compare `drr` column across methods. If Hybrid DRR < Prompt DRR, direction modeling improves.
v2 methods have the most complete run configs; v1 uses GPT-4o-mini as verifier.

### DeepSeek vs. OpenAI

If `Prompt_DS_Flash` shows higher recall than `Prompt_OAI` on rare labels,
this suggests LLM model choice meaningfully affects rare-class recall —
a key input for deciding which backbone to use in the augmentation pipeline.

---

## 7. Research Implications

Based on this diagnostic analysis, the following augmentation strategies are indicated:

### (a) Recall-focused Thresholding

If DeBERTa-only shows high precision but low recall on rare labels,
lowering the classification threshold per-group can recover recall.
Target: labels in `rare` / `very_rare` / `zero_train` threshold groups.

### (b) Traditional Paraphrase Augmentation

Labels with 1–15 train examples (`very_rare`, `rare`) are strong candidates
for synonym replacement and back-translation augmentation.
See `rare_low_recall_labels.csv` for a pre-filtered candidate list.

### (c) LLM-Generated Rare-Class Positives

Labels where **all methods** fail (recall < 0.10) need synthetic positives.
Use an LLM to generate news-style sentences that express the target value.
See `method_gap_analysis.csv` column `all_methods_fail`.

### (d) Hard Negatives for Over-Predicted Labels

Labels with high FP counts and low precision (see `high_false_positive_labels.csv`)
need hard negative training examples — articles that are topically similar but
do **not** express the target value.

### (e) Direction-Contrastive Samples

Labels with high direction-reversal rates (see `high_direction_error_labels.csv`)
need contrastive pairs: one aligned example and one contradictory example for the same value.
This is especially important if `drr` is high across methods.

---

## 8. Important Constraint

> **This report is ONLY diagnostic analysis. No augmentation has been performed.**  
> No models were trained. No APIs were called. No existing files were modified.  
> All analysis uses local prediction files and gold labels only.

---

## Output Files

All outputs saved to: `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_label_diagnosis/20260613_145847`

| File | Description |
|---|---|
| `method_inventory.csv` | Validation table for all candidate result sets |
| `overall_metrics.json/.csv` | Official Task-1a/1b metrics per method |
| `overall_comparison_table.txt` | Plain-text aligned metrics table |
| `label_frequency_l1.csv/.json` | L1 label frequency + tertile/threshold groups |
| `per_label_l1_metrics.csv/.json` | Per-label P/R/F1 per method (54 labels × N methods) |
| `per_class_108_metrics.csv/.json` | Per-class metrics (108 = 54 L1 × 2 directions) |
| `frequency_group_summary.csv/.json` | Group-level micro/macro P/R/F1 |
| `rare_low_recall_labels.csv` | Rare labels with low recall — augmentation candidates |
| `high_false_positive_labels.csv` | Over-predicted labels — hard-negative candidates |
| `high_direction_error_labels.csv` | High direction-reversal labels |
| `method_gap_analysis.csv` | Label-wise method comparison (gains, failure flags) |
| `figures/` | All PNG diagnostic figures |
| `diagnosis_report.md` | This report |
| `diagnosis_run_config.json` | Run metadata |
