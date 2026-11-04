#!/bin/bash
# 以唯一时间标签完整重跑 E7-G4 DEV；所有可交付结果归档到同一 run 目录。
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <run-id>" >&2
  exit 2
fi

cd /Users/lloydhuang/Documents/GitHub/fehu-project/ntcir19_fehu-master
set -a
source .env
set +a

readonly RUN_ID="$1"
readonly PY="venv/bin/python"
readonly ROOT="E7G4Flash0731Dev/runs/$RUN_ID"
readonly LOG="$ROOT/logs"
readonly SEG6="$ROOT/segmentation/e6/segments_dev.json"
readonly SEG6B="$ROOT/segmentation/e6b/segments_dev.json"
readonly E1_SRC="RH_test/E1_fewshot_repair/runs/${RUN_ID}_e1"
readonly E6_SRC="RH_test/E6_e3a_self_segmentation/runs/${RUN_ID}_e6"
readonly E6B_SRC="RH_test/E6b_granularity_control/runs/${RUN_ID}_e6b"
readonly E6C_SRC="RH_test/E6c_pro_nonthinking/runs/${RUN_ID}_e6c"
readonly LIU_DIR="$ROOT/members/Liu"
readonly CONFIRMED_EMPTY="$ROOT/report/confirmed_empty.txt"
readonly ARTICLES="dataset/dev/dev_event_base.json"

mkdir -p "$LOG" "$ROOT/segmentation/e6" "$ROOT/segmentation/e6b" \
  "$ROOT/members" "$ROOT/fusion" "$ROOT/report" "$ROOT/metadata"
touch "$CONFIRMED_EMPTY"

retry_run() {
  local name="$1"
  local attempts="$2"
  local log_path="$3"
  shift 3
  local attempt
  local status
  for attempt in $(seq 1 "$attempts"); do
    echo "[$(date -Iseconds)] $name attempt $attempt/$attempts" | tee -a "$log_path"
    set +e
    "$@" 2>&1 | tee -a "$log_path"
    status=${PIPESTATUS[0]}
    set -e
    if [ "$status" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -lt "$attempts" ]; then
      echo "[$name] failed with status $status; retrying in 30 seconds" | tee -a "$log_path"
      sleep 30
    fi
  done
  echo "[$name] exhausted $attempts attempts" >&2
  return 1
}

check_cache() {
  local name="$1"
  local cache_path="$2"
  local stage_log="$3"
  shift 3
  local status
  set +e
  "$PY" E7G4Test/scripts/cache_health.py \
    --name "$name" --cache "$cache_path" --log "$stage_log" \
    --articles "$ARTICLES" --passno 1 2>&1 | tee -a "$LOG/cache_health.log"
  status=${PIPESTATUS[0]}
  set -e
  if [ "$status" -eq 2 ]; then
    retry_run "${name}_empty_refetch" 10 "$stage_log" "$@"
    set +e
    "$PY" E7G4Test/scripts/cache_health.py \
      --name "$name" --cache "$cache_path" --log "$stage_log" \
      --articles "$ARTICLES" --passno 2 2>&1 | tee -a "$LOG/cache_health.log"
    status=${PIPESTATUS[0]}
    set -e
  fi
  if [ "$status" -ne 0 ]; then
    echo "[$name] cache validation failed with status $status" >&2
    return "$status"
  fi
  grep "^CONFIRMED_EMPTY" "$LOG/cache_health.log" >> "$CONFIRMED_EMPTY" || true
}

copy_member() {
  local source_dir="$1"
  local name="$2"
  local target_dir="$ROOT/members/$name"
  if [ -e "$target_dir" ]; then
    if diff -qr "$source_dir" "$target_dir" >/dev/null; then
      echo "[$name] identical archive exists; resuming after copy"
      return 0
    fi
    echo "Existing member archive differs from source: $target_dir" >&2
    return 1
  fi
  cp -R "$source_dir" "$target_dir"
}

readonly E1_CMD=("$PY" RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced)
readonly LIU_CMD=("$PY" liu_method/run_pipeline.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced
  --cache_path "$LIU_DIR/cache.json" --output_dir "$LIU_DIR")

# 第一阶段可独立并行：两套切分、E1 与 Liu。
if [ -f "$SEG6" ]; then
  echo "[seg_e6] completed output exists; resuming after this stage"
else
  retry_run seg_e6 20 "$LOG/seg_e6.log" "$PY" \
    RH_test/E6_e3a_self_segmentation/scripts/run_segmentation_e6.py \
    --mode dev --model deepseek-v4-flash --out "$SEG6"
fi &
pid_seg6=$!
if [ -f "$SEG6B" ]; then
  echo "[seg_e6b] completed output exists; resuming after this stage"
else
  retry_run seg_e6b 20 "$LOG/seg_e6b.log" "$PY" \
    RH_test/E6b_granularity_control/scripts/run_segmentation_e6b.py \
    --mode dev --model deepseek-v4-flash --out "$SEG6B"
fi &
pid_seg6b=$!
retry_run e1 20 "$LOG/e1.log" env E1_RUN_TS="${RUN_ID}_e1" "${E1_CMD[@]}" &
pid_e1=$!
retry_run liu 20 "$LOG/liu.log" "${LIU_CMD[@]}" &
pid_liu=$!

wait "$pid_seg6"
wait "$pid_seg6b"
wait "$pid_e1"
wait "$pid_liu"

