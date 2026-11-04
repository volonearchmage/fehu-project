#!/bin/bash
# E7G4Flash0731Dev stage 2 — run AFTER all members complete:
#   1. score every member with the official evaluator
#   2. run the frozen E7 fusion grid (crossfit) on the new members
#   3. G4 direction-QA on the G3 output
#   4. paired article bootstrap
# v2-probs substitution documented in run_dev_flow.sh header.
set -u
cd /Users/lloydhuang/Documents/GitHub/fehu-project/ntcir19_fehu-master
set -a; source .env; set +a
PY=venv/bin/python

RTS=e7g4_fl0731_20260813
T=E7G4Flash0731Dev
FUS=RH_test/E7_calibrated_jury_fusion/scripts/run_fusion_e7.py
QA=RH_test/E7_calibrated_jury_fusion/scripts/run_direction_qa_e7.py
BS=RH_test/E7_calibrated_jury_fusion/scripts/bootstrap_e7.py
SC=$T/scripts/score_member.py
FC=$T/scripts/score_fusion_cell.py
V2=RH_test/E5_deberta_auxiliary_fusion/inputs/dev_fp_seed44_probs.jsonl
E1=RH_test/E1_fewshot_repair/runs/$RTS
LIU=output/task1/runs/dev_deepseek_deepseek-v4-flash_targeted_more_shot_balanced_temp0p1_max8000
E6=RH_test/E6_e3a_self_segmentation/runs/$RTS
E6B=RH_test/E6b_granularity_control/runs/$RTS
E6C=RH_test/E6c_pro_nonthinking/runs/$RTS

mkdir -p $T/report

# ---------- 1. member scoring ----------------------------------------------
M=$T/report/members.json; rm -f $M
for spec in "E1:$E1" "Liu:$LIU" "E6:$E6" "E6b:$E6B" "E6c:$E6C"; do
  name=${spec%%:*}; dir=${spec#*:}
  if [ -f "$dir/pred_task1b.json" ]; then
    $PY $SC --name $name --run_dir "$dir" --out $M --append
  else
    echo "[score] MISSING predictions for $name at $dir"
  fi
done

# ---------- 2. fusion grid (crossfit, dev) -----------------------------------
for cell in G0_passthrough G1_veto G2_veto_noliu G3_veto_add G5_veto_nogate; do
  OUT=$T/fusion/$cell
  [ -d "$OUT" ] && { echo "[fusion] $cell exists, skipping"; continue; }
  $PY $FUS --cell $cell --primary_name E6b \
    --articles dataset/dev/dev_event_base.json \
    --gold_1b dataset/gold_labels/dev/dev_human_values.json \
    --v2_probs $V2 \
    --member E1=$E1/pred_task1b.json \
    --member Liu=$LIU/pred_task1b.json \
    --member E6=$E6/pred_task1b.json \
    --member E6b=$E6B/pred_task1b.json \
    --member E6c=$E6C/pred_task1b.json \
    --out_dir $OUT >> $T/logs/fusion.log 2>&1 \
    || { echo "FUSION $cell FAILED"; tail -5 $T/logs/fusion.log; exit 1; }
  $PY $FC --cell $cell --run_dir $OUT | tee -a $T/logs/fusion.log
done

# ---------- 3. G4 direction-QA ----------------------------------------------
if [ ! -d "$T/fusion/G4_dirqa" ]; then
  $PY $QA --in_run $T/fusion/G3_veto_add --out_dir $T/fusion/G4_dirqa \
    --articles dataset/dev/dev_event_base.json \
    >> $T/logs/dirqa.log 2>&1 \
    || { echo "DIRQA FAILED"; tail -5 $T/logs/dirqa.log; exit 1; }
fi
$PY $FC --cell G4_dirqa --run_dir $T/fusion/G4_dirqa | tee -a $T/logs/fusion.log

# ---------- 4. bootstrap -----------------------------------------------------
$PY $BS \
  --system "G4=$T/fusion/G4_dirqa/pred_task1b.json" \
  --system "G3=$T/fusion/G3_veto_add/pred_task1b.json" \
  --system "E6b=$E6B/pred_task1b.json" \
  --system "E1=$E1/pred_task1b.json" \
  --system "Liu=$LIU/pred_task1b.json" \
  --pairs G4:E6b G4:E1 G4:Liu \
  --n 10000 --out $T/report/bootstrap.json \
  | tee $T/logs/bootstrap.log

echo "E7G4 FLASH-0731 DEV FUSION COMPLETE"
