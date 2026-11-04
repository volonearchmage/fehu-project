# FEHU SOL2：三步渐进实验路线

**日期：** 2026-07-24  
**状态：** Step 1、Step 2 已完成；Step 3 尚未执行  
**目标：** 每次只增加一个机制，先看真实效果，再分析下一步，不同时堆叠多个尚未验证的方法。

---

## 0. 固定前提

### Task-1 Test 输入边界

正式 test 只能读取：

```text
dataset/test/test_article_event_base.json
```

只允许使用：

```text
guid / title / content / actors
```

不读取 Task-2 的 `test_subevent_event_base.json`，也不把 E3/E3a 作为可提交方案。

### 当前 Pro non-thinking 基线

| Temperature | 1b Micro | 1b Macro | Precision | Recall | DRR ↓ | 1a Micro |
|---:|---:|---:|---:|---:|---:|---:|
| **0.0** | **0.5398** | **0.3914** | **0.5101** | 0.5732 | **0.0518** | **0.6804** |
| 0.1 | 0.5297 | 0.3854 | 0.4906 | 0.5757 | 0.0558 | 0.6740 |
| 0.3 | 0.5293 | 0.3899 | 0.5006 | — | 0.0567 | 0.6698 |

结论已经明确：

> **DeepSeek V4 Pro non-thinking, T=0 是当前最优单温度基线。**

因此后续所有新实验都以 `T=0` 为默认配置。`T=0.1/0.3` 不再作为独立冠军，只在 Step 1 中检查它们是否能为 `T=0` 提供互补候选。

## 已执行结果摘要

| 方法 | 1b Precision | 1b Recall | 1b Micro | 1b Macro | DRR ↓ | 决策 |
|---|---:|---:|---:|---:|---:|---|
| Pro T=0 原始基线 | 0.5101 | 0.5732 | 0.5398 | **0.3914** | 0.0518 | 冻结基线 |
| Step 1：T0 + 跨温度共识 residual | 0.4993 | 0.5950 | 0.5430 | 0.3953 | 0.0603 | NO-GO：DRR 明显恶化 |
| Step 2：单 Actor standalone | 0.4373 | **0.6247** | 0.5145 | 0.3623 | 0.0684 | REJECT：过度预测 |
| Step 2：两 view 的 value agreement，沿用 T0 direction | **0.5579** | 0.5343 | **0.5458** | 0.3902 | **0.0455** | 最佳诊断候选；需 TRAIN 内复现 |

核心结论：单 Actor Prompt 不是更好的独立系统，但它可以作为第二个 view 过滤 T=0。只保留两个 view 都预测到的 `(actor,L1)`，并沿用 T=0 的 direction，可将 Micro-F1 从 0.5398 提高到 0.5458，同时提升 precision、改善 DRR；代价是 recall 下降、Macro-F1 轻微下降 0.0012。该规则是在 Dev 分析后发现的，不能未经 TRAIN-calib 复现就直接用于 test。

---

# Step 1：Anchor 结合（已完成）

## 1.1 目的

不调用模型、不改 Prompt，只使用已经生成的三个温度 prediction，回答一个最简单的问题：

> `T=0.1` 和 `T=0.3` 是否共同发现了 `T=0` 漏掉的可靠标签？

如果答案是否定的，就彻底停止温度集成；如果答案是肯定的，再保留这一条最简单的 anchor 补漏规则。

## 1.2 集合定义

每个 direction-aware 预测原子定义为：

```text
(guid, actor_id, l1_value_id, direction)
```

三个集合：

```text
S0  = T=0.0 的全部预测
S01 = T=0.1 的全部预测
S03 = T=0.3 的全部预测
```

只选择两个非最优温度共同同意、而 `T=0` 没有的标签：

```text
R = (S01 ∩ S03) - S0
```

构造新的 anchor：

```text
S_anchor = S0 ∪ R
```

这里的交集必须包含相同 direction。若 `T=0.1` 与 `T=0.3` 对同一个 L1 的方向不一致，该标签不进入 `R`，只记录为 direction conflict。