readonly E1_CACHE="$E1_SRC/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json"
check_cache e1 "$E1_CACHE" "$LOG/e1.log" env E1_RUN_TS="${RUN_ID}_e1" "${E1_CMD[@]}"
check_cache liu "$LIU_DIR/cache.json" "$LOG/liu.log" "${LIU_CMD[@]}"
copy_member "$E1_SRC" E1

readonly E6_CMD=("$PY" RH_test/E6_e3a_self_segmentation/scripts/run_pipeline_e6.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced --segments "$SEG6")
readonly E6B_CMD=("$PY" RH_test/E6b_granularity_control/scripts/run_pipeline_e6b.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced --segments "$SEG6B")
readonly E6C_CMD=("$PY" RH_test/E6c_pro_nonthinking/scripts/run_pipeline_e6c.py
  --mode dev --provider deepseek --model deepseek-v4-pro
  --prompt_variant targeted_more_shot_balanced --segments "$SEG6B")

# 第二阶段共享新切分，但三个成员之间相互独立。
retry_run e6 20 "$LOG/e6.log" env E6_RUN_TS="${RUN_ID}_e6" "${E6_CMD[@]}" &
pid_e6=$!
retry_run e6b 20 "$LOG/e6b.log" env E6B_RUN_TS="${RUN_ID}_e6b" "${E6B_CMD[@]}" &
pid_e6b=$!
retry_run e6c 20 "$LOG/e6c.log" env E6C_RUN_TS="${RUN_ID}_e6c" "${E6C_CMD[@]}" &
pid_e6c=$!

wait "$pid_e6"
wait "$pid_e6b"
wait "$pid_e6c"

readonly E6_CACHE="$E6_SRC/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json"
readonly E6B_CACHE="$E6B_SRC/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json"
readonly E6C_CACHE="$E6C_SRC/cache_dev_deepseek_deepseek-v4-pro_targeted_more_shot_balanced_temp0p1_max8000.json"
check_cache e6 "$E6_CACHE" "$LOG/e6.log" env E6_RUN_TS="${RUN_ID}_e6" "${E6_CMD[@]}"
check_cache e6b "$E6B_CACHE" "$LOG/e6b.log" env E6B_RUN_TS="${RUN_ID}_e6b" "${E6B_CMD[@]}"
check_cache e6c "$E6C_CACHE" "$LOG/e6c.log" env E6C_RUN_TS="${RUN_ID}_e6c" "${E6C_CMD[@]}"
copy_member "$E6_SRC" E6
copy_member "$E6B_SRC" E6b
copy_member "$E6C_SRC" E6c

readonly MEMBER_REPORT="$ROOT/report/members.json"
for name in E1 Liu E6 E6b E6c; do
  "$PY" E7G4Flash0731Dev/scripts/score_member.py \
    --name "$name" --run_dir "$ROOT/members/$name" \
    --out "$MEMBER_REPORT" --append | tee -a "$LOG/scoring.log"
done

readonly FUSION_SCRIPT="RH_test/E7_calibrated_jury_fusion/scripts/run_fusion_e7.py"
readonly V2_PROBS="RH_test/E5_deberta_auxiliary_fusion/inputs/dev_fp_seed44_probs.jsonl"
for cell in G0_passthrough G1_veto G2_veto_noliu G3_veto_add G5_veto_nogate; do
  "$PY" "$FUSION_SCRIPT" --cell "$cell" --primary_name E6b \
    --articles "$ARTICLES" --gold_1b dataset/gold_labels/dev/dev_human_values.json \
    --v2_probs "$V2_PROBS" \
    --member "E1=$ROOT/members/E1/pred_task1b.json" \
    --member "Liu=$ROOT/members/Liu/pred_task1b.json" \
    --member "E6=$ROOT/members/E6/pred_task1b.json" \
    --member "E6b=$ROOT/members/E6b/pred_task1b.json" \
    --member "E6c=$ROOT/members/E6c/pred_task1b.json" \
    --out_dir "$ROOT/fusion/$cell" 2>&1 | tee -a "$LOG/fusion.log"
  "$PY" E7G4Flash0731Dev/scripts/score_fusion_cell.py \
    --cell "$cell" --run_dir "$ROOT/fusion/$cell" | tee -a "$LOG/fusion.log"
done

retry_run g4_dirqa 20 "$LOG/dirqa.log" "$PY" \
  RH_test/E7_calibrated_jury_fusion/scripts/run_direction_qa_e7.py \
  --in_run "$ROOT/fusion/G3_veto_add" --out_dir "$ROOT/fusion/G4_dirqa" \
  --articles "$ARTICLES" --fail_on_qa_error
"$PY" E7G4Flash0731Dev/scripts/score_fusion_cell.py \
  --cell G4_dirqa --run_dir "$ROOT/fusion/G4_dirqa" | tee -a "$LOG/fusion.log"

"$PY" RH_test/E7_calibrated_jury_fusion/scripts/bootstrap_e7.py \
  --system "G4=$ROOT/fusion/G4_dirqa/pred_task1b.json" \
  --system "G3=$ROOT/fusion/G3_veto_add/pred_task1b.json" \
  --system "E6b=$ROOT/members/E6b/pred_task1b.json" \
  --system "E1=$ROOT/members/E1/pred_task1b.json" \
  --system "Liu=$ROOT/members/Liu/pred_task1b.json" \
  --pairs G4:E6b G4:E1 G4:Liu --n 10000 \
  --out "$ROOT/report/bootstrap.json" | tee "$LOG/bootstrap.log"

date -Iseconds > "$ROOT/metadata/completed_at.txt"
echo "E7-G4 DEV refresh complete: $ROOT"
