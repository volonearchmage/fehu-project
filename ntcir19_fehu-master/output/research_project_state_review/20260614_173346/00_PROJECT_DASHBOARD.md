# FEHU Project State Dashboard

**Audit timestamp:** `20260614_173346`  ·  **Audit folder:** `output/research_project_state_review/20260614_173346/`
**Direction convention everywhere:** `"1"` = aligned, `"0"` = contradictory.

---

## Status in one paragraph

The FEHU / NTCIR-19 Task-1 project is **stable, well-instrumented, and paused at a clean human-review checkpoint**. The legacy-script bugs identified by the prior audit (C1, C2, H1, H3, H4) are all fixed in the working tree. The latest preview (`v2`, 18 requests) has been independently audited — 12 pass, 6 design-justified warnings, 0 failures. The FEHU prediction-format guard and the augmented-data guard are both implemented and verified. No API has been called, no model has been trained, no official file has been modified. The next correct action is **human review of the v2 preview**; do **not** author `run_generation.py` or call any API until that is done.

---

## Audit folder layout

```
output/research_project_state_review/20260614_173346/
├── 00_PROJECT_DASHBOARD.md              ← this file
├── 01_REPORT_CHRONOLOGY/
│   ├── report_chronology.md             (timeline of all known reports)
│   └── report_claims_matrix.csv         (20 claims · 12 verified · 5 verified-then-fixed · 1 documented hazard · 2 design/runtime accepted)
├── 02_FILE_INVENTORY/
│   ├── current_file_inventory.md        (67 paths, 0 missing)
│   ├── generated_artifact_manifest.json
│   └── important_paths_table.csv
├── 03_PREVIEW_V2_AUDIT/
│   ├── preview_v2_quality_audit.md      (per-condition findings)
│   ├── preview_v2_request_matrix.csv    (18 rows · 19 cols · pass/warn/fail per row)
│   └── preview_v2_warning_items.csv     (6 design-justified warnings)
├── 04_SAFETY_AND_SUBMISSION_GATES/
│   ├── safety_gate_checklist.md         (15/15 PASS)
│   ├── forbidden_modification_check.md
│   └── direction_mapping_audit.md       (PASS)
├── 05_RESEARCH_DECISION/
│   ├── go_no_go_decision.md             (GO: human review · NO-GO: API generation, training, submission)
│   └── recommended_next_steps.md        (6 staged steps)
└── 06_SESSION_REPORT/
    ├── actions_performed_report.md
    ├── commands_run.log
    └── files_created_or_modified.md
```

---

## Key components at a glance

| Component | State | Last touched | Notes |
|---|---|---|---|
| Official `dataset/**` | UNTOUCHED | 2026-05-17 | Frozen reference |
| `evaluation.py` | UNCHANGED vs HEAD | 2026-05-13 | Direction docstring inverted (DRR symmetric, score correct); never modified |
| `src/run_pipeline.py` | post-repair (C1/H1/H4 fixed) | 2026-06-13 | `--model` now wired, cache + output model-keyed, gold filtered on `--limit` |
| `src/train_deberta.py` | post-repair (C2 fixed) | 2026-06-13 | Default output now `output/task1_deberta/`, run_config emitter added |
| `src/hybrid_pipeline.py` | post-repair (H3 fixed) | 2026-06-13 | DeBERTa baseline → `output/task1_deberta/`, model-keyed cache |
| `src/hybrid_v2.py`, `src/run_pipeline_deepseek_flash.py` | already clean | 2026-05-18/19 | Untracked but functional |
| Trained checkpoint | unchanged | 2026-05-17 | `checkpoints/best_model/` not touched today |
| Latest diagnosis | `output/research_label_diagnosis/20260613_145847/` | 2026-06-13 | Best Task-1b µF1 = 0.4964 (Prompt_DS_Flash) |
| Latest plan | `output/research_augmentation_plan/20260614_131524/` | 2026-06-14 13:15 | 20 selected labels, pilot budget 216 samples |
| Preview v1 | `output/research_generation_preview/20260614_163649/` | 2026-06-14 16:36 | First-pass; preserved for history |
| Preview v2 | `output/research_generation_preview/20260614_171644/` | 2026-06-14 17:16 | 18 requests, `preview_revision: 2`, READY FOR REVIEW |
| Submission safety guards | `research/fehu_submission_safety/` | 2026-06-14 | Both guards exit-cleanly; format guard CLEAN on Prompt_DS_Flash dev output |
| `output/task1*/`, `logs/cache_*` | UNTOUCHED today | 2026-05-17 → 19 | Independently verified by `find -newermt` |