## 1.3 为什么第一步只做加法

`T=0` 已经是三个温度中最好的完整系统。第一步不允许：

- 删除 `T=0` 已有标签；
- 用 majority 过滤 `T=0`；
- 修改 `T=0` 的方向；
- 增加 verifier；
- 增加任何新 Prompt。

这样最终差异只来自 `R`，可以准确判断补入候选是否有效。

## 1.4 必须报告的结果

### A. Residual 本身

| 指标 | 结果 |
|---|---:|
| `R` 候选数 | 162 |
| TP | 52 |
| FP | 110 |
| Precision | 0.3210 |
| 覆盖的 directed classes | 59 |
| direction conflicts 数 | 78 |

### B. 完整系统

| 系统 | 1b Micro | 1b Macro | Precision | Recall | DRR | 1a Micro |
|---|---:|---:|---:|---:|---:|---:|
| `S0` | 0.5398 | 0.3914 | 0.5101 | 0.5732 | 0.0518 | 0.6804 |
| `S_anchor` | 0.5430 | 0.3953 | 0.4993 | 0.5950 | 0.0603 | 0.6808 |

同时报告：

```text
ΔMicro
ΔMacro
ΔPrecision
ΔRecall
ΔDRR
Δ1a Micro
```

## 1.5 数学判断线

当前 `T=0` 的 Micro-F1 为 0.5398。纯新增候选若要提高 Micro-F1，其 direction-aware precision 必须满足：

$$
q_R > \frac{0.5398}{2}=0.2699
$$

这是诊断边界，不是可以直接搬到 test 的 Dev 阈值。

## 1.6 Step 1 决策

### 保留 Anchor 结合

同时满足：

1. `S_anchor` Micro-F1 高于 0.5398；
2. `R` precision 高于 0.2699；
3. Macro-F1 不低于 0.3914；
4. DRR 不劣于 0.0518。

则把 `S_anchor` 作为进入 Step 2 的新基线。

### 放弃温度结合

只要出现以下任一情况：

- Micro-F1 没有提升；
- `R` precision 不足 0.2699；
- Macro 明显下降；
- DRR 变差。

就完全放弃 `T=0.1/0.3`，继续使用原始 `S0` 进入 Step 2。

### Step 1 主要交付物

主要结果文件：

```text
fehuSOL2/outputs/step1_anchor/pred_task1b_anchor.json
fehuSOL2/outputs/step1_anchor/STEP1_REPORT.md
```

实际结果满足 Micro、Macro 和 residual precision 三项条件，但 DRR 从 0.0518 恶化到 0.0603，因此按冻结规则判定 **NO-GO**。Step 2 使用原始 `S0`，不使用温度 residual。

---

# Step 2：单 Actor Prompt（已完成）

## 2.1 唯一改动

保持以下内容全部不变：

- DeepSeek V4 Pro non-thinking；
- `temperature=0`；
- system prompt；
- few-shot demos；
- taxonomy；
- 输出 schema 和 evaluator。

唯一改动是：

> 从“一次调用同时判断文章中所有 actors”，改为“一次调用只判断一个 target actor”。

每次仍提供：

- 完整 title/content；
- 完整 actor 列表，避免身份混淆；
- 明确标出的 target actor。

最后按 actor_id 合并成文章级输出。

这一方案不依赖 subevent，也不生成摘要或伪 subevent。

## 2.2 为什么测试这一项

单次文章 Prompt 同时处理多个 actor，可能发生：

- 不同 actor 的证据互相转移；
- 模型注意力被多个 actor 分散；
- 次要 actor 的 tail values 被遗漏；
- direction 受其他 actor 行为干扰。

Step 2 只检验“actor attention dilution”是否真实存在。

## 2.3 必须报告

将 Step 2 与 Step 1 的冠军基线比较：

