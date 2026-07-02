# Ready-to-Use Prompt: AI-Assisted Verification of 6 Unified Candidates

**Purpose:** This is the exact prompt to use as the next Claude Code task after this audit.  
**Audience:** Claude Code (next session).

---

## Prompt

We are continuing the DRA-FEHU (Diagnosis-driven Recall-focused Augmentation) research for NTCIR-19 Task-1. The previous session completed a tiny pilot of LLM-generated augmentation data, followed by a targeted repair/regeneration pass. A unified candidate set of 6 samples now exists and has passed rule-based structural validation. This session performs AI-assisted semantic verification of those 6 candidates.

**Important safety boundaries — you MUST follow all of these:**
- Do NOT call any external LLM API (no DeepSeek, no OpenAI, no Anthropic API calls).
- If you believe LLM-as-judge scoring would be valuable, prepare a template and prompt preview only — do not execute any API calls.
- Do NOT modify official dataset files: `dataset/**`, `dataset/gold_labels/**`.
- Do NOT modify `evaluation.py`.
- Do NOT modify `logs/cache_*.json`.
- Do NOT modify any previous output folders: `output/research_generation_*`, `output/research_human_*`.
- Do NOT create `pred_task1a.json` or `pred_task1b.json`.
- Do NOT create an augmented training file (no `*augmented_train*`, no `*_training_data*`).
- Do NOT mark any candidate as `training_ready: true` — leave all as false.
- Do NOT fill in `human_decision` fields — leave them blank.
- Do NOT run model training.
- Do NOT print, log, or read any API key or `.env` file.

**Input files to read:**

1. `output/research_generation_tiny_pilot_repair/20260615_175432/07_unified_candidate_samples.jsonl` — the 6 unified candidates with full generated content and validation summaries
2. `output/research_generation_tiny_pilot_repair/20260615_175432/08_unified_validation_table.csv` — per-candidate rule-based validation summary
3. `output/research_generation_tiny_pilot_repair/20260615_175432/09_human_verification_sheet_REPAIRED.csv` — the human review template (do NOT overwrite this file)
4. `dataset/hv_categories/level_1_to_level_2.json` — to verify L1→L2 taxonomy mappings
5. `dataset/hv_categories/human_value_level1_values.json` — L1 value name list
6. `dataset/hv_categories/human_value_level2_values.json` — L2 value name list

**Task:**

Perform AI-assisted semantic verification of the 6 unified candidates using rule-based reasoning only (no LLM API). For each candidate, assess:

1. **Value semantic alignment:** Does the article content genuinely exemplify the stated L1 value? Is the connection clear and direct?
2. **Actor centrality:** Is the stated actor the primary agent performing the value-relevant action? Is the actor present in the article?
3. **Evidence sentence quality:** Does the evidence sentence capture the most relevant moment? For WARN candidates where actor_mention is not in the evidence sentence — is the sentence still semantically sufficient?
4. **Direction correctness:** Does direction "1" (aligned) or "0" (contradictory) correctly describe the actor's relation to the value?
5. **Content naturalness:** Does the content read as plausible real-world news? Any "As an AI...", benchmark leakage, or clearly synthetic phrasings?
6. **Direction-contrastive pair coherence (for paired candidates):** Candidates `prev_dir_contrast_12_002_aligned_ce1da19f54` and `prev_dir_contrast_12_002_contradictory_ce1da19f54` are paired for L1 value 12 (Have success). Candidates `prev_dir_contrast_38_003_aligned_e969e14138` and `prev_dir_contrast_38_003_contradictory_e969e14138` are paired for L1 value 38 (Be honest). For each pair: do they present the same value with genuinely opposite directions?

**Suggestions to assign (not final decisions):**

- `ACCEPT` — passes all checks; suitable for human confirmation
- `REVIEW` — one or more minor concerns; human should inspect before deciding
- `REJECT` — clear semantic or factual error; should not be used for training

Do NOT populate `human_decision` fields. These are AI suggestions only. The `candidate_status` must remain `PENDING_HUMAN_VERIFICATION` for all candidates. The `training_ready` field must remain `false` for all candidates.

**Output files to create** in `output/research_ai_verification/<CURRENT_TIMESTAMP>/`:

1. `00_VERIFICATION_DASHBOARD.md` — summary: ACCEPT/REVIEW/REJECT counts, any blockers
2. `01_ai_verification_report.csv` — per-candidate row with all criterion ratings and overall suggestion
3. `02_ai_verification_detail.md` — narrative rationale per candidate
4. `03_direction_pair_coherence_check.md` — analysis of the two contrastive pairs
5. `04_human_spot_check_instructions.md` — specific questions for the human reviewer per candidate
6. `05_llm_judge_template_preview.md` — if you believe LLM-as-judge scoring would add value, write the prompt template here. Do NOT execute it.
7. `06_human_decision_template.csv` — blank template with same columns as `09_human_verification_sheet_REPAIRED.csv` plus a `ai_suggestion` column; leave `human_decision` blank
8. `07_session_report.md` — commands run, files read, files created, API called (must be NO), training run (must be NO), official data modified (must be NO)

After completing the verification, report to the user: ACCEPT/REVIEW/REJECT counts, which candidates need human attention, and whether any candidate should be flagged for removal from the pool.

Proceed carefully.
