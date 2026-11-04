# v2 pilot 审阅包

本目录只整理已经完成的 `pilot_20261105-023648/execution` 结果。本次交付没有追加训练、推理、指标计算或官方评分，也没有访问 holdout/DEV/TEST gold。

主报告：[PILOT_RESULTS.md](PILOT_RESULTS.md)。该副本与 Linux 原始报告逐字节一致；报告中“未push”等措辞描述实验完成时的历史状态。本次单独提交与推送审阅包，不改写原始结果。

| 审阅内容 | 文件 |
| --- | --- |
| 实际运行的 v2 源码 | [上级源码目录](../..)；与 [source_final_sha256.json](source_final_sha256.json) 对应 |
| 固定协议原文 | [05协议](protocol_reference/05_task2_research_protocol_v2.md)、[06执行要求](protocol_reference/06_run_task2_pilot_v2.txt)；发布提交 `d9d070ba1290c30520f8a56c053fb753fe30e956` |
| 来源与复制校验 | [PROVENANCE.json](PROVENANCE.json)、[COPY_MANIFEST.json](COPY_MANIFEST.json)、[REVIEW_FILES.json](REVIEW_FILES.json) |
| 冻结配置与实际命令 | [frozen.json](frozen.json)、[T](config_T.json)/[J](config_J.json)/[S](config_S.json)、[COMMANDS.md](COMMANDS.md)、[launcher.json](launcher.json)、[driver_result.json](driver_result.json) |
| 每个 epoch 的损失和 tune 指标 | `T/epoch_1.json` 至 `S/epoch_3.json`；[CSV曲线数据](learning_curves.csv)；三组 `training.jsonl` 保留全部498步的原始计时/LR/损失记录 |
| 完整曲线 | [学习曲线PNG](learning_curves.png)/[PDF](learning_curves.pdf)，[选定模型PR PNG](tune_pr_curves.png)/[PDF](tune_pr_curves.pdf)；各组每轮及各选定方法的 `pr_curve*.npz` 保存全部扫描边界 |
| T/J/S/P选型和官方结果 | [汇总](tune_evaluation/summary.json)；各方法 `selection.json`、`selected/metrics.json`、`fixed_05/metrics.json`、命令和原始stdout |
| 预测及覆盖核对 | 各方法 `selected/`、`fixed_05/` 中官方格式预测及 `coverage.json`；[tune gold](tune_evaluation/tune_gold.json) 和 [来源](tune_evaluation/gold_provenance.json) |
| 每个标签的预测数量 | 各方法 `diagnostics.json` 的 `per_class[].predicted_positives`，并提供 [T](tune_evaluation/T/per_label_predictions.csv)/[J](tune_evaluation/J/per_label_predictions.csv)/[S](tune_evaluation/S/per_label_predictions.csv)/[P](tune_evaluation/P/per_label_predictions.csv) 的逐字段CSV转录 |
| 机制与错误例子 | 各方法 `diagnostics.json`；[方法差异和TP/FP例子](tune_evaluation/comparisons.json) |
| 输入完整性与缓存hash | [manifest](input_cache/manifest.json)、[fit逐bag清单](input_cache/fit.coverage.json)、[tune逐bag清单](input_cache/tune.coverage.json)；不包含token缓存本体 |
| 工程检查与失败尝试 | [真实GPU receipt](preflight/receipt.json)、[恢复一致性](preflight/resume_consistency.json)、[工程修订](ENGINEERING_CHANGE.md)、[先前失败诊断](prior_attempt/resume_failure_diagnosis.json)、[确定性复核](prior_attempt/resume_deterministic_diagnosis.json) |
| 缺失指标和本地大文件 | [METRIC_AVAILABILITY.md](METRIC_AVAILABILITY.md)、[LOCAL_ONLY_ARTIFACTS.json](LOCAL_ONLY_ARTIFACTS.json) |

本轮开发集结果：Task2b F1 T10.58%、J10.92%、S11.28%、P11.37%；固定0.5均全空。S相对J小幅提高F1，同时降低召回；尚无优于P的证据。这些是单种子、三轮、经过tune选择的弱开发结果。

`per_label_predictions.csv` 仅转录已有JSON字段，没有重新评分。AP的空CSV单元格对应原始JSON中的 `null`：该类tune正例支持为0，AP未定义；不能解释为0或测量缺失。未记录的指标另有明确清单。

原报告中的“上级 `protocol_reference/`”“上级 `focused_cpu_checks.json`”“上级 `resume_*_diagnosis.json`”指原Linux目录布局；审阅包分别放在本目录的 `protocol_reference/` 和 `prior_attempt/`。绝对checkpoint/缓存路径仍是本机来源路径；本仓库不包含这些大文件。PR曲线NPZ是小型数值审计结果，不是模型权重或token缓存。

源文件、模型、数据和代码hash引用的 v1/evaluator 依赖已在基底提交 `9d162c6dd8e971cd58e1e240891892de129dc62b` 中；本次仅提交当前 v2 源码和本审阅目录。根目录及 v1 的其他未提交修改保持原状。`USER_STOP.json` 和全部历史证据不变。
