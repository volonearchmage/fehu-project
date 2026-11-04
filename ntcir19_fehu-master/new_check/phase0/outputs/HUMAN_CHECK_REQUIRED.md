# HUMAN_CHECK_REQUIRED — Phase 0

Items that could not be resolved safely from repository evidence.

## DRR docstring/variable names call direction '0' aligned, while dataset/hv_catego

- **Path:** `evaluation.py (lines 33–39, 65–81)`
- **Uncertainty:** DRR docstring/variable names call direction '0' aligned, while dataset/hv_categories/direction_mapping.json defines '1' = aligned. The DRR arithmetic is symmetric, so official numbers are unaffected; Phase-0 reversal attribution follows direction_mapping.json.
- **Why not automatically resolvable:** the naming conflict is in official scorer code, which this project never modifies; only the task organizers can say which comment is authoritative
- **What to inspect/confirm:** confirm with the task documentation that '1'=aligned is the intended semantic (all repo experiment reports assume it)
- **Blocks:** interpretation only — no metric is affected

## no exported dev probabilities exist for the baseline model, so threshold sensiti

- **Path:** `output/research_ablation_smoke_runs/20260704_201355/baseline/`
- **Uncertainty:** no exported dev probabilities exist for the baseline model, so threshold sensitivity could only be computed for augmented v2
- **Why not automatically resolvable:** producing them requires loading the checkpoint and running local inference, which Phase 0 is forbidden to do
- **What to inspect/confirm:** approve the Phase-1 step: one local inference pass from the stored baseline checkpoint to export probabilities
- **Blocks:** blocks the baseline column of the threshold-sensitivity table (the 'was the baseline learning but thresholded away?' question)

## LLM/hybrid systems differ from the DeBERTa runs in far more than augmentation (m

- **Path:** `output/task1/runs/dev_deepseek_.../pred_task1b.json (liu_frozen), hybrid H2/H3 prediction files`
- **Uncertainty:** LLM/hybrid systems differ from the DeBERTa runs in far more than augmentation (model family, prompt, inference protocol); they are included as descriptive context only
- **Why not automatically resolvable:** no artifact can make these causally comparable to the augmentation question
- **What to inspect/confirm:** when discussing with the professor, present LLM/hybrid rows as context, never as augmentation evidence
- **Blocks:** interpretation only

## 3 probability rows belong to dev actors absent from gold ([('1-15231-2-1', '1-15

- **Path:** `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/02_deberta_actor_probabilities.jsonl`
- **Uncertainty:** 3 probability rows belong to dev actors absent from gold ([('1-15231-2-1', '1-15231-2-1-1'), ('8-6386-5-t', '8-6386-5-t-3'), ('3-18136-5-t', '3-18136-5-t-1')])
- **Why not automatically resolvable:** whether a submission-time system would also predict for these actors is a protocol choice, not derivable from the artifact
- **What to inspect/confirm:** confirm that excluding non-gold actors matches the frozen v2 prediction protocol (it does per src/train_deberta.py build_examples with DEV_LABELS), and note micro-precision would change if they were included with non-empty predictions
- **Blocks:** interpretation only — does not block any Phase-0 metric
