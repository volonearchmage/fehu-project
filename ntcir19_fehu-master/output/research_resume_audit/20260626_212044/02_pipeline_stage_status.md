# DRA-FEHU Pipeline Stage Status
**Audit Date:** 2026-06-26

---

## Stage 1: Previous Model Comparison
**Status: COMPLETED**

Baseline GPT-4o-mini pipeline, hybrid DeBERTa+LLM pipeline, and DeepSeek V4 Flash/Pro variants were run on the dev set. Label diagnosis revealed persistent recall failure on rare L1 values and a DeBERTa direction-reversal (DRR) problem. Results are stored in:
- `output/task1/` (GPT-4o-mini baseline)
- `output/task1_hybrid*/` (hybrid variants)
- `output/task1_prompt_deepseek*/` (DeepSeek variants)
- `output/research_label_diagnosis/` (diagnosis reports)

---

## Stage 2: DRA-FEHU Framework Design
**Status: COMPLETED**

The diagnosis-driven augmentation strategy was designed:
- Augmentation types defined: `rare_positive`, `direction_contrastive`
- Target L1 values selected based on per-class F1 analysis
- Framework documented in `output/research_augmentation_plan/20260614_131524/`
- Experiment registry created in `output/research_experiment_registry/20260614_123732/`
- Generation model strategy documented in `research/fehu_generation_model_strategy/`

---

## Stage 3: Preview Request Construction
**Status: COMPLETED**

Generation requests were constructed and previewed before human review:
- Output: `output/research_generation_preview/20260614_171644/`
- Key files: `generation_requests_preview.jsonl` (full request set), `human_review_sheet.csv`, `generation_preview_config.json`
- Earlier draft also exists at `output/research_generation_preview/20260614_163649/`
- Code: `research/fehu_augmentation_generation_preview_v1/`

---

## Stage 4: Human Review Pack
**Status: COMPLETED**

A structured human-review pack was prepared to allow manual approval/rejection of generation requests before any LLM API call:
- Output: `output/research_human_review_pack/20260615_161044/`
- Includes: request review table, risk-scoring rules, manual review instructions
- A draft low-risk candidate manifest was produced for approval

---

## Stage 5: Human Approval Manifest
**Status: COMPLETED**

Human approval decisions were recorded, and a final approved manifest was generated:
- Output: `output/research_human_approval/20260616_004845/`
- Key file: `02b_human_approved_manifest.jsonl` — **6 approved requests** (confirmed by line count)
- Deferred/rejected requests documented separately
- Generation readiness gate confirmed passed

---

## Stage 6: Dry-Run
**Status: COMPLETED**

A full dry-run of the generation pipeline was executed against the approved manifest without calling the LLM API:
- Output: `output/research_generation_dry_run/20260616_013343/`
- Manifest validated, prompts previewed, output schema confirmed
- Safety checklist passed: no secret-shaped tokens in manifest
- API key guidance documented as environment variable references only

---

## Stage 7: DeepSeek V4 Tiny Pilot Generation
**Status: COMPLETED**

The approved 6-request manifest was sent to DeepSeek V4 (Flash/Pro):
- Output: `output/research_generation_tiny_pilot/20260615_171954/`
- **4 requests** parsed successfully (`04_parsed_samples.jsonl`)
- **2 requests** produced truncated/failed responses (`05_failed_requests.jsonl`)
- Initial validation: 4 candidates (some PASS, some WARN)
- Code: `research/fehu_tiny_pilot_generation_v1/run_tiny_pilot_generation.py`

---

## Stage 8: Targeted Repair / Regeneration
**Status: COMPLETED**

The 2 truncated responses and 1 deterministic field mismatch were repaired:
- Output: `output/research_generation_tiny_pilot_repair/20260615_175432/`
- All 11 expected files are present
- **1 deterministic repair** applied (evidence_sentence expanded to match exact content sentence)
- **2 regeneration requests** sent (`03_regeneration_requests.jsonl`)
- **0 failed regenerations** (`06_regeneration_failed_requests.jsonl` is empty)
- **6 unified candidates** in `07_unified_candidate_samples.jsonl`
- Code: `research/fehu_tiny_pilot_repair_v1/repair_and_regenerate_tiny_pilot.py`

---

## Stage 9: Current Candidate Verification Readiness
**Status: COMPLETED (ready to proceed)**

The unified candidate set is validated and ready for the next step:
- 6 candidates, 3 PASS + 3 WARN + 0 FAIL
- All candidates: `candidate_status = PENDING_HUMAN_VERIFICATION`
- All candidates: `training_ready = false`
- All `human_decision` fields in verification sheet are blank (awaiting AI-assisted then human verification)
- Human verification sheet: `09_human_verification_sheet_REPAIRED.csv`

---

## Missing Next Stages

| Stage | Status | Description |
|-------|--------|-------------|
| Stage 10: AI-assisted semantic verification | **MISSING** | Run rule-based + LLM-as-judge checks; produce ACCEPT/REVIEW/REJECT recommendations per candidate |
| Stage 11: Human spot-check | MISSING | Reviewer confirms AI recommendations for WARN/REVIEW candidates |
| Stage 12: Verified candidate set creation | MISSING | Create `verified_augmented_candidates.jsonl` with human_decision fields populated |
| Stage 13: Training data preparation | MISSING | Convert verified candidates to FEHU training format |
| Stage 14: DeBERTa LoRA fine-tuning with augmented data | MISSING | Retrain and evaluate on dev set |
| Stage 15: Ablation study | MISSING | Compare base vs. augmented models on rare-class recall and DRR |
| Stage 16: Final test submission | MISSING | Generate `pred_task1a.json` and `pred_task1b.json` for test set |
