# Flash Direction Verification on Temperature Consensus Candidates

**日期：** 2026-07-24
**实验类型：** 零 API 后处理分析
**基线：** E1 Pro T=0.0 (non-thinking), 177 dev, 1b Micro 0.5398

---

## 一、实验设计

### 数学框架：Value/Direction Decomposition

$$\text{Pro T=0.0}: x \rightarrow S_0 \quad \text{(高精度基座，价值识别 + 方向)}$$
$$\text{Pro T=0.1+T=0.3 共识}: x \rightarrow R \quad \text{(162 个边界候选标签)}$$
$$\text{Flash}: (x, l \in R) \rightarrow \hat{d} \quad \text{(方向校正 oracle)}$$

$$S_{final} = S_0 \cup \{ (l, d_{flash}) : l \in R \land \text{Flash 对 } l \text{ 有方向判断} \}$$

### 规则

| Flash 判断 | 操作 | 含义 |
|---|---|---|
| Flash 预测了相同的 (actor, l1) 且方向一致 | **保留** Pro 的方向 | Flash 确认 |
| Flash 预测了相同的 (actor, l1) 但方向相反 | **保留但翻转**方向为 Flash 的 | Flash 方向更可靠 |
| Flash 未预测该 (actor, l1) | **丢弃** | Flash 未找到证据，疑为 FP |

---

## 二、结果

### 2.1 R 候选的 Flash 分类

| 分组 | 数量 | TP | FP | Precision | 操作 |
|---|---|---|---|---|---|
| Flash 方向一致 | 46 | 20 | 26 | 0.4348 | 保留 |
| **Flash 方向翻转** | **13** | **10** | **3** | **0.7692** | 保留(翻转) |
| Flash 无判断 | 103 | 30 | 73 | 0.2913 | 丢弃 |

关键发现：**Flash 方向翻转组 Precision 0.77**——当 Flash 和 Pro 在方向上不一致时，Flash 的判断非常可靠。

### 2.2 全量评测对比

| 指标 | T=0.0 (S0) | S0∪R | **S0∪Flash(R)** | Δ vs S0 |
|---|---|---|---|---|
| **1b Micro F1** | 0.5398 | 0.5430 | **0.5428** | **+0.0030** |
| **1b Macro F1** | 0.3914 | 0.3953 | **0.4020** | **+0.0106** 🔥 |
| 1b Precision | 0.5101 | 0.4993 | 0.5086 | −0.0015 |
| 1b Recall | 0.5732 | 0.5950 | 0.5820 | +0.0088 |
| **DRR** | 0.0518 | 0.0603 | **0.0540** | +0.0022 |
| DRR 翻转数 | 115/2222 | 134/2222 | 120/2222 | +5 |
| | | | | |
| 1a Micro F1 | 0.6804 | 0.6808 | **0.6826** | +0.0022 |
| 1a Macro F1 | 0.5544 | 0.5535 | **0.5557** | +0.0013 |
| | | | | |
| 预测总数 | 2,686 | 2,848 | 2,735 | +49 |

### 2.3 三方案对比

| 维度 | S0∪R (纯共识) | S0∪Flash(R) | 解读 |
|---|---|---|---|
| Micro 增益 | +0.0032 | +0.0030 | 接近 |
| **Macro 增益** | +0.0039 | **+0.0106** | Flash 验证 2.7× |
| DRR 恶化 | +0.0085 | **+0.0022** | Flash 压制 74% |
| 保留候选 | 162/162 | **59/162 (36%)** | 精选 |

**Flash 方向验证在保留 Micro 增益的同时，将 Macro 增益放大 2.7 倍，DRR 恶化压缩 74%。**

---

## 三、与已有系统对比

| 指标 | S0∪Flash(R) | 刘 frozen | 刘 Ensemble | Hybrid H3 |
|---|---|---|---|---|
| 1b Micro | 0.5428 | 0.535 | **0.5543** | 0.5474 |
| 1b Macro | **0.4020** | 0.339 | 0.3277 | 0.338 |
| 1b Precision | 0.5086 | **0.568** | — | 0.548 |
| DRR | 0.0540 | **0.023** | 0.0345 | 0.031 |
| 1a Micro | **0.6826** | 0.645 | — | 0.662 |
| 1a Macro | **0.5557** | 0.478 | 0.5366 | 0.503 |

**1b Macro 0.4020 是所有系统中最高！** 1a 也全面领先。

---

## 四、数学解释

### 4.1 为什么 Flash 方向翻转组 Precision 这么高？

Flash DRR=0.032 vs Pro DRR=0.052。当两者方向冲突时：

$$P(\text{Flash 正确} | \text{Flash} \neq \text{Pro}) = \frac{P(\text{Flash 正确}) \cdot P(\text{Pro 错误})}{P(\text{冲突})}$$

Flash 正确率 ≈ 0.968，Pro 正确率 ≈ 0.948，两者独立假设下：
$$P(\text{Flash 正确} | \text{冲突}) \approx \frac{0.968 \times 0.052}{0.968\times0.052 + 0.032\times0.948} \approx 0.62$$

但实际观测是 0.77——说明冲突不是随机的，而是 Pro 系统性在某些标签上方向判断薄弱。

### 4.2 总体策略验证

Value/Direction Decomposition 在 Pro+Flash 组合上也成立：

$$\text{Pro}: \text{高 Recall (标签覆盖)} \quad (0.573 \rightarrow 0.582)$$
$$\text{Flash}: \text{高 Precision 方向} \quad (\text{DRR 0.032})$$
$$\text{组合}: \text{取两者之长} \quad (\text{Micro +0.003, Macro +0.011})$$

这与 Hybrid H3 的核心范式一致，但实现更轻量（无需训练 DeBERTa）。

---

## 五、文件路径

```
Mathematical_optimization/
├── flash_direction_verify/
│   ├── pred_task1a.json
│   ├── pred_task1b.json
│   ├── metrics.json
│   └── docs/
│       └── FLASH_DIRECTION_VERIFY_20260724.md  ← 本报告
├── temperature_ablation/
│   ├── t0.0/
│   ├── t0.1/
│   ├── t0.3/
│   ├── t_consensus/
│   └── docs/
└── docs/
    └── DS_A3_A4_A5_E1PRO_20260724.md
```

---

## 六、下一步

1. **提交候选：** S0∪Flash(R) 在 1b Macro 0.4020 和 1a Micro 0.6826 创下新高，可考虑作为 test 提交
2. **DRR 仍有空间：** 0.0540 vs 刘的 0.023，可尝试对 R 中 Flash 无判断的 103 个候选做精筛（目前全部丢弃）
3. **真实 Flash API 验证：** 本实验用已有 Flash 预测做 oracle，正式提交前应对 R 候选调用 Flash API 做定向验证
