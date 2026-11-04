# 已执行命令与恢复接口

以下是已完成pilot的命令记录，不是本次发布操作重新执行的实验。当前任务只整理、提交和推送。输出目录已存在，不能直接重跑覆盖结果。

实际解释器、工作目录、白名单环境及启动PID来自 [launcher.json](launcher.json)。逐条件真实argv、开始时间、耗时及退出码来自 [driver_result.json](driver_result.json)。

```bash
cd /home/szf-4090/projects/fehu-project-main-2da2ea5
FEHU_PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
FEHU_RUN=/home/szf-4090/projects/fehu-project-main-2da2ea5/ntcir19_fehu-master/output/task2_scope_local_v2/pilot_20261105-023648/execution
export PYTHONPATH=/home/szf-4090/projects/fehu-project-main-2da2ea5/ntcir19_fehu-master
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_PROGRESS_BARS=1 CUBLAS_WORKSPACE_CONFIG=:4096:8

# 已完成：有限driver在独立session中依次执行下列四阶段，没有自动重试。
"$FEHU_PY" -m research.task2_scope_local_v2.driver --run "$FEHU_RUN"

# driver实际依次调用的argv：
"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method T
"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method J
"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method S
"$FEHU_PY" -m research.task2_scope_local_v2.score --run "$FEHU_RUN"
```

官方评价器的八次真实命令位于 `tune_evaluation/{T,J,S,P}/{selected,fixed_05}/command.json`，对应原始 `stdout.json`、`stderr.txt` 和包含TP/FP/FN核对的 `metrics.json` 已一同提交。评价范围均为tune。

训练前的真实GPU预检命令为：

```bash
"$FEHU_PY" -m research.task2_scope_local_v2.preflight --run "$FEHU_RUN"
```

已实现、但本轮完整训练没有中断后使用的显式epoch恢复接口如下。它仅供今后另行授权的恢复，要求新输出目录、原始本机缓存/权重和匹配binding；不支持自动或microbatch中途恢复。

```bash
"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method J \
  --resume "$FEHU_RUN/J/epoch_1.pt" --out "$FEHU_RUN/J_recovered_new"
"$FEHU_PY" -m research.task2_scope_local_v2.score --run "$FEHU_RUN" \
  --j-dir "$FEHU_RUN/J_recovered_new" --out "$FEHU_RUN/tune_evaluation_recovered_new"
```

恢复一致性证据来自既有 `preflight/resume_consistency.json`，使用少量真实optimizer groups检查完整状态序列化和下一步一致性，不冒充实际完成了一次整epoch恢复实验。本次发布没有重新执行上述任何命令或CPU测试。
