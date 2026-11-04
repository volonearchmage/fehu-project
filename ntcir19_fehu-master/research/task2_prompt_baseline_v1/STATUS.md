# 付费全量实验已停止，完成子集已评分

用户因成本于 2026-11-04 明确中止付费推理。保持 `USER_STOP.json`，不要自动续跑。

完成 508/1,526 个子事件，66 篇文章，1,328 个主体—事件组合；余下 1,018 个未完成。
离线评分新增 API 调用为 0。

| 任务 | Precision | Recall | Micro-F1 | Macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| Task-2a | 22.52% | 67.67% | 33.79% | 30.24% |
| Task-2b | 18.10% | 60.86% | 27.90% | 22.63% |

Task-2b DRR 为 13/981 = 1.3252%。这是非随机完成子集，不能视为完整 DEV 或 TEST。

- [报告](subset_evaluation_completed/RESULTS_zh.md)
- [官方指标](subset_evaluation_completed/metrics_official.json)
- [评分包](exports/completed_subset_official_scores.zip)
- [Linux 迁移说明](../../docs/linux_4090_handoff/README.md)

使用 `verify_offline.py` 在新目录离线复评。历史 runner 的直接 `run` 入口不检查停止标记，禁止调用。
原始请求、响应、冻结代码与历史指标保留不变。
