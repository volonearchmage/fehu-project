# Execution Log — DRA-FEHU Smoke Run

## Baseline (Condition A)
- start: 2026-07-04T20:15:08+09:00  end: 2026-07-04T20:17:48+09:00  (~2m40s)
- exit code: 0
- early stop at epoch 5/15 (best at epoch 1); best dev Task-1b micro_F1 = 0.3023
- logs: `output/research_ablation_smoke_runs/20260704_201355/baseline/logs/stdout.log`, `stderr.log`

## Augmented (Condition B)
- start: 2026-07-04T20:19:59+09:00  end: 2026-07-04T20:25:35+09:00  (~5m36s)
- exit code: 0
- early stop at epoch 11/15 (best at epoch 7); best dev Task-1b micro_F1 = 0.3060
- logs: `output/research_ablation_smoke_runs/20260704_201355/augmented/logs/stdout.log`, `stderr.log`

## stdout/stderr notes
- stderr in both runs contains the standard benign transformers warning about UNEXPECTED
  DeBERTa mask-prediction head weights when loading AutoModel (pretraining heads dropped).
- No Tracebacks, no CUDA OOM, no retries. Both runs completed on the first attempt.
- Note: the harness session restarted during the augmented run; the detached process kept
  running and its exit code (0) was captured by the wrapper into exit_code.txt. A stale
  harness-side task wrapper separately reported -1; the authoritative exit code is the
  file written by the run itself (0).

## Both runs completed: YES (exit 0 / exit 0)
