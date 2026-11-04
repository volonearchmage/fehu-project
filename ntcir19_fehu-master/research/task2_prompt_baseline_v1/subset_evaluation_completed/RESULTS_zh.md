# 已完成子集的官方评分（全量运行已由用户中止）

评分时间：2026-11-04T20:00:07.275484+09:00。本次完全离线，新增模型调用为 0。

范围：508/1526 个子事件（33.29%），涉及 66 篇文章、1328 个主体—子事件组合。其中 50 篇文章的全部子事件已完成。

模型请求为 deepseek-flash，thinking enabled，reasoning_effort=max。冻结的零样本 prompt 使用当前子事件、全文背景及官方价值定义。

| 任务 | Micro精确率 % | Micro召回率 % | Micro-F1 % | Macro-F1 % |
| --- | ---: | ---: | ---: | ---: |
| task2a | 22.52 | 67.67 | 33.79 | 30.24 |
| task2b | 18.10 | 60.86 | 27.90 | 22.63 |

Task-2b DRR：1.3252%；方向反转 13/981。
Task-2b TP / FP / FN：597 / 2701 / 384。

本次结果的主要问题是过度预测：输出了 3,298 个有向标签，而金标为 981 个；精确率为 18.10%，召回率为 60.86%。
716 个主体—事件组合的金标为空，其中 247 个仍被预测为非空，贡献 964 个误报。
误报最多的前三个有向类别为：1:22 Have good health（TP=16, FP=193, FN=3）；1:42 Be responsible（TP=110, FP=166, FN=41）；1:13 Be capable（TP=23, FP=147, FN=1）。
这些统计支持优先检查标签纳入标准和事件归属；没有同子集、同 prompt 的非思考对照，因此不能据此把问题单独归因于 max 模式。

仅保留成功完成的 guid/subevent_id 对应金标，并用官方评分器命令行运行。未运行的子事件不作为空预测或漏报计入本次评分。
评分器来自固定官方 commit，仅关闭硬编码 DEBUG 路径覆盖；指标和 parser 未改动。独立集合计数复核 Micro/Macro-F1 与 DRR 计数通过。

这批样本由并发完成状态决定，并非随机三分之一；输出截断、限流和耗时可能造成选择偏差。Macro-F1 只平均本子集中有金标支持的标签。
因此这是约三分之一 DEV 的探索性结果，不能直接与完整 DEV 的其他系统分数相减，也不能当作全量或官方 TEST 成绩。

按金标分解 FP：同主体文章金标也没有该有向标签 1308；文章有该标签、当前事件无该标签 1393。
上述为标签集合对照，不等价于逐例人工确认的语义错误原因。

全部已返回 full-run 尝试的 API 用量：{"prompt_tokens": 2352840, "completion_tokens": 11356724, "total_tokens": 13709564, "prompt_cache_hit_tokens": 1677808, "prompt_cache_miss_tokens": 675032}。包含失败的截断响应，不代表本次离线评分新增费用。

结果文件：metrics_official.json、gold_subset.json、pred_task2a.json、pred_task2b.json、evaluation_manifest.json、逐标签/文章/主体事件 CSV 及 errors.jsonl。