---

## Timeline of major research artifacts

```
2026-05-13  ┃ Initial commit (evaluation.py, dataset, baseline run_pipeline.py)
2026-05-17  ┃ DeBERTa training; first predictions in output/task1_*
2026-05-18  ┃ Hybrid v1 + Hybrid v2 (OAI) runs
2026-05-19  ┃ Hybrid v2 DeepSeek Pro + Flash runs; Prompt DS Flash run
            ┃
2026-06-13  ┃ Label-diagnosis module created → 2 runs (no-fig + with figs)
            ┃ Project audit module created → final_audit_report.md identifies C1/C2/H1/H3/H4
            ┃ Legacy scripts patched (run_pipeline.py, train_deberta.py, hybrid_pipeline.py)
            ┃ Post-repair verification: prompts byte-identical
            ┃
2026-06-14  ┃ Experiment-management module (registry + visualizer)
   12:37    ┃   ├─ experiment_registry.csv
   12:37    ┃   └─ visualization dashboard (8 figs)
   13:15    ┃ Augmentation plan v1 → 20 selected labels, pilot budget
   16:36    ┃ Preview v1 (18 requests, base prompts)
   16:38    ┃ FEHU prediction format guard smoke test on Prompt_DS_Flash → CLEAN ✅
   17:16    ┃ Preview v2 (preview_revision=2; actor aliases, smart-truncate, 14-field schema)
   17:33    ┃ THIS AUDIT — project state review
```

---

## Do / Do Not

| Do (✅ safe, encouraged) | Do Not (🛑 forbidden) |
|---|---|
| Read & edit `human_review_sheet.csv` to record approvals | Author `research/fehu_augmentation_v1/run_generation.py` |
| Read full prompts in `generation_requests_preview.jsonl` | Call any LLM API |
| Use `inspect_generation_preview.py` for fast summaries | Train any model |
| Compare v1 vs v2 prompts to inspect what changed | Overwrite anything in `output/task1*/` |
| Re-run `experiment_registry.py` (writes new TS folder) | Re-run `train_deberta.py` |
| Re-run `visualize_results.py` | Write `pred_task1*.json` for the test set |
| Re-run `fehu_prediction_format_guard.py` on any pred | Modify `evaluation.py` |
| Re-run `validate_augmented_data.py` (no input → usage exit) | Modify any `dataset/**` file |
| Add notes to `research/fehu_repair_and_augmentation_v1/` | Read `.env` (file doesn't exist; do not create one) |

---

## Go / No-Go summary

| Action | Decision |
|---|---|
| Human review of v2 preview | ✅ **GO** |
| Create `run_generation.py` | 🛑 NO-GO (wait for review) |
| Tiny-pilot API generation | 🛑 NO-GO |
| Model training | 🛑 NO-GO |
| Final FEHU submission | 🛑 NO-GO |

See `05_RESEARCH_DECISION/go_no_go_decision.md` for justification.

---

## Quick links

- Per-condition v2 audit: `03_PREVIEW_V2_AUDIT/preview_v2_quality_audit.md`
- Request matrix (18 rows): `03_PREVIEW_V2_AUDIT/preview_v2_request_matrix.csv`
- Warning items (6 rows): `03_PREVIEW_V2_AUDIT/preview_v2_warning_items.csv`
- Safety gates (15/15 PASS): `04_SAFETY_AND_SUBMISSION_GATES/safety_gate_checklist.md`
- Direction-mapping audit (PASS): `04_SAFETY_AND_SUBMISSION_GATES/direction_mapping_audit.md`
- Decision sheet: `05_RESEARCH_DECISION/go_no_go_decision.md`
- Staged plan: `05_RESEARCH_DECISION/recommended_next_steps.md`
- All-reports timeline: `01_REPORT_CHRONOLOGY/report_chronology.md`
- Claims matrix (20 verified claims): `01_REPORT_CHRONOLOGY/report_claims_matrix.csv`
- File inventory (67 paths): `02_FILE_INVENTORY/current_file_inventory.md`
- Session report: `06_SESSION_REPORT/actions_performed_report.md`

---

## Final one-line recommendation

> **Proceed to human review of `output/research_generation_preview/20260614_171644/human_review_sheet.csv`; do not author `run_generation.py` or call any API until that review is complete.**
