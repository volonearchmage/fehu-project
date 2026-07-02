# FEHU Label Diagnosis

Research-grade diagnostic analysis of Task-1 prediction results.
Answers the professor's question: **recall/precision on each label, from frequent to rare**.

## Purpose

Before any data augmentation, this module performs a rigorous per-label analysis:

- Which labels are frequent / rare by train count?
- Which labels have low recall, low precision, or high direction errors?
- Do all methods fail on the same labels?
- Is DeBERTa behaving as a recall-focused or precision-focused model?

## Run

From the project root:

```bash
python research/fehu_label_diagnosis/label_diagnosis.py
```

No arguments needed. All input paths are resolved relative to the project root.

## Output

Results are saved to a timestamped folder (never overwritten):

```
output/research_label_diagnosis/YYYYMMDD_HHMMSS/
```

| File | Description |
|---|---|
| `method_inventory.csv` | Validates all candidate result folders |
| `overall_metrics.json/.csv` | Official Task-1a/1b metrics per method |
| `overall_comparison_table.txt` | Aligned text comparison table |
| `label_frequency_l1.csv/.json` | Train/dev counts + frequency groups for all 54 L1 labels |
| `per_label_l1_metrics.csv/.json` | Per-label P/R/F1 (value-level + direction-aware) per method |
| `per_class_108_metrics.csv/.json` | Per-class metrics for all 108 classes (54 L1 × 2 directions) |
| `frequency_group_summary.csv/.json` | Micro/macro P/R/F1 aggregated by frequency group |
| `rare_low_recall_labels.csv` | Rare labels with recall < 0.30 — augmentation candidates |
| `high_false_positive_labels.csv` | Over-predicted labels — hard-negative candidates |
| `high_direction_error_labels.csv` | Labels with high direction reversal rates |
| `method_gap_analysis.csv` | Label-wise method comparison (gains, failure flags) |
| `figures/` | 8 PNG diagnostic figures |
| `diagnosis_report.md` | Full Markdown research report |
| `diagnosis_run_config.json` | Run metadata |

## Frequency Groups

**Tertile (18 each):**

| Group | Definition |
|---|---|
| frequent | Top-18 labels by train count |
| medium | Middle-18 labels |
| rare | Bottom-18 labels |

**Threshold:**

| Group | Train count |
|---|---|
| zero_train | 0 |
| very_rare | 1–5 |
| rare | 6–15 |
| medium | 16–40 |
| frequent | > 40 |

## Input Files

- `dataset/gold_labels/train/train_human_values.json`
- `dataset/gold_labels/dev/dev_human_values.json`
- `dataset/hv_categories/human_value_level1_values.json`
- `dataset/hv_categories/human_value_level2_values.json`
- `dataset/hv_categories/level_1_to_level_2.json`
- `evaluation.py` (imported as a module — not modified)

## Result Folders Analyzed

1. `output/task1_prompt/` — Prompt OAI
2. `output/task1_prompt_deepseek_v4_flash/` — Prompt DS Flash
3. `output/task1_deberta/` — DeBERTa-only
4. `output/task1_hybrid/` — Hybrid v1
5. `output/task1_hybrid_v2_deepseek_deepseek_v4_pro/` — Hybrid v2 DS Pro
6. `output/task1_hybrid_v2_deepseek_deepseek_v4_flash/` — Hybrid v2 DS Flash
7. `output/task1_hybrid_v2/` — optional old Hybrid v2
8. `output/task1_hybrid_v2_openai_gpt_4o_mini/` — optional old Hybrid v2 mini

Missing or incomplete folders are skipped with a warning.

## Rules

- Does **not** modify any existing file.
- Does **not** call any API.
- Does **not** run model training.
- All output is written to a new timestamped folder.
- Uses UTF-8 throughout.
