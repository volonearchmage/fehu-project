#!/bin/bash
# E7G4Flash0731Dev orchestrator — re-run the frozen E7-G4 pipeline on DEV with
# the upgraded DeepSeek V4 Flash 0731 snapshot (same model id: deepseek-v4-flash).
#
# Mirrors E7G4Test/scripts/run_test_flow.sh but:
#   - mode = dev (gold available -> measurable effect of the flash upgrade)
#   - macOS paths, venv python
#   - fresh run-dir tags (e7g4_fl0731_20260813) so NO old-flash cache is reused
#   - v2-probs substitution: dev_fp_seed44_probs.jsonl (E5 frozen copy of the
#     F' seed-44 probabilities; the original 02_deberta_actor_probabilities.jsonl
#     is not present on this machine) — documented, not silent.
#
# Stages are cache-resumable; each member stage has an outer retry loop for API
# 503 bursts; after each member run a cache-health pass purges empty responses
# and re-fetches ONCE (loud abort on persistent API failure). No fallbacks.
set -u
cd /Users/lloydhuang/Documents/GitHub/fehu-project/ntcir19_fehu-master
set -a; source .env; set +a
PY=venv/bin/python

RTS=e7g4_fl0731_20260813            # run-dir tag for member pipelines
T=E7G4Flash0731Dev
LOG=$T/logs
SEG=$T/segmentation
SEG6=$SEG/e6/segments_dev.json
SEG6B=$SEG/e6b/segments_dev.json
CONFIRMED=$LOG/confirmed_empty.txt
: > $CONFIRMED
mkdir -p $SEG/e6 $SEG/e6b

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
  $PY E7G4Test/scripts/cache_health.py --name $name --cache "$cache" \
      --log "$log" --articles dataset/dev/dev_event_base.json \
      --passno 1 | tee -a $LOG/health.log
  local rc=${PIPESTATUS[0]}
  if [ $rc -eq 2 ]; then
    echo "[$name] re-fetching purged articles" | tee -a $LOG/health.log
    "$@" >> $log 2>&1 || { echo "[$name] re-fetch run failed"; exit 1; }
    $PY E7G4Test/scripts/cache_health.py --name $name --cache "$cache" \
        --log "$log" --articles dataset/dev/dev_event_base.json \
        --passno 2 | tee -a $LOG/health.log
    rc=${PIPESTATUS[0]}
    [ $rc -ne 0 ] && { echo "[$name] health ABORT"; exit 1; }
    grep "^CONFIRMED_EMPTY" $LOG/health.log >> $CONFIRMED || true
  elif [ $rc -ne 0 ]; then
    echo "[$name] health ABORT"; exit 1
  fi
}

# ---------- S1/S2: segmentations (frozen prompts, new flash) ----------------
[ -f $SEG6 ] || outer seg_e6 20 $PY \
  RH_test/E6_e3a_self_segmentation/scripts/run_segmentation_e6.py \
  --mode dev --model deepseek-v4-flash --out $SEG6
[ -f $SEG6B ] || outer seg_e6b 20 $PY \
  RH_test/E6b_granularity_control/scripts/run_segmentation_e6b.py \
  --mode dev --model deepseek-v4-flash --out $SEG6B

# ---------- S3: E1 ----------------------------------------------------------
E1CMD=($PY RH_test/E1_fewshot_repair/scripts/run_pipeline_e1.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced)
E1_RUN_TS=$RTS outer e1 20 "${E1CMD[@]}"
E1CACHE=RH_test/E1_fewshot_repair/runs/$RTS/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health e1 $E1CACHE $LOG/e1.log env E1_RUN_TS=$RTS "${E1CMD[@]}"

# ---------- S4: Liu ---------------------------------------------------------
# Guard: Liu's output dir tag is fixed by its naming scheme. If a frozen
# old-flash dev run exists, preserve it before overwriting.
LIU_OLD=output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000
if [ -d $LIU_OLD ]; then
  echo "[liu] backing up existing dev run dir -> ${LIU_OLD}_oldflash_backup"
  mv $LIU_OLD ${LIU_OLD}_oldflash_backup
fi
LIUCMD=($PY liu_method/run_pipeline.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced)
outer liu 20 "${LIUCMD[@]}"
LIUCACHE=logs/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health liu $LIUCACHE $LOG/liu.log "${LIUCMD[@]}"

# ---------- S5: E6 (fine segments) ------------------------------------------
E6CMD=($PY RH_test/E6_e3a_self_segmentation/scripts/run_pipeline_e6.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced --segments $SEG6)
E6_RUN_TS=$RTS outer e6 20 "${E6CMD[@]}"
E6CACHE=RH_test/E6_e3a_self_segmentation/runs/$RTS/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health e6 $E6CACHE $LOG/e6.log env E6_RUN_TS=$RTS "${E6CMD[@]}"

# ---------- S6: E6b (6-9 segments, primary) ---------------------------------
E6BCMD=($PY RH_test/E6b_granularity_control/scripts/run_pipeline_e6b.py
  --mode dev --provider deepseek --model deepseek-v4-flash
  --prompt_variant targeted_more_shot_balanced --segments $SEG6B)
E6B_RUN_TS=$RTS outer e6b 20 "${E6BCMD[@]}"
E6BCACHE=RH_test/E6b_granularity_control/runs/$RTS/cache_dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000.json
health e6b $E6BCACHE $LOG/e6b.log env E6B_RUN_TS=$RTS "${E6BCMD[@]}"

# ---------- S7: E6c (pro non-thinking, NEW E6b segments) --------------------
E6CCMD=($PY RH_test/E6c_pro_nonthinking/scripts/run_pipeline_e6c.py
  --mode dev --provider deepseek --model deepseek-v4-pro
  --prompt_variant targeted_more_shot_balanced --segments $SEG6B)
E6C_RUN_TS=$RTS outer e6c 20 "${E6CCMD[@]}"
E6CCACHE=RH_test/E6c_pro_nonthinking/runs/$RTS/cache_dev_deepseek_deepseek-v4-pro_targeted_more_shot_balanced_temp0p1_max8000.json
health e6c $E6CCACHE $LOG/e6c.log env E6C_RUN_TS=$RTS "${E6CCMD[@]}"

echo "E7G4 FLASH-0731 DEV MEMBERS COMPLETE"
