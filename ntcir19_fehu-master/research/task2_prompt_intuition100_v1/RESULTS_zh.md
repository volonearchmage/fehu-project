# Task 2 多方向无思考 prompt 实验

阶段：confirm；100 个子事件 × 3 个 prompt 全部完整；每个事件包含全部候选 actor。

探索锁定的主要方法：**VETO**。A 原始 prompt，B 主体/事件归属，C 行为/价值/方向。VETO=A∩(B∪C)；CONSENSUS=至少两个 prompt 同意同一 actor/value/direction。UNION 仅诊断，不参与选优。

| 方法 | 任务 | Precision | Recall | micro-F1 | TP/FP/FN |
|---|---|---:|---:|---:|---|
| A | task2a | 13.14% | 76.61% | 22.43% | 131/866/40 |
| A | task2b | 9.86% | 63.78% | 17.08% | 118/1079/67 |
| B | task2a | 14.27% | 73.68% | 23.91% | 126/757/45 |
| B | task2b | 10.55% | 60.54% | 17.96% | 112/950/73 |
| C | task2a | 13.93% | 77.78% | 23.62% | 133/822/38 |
| C | task2b | 10.49% | 64.86% | 18.06% | 120/1024/65 |
| VETO | task2a | 14.35% | 75.44% | 24.11% | 129/770/42 |
| VETO | task2b | 10.79% | 62.16% | 18.39% | 115/951/70 |
| CONSENSUS | task2a | 13.89% | 76.02% | 23.49% | 130/806/41 |
| CONSENSUS | task2b | 10.45% | 63.24% | 17.93% | 117/1003/68 |
| UNION | task2a | 12.21% | 80.12% | 21.19% | 137/985/34 |
| UNION | task2b | 8.83% | 68.11% | 15.63% | 126/1301/59 |

所有分数通过官方 CLI 和独立计数/DRR 核对；失败响应未当作空预测。探索 12 条来自 TRAIN fit、每文一条，正文和标题均不与 DEV 重合，是开发探索数据，不能称独立测试。

确认 100 条由全部 1526 个 DEV 事件按冻结 hash 选出，覆盖 78 篇文章、267 个 actor/event。不是完整 DEV/TEST；应检查长度、actor数、文章聚类与 TRAIN 重合等差异。确认成绩不会改变已锁定 primary。

三个 prompt 是同一模型的不同指令视角，错误不独立，投票不保证提升；交集策略可能提高精度但降低召回。与历史 max 的比较只针对确认样本和旧 508 成功事件的交集，同时存在时间、模型版本、温度和输出上限差异，不能当作‘思考开关’因果实验。

全部阶段已知 usage：{"returned_attempts": 336, "usage": {"prompt_tokens": 1341312, "completion_tokens": 74985, "total_tokens": 1416297, "prompt_cache_hit_tokens": 920832, "prompt_cache_miss_tokens": 420480, "reasoning_tokens_field_missing_responses": 336, "reasoning_content_nonempty_responses": 0}, "models": {"deepseek-flash": 336}, "fingerprints": {"bc19ba97cbe016479903222bb1578db6": 336}, "known_usage_peak_uncached_estimate_usd": "0.4923756", "global_charge_plus_unsettled_reservations_usd": "0.4923756", "attempts": 336, "technical_retries": 0, "not_account_bill": true, "all_returned_attempts_have_explicit_zero_reasoning": false, "missing_reasoning_usage_is_not_verified_zero": true}。成本为峰值无缓存折扣估算，不是账户账单；未知 usage 请求保留完整最坏预留。共享硬上限 US$1.50 / 360 attempts，可能导致实验无法完成。

原 USER_STOP.json 保留。本目录 RUN_STOP.json 可停止后续请求；stage RUN_STARTED.json 阻止自动重跑；没有查询账户余额。
