# SOL2 Step 1 — Anchor 结合实验报告

**模型身份：** DeepSeek V4 Pro，non-thinking (`thinking=disabled`)  
**数据：** Dev 177 篇  
**API 调用：** 0  
**规则：** `S_anchor = S0 ∪ ((S0.1 ∩ S0.3) - S0)`，交集为 direction-aware 原子。

## 结果

| 系统 | Micro-P | Micro-R | Micro-F1 | Macro-F1 | DRR | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T=0 anchor | 0.5101 | 0.5732 | 0.5398 | 0.3914 | 0.0518 | 1370 | 1316 | 1020 |
| Anchor + consensus residual | 0.4993 | 0.5950 | 0.5430 | 0.3953 | 0.0603 | 1422 | 1426 | 968 |

## Residual 质量

- 候选：**162**
- TP / FP：**52 / 110**
- Precision：**0.3210**
- `F1/2` 理论线：**0.2699**
- 涉及 directed classes：**59**
- T=0.1/T=0.3 value-level direction conflicts：**78**

## 增量

- Δ Micro-F1：**+0.0032**
- Δ Macro-F1：**+0.0039**
- Δ Precision：**-0.0108**
- Δ Recall：**+0.0218**
- Δ DRR：**+0.0085**

## 决策

```json
{
  "micro_improved": true,
  "residual_precision_above_f1_over_2": true,
  "macro_not_worse": true,
  "drr_not_worse": false
}
```

**Step 1 结论：NO-GO，温度 residual 不作为 Step 2 基线；继续使用原始 T=0。**
