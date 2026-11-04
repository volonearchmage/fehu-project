#!/bin/bash
# Phase 2 — run the 3x3 controlled ablation (cells A/B/C x seeds 42/43/44)
# using the FROZEN masked trainer (unmodified, invoked read-only):
#   output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_deberta_masked_v2.py
# With an empty supervision map the trainer is exactly the original
# src/train_deberta.py behavior (all-ones masks), so:
#   A = official only            + empty map   (original protocol)
#   B = official + 900 round-2   + empty map   (assume-negative)
#   C = official + 900 round-2   + round-2 map (masked supervision)
# Everything else (LoRA config, lr, schedule, batch, epochs<=15, patience 4
# on dev 1b micro-F1, threshold 0.3) is identical across cells by
# construction. Sequential execution on the single GPU. set -e: any failed
# run aborts the whole batch (no fallbacks).
set -euo pipefail

BASE=/home/szf-4090/projects/fehu-project/ntcir19_fehu-master
PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
TRAINER=$BASE/output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_deberta_masked_v2.py
INP=$BASE/new_check/phase2/inputs
RUNS=$BASE/new_check/phase2/runs
LOGS=$BASE/new_check/phase2/logs
OFF_ART=$BASE/dataset/train/train_event_base.json
OFF_LAB=$BASE/dataset/gold_labels/train/train_human_values.json
AUG_ART=$INP/train_event_base_official_plus_900.json
AUG_LAB=$INP/train_human_values_official_plus_900.json
EMPTY=$INP/supervision_map_empty.json
R2MAP=$INP/supervision_map_round2_only.json

mkdir -p "$RUNS" "$LOGS"

run_cell () {
  local cell=$1 seed=$2 art=$3 lab=$4 map=$5
  local dir=$RUNS/${cell}_seed${seed}
  if [ -e "$dir" ]; then echo "ABORT: $dir already exists"; exit 1; fi
  echo "=== [$(date +%H:%M:%S)] cell $cell seed $seed ==="
  $PY "$TRAINER" \
    --train_articles "$art" --train_labels "$lab" --supervision_map "$map" \
    --seed "$seed" \
    --checkpoint_dir "$dir/checkpoints" \
    --output_dir "$dir/output" \
    --version "phase2_${cell}_s${seed}" \
    > "$LOGS/train_${cell}_seed${seed}.log" 2>&1
  echo "=== [$(date +%H:%M:%S)] cell $cell seed $seed done ==="
}

for seed in 42 43 44; do
  run_cell A "$seed" "$OFF_ART" "$OFF_LAB" "$EMPTY"
  run_cell B "$seed" "$AUG_ART" "$AUG_LAB" "$EMPTY"
  run_cell C "$seed" "$AUG_ART" "$AUG_LAB" "$R2MAP"
done

echo "ALL 9 RUNS COMPLETE $(date)"
