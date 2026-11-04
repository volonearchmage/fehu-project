# SOL2 Step 2 — Anchor 组合离线分析

所有组合均为零 API、Dev 诊断。`value_agreement_t0_direction` 只保留两个 view 都提出的 value，并沿用原始 T=0 direction。

| 方法 | Micro-P | Micro-R | Micro-F1 | Macro-F1 | DRR | 预测数 | 1a Micro |
|---|---:|---:|---:|---:|---:|---:|---:|
| t0_base | 0.5101 | 0.5732 | 0.5398 | 0.3914 | 0.0518 | 2686 | 0.6804 |
| single_actor | 0.4373 | 0.6247 | 0.5145 | 0.3623 | 0.0684 | 3414 | 0.6604 |
| directed_intersection | 0.5683 | 0.5243 | 0.5454 | 0.3835 | 0.0378 | 2205 | 0.6760 |
| union | 0.4134 | 0.6736 | 0.5123 | 0.3748 | 0.0824 | 3895 | 0.6628 |
| value_agreement_t0_direction | 0.5579 | 0.5343 | 0.5458 | 0.3902 | 0.0455 | 2289 | 0.6784 |

**Micro-F1 最佳：`value_agreement_t0_direction` (0.5458)。**

注意：组合规则是看过 Dev 后的诊断结果，不能未经 TRAIN 内复现便直接冻结到 test。
