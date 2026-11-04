# SOL2 Step 3: Direction QA Fix — Report

**日期：** 2026-07-26
**方法：** Flash 作为方向 oracle，修复 T=0 baseline 的方向错误
**基线：** Pro T=0.0 baseline (Micro 0.5398, DRR 0.0518)

---

## 一、方法

### 策略（per fehuSOL2.md §3.2）

保持 value 集合完全不变，只对方向做修正：

1. **方向冲突检测**：T=0 和 single-actor 对同一 (actor, L1) 预测不同方向 → 119 对冲突
2. **高 DRR 类识别**：从 T=0 baseline 在 dev 上统计每类 DRR → 识别 top-10 高风险类
3. **Flash 方向覆盖**：对 T=0 的每个预测，若 Flash 有方向判断且与 T=0 不同 → 翻转为 Flash 方向

### 零 API 成本

使用已有 Flash 全量预测 (`runs/20260724_160254/`) 作为方向 oracle，无需额外 API 调用。

---

## 二、结果

### 2.1 方向冲突分析

```
T=0 vs single-actor direction conflicts: 119 pairs
主要冲突类: L1=26, 27, 44 (安全/稳定/平等类)
```

### 2.2 高 DRR 类 Top-5

| 类 | DRR | 翻转/总数 |
|---|---|---|
| 1:20 | 0.600 | 3/5 |
| 1:25 | 0.583 | 7/12 |
| 0:18 | 0.500 | 4/8 |
| 1:40 | 0.500 | 3/6 |
| 0:42 | 0.352 | 19/54 |

### 2.3 Flash 方向修正

```
Flash flipped:  98 directions
Flash kept:    2588 directions
```

### 2.4 全量评测

| 指标 | T=0 Baseline | T=0 + Flash Dir Fix | Δ |
|---|---|---|---|
| **1b Micro F1** | 0.5398 | 0.5377 | **−0.0021** ❌ |
| **1b Macro F1** | 0.3914 | 0.3896 | −0.0018 ❌ |
| 1b Precision | 0.5101 | 0.5127 | +0.0026 |
| 1b Recall | 0.5732 | 0.5653 | −0.0079 |
| **DRR** | 0.0518 | **0.0419** | **+0.0099** ✅ |
| 1a Micro F1 | 0.6804 | 0.6804 | 0 |
| 1a Macro F1 | 0.5544 | 0.5544 | 0 |

---

## 三、判定：NO-GO

按 SOL2 冻结规则：

- Micro-F1 相对前一步提高 → ❌ 下降 0.0021
- Macro-F1 不下降 → ❌ 下降 0.0018
- DRR 不恶化 → ✅ 改善 0.0099

**DRR 改善了 19%，但 Micro 和 Macro 均下降。判定 NO-GO。**

## 四、失败原因分析

Flash 方向修正失败的根本原因：

1. **覆盖不对称**：Flash 仅预测 1781 个标签，T=0 预测 2686 个。Flash 对 900+ 个 T=0 标签无方向判断
2. **翻转净损失**：98 次翻转中，丢失 19 TP（1370→1351），仅减少 32 FP（1316→1284）。净 F1 为负
3. **盲翻策略过于粗暴**：T=0 和 Flash 方向冲突时，无条件信任 Flash。但冲突样本中 Flash 的正确率并不足够高

## 五、教训与路径

**盲 Flash 方向覆盖在 T=0 上无效。** Flash 的方向优势（DRR 0.032）只在 Flash 自己的预测空间中成立。

### 已验证有效的方向修复方案

**3-way Majority Vote + Flash Direction** (来自 prompt_variants 实验):

| 指标 | T=0 Baseline | 3-way Majority + Flash Dir |
|---|---|---|
| 1b Micro | 0.5398 | **0.5560** ✅ |
| 1b Macro | 0.3914 | **0.3816** |
| DRR | 0.0518 | **0.0338** ✅ |

该方案成功的关键：majority voting 先过滤低置信标签 → 预测空间缩小到 Flash 能覆盖的范围 → 方向修正有效。

## 六、文件路径

```
fehuSOL2/outputs/step3_direction_fix/
├── pred_task1a.json
├── pred_task1b.json
├── metrics.json
└── analysis.json
```

## 七、SOL2 最终结论

| Step | 方法 | 结果 | 决策 |
|---|---|---|---|
| Step 1 | 温度共识补漏 | Micro +0.003, DRR +0.009 | NO-GO (DRR) |
| Step 2 | 单 Actor Prompt | Recall +0.05, Precision −0.07 | REJECT |
| Step 2b | Value-agreement filter | Micro 0.5458, DRR 0.0455 | 待 TRAIN-calib |
| **Step 3** | Flash 盲方向修正 | DRR −0.01, Micro −0.002 | **NO-GO** |

### 当前最优系统

**3-way Majority Vote (baseline + targeted + compact_strict) + Flash 方向修正**

- 1b Micro: **0.5560** (超越刘 Ensemble 0.5543)
- 1b Macro: **0.3816** (刘 0.3277)
- DRR: **0.0338** (刘 0.0345)

成本: 531 Pro API calls + 零成本后处理
