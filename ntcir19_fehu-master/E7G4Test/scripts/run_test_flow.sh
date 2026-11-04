#!/bin/bash
# E7G4Test orchestrator — frozen E7-G4 pipeline, one complete Task-1 test run.
# Every member pipeline/prompt/threshold is the frozen dev artifact; the only
# new inputs are the official test articles. Stages are cache-resumable; each
# stage gets an outer retry loop for API 503 bursts; after each member run a
# cache-health pass purges empty responses and re-fetches ONCE (loud abort on
# persistent API failure). No fallbacks.
set -u
cd /home/szf-4090/projects/fehu-project/ntcir19_fehu-master
set -a; source .env; set +a

RTS=e7g4test_20260726            # run-dir tag for member pipelines
T=E7G4Test
LOG=$T/logs
SEG6=$T/members/E6/segmentation/segments_test.json
SEG6B=$T/members/E6b/segmentation/segments_test.json
CONFIRMED=$LOG/confirmed_empty.txt
: > $CONFIRMED

outer() {  # outer <name> <max_attempts> <cmd...>
  local name=$1 max=$2; shift 2
  for i in $(seq 1 $max); do
    echo "=== [$name] outer attempt $i ($(date +%H:%M:%S)) ===" | tee -a $LOG/$name.log
    "$@" >> $LOG/$name.log 2>&1 && return 0
    echo "[$name] attempt $i failed; retrying in 90s" | tee -a $LOG/$name.log
    sleep 90
  done
  echo "[$name] EXHAUSTED $max attempts — ABORT"; exit 1
}

health() {  # health <name> <cache> <log> — purge+rerun-once protocol
  local name=$1 cache=$2 log=$3; shift 3
  python $T/scripts/cache_health.py --name $name --cache "$cache" \
      --log "$log" --articles dataset/test/test_article_event_base.json \
      --passno 1 | tee -a $LOG/health.log
  local rc=${PIPESTATUS[0]}
  if [ $rc -eq 2 ]; then
    echo "[$name] re-fetching purged articles" | tee -a $LOG/health.log
    "$@" >> $log 2>&1 || { echo "[$name] re-fetch run failed"; exit 1; }
    python $T/scripts/cache_health.py --name $name --cache "$cache" \
        --log "$log" --articles dataset/test/test_article_event_base.json \
        --passno 2 | tee -a $LOG/health.log
    rc=${PIPESTATUS[0]}
    [ $rc -ne 0 ] && { echo "[$name] health ABORT"; exit 1; }
    grep "^CONFIRMED_EMPTY" $LOG/health.log >> $CONFIRMED || true
  elif [ $rc -ne 0 ]; then
    echo "[$name] health ABORT"; exit 1
  fi
}

# ---------- S1/S2: segmentations (frozen prompts) ---------------------------
[ -f $SEG6 ] || outer seg_e6 20 python \
  RH_test/E6_e3a_self_segmentation/scripts/run_segmentation_e6.py \
  --mode test --model deepseek-v4-flash --out $SEG6
[ -f $SEG6B ] || outer seg_e6b 20 python \
  RH_test/E6b_granularity_control/scripts/run_segmentation_e6b.py \
  --mode test --model deepseek-v4-flash --out $SEG6B

# ---------- S3: E1 ----------------------------------------------------------
E1CMD=(python RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py
  --mode test --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced)
E1_RUN_TS=$RTS outer e1 20 "${E1CMD[@]}"
E1CACHE=RH_test/E1_fewshot_repair/runs/$RTS/cache_test_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health e1 $E1CACHE $LOG/e1.log env E1_RUN_TS=$RTS "${E1CMD[@]}"

# ---------- S4: Liu ---------------------------------------------------------
LIUCMD=(python liu_method/run_pipeline.py
  --mode test --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced)
outer liu 20 "${LIUCMD[@]}"
LIUCACHE=logs/cache_test_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health liu $LIUCACHE $LOG/liu.log "${LIUCMD[@]}"

# ---------- S5: E6 (fine segments) ------------------------------------------
E6CMD=(python RH_test/E6_e3a_self_segmentation/scripts/run_pipeline_e6.py
  --mode test --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced --segments $SEG6)
E6_RUN_TS=$RTS outer e6 20 "${E6CMD[@]}"
E6CACHE=RH_test/E6_e3a_self_segmentation/runs/$RTS/cache_test_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health e6 $E6CACHE $LOG/e6.log env E6_RUN_TS=$RTS "${E6CMD[@]}"

# ---------- S6: E6b (6-9 segments) ------------------------------------------
E6BCMD=(python RH_test/E6b_granularity_control/scripts/run_pipeline_e6b.py
  --mode test --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced --segments $SEG6B)
E6B_RUN_TS=$RTS outer e6b 20 "${E6BCMD[@]}"
E6BCACHE=RH_test/E6b_granularity_control/runs/$RTS/cache_test_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health e6b $E6BCACHE $LOG/e6b.log env E6B_RUN_TS=$RTS "${E6BCMD[@]}"

# ---------- S7: E6c (pro non-thinking, E6b segments) ------------------------
E6CCMD=(python RH_test/E6c_pro_nonthinking/scripts/run_pipeline_e6c.py
  --mode test --provider deepseek --model deepseek-v4-pro
  --prompt_variant targeted_more_shot_balanced --segments $SEG6B)
E6C_RUN_TS=$RTS outer e6c 20 "${E6CCMD[@]}"
E6CCACHE=RH_test/E6c_pro_nonthinking/runs/$RTS/cache_test_deepseek_deepseek-v4-pro_targeted_more_shot_balanced_temp0p1_max8000.json
health e6c $E6CCACHE $LOG/e6c.log env E6C_RUN_TS=$RTS "${E6CCMD[@]}"

# ---------- S8: frozen fusion, apply calibration ----------------------------
python RH_test/E7_calibrated_jury_fusion/scripts/run_fusion_e7.py \
  --cell G3_veto_add --primary_name E6b --calibration apply \
  --calibration_file $T/fusion/calfit_dev/calibration.json \
  --articles dataset/test/test_article_event_base.json \
  --v2_probs $T/inputs/test_v2_probabilities.jsonl \
  --member E1=RH_test/E1_fewshot_repair/runs/$RTS/pred_task1b.json \
  --member Liu=output/task1/runs/test_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000/pred_task1b.json \
  --member E6=RH_test/E6_e3a_self_segmentation/runs/$RTS/pred_task1b.json \
  --member E6b=RH_test/E6b_granularity_control/runs/$RTS/pred_task1b.json \
  --member E6c=RH_test/E6c_pro_nonthinking/runs/$RTS/pred_task1b.json \
  --out_dir $T/fusion/G3_veto_add >> $LOG/fusion.log 2>&1 \
  || { echo "FUSION APPLY FAILED"; tail -5 $LOG/fusion.log; exit 1; }

# ---------- S9: frozen direction-QA -----------------------------------------
outer dirqa 15 python \
  RH_test/E7_calibrated_jury_fusion/scripts/run_direction_qa_e7.py \
  --in_run $T/fusion/G3_veto_add --out_dir $T/fusion/G4_dirqa \
  --articles dataset/test/test_article_event_base.json

echo "E7G4TEST FLOW COMPLETE"
