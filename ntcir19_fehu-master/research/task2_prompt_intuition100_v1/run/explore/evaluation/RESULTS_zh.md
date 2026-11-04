# Task 2 多方向无思考 prompt 实验

阶段：explore；12 个子事件 × 3 个 prompt 全部完整；每个事件包含全部候选 actor。

探索锁定的主要方法：**VETO**。A 原始 prompt，B 主体/事件归属，C 行为/价值/方向。VETO=A∩(B∪C)；CONSENSUS=至少两个 prompt 同意同一 actor/value/direction。UNION 仅诊断，不参与选优。

| 方法 | 任务 | Precision | Recall | micro-F1 | TP/FP/FN |
|---|---|---:|---:|---:|---|
| A | task2a | 11.45% | 88.24% | 20.27% | 15/116/2 |
| A | task2b | 10.32% | 76.19% | 18.18% | 16/139/5 |
| B | task2a | 12.10% | 88.24% | 21.28% | 15/109/2 |
| B | task2b | 10.00% | 71.43% | 17.54% | 15/135/6 |
| C | task2a | 12.12% | 94.12% | 21.48% | 16/116/1 |
| C | task2b | 10.56% | 80.95% | 18.68% | 17/144/4 |
| VETO | task2a | 12.00% | 88.24% | 21.13% | 15/110/2 |
| VETO | task2b | 10.74% | 76.19% | 18.82% | 16/133/5 |
| CONSENSUS | task2a | 11.72% | 88.24% | 20.69% | 15/113/2 |
| CONSENSUS | task2b | 10.53% | 76.19% | 18.50% | 16/136/5 |
| UNION | task2a | 11.26% | 100.00% | 20.24% | 17/134/0 |
| UNION | task2b | 9.63% | 85.71% | 17.31% | 18/169/3 |

所有分数通过官方 CLI 和独立计数/DRR 核对；失败响应未当作空预测。探索 12 条来自 TRAIN fit、每文一条，正文和标题均不与 DEV 重合，是开发探索数据，不能称独立测试。

确认 100 条由全部 1526 个 DEV 事件按冻结 hash 选出，覆盖 78 篇文章、267 个 actor/event。不是完整 DEV/TEST；应检查长度、actor数、文章聚类与 TRAIN 重合等差异。确认成绩不会改变已锁定 primary。

三个 prompt 是同一模型的不同指令视角，错误不独立，投票不保证提升；交集策略可能提高精度但降低召回。与历史 max 的比较只针对确认样本和旧 508 成功事件的交集，同时存在时间、模型版本、温度和输出上限差异，不能当作‘思考开关’因果实验。

全部阶段已知 usage：{"returned_attempts": 36, "usage": {"prompt_tokens": 143154, "completion_tokens": 9064, "total_tokens": 152218, "prompt_cache_hit_tokens": 88832, "prompt_cache_miss_tokens": 54322, "reasoning_tokens_field_missing_responses": 36, "reasoning_content_nonempty_responses": 0}, "models": {"deepseek-flash": 36}, "fingerprints": {"bc19ba97cbe016479903222bb1578db6": 36}, "known_usage_peak_uncached_estimate_usd": "0.0538230", "global_charge_plus_unsettled_reservations_usd": "0.0538230", "attempts": 36, "technical_retries": 0, "not_account_bill": true, "all_returned_attempts_have_explicit_zero_reasoning": false, "missing_reasoning_usage_is_not_verified_zero": true}。成本为峰值无缓存折扣估算，不是账户账单；未知 usage 请求保留完整最坏预留。共享硬上限 US$1.50 / 360 attempts，可能导致实验无法完成。

原 USER_STOP.json 保留。本目录 RUN_STOP.json 可停止后续请求；stage RUN_STARTED.json 阻止自动重跑；没有查询账户余额。
