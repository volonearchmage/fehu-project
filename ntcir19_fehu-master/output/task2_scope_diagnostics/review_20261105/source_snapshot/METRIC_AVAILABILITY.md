# 已有指标与未记录项

本次只复制或逐字段转录已有文件，不运行模型，不执行评价器，不从概率缓存重新生成缺失指标。

| 内容 | 记录状态与位置 |
| --- | --- |
| 每epoch fit事件/文章/总损失 | 已记录：`T/J/S/epoch_*.json`；训练模式下不断更新参数的累计值，不是固定checkpoint的fit评估loss |
| 每epoch fit正/负标签BCE | 已记录：同上；按有效label cells平均 |
| 每步LR、梯度有限性、bags/microbatches、吞吐、显存 | 已记录：`T/J/S/training.jsonl`；汇总见 `training_cost.json` |
| fit的P/R/F1、AP和完整fit预测 | **未记录**；没有为补齐而重新推理或评分 |
| tune每epoch精确选阈值P/R/F1、TP/FP/FN、micro-AP、固定0.5结果 | 已记录：各epoch JSON及 `learning_curves.csv` |
| tune的BCE/eval loss | **未记录** |
| T/J/S/P选定epoch、精确阈值、官方2a/2b micro/macro F1与计数 | 已记录：`tune_evaluation/*/selection.json` 及 `selected/metrics.json`；P只使用已选J epoch3 |
| 逐epoch与选定模型的完整PR曲线 | 已记录：所有 `pr_curve*.npz`，包含原始概率阈值与对应累计计数，没有抽样替代完整曲线 |
| 概率直方图、分位数、均值/方差 | **未记录**；本次未新增统计 |
| 正/负标签平均预测概率 | **未记录**；已有正/负BCE不能冒充平均概率 |
| 逐候选article/event原始概率 | 已记录但体积较大，本机保留。`LOCAL_ONLY_ARTIFACTS.json` 列出每epoch原始概率和选定方法分数缓存的路径、字节数及既有SHA-256；不上传这些缓存 |
| 各标签预测数量、fit/tune支持数、TP/FP/FN | 已记录于各方法 `diagnostics.json`；CSV为字段转录，未重新计算 |
| 各标签概率直方图或分位数 | **未记录** |
| 机制诊断 | 已记录：选定模型tune上的原始event>article率、正负文章项max承接、文章独有标签误报、空候选误报、同文多主体差异 |
| 整个训练过程的逐步max梯度归属 | **未记录**；选定checkpoint的tune诊断不是训练全程的梯度统计 |
| holdout/DEV/TEST效果、额外seed或更长预算 | **未记录／未执行**，本次没有补做 |

完整PR边界反映已经保存的全体有效候选×108标签分数排序，但本审阅包不把它改称为已经记录了概率直方图、分位数或概率校准评估。
