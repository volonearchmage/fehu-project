# FEHU Project Audit

Static, read-only audit of the FEHU project.

## What this folder contains

This folder is the persistent home of the audit module. It deliberately
holds no scripts and no automated checks — the audit was performed by
inspection, with all findings written to a timestamped folder under
`output/research_project_audit/`.

To re-run the audit, ask the assistant: *"re-audit the FEHU project"*.

## Where to find the results

Most recent audit:
```
output/research_project_audit/YYYYMMDD_HHMMSS/
```

Each timestamped folder contains:

| File | Purpose |
|---|---|
| `final_audit_report.md` | Severity-ranked summary of all findings |
| `project_inventory.md/.csv` | Inventory of every audited file/folder |
| `format_check_report.md` | Dataset and prediction format check |
| `evaluation_logic_audit.md` | How each script uses evaluation.py |
| `output_versioning_audit.md` | Output-folder overwrite/versioning audit |
| `output_folder_inventory.csv` | Per-folder metadata table |
| `model_provider_cache_audit.md` | Model/provider/cache/secrets audit |
| `code_correctness_audit.md` | Syntax + static-inspection findings |
| `prediction_consistency_check.md/.csv` | Per-method prediction validation |
| `diagnosis_script_audit.md` | Audit of label_diagnosis.py |
| `reproducibility_audit.md` | Reproducibility narrative |
| `reproducibility_matrix.csv` | Per-method reproducibility matrix |
| `proposed_patch_plan.md` | Patch plan (not applied) |

## Audit rules

- Strictly read-only on existing code, data, and predictions.
- No API calls, no training, no full inference.
- All output is written to a new timestamped folder; old audits are preserved.
- The audit may run `py_compile`, `grep`, and small read-only Python snippets.
