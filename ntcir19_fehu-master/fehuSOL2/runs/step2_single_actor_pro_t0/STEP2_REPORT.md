# SOL2 Step 2 — 单 Actor Prompt 实验报告

**模型：** DeepSeek V4 Pro，non-thinking (`thinking=disabled`)  
**温度：** 0.0  
**唯一 Prompt 改动：** 每次调用只判断一个 target actor；全文和完整 actor 列表保留。  
**基线：** 原始 Pro non-thinking T=0（Step 1 判定 NO-GO 后未采用温度 residual）。

## 总体结果

| 系统 | Micro-P | Micro-R | Micro-F1 | Macro-F1 | DRR | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 原始 T=0 | 0.5101 | 0.5732 | 0.5398 | 0.3914 | 0.0518 | 1370 | 1316 | 1020 |
| 单 Actor | 0.4373 | 0.6247 | 0.5145 | 0.3623 | 0.0684 | 1493 | 1921 | 897 |

## 增量

- Δ Micro-F1：**-0.0253**
- Δ Macro-F1：**-0.0291**
- Δ Precision：**-0.0728**
- Δ Recall：**+0.0515**
- Δ DRR：**+0.0166**
- Δ Task-1a Micro-F1：**-0.0200**

## 互补性

- Step2-only：**1209**，TP/FP = **240/969**，precision = **0.1985**
- Baseline-only：**481**，其中被移除 TP/FP = **117/364**
- attribution-like FP：baseline **274** → Step2 **450**

## 决策

**Standalone：REJECT。**

不提升单 Actor standalone，也不直接补入其 residual：Step2-only precision 只有 0.1985，低于基线 `F1/2=0.2699`。

后续零 API 组合诊断发现，单 Actor view 更适合充当 agreement filter：仅保留两个 view 都预测到的 `(actor,L1)`，并沿用 T=0 direction，可得到 Micro-F1 0.5458、DRR 0.0455。该规则是在 Dev 分析后发现的，只能视为待 TRAIN-calib 复现的候选，不能直接用于 test。
