# FEHU Experiment Management

Two safe, local-only tools for tracking everything in `output/`.

## experiment_registry.py

Scans every known method folder, validates its prediction files, reads its
`run_config.json` if present, and produces a single registry CSV + JSON.

```bash
python research/fehu_experiment_management/experiment_registry.py
```

Output:
```
output/research_experiment_registry/YYYYMMDD_HHMMSS/
├── experiment_registry.csv
├── experiment_registry.json
├── output_folder_inventory.csv
└── result_trustworthiness_notes.md
```

The registry assigns each folder one of:
- `canonical_prompt_oai` / `canonical_prompt_ds_flash`
- `canonical_deberta` / `canonical_hybrid_v1`
- `canonical_hybrid_v2_ds_pro` / `canonical_hybrid_v2_ds_flash`
- `legacy_duplicate_ambiguous` (for `output/task1/`)
- `orphan_legacy_hybrid_v2` (for `output/task1_hybrid_v2/`)
- `limit_debug_run`
- `unknown`

The script makes no changes to existing files.

## visualize_results.py

Reads the most recent label-diagnosis output and produces a presentation-ready
dashboard.

```bash
python research/fehu_experiment_management/visualize_results.py \
    --diagnosis_dir output/research_label_diagnosis/20260613_145847
```

Output:
```
output/research_visualization_dashboard/YYYYMMDD_HHMMSS/
├── dashboard_summary.md
├── overall_metrics_clean.csv
├── method_ranking_task1b.csv
└── figures/
    ├── task1b_micro_f1_by_method.png
    ├── task1b_precision_recall_scatter.png
    ├── drr_by_method.png
    ├── rare_recall_by_method.png
    ├── frequency_group_recall_task1b.png
    ├── frequency_group_precision_task1b.png
    ├── frequent_medium_rare_f1_by_method.png
    └── augmentation_need_by_label.png
```

Both tools are safe:
- No API calls.
- No model inference.
- No modifications to existing files.
- All output is timestamped and never overwrites a previous run.

See `OUTPUT_NAMING.md` for the canonical-folder vocabulary used by both tools.
