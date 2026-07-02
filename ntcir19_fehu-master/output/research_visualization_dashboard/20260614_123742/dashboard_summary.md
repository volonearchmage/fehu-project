# FEHU Visualization Dashboard

**Generated:** 20260614_123742  
**Source diagnosis:** `/home/szf-4090/projects/fehu-project/ntcir19_fehu-master/output/research_label_diagnosis/20260613_145847`  

## Headlines

- **Best Task-1b µF1:** `Prompt_DS_Flash` = 0.4964
- **Lowest DRR:** `Prompt_OAI` = 0.0212
- **Best rare-label avg recall_dir:** `Prompt_DS_Flash` = 0.0989
- **Diagnostic flags:** rare+low-recall rows = 101, high-FP rows = 15, high-direction-error rows = 68

## Figures

- `task1b_micro_f1_by_method.png` — overall ranking
- `task1b_precision_recall_scatter.png` — P/R trade-off
- `drr_by_method.png` — direction-reversal rate
- `rare_recall_by_method.png` — rare-tertile micro-recall
- `frequency_group_recall_task1b.png` — recall split by tertile
- `frequency_group_precision_task1b.png` — precision split by tertile
- `frequent_medium_rare_f1_by_method.png` — F1 split by tertile
- `augmentation_need_by_label.png` — per-label flag counts

## Files

- `overall_metrics_clean.csv` — trimmed copy of `overall_metrics.csv`
- `method_ranking_task1b.csv` — methods ranked by Task-1b micro-F1

## Constraints honored

This dashboard only reads existing CSVs. No predictions were recomputed; 
no APIs were called; no existing files were modified.