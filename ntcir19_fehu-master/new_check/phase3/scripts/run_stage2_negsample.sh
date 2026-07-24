#!/bin/bash
# Phase 3 stage 2 — target-class negative down-sampling on the stage-1
# winning configuration (full official+340+900 data).
#   usage: run_stage2_negsample.sh <masked|assumeneg>
# Cells: N3 = 1:3 positive:negative per target class, N1 = 1:1.
# Trainer: new_check/phase3/scripts/train_phase3_negsample.py (copy of the
# frozen masked trainer + per-class negative down-sampling via loss masks;
# without --neg_sample_targets it is behavior-identical to the frozen one).
set -euo pipefail

POLICY=${1:?usage: run_stage2_negsample.sh <masked|assumeneg>}
BASE=/home/szf-4090/projects/fehu-project/ntcir19_fehu-master
PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
TRAINER=$BASE/new_check/phase3/scripts/train_phase3_negsample.py
V2IN=$BASE/output/research_augmented_deberta_v2_unfiltered/20260714_032758/inputs
ART=$V2IN/augmented_train_event_base_v2.json
LAB=$V2IN/augmented_train_human_values_v2.json
TARGETS=$BASE/new_check/phase3/inputs/neg_sample_targets_18.json
RUNS=$BASE/new_check/phase3/runs
LOGS=$BASE/new_check/phase3/logs

case $POLICY in
  masked)    MAP=$V2IN/supervision_map.json ;;
  assumeneg) MAP=$BASE/new_check/phase2/inputs/supervision_map_empty.json ;;
  *) echo "ABORT: unknown policy $POLICY"; exit 1 ;;
esac

run_cell () {
  local cell=$1 seed=$2 ratio=$3
  local dir=$RUNS/${cell}_seed${seed}
  if [ -e "$dir" ]; then echo "ABORT: $dir already exists"; exit 1; fi
  echo "=== [$(date +%H:%M:%S)] cell $cell seed $seed (ratio $ratio, $POLICY) ==="
  $PY "$TRAINER" \
    --train_articles "$ART" --train_labels "$LAB" --supervision_map "$MAP" \
    --neg_sample_targets "$TARGETS" --neg_pos_ratio "$ratio" \
    --seed "$seed" \
    --checkpoint_dir "$dir/checkpoints" \
    --output_dir "$dir/output" \
    --version "phase3_${cell}_s${seed}" \
    > "$LOGS/train_${cell}_seed${seed}.log" 2>&1
  echo "=== [$(date +%H:%M:%S)] cell $cell seed $seed done ==="
}

for seed in 42 43 44; do
  run_cell N3 "$seed" 3.0
  run_cell N1 "$seed" 1.0
done
echo "STAGE2 COMPLETE ($POLICY) $(date)"
