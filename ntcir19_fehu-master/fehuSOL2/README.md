# FEHU SOL2

本目录独立保存 Step 1、Step 2 的实验思路、代码、模型输出、指标和验证结果。

## 最短结论

| 方法 | Precision | Recall | Micro-F1 | Macro-F1 | DRR ↓ | 判断 |
|---|---:|---:|---:|---:|---:|---|
| Pro non-thinking T=0 基线 | 0.5101 | 0.5732 | 0.5398 | 0.3914 | 0.0518 | 冻结基线 |
| Step 1 温度 residual | 0.4993 | 0.5950 | 0.5430 | 0.3953 | 0.0603 | NO-GO |
| Step 2 单 Actor standalone | 0.4373 | 0.6247 | 0.5145 | 0.3623 | 0.0684 | REJECT |
| Step 2 value agreement + T0 direction | 0.5579 | 0.5343 | **0.5458** | 0.3902 | **0.0455** | Dev 候选，需 TRAIN 复现 |

所有在线调用均为 `deepseek-v4-pro`、`thinking=disabled`、`temperature=0.0`。Step 2 共执行 459 个 actor 调用，459 个成功，无重试、无跨 actor 输出、无格式错误。

## 文件入口

- `fehuSOL2.md`：三步思路与已执行结果
- `outputs/step1_anchor/STEP1_REPORT.md`：Step 1 报告
- `runs/step2_single_actor_pro_t0/STEP2_REPORT.md`：Step 2 standalone 报告
- `runs/step2_single_actor_pro_t0/anchor_combinations/ANCHOR_COMBINATIONS_REPORT.md`：两 view 组合报告
- `VALIDATION_REPORT.md`：14 项产物一致性校验
- `scripts/`：执行、分析和校验代码
- `tests/`：离线不变量测试

下一步最简单且科学的动作不是立刻上 Step 3，而是在 TRAIN 内固定一个 calibration split，复现 `value_agreement_t0_direction`。只有它仍然优于 T=0，才冻结规则并进入 test。