| 指标 | Step 1 冠军 | 单 Actor Prompt | Δ |
|---|---:|---:|---:|
| 1b Micro | 0.5398 | 0.5145 | −0.0253 |
| 1b Macro | 0.3914 | 0.3623 | −0.0291 |
| Precision | 0.5101 | 0.4373 | −0.0728 |
| Recall | 0.5732 | 0.6247 | +0.0515 |
| DRR | 0.0518 | 0.0684 | +0.0166 |
| 1a Micro | 0.6804 | 0.6604 | −0.0200 |
| labels/actor | 5.8519 | 7.6892 | +1.8373 |

还要单独统计：

- 单 Actor Prompt 相对基线的 unique TP；
- unique FP；
- actor attribution errors；
- 多 actor 文章与单 actor 文章的分组增益。

## 2.4 Step 2 决策

- 如果 Micro/Macro 都改善：单 Actor Prompt 成为新冠军；
- 如果 recall 提升但 precision 明显下降：保留其 residual candidates，进入 Step 3 做局部验证；
- 如果没有提供有价值的 unique TP：放弃单 Actor Prompt，Step 3 只处理当前冠军的方向问题；
- 不在 Step 2 同时加入句子编号、A3/A4 或新 verifier。

实际结果属于第二种情形，但 residual 的 precision 只有 0.1985，明显低于当前系统的 `F1/2=0.2699`，因此不建议直接补入 residual。进一步的零 API 组合分析表明，更值得保留的是反方向用法：把单 Actor 输出作为 T=0 的 value-level agreement filter，而不是作为新增候选生成器。该组合在 Dev 上得到 Micro-F1 0.5458、DRR 0.0455，但必须先在 TRAIN-calib 内复现。

---

# Step 3：只修复 Step 2 暴露出的主要问题

Step 3 不提前堆叠所有机制。它只根据 Step 2 的结果选择一个问题处理。

## 3.1 如果主要问题是 Precision

只验证“新系统相对 anchor 新增的标签”，不重新审核 anchor。

```text
Residual = S_new - S_anchor
```

Verifier 每次只判断：

```text
给定 actor、一个 L1 definition 和文章：
这个候选是否有 actor-specific evidence？
如果成立，direction 是 aligned 还是 contradictory？
```

只输出 `accept/reject + direction`。禁止扫描和新增其他标签。

## 3.2 如果主要问题是 DRR

保持 value 集合完全不变，只对以下项目做 direction QA：

- 不同 source 预测方向冲突的 `(actor,L1)`；
- TRAIN 内预先识别的高风险 direction 组。

不重新判断 value，不增加或删除 L1。

## 3.3 如果主要问题是 Recall

只有在 Step 2 证明候选覆盖仍不足时，才考虑下一轮 residual Prompt。A3 Actor prior、A4 NPMI 或句子编号都不在本轮自动启用，而是作为 SOL3 的候选，不继续塞进 SOL2。

## 3.4 最终判断

Step 3 只和 Step 2 冠军做一对一比较，并报告相同指标。最终系统必须满足：

- Micro-F1 相对前一步提高；
- Macro-F1 不下降；
- DRR 不恶化；
- 新增 API 成本有清楚记录。

若 Step 3 没有净增益，则回退到 Step 2 冠军；不为了“已经实现”而保留无效组件。

---

# 三步流程总览

```text
Step 1：现有三个温度的 Anchor 结合
         0 API，先判断温度是否有互补信息
                         │
                         ▼
Step 2：Pro T=0 单 Actor Prompt
         只检验 actor attention dilution
                         │
                         ▼
Step 3：只修一个主要问题
         Precision → residual verifier
         DRR       → direction QA
         Recall    → 停止 SOL2，另开 SOL3
```

Step 1、Step 2 已完成。Step 2 standalone 被拒绝，但其 value agreement 过滤组合形成了当前最好的 SOL2 诊断候选（Micro 0.5458、DRR 0.0455）。下一步不应直接运行复杂 Step 3；应先在 TRAIN 内部复现该 agreement 规则，确认它不是 Dev 偶然性，再决定是否做 residual verifier。
