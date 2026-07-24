#!/bin/bash
# Phase 3 stage 1 — full 1,240-record data under both supervision policies:
#   Fp = official + 340 + 900, masked supervision  (v2's exact configuration;
#        seed 42 is an exact-replication anchor for the historical v2 run)
#   Gp = official + 340 + 900, assume-negative (empty supervision map)
# Seeds 42/43/44. Frozen trainer, unmodified. Training data = the v2 run's
# own input files (read-only), so Fp is byte-for-byte v2's configuration.
set -euo pipefail

BASE=/home/szf-4090/projects/fehu-project/ntcir19_fehu-master
PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
TRAINER=$BASE/output/research_augmented_deberta_v2_unfiltered/20260714_032758/scripts/train_deberta_masked_v2.py
V2IN=$BASE/output/research_augmented_deberta_v2_unfiltered/20260714_032758/inputs
ART=$V2IN/augmented_train_event_base_v2.json
LAB=$V2IN/augmented_train_human_values_v2.json
FULLMAP=$V2IN/supervision_map.json
EMPTY=$BASE/new_check/phase2/inputs/supervision_map_empty.json
RUNS=$BASE/new_check/phase3/runs
LOGS=$BASE/new_check/phase3/logs
mkdir -p "$RUNS" "$LOGS"

run_cell () {
  local cell=$1 seed=$2 map=$3
  local dir=$RUNS/${cell}_seed${seed}
  if [ -e "$dir" ]; then echo "ABORT: $dir already exists"; exit 1; fi
  echo "=== [$(date +%H:%M:%S)] cell $cell seed $seed ==="
  $PY "$TRAINER" \
    --train_articles "$ART" --train_labels "$LAB" --supervision_map "$map" \
    --seed "$seed" \
    --checkpoint_dir "$dir/checkpoints" \
    --output_dir "$dir/output" \
    --version "phase3_${cell}_s${seed}" \
    > "$LOGS/train_${cell}_seed${seed}.log" 2>&1
  echo "=== [$(date +%H:%M:%S)] cell $cell seed $seed done ==="
}

for seed in 42 43 44; do
  run_cell Fp "$seed" "$FULLMAP"
  run_cell Gp "$seed" "$EMPTY"
done
echo "STAGE1 COMPLETE $(date)"
