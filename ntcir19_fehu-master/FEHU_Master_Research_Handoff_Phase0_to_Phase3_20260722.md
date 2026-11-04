# FEHU 研究总交接文档：从项目起点到 Phase 0–3

**项目：** NTCIR-19 FEHU Task-1  
**研究者：** Huang Peiyang  
**研究方向：** Diagnosis-guided / Label-aware LLM Data Augmentation for Actor-conditioned Human Value Recognition  
**当前重点：** Task-1b 的 108 个 `direction:L1` 类别，尤其是 18 个低频、零召回或困难目标类别  
**更新时间：** 2026-07-22  
**主要代码目录：** `~/projects/fehu-project/ntcir19_fehu-master`  
**当前验证工作区：** `ntcir19_fehu-master/new_check/`

---

## 0. 文档用途与证据边界

本文件用于：

1. 汇总 FEHU 项目的任务要求、研究目标、数据与评估约束；
2. 记录数据增强、Prompt、Hybrid 和 DeBERTa 训练路线；
3. 汇总 Phase 0、Phase 1、Phase 2、Phase 3 的实际实验结果；
4. 解释研究思路为何多次调整；
5. 明确目前可以主张、不能主张和仍需验证的结论；
6. 作为后续 Claude Code、论文写作、PPT、教授汇报和新对话的统一上下文。

本文件只使用以下已提供证据：

- FEHU 官方 Task Description、Formal Data、Result Evaluation 文档；
- `PHASE0_VALIDATION_REPORT.md` 的完整内容；
- Phase 1、Phase 2、Phase 3 的 Claude Code completion summaries；
- 2026-07-14 以前的 FEHU 项目 handoff、PPT 与研究记录；
- 当前对话中已经明确纠正的事实。

**重要限制：**

- Phase 0 的精确表格数据可直接写入本文件；
- Phase 1–3 只写 completion summary 中明确给出的数字；
- 未在 summary 中提供的 Phase 2/3 详细均值、标准差和逐 seed 表格，不在此猜测，应以各自报告和 `outputs/` 为准；
- 早期材料中关于“人工审核 340 条数据”的说法已经被后续审计纠正，不能继续沿用。

---

# 1. FEHU 任务与官方评估要求

## 1.1 Task-1 的目标

FEHU Task-1 是文章级、actor-conditioned 的人类价值识别任务。

### Task-1a

输出：

```text
<guid, actor, Level-2 human value>
```

Task-1a 不区分 aligned / contradictory 方向。

### Task-1b

输出：

```text
<guid, actor, Level-1 human value, direction>
```

方向约定：

```text
aligned       = 1
contradictory = 0
```

Task-1b 一共有：

```text
54 个 Level-1 value × 2 个方向 = 108 个 direction-specific classes
```

当前论文研究和 Phase 0–3 的核心集中在 Task-1b。

## 1.2 主要错误类型

- **Omission error：** 漏掉 gold label；
- **Reversal error：** 预测到了同一 L1 value，但方向与 gold 相反。

DRR（Direction Reversal Rate）越低越好。

## 1.3 官方 evaluator 固定意味着什么

官方 `evaluation.py` 固定了评估方式，但**没有限制模型如何产生预测**。

允许的系统包括：

- DeBERTa / LoRA fine-tuning；
- Prompt-only LLM；
- DeBERTa + LLM cascade；
- voting / union / intersection；
- residual correction；
- learned fusion；
- teacher–student 或 distillation。

唯一要求是最终输出符合官方预测文件格式，并使用官方 evaluator 计算结果。

因此：

> 官方 evaluator 固定，不等于只能使用单一模型，也不等于不能做 Hybrid。

## 1.4 当前必须报告的指标

教授明确要求不能只报告 Micro-F1 和 Macro-F1。当前标准输出应包括：

### 对三个标签组分别报告

1. 18 个 target labels；
2. 其余 90 个 non-target labels；
3. 全部 108 个 labels。

### 每组均报告六项指标

- Micro Precision
- Micro Recall
- Micro F1
- Macro Precision
- Macro Recall
- Macro F1

### 额外诊断

- 每个 target label 的 TP / FP / FN / P / R / F1；
- gold support；
- predicted positives；
- ROC-AUC；
- oracle per-label F1（仅作诊断，不能当作正式部署结果）；
- direction reversals / DRR；
- distinct predicted classes；
- seed mean、standard deviation、最好和最差 run；
- threshold sensitivity；
- score separation；
- positive / known-negative / masked-unknown 的训练比例。

---

# 2. 工程与实验管理要求

## 2.1 不可违反的原则

1. 不修改官方训练、dev、test 数据；
2. 不修改官方 `evaluation.py`；
3. 不覆盖旧实验；
4. 每次实验保存独立配置、输入、日志、checkpoint、预测和报告；
5. 所有新验证工作存放在 `new_check/`；
6. Bug 必须从第一性原理分析；
7. 不增加会掩盖主流程错误的 silent fallback；
8. 输入不兼容时必须明确失败，不能静默转换；
9. 每次运行记录 seed、threshold、数据组成、supervision policy 和 checkpoint hash；
10. 未正式人工审核的数据不能称为 human-verified；
11. 不在最终 dev 上训练融合器或利用 dev gold 反向修正模型；
12. checkpoint 和 threshold 的选择应尽量使用 internal split，最终 dev 用于报告；
13. 重要训练条件至少运行 3 seeds；
14. Prompt-only、DeBERTa augmentation、Hybrid 和外部报告结果必须清楚分开。

## 2.2 `new_check/` 当前结构

```text
ntcir19_fehu-master/new_check/
├── README.md
├── phase0/
│   ├── scripts/
│   ├── configs/
│   ├── outputs/
│   ├── logs/
│   └── reports/
├── phase1/
│   ├── scripts/
│   ├── outputs/
│   └── reports/
├── phase2/
│   ├── scripts/
│   ├── configs/
│   ├── checkpoints/
│   ├── outputs/
│   ├── logs/
│   └── reports/
└── phase3/
    ├── scripts/
    ├── configs/
    ├── checkpoints/
    ├── outputs/
    ├── logs/
    └── reports/
```

Phase 0–3 均声明未修改既有研究产物，新增文件只存放在 `new_check/`。

---

# 3. 研究问题如何形成

## 3.1 最初问题：DeBERTa 的长尾类别塌缩

官方数据训练的 DeBERTa baseline 在 Task-1b 上：

| 指标 | Baseline |
|---|---:|
| Micro Precision | 0.266 |
| Micro Recall | 0.349 |
| Micro F1 | 0.302 |
| Macro Precision | 0.020 |
| Macro Recall | 0.074 |
| Macro F1 | 0.031 |
| DRR | 0.217 |
| Predicted classes | 8 / 108 |

主要问题不是只有整体 F1 不高，而是：

> 模型只预测 108 类中的 8 类，绝大多数低频或困难标签处于零召回状态。

因此研究重点从“整体提高 F1”转向：

- 恢复模型从不预测的类别；
- 提高长尾覆盖；
- 分析 direction-specific failure；
- 在不制造大量误报和 reversal 的前提下提高 recall。

## 3.2 Prompt-only 路线成为强基线

Liu Dongyang 的 `targeted_more_shot_balanced` Prompt 使用 DeepSeek V4 Flash，在本地完整复现中取得：

| 指标 | Liu targeted Prompt |
|---|---:|
| Task-1b Micro Precision | 0.5677（Phase 0 重算为 0.568） |
| Task-1b Micro Recall | 0.5054（Phase 0 重算为 0.505） |
| Task-1b Micro F1 | 0.5347（Phase 0 重算为 0.535） |
| Task-1b Macro F1 | 0.3385（Phase 0 重算为 0.339） |
| DRR | 0.0230 |

这证明：

- Prompt-only 系统整体明显强于 DeBERTa；
- Prompt 对 precision 和 direction reasoning 更可靠；
- DeBERTa 的研究价值不应仅靠“最终分数超过 LLM”来证明；
- DeBERTa 更适合研究低成本、本地化、训练信号、长尾学习和高召回候选生成。

---

# 4. 数据增强主线的早期阶段

## 4.1 Tiny pilot：证明生成流程可行，不证明模型有效

流程：

```text
Preview
→ Human Review Pack
→ Human Approval
→ Tiny Pilot
→ Repair / Regeneration
→ Unified Validation
```

Tiny pilot 约 6 条候选，证明：

- LLM 可以按 actor、value、direction 生成候选；
- 结构检查、修复和重新生成流程可以运行；
- 数据可以进入训练脚本。

Smoke run 中：

```text
Task-1b Micro-F1: 0.3023 → 0.3060
```

但目标标签 recall 仍为 0，因此只能说：

> 流程可训练，不能说增强有效。

## 4.2 Round 1：340 条 AI-screened synthetic silver

数据组成：

```text
1228 official
+ 340 round-1 synthetic
= 1568 articles
```

340 条数据覆盖 6 个 L1 和两个方向，但其标签形式主要是稀疏、单标签或 target-only。

### v1 结果

| 指标 | Baseline | Augmented v1 |
|---|---:|---:|
| Task-1b Micro P | 0.2664 | 0.3061 |
| Task-1b Micro R | 0.3494 | 0.2958 |
| Task-1b Micro F1 | 0.3023 | 0.3009 |
| Task-1b Macro F1 | 0.0305 | 0.0261 |
| DRR | 0.2165 | 0.1364 |

六个增强目标的 Task-1b recall 仍然全部为 0。

### v1 诊断

v1 不是“数据越多越好”，而是出现：

```text
Precision 上升
Recall 下降
Macro-F1 下降
预测类别数减少
```

关键怀疑变成：

> target-only synthetic records 中没有标注的其他标签，被普通 BCE 当作 negative，可能对真实正类形成错误负监督。

这导致研究从：

```text
单纯增加 rare-label samples
```

转向：

```text
数据增强 + partial-label supervision
```

---

# 5. Round 2：18 个 direction-specific targets 与 900 条数据

## 5.1 18 个目标的选择

18 个 target labels 由方向和 L1 共同定义，不是 18 个无方向 value。

冻结的 18 个 target：

```text
0:31, 0:48, 0:53, 0:16, 0:19, 0:20,
0:13, 0:37, 0:29, 0:2, 0:33, 0:32,
0:40, 0:28, 1:31, 1:10, 1:49, 1:4
```

其中：

- 14 个 contradictory；
- 4 个 aligned；
- 每个 target 在 dev 上均有 gold support；
- 总 target gold labels = 140。

目标选择原则包括：

- official train frequency 较低；
- dev support 不为零；
- baseline recall 为 0；
- direction-specific；
- 避免把仅仅“困难但高频”的标签全部混入 rare-label 主目标。

## 5.2 900 条 Round-2 数据

生成设计：

```text
18 targets × 50 samples = 900
```

策略包括：

- targeted ICL；
- transformation；
- contrastive；
- hard negative。

生成结果：

```text
900 raw candidates
72 target × strategy buckets 全部填满
0 unparseable
900 structurally valid
```

这 900 条经过自动结构检查，但**没有正式人工筛选**。

## 5.3 完整训练数据

历史 v2 使用：

```text
1228 official
+ 340 round-1
+ 900 round-2
= 2468 articles
```

训练监督分为：

- `full_multilabel`：正常 108-label supervision；
- `target_only`：只对明确标签计算 loss，其他位置 masked 为 unknown。

## 5.4 历史 v2 单 seed 结果

Phase 0 对历史 v2 的重算：

| 标签组 | Micro P | Micro R | Micro F1 | Macro P | Macro R | Macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| Target 18 | 0.076 | 0.086 | 0.081 | 0.026 | 0.069 | 0.036 |
| Non-target 90 | 0.243 | 0.569 | 0.341 | 0.113 | 0.270 | 0.153 |
| All 108 | 0.238 | 0.541 | 0.331 | 0.096 | 0.231 | 0.130 |

Target 18：

```text
TP = 12
FP = 146
FN = 128
```

历史 v2 的主要现象：

- 从 18 个 target 全部零预测，变成 5/18 有 TP；
- 预测类别由 baseline 的 8 类扩大到 50 类；
- recall 和 macro 指标提高；
- precision 下降；
- DRR 由 0.217 恶化到 0.288；
- target direction reversals 由 9 增加到 23。

因此历史 v2 只能表述为：

> 模型开始学习更广的标签空间，但 precision 和方向可靠性较差。

---

# 6. 教授反馈引发的验证路线

教授要求回答：

1. 18 个 target labels 与其余标签分别计算 P/R/F1；
2. 同时报告 macro P/R/F1 和 micro P/R/F1；
3. 人工筛选是否有效；
4. 是否需要把正负样本调整到接近 50:50；
5. 18 个标签还有哪些提高方式；
6. LoRA-DeBERTa 如何与 Liu prompting 集成，是否作为 voter。

这一反馈使研究从“展示一个较好的单 seed v2”转向：

> 对数据、supervision、threshold、imbalance、seed stability 和 Hybrid 进行因果与机制验证。

---

# 7. Phase 0：基于已有产物的完整重评估

**报告：**

```text
new_check/phase0/reports/PHASE0_VALIDATION_REPORT.md
```

## 7.1 Phase 0 做了什么

- 不训练；
- 不推理；
- 不调用 API；
- 重算已有 6 个系统的所有指标；
- 验证 prediction、gold、label mapping、threshold 和 artifact compatibility；
- 分别分析 target 18 / non-target 90 / all 108；
- 统计 imbalance、FP/FN、reversal、threshold sensitivity；
- 明确哪些结论仍然 confounded。

## 7.2 六个系统在 Target 18 上的结果

| System | Micro P | Micro R | Micro F1 | Macro P | Macro R | Macro F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DeBERTa baseline | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 140 |
| Augmented v1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 140 |
| Historical v2 | 0.076 | 0.086 | 0.081 | 0.026 | 0.069 | 0.036 | 12 | 146 | 128 |
| Liu Prompt | 0.304 | 0.200 | 0.241 | 0.407 | 0.211 | 0.213 | 28 | 64 | 112 |
| Hybrid H2 | 0.257 | 0.250 | 0.254 | 0.333 | 0.251 | 0.229 | 35 | 101 | 105 |
| Hybrid H3 | 0.282 | 0.221 | 0.248 | 0.330 | 0.222 | 0.212 | 31 | 79 | 109 |

## 7.3 Non-target 90 与 All 108

### Non-target 90

| System | Micro P | Micro R | Micro F1 | Macro P | Macro R | Macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 0.266 | 0.371 | 0.310 | 0.025 | 0.092 | 0.038 |
| v1 | 0.306 | 0.314 | 0.310 | 0.024 | 0.068 | 0.032 |
| Historical v2 | 0.243 | 0.569 | 0.341 | 0.113 | 0.270 | 0.153 |
| Liu | 0.580 | 0.524 | 0.551 | 0.451 | 0.348 | 0.369 |
| H2 | 0.516 | 0.611 | 0.560 | 0.419 | 0.412 | 0.392 |
| H3 | 0.561 | 0.567 | 0.564 | 0.429 | 0.361 | 0.369 |

### All 108

| System | Micro P | Micro R | Micro F1 | Macro P | Macro R | Macro F1 | DRR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0.266 | 0.349 | 0.302 | 0.020 | 0.074 | 0.031 | 0.217 |
| v1 | 0.306 | 0.296 | 0.301 | 0.019 | 0.055 | 0.026 | 0.136 |
| Historical v2 | 0.238 | 0.541 | 0.331 | 0.096 | 0.231 | 0.130 | 0.288 |
| Liu | 0.568 | 0.505 | 0.535 | 0.442 | 0.321 | 0.339 | 0.023 |
| H2 | 0.504 | 0.590 | 0.543 | 0.402 | 0.381 | 0.360 | 0.036 |
| H3 | 0.548 | 0.547 | 0.547 | 0.410 | 0.334 | 0.338 | 0.031 |

## 7.4 Phase 0 的主要结论

1. Baseline 和 v1 在 18 个 target 上完全零预测；
2. v2 恢复了少量 target，但 FP 非常多；
3. non-target F1 没有下降，但 precision、FP 和 DRR 明显恶化；
4. 不能只说“没有损害其他标签”，应说：
   - non-target F1 提高；
   - 但以更低 precision、更多 FP 和更多 reversal 为代价；
5. target positive : known-negative 极度不平衡：
   - official：约 1:29 到 1:475；
   - augmentation 后：约 1:44 到 1:68；
6. v2 的 target score 可以通过低 threshold 恢复 recall，但 precision 不可用；
7. 历史 baseline 没有 probability export，因此需要 Phase 1；
8. 历史 v2 同时改变了数据和 supervision policy，无法判断 900 数据与 masked loss 各自作用；
9. 人工筛选效果无法回答，因为训练数据没有经过正式人工筛选。

## 7.5 人工筛选的真实情况

当前可以向教授如实说明：

- 900 条：自动结构验证；
- 340 条：自动 / AI semantic screening；
- 只有 6 条 pilot 曾经过人工检查；
- 这 6 条没有进入 v1/v2 正式训练；
- 因此不存在可以评价的“人工筛选训练组”。

早期 PPT 中“340 条结合人工审核”的表述不再准确，后续材料必须修正。

---

# 8. Phase 1：Baseline 概率导出与 threshold 假设检验

**报告：**

```text
new_check/phase1/reports/PHASE1_BASELINE_PROBABILITY_REPORT.md
```

## 8.1 Phase 1 做了什么

- 从冻结的 official-only baseline checkpoint 导出 108 类 actor-level probabilities；
- 未重新训练；
- 0.30 threshold 后完全复现历史 baseline prediction；
- 与 v2 使用同样的 threshold sweep 和 oracle per-label 分析；
- 比较 baseline 与 v2 的 target score separation。

## 8.2 Phase 1 结果

Baseline target signal：

```text
Mean target AUC = 0.536
8 / 18 targets below AUC 0.5
Gold target 的最高预测概率 = 0.157
所有 target 的 dev-oracle F1 ≤ 0.16
Mean oracle F1 = 0.053
```

threshold 0.05 时：

```text
Target recall = 0.94
Precision = 0.058
DRR = 0.90
```

这不是可恢复信号，而是 blanket prediction。

v2 对比：

```text
Mean target AUC = 0.697
相对 baseline +0.16
```

## 8.3 Phase 1 改变了什么

被否定的假设：

> Baseline 可能已经学到了 target，只是 threshold 0.30 太高。

实际结论：

> Baseline 基本没有 target separation，降低 threshold 不能救回它。

因此 v2 的 target signal 确实来自训练发生了变化，而不是简单 threshold artifact。

但仍然不能知道：

- 是 900 数据；
- 是 340 数据；
- 是 masked supervision；
- 或是它们的组合。

这直接推动 Phase 2 的受控消融。

---

# 9. Phase 2：900 条数据与监督策略的三组受控消融

**报告：**

```text
new_check/phase2/reports/PHASE2_CONTROLLED_ABLATION_REPORT.md
```

## 9.1 条件设计

每个条件 seeds 42 / 43 / 44，共 9 个训练 run：

```text
A = Official only
B = Official + 900, assume-negative
C = Official + 900, masked
```

340 条 Round-1 数据在 Phase 2 中明确排除。

## 9.2 Phase 2 的问题

1. 900 条数据是否提高 18 个 target？
2. masked supervision 是否是主要提升来源？
3. 结果是否跨 seed 稳定？

## 9.3 Phase 2 结果

### 900 条数据有效，但主要体现在 score separation

Official-only A：

```text
3 seeds 均没有 target prediction
Mean target AUC = 0.513
```

加入 900：

```text
B − A target AUC = +0.111
C − A target AUC = +0.064
```

6 个 augmented runs 的 target AUC 均高于对应 official-only。

因此可以主张：

> 900 条数据确实让模型学到了 target-label score signal。

但固定 threshold 0.30 下：

```text
B 的 target TP = 0 / 2 / 12
```

说明 fixed-threshold P/R/F1 高度受 seed 影响，尚未形成稳定分类器。

### 900-only 条件下，masked 不是主要提升来源

```text
C − B target AUC = -0.047
3 / 3 seeds 均为负
Target TP 平均减少约 4
Macro-F1 多数 seed 下降
```

Phase 2 当时结论：

> 对 900 条较完整的 Round-2 数据，assume-negative 比 masked 更能利用监督信息。

可能原因：

- masked target-only record 只监督 1–2 / 108 个位置；
- assume-negative 为其余大量类别提供近似正确的负监督；
- 因此 Round-2 数据上 masking 可能丢失了有用的负信息。

### Seed stability

- AUC 差异方向稳定；
- 固定阈值指标不稳定；
- 单 seed 结果不足以支撑机制结论。

## 9.4 Phase 2 尚未解释的问题

Phase 2 的 B/C 均低于历史 v2 的 Macro-F1 0.130。

主要缺失变量是：

```text
340 条 Round-1 sparse / single-label records
```

因此下一步必须比较完整 1240 数据下的两个 supervision policies。

---

# 10. Phase 3：完整 1240 数据、监督交互与负样本下采样

**报告：**

```text
new_check/phase3/reports/PHASE3_FULL_DATA_AND_NEGATIVE_SAMPLING_REPORT.md
```

**详细表格：**

```text
new_check/phase3/outputs/
```

## 10.1 Phase 3 运行内容

总计 12 个训练 run。

### Stage 1：完整数据下比较 supervision

```text
F′ = Official + 340 + 900, masked
G′ = Official + 340 + 900, assume-negative
```

seeds：

```text
42 / 43 / 44
```

F′ 与历史 v2 的数据、trainer 和 supervision map 一致。

### Stage 2：在 masked winner 上进行 target negative downsampling

```text
N3 = target known-negative ratio 约 1:3
N1 = target known-negative ratio 约 1:1
```

实现约束：

- positive 不删除；
- known negative 只参与下采样；
- unknown / masked slots 不参与 negative sampling；
- 其他代码与历史 trainer 分离；
- 旧 trainer 和旧结果不修改。

## 10.2 历史 v2 是否可复现

F′ seed 42 在相同数据、trainer 和 seed 下得到：

```text
Micro-F1 = 0.3154
```

历史 v2 为：

```text
Micro-F1 = 0.3306
```

F′ 三 seed 范围：

```text
Micro-F1 = 0.290–0.358
Macro-F1 = 0.022–0.182
```

历史 v2 落在这一分布内。

结论：

> 历史 v2 可以“分布上复现”，但不能依赖 byte-identical 的单次结果。

原因被归因于长训练轨迹中的 CUDA nondeterminism 和训练高方差。

F′ seed 44：

```text
Macro-F1 = 0.182
Target TP = 37
Target AUC = 0.747
```

这是目前最强的 student 单 run，但不能作为唯一主结果。

F′ seed 43 在 epoch 1 collapse，说明 masked full-data family：

```text
high variance / high ceiling
```

## 10.3 完整数据下的监督策略结论

Phase 3 中，masked F′ 在 mean target readouts、overall micro 和 DRR 上优于 G′。

这与 Phase 2 的 900-only 结果相反。

合并 Phase 2 与 Phase 3，可得到当前最重要的机制结论：

> supervision policy 的效果取决于 synthetic data composition。

解释：

### 对 900 条 Round-2 较完整数据

```text
assume-negative 更好
```

因为其未标注位置大多可以提供近似正确的负监督。

### 加入 340 条 sparse / single-label 数据后

```text
masked 更好
```

因为如果对 340 条的未标注位置使用 assume-negative，会把 unknown 误当作 negative，复现 v1 的错误负监督机制。

因此 masked supervision 不能被简单“删除”，也不能被描述为普遍更强。正确结论是：

> Masked supervision protects sparse partially labelled synthetic records, but is not universally optimal for all synthetic data compositions.

## 10.4 Negative downsampling 结果

### N3：约 1:3

Target recall：

```text
约 0.09 → 0.59
```

覆盖：

```text
16 / 18 targets 有命中
```

摘要中报告：

```text
Target-18 F1 = 0.054
Overall Macro-F1 mean = 0.107
Best seed overall Macro-F1 = 0.177
```

同时：

```text
Target AUC 基本不变
Overall Micro-F1 约下降 0.09
DRR 恶化
```

因此 N3 的作用主要是：

```text
calibration / prediction propensity shift
```

不是：

```text
better ranking or better representation learning
```

N3 让模型更愿意预测 target，从而显著提高 recall，但没有让正负分数更可分。

### N1：约 1:1

结果：

- 接近 blanket firing；
- target recall 很高；
- AUC 下降到接近 chance；
- 模型失去排序能力。

结论：

> 1:1 对当前 108 类多标签任务过于激进，不应作为主方法。

## 10.5 Phase 3 的当前主配置

作为完整数据 student baseline：

```text
Official + 340 + 900
Masked supervision
No aggressive negative downsampling
Multi-seed reporting
```

N3 的更合理定位：

```text
high-recall candidate generator
```

而不是 standalone final classifier。

---

# 11. Phase 0–3 如何回答教授的问题

## 11.1 “18 个标签单独评估”

已完成。

必须同时给出：

- target 18；
- non-target 90；
- all 108；
- micro P/R/F1；
- macro P/R/F1；
- per-label metrics；
- DRR / reversals。

历史 v2 的 target 18：

```text
Micro P/R/F1 = 0.076 / 0.086 / 0.081
Macro P/R/F1 = 0.026 / 0.069 / 0.036
```

但 Phase 3 证明单 seed 不稳定，因此正式论文应优先使用 Phase 2/3 的多 seed mean ± std；精确数字应从对应 `outputs/` 提取。

## 11.2 “900 条数据对 target 有什么精确作用”

Phase 2 给出的最干净结论：

```text
B − A target AUC = +0.111
C − A target AUC = +0.064
所有 augmented runs 均为正向
```

因此：

> 900 条数据稳定提高 target score separation，但固定阈值下的 TP/F1 仍然受 seed 影响，尚未成为稳定分类器。

## 11.3 “人工筛选是否有效”

真实答案：

> 无法评价。

原因：

- 900 没有人工筛选；
- 340 不是正式人工审核数据；
- 只有 6 条 pilot 有人工检查；
- 6 条 pilot 未进入正式 v1/v2 训练。

若未来必须研究人工筛选，应设计：

```text
unfiltered
vs AI-screened
vs human-reviewed
vs random size-matched
```

且数量、标签分布和训练设置要匹配。

## 11.4 “是否需要 negative downsampling”

Phase 3 证明：

- 1:3 显著提高 target recall；
- 但不提高 AUC；
- 损害 overall micro 和 DRR；
- 1:1 破坏排序能力。

因此：

> 负样本下采样对 recall 有效，但不适合作为独立最终解决方案。

## 11.5 “18 个标签还有哪些提升方法”

按当前证据排序：

1. internal split 上的 per-class threshold tuning；
2. N3 作为 high-recall candidate generator；
3. Liu Prompt / LLM 作为 precision 与 direction verifier；
4. 增加 F′ seeds，分析 collapse / peak 双峰；
5. macro-aware 或 target-aware checkpoint selection；
6. 对 direction reversal 做专门校准；
7. 对 340 与 900 的数据质量和标签完整性分别设计 supervision；
8. 必要时做受控人工筛选实验。

## 11.6 “如何与 Liu prompting 集成，是否 voting”

当前证据不支持简单 equal voting 作为首选。

更合理的结构：

```text
N3 / F′ DeBERTa
→ high-recall candidates
→ Liu Prompt verifies label and direction
→ final official-format prediction
```

或者：

```text
Liu Prompt as primary prediction
+ DeBERTa only rescues selected missed target labels
```

为什么不建议旧式 DeBERTa-first gate：

- baseline / v1 对 18 targets 零预测；
- DeBERTa 候选不足时，Liu verifier 无法恢复没进入候选的标签；
- DeBERTa 噪声高时，LLM 要处理大量 FP 和 reversal；
- verifier-only Prompt 会限制 Liu 的主动发现能力。

现有 Phase 0 结果显示 Hybrid 并非全部弱于 Liu：

### Target 18

```text
Liu Micro-F1 = 0.241
H2 Micro-F1 = 0.254
H3 Micro-F1 = 0.248
```

### All 108

```text
Liu Micro-F1 = 0.535
H2 Micro-F1 = 0.543
H3 Micro-F1 = 0.547
```

但提升幅度有限，而且旧 Hybrid 使用的是较弱候选模型。Phase 3 的 N3 提供了新的高召回候选来源，因此值得重新设计 Hybrid，而不是简单重复旧版本。

---

# 12. 一路上的研究思路转变

## 阶段 1：追求整体 DeBERTa F1

最初问题被理解为：

```text
DeBERTa 整体性能不够好
```

后来发现真正关键是：

```text
只预测 8 / 108 类
```

研究焦点转为长尾与零召回类别。

## 阶段 2：LLM 直接生成少量数据

Tiny pilot 证明：

```text
可以生成、修复、验证、训练
```

但没有证明：

```text
模型性能改善
```

## 阶段 3：扩大到 340 条数据

直觉是：

```text
更多目标样本 → 目标 recall 提高
```

实际 v1：

```text
recall 更低、类别更少
```

因此研究从“数量问题”转向“监督错误问题”。

## 阶段 4：提出 masked partial-label supervision

当时推理：

```text
target-only 数据的未知标签不应全部视为 negative
```

于是 Round-2 设计了 18 个 direction-specific target、900 条 label-aware 数据与 masked loss。

历史 v2 单 seed 出现显著 macro/recall 提升，早期曾把 masked supervision 视为主要原因。

## 阶段 5：教授要求 target-only 指标与因果检查

教授反馈指出：

- 必须单独看 18 targets；
- 必须报告全部 macro/micro P/R/F1；
- 需要验证筛选、负样本比例与 Hybrid；
- 不能只展示 overall F1。

研究从“结果展示”进入“因果验证”。

## 阶段 6：Phase 0 发现历史 v2 被混杂

Phase 0 证明：

```text
数据变化 + supervision policy 变化
```

同时发生，因此不能归因于 masked 或 900。

同时发现：

- precision 很差；
- imbalance 极端；
- threshold 不是唯一问题；
- 人工筛选从未真正发生。

## 阶段 7：Phase 1 排除 baseline threshold artifact

Baseline AUC 接近 chance，没有 latent target signal。

研究问题变为：

```text
到底是哪一种训练变化产生了 target signal？
```

## 阶段 8：Phase 2 发现 900 数据有效，masked 在 900-only 下更差

第一次控制实验表明：

- 900 数据稳定提高 AUC；
- assume-negative 在 Round-2-only 下比 masked 更好；
- 早期“masked 是主因”的解释被推翻。

## 阶段 9：Phase 3 发现 data composition × policy interaction

加入 340 sparse records 后：

- masked 又优于 assume-negative；
- 说明 supervision policy 不能脱离数据标签完整性讨论；
- masked 的价值是保护 sparse partial labels，而不是普遍优越。

## 阶段 10：Negative downsampling 提供 recall，但不是 learning

1:3 显著提高 recall，但 AUC 不变。

因此研究进一步区分：

```text
representation / ranking improvement
```

与：

```text
calibration / decision propensity shift
```

## 当前研究认识

目前最严谨的核心结论是：

> Diagnosis-guided augmentation can introduce measurable target-label signal, but the benefit depends on synthetic-data composition, supervision policy, seed stability and decision calibration. Masked supervision is useful for sparse partial-label records, while moderate negative downsampling primarily increases recall rather than improving class separation.

---

# 13. 当前可主张与不可主张的结论

## 13.1 可以主张

1. Baseline 对 18 targets 基本没有可用 latent signal；
2. 900 条 Round-2 数据跨 seed 提高 target AUC；
3. 数据增强确实改变了模型对 target 的 score separation；
4. supervision policy 与数据标签完整性存在 interaction；
5. 340 sparse records 使用 assume-negative 存在错误负监督风险；
6. full-data masked configuration 具有更高上限，但方差大；
7. 1:3 negative downsampling 显著提高 target recall；
8. 1:3 不提高 AUC，主要是 calibration shift；
9. 1:1 过度下采样会破坏排序能力；
10. Prompt-only Liu 仍然是更强、更稳定的总体基线；
11. Hybrid H2/H3 在部分指标上已小幅超过 Liu；
12. 新 N3 候选可能比旧 DeBERTa 更适合重新做 LLM verifier。

## 13.2 不能主张

1. 900 条数据已经产生稳定、可用的 18-label classifier；
2. masked supervision 在任何数据组成下都更好；
3. assume-negative 在任何数据组成下都更好；
4. 历史 v2 单 seed 结果可以精确复现；
5. 1:3 downsampling 改善了表示学习；
6. 人工筛选已经被证明有效；
7. DeBERTa 已整体超过 Liu Prompt；
8. 旧 Hybrid 证明了所有 Hybrid 都无效；
9. dev-oracle threshold 可以作为最终系统指标；
10. 利用 dev gold 训练 fusion 后仍可在同一 dev 上公平报告。

---

# 14. 当前研究主线建议

## 14.1 论文研究主线

建议表述为：

> Diagnosis-guided LLM Data Augmentation with Data-composition-aware Partial-label Supervision for Rare Direction-specific Human Value Recognition

中文可写为：

> 面向稀缺方向特定人类价值识别的错误诊断引导式大语言模型数据增强与数据组成感知的部分标签监督研究

核心贡献候选：

1. 基于 baseline error / zero-recall 的 18 个 direction-specific target 诊断；
2. 900 条 label-aware synthetic generation；
3. 系统分离 data effect 与 supervision effect；
4. 发现 data composition × supervision policy interaction；
5. 揭示 negative downsampling 提高 recall 但不提高 ranking；
6. 多 seed 和 probability-level 诊断，而非只看单次 fixed-threshold F1。

## 14.2 工程 / 提交系统主线

近期追求官方分数时：

```text
Liu targeted Prompt
或 H2/H3 类 Hybrid
```

研究增强方法时：

```text
F′ full-data masked student
N3 high-recall candidate generator
Liu verifier
```

两条路线必须分开陈述：

- Prompt-only：近期系统性能；
- Augmentation：论文研究贡献；
- Hybrid：两者的后续结合。

---

# 15. 下一阶段建议

## 15.1 第一优先：Per-class threshold tuning

使用已有 F′ / N3 checkpoints 与 probabilities，不重新训练。

要求：

- threshold 在 internal validation split 选择；
- final dev 只报告；
- 比较 target 18 / non-target 90 / all 108；
- 观察 N3 的 recall 是否能在更合理 precision 下保留；
- 同时报告 DRR。

## 15.2 第二优先：重新设计 Hybrid

推荐对比：

```text
Liu alone
F′ alone
N3 alone
Liu + F′ candidates
Liu + N3 candidates
Liu primary + controlled DeBERTa rescue
```

不要只做简单 union / intersection。

需要明确：

- DeBERTa candidate threshold；
- Liu 是否允许发现新标签；
- 是否只验证 targets；
- direction conflict 如何处理；
- 融合规则只能在 internal split 设计。

## 15.3 第三优先：增加 F′ seeds

目的：

- 判断 epoch-1 collapse 比例；
- 估计 mean / std / confidence interval；
- 判断 seed 44 是否异常高值；
- 测试 macro-aware / target-aware checkpoint selection；
- 减少单 run 叙事。

## 15.4 人工筛选实验

只有教授明确要求时再做。

最低可辩护设计：

```text
same generated pool
same label distribution
same sample count
unfiltered vs AI-screened vs human-reviewed vs random size-matched
```

否则不能判断 manual filtering 的独立作用。

---

# 16. 未来每个实验的强制输出清单

## 16.1 配置与可复现性

- run ID；
- git branch / commit；
- trainer path；
- model / LoRA configuration；
- data files 与 SHA-256；
- seed；
- train/internal-val/dev split；
- supervision policy；
- negative sampling policy；
- threshold policy；
- best epoch；
- stopping reason；
- GPU / environment；
- checkpoint hashes。

## 16.2 指标

分别对：

```text
Target 18
Non-target 90
All 108
```

报告：

- Micro P / R / F1；
- Macro P / R / F1；
- mean ± std；
- per-seed values；
- TP / FP / FN；
- predicted classes；
- DRR / reversal count。

## 16.3 Probability diagnostics

- per-target ROC-AUC；
- mean / median AUC；
- below-chance target count；
- positive / negative score quantiles；
- oracle per-label F1；
- threshold sensitivity；
- calibration curves（如后续实现）。

## 16.4 错误分析

- target FN；
- target FP；
- non-target FP；
- direction reversals；
- zero-prediction labels；
- blanket-firing labels；
- seed collapse；
- incompatible artifacts；
- `HUMAN_CHECK_REQUIRED`。

## 16.5 报告

每个 Phase 至少包括：

```text
reports/PHASE*_REPORT.md
outputs/*.csv
outputs/*.json
run_manifest.json
README rerun command
```

---

# 17. 关键文件索引

## 官方文件

```text
dataset/gold_labels/train/train_human_values.json
dataset/gold_labels/dev/dev_human_values.json
evaluation.py
direction_mapping.json
human_value_level1_values.json
human_value_level2_values.json
human_value_taxonomy.json
```

## 数据增强

```text
output/research_first_round_ai_filtered_augmentation/...
output/research_label_aware_low_frequency_augmentation_v2/...
output/research_augmented_deberta_v1/...
output/research_augmented_deberta_v2_unfiltered/...
```

## 当前验证报告

```text
new_check/phase0/reports/PHASE0_VALIDATION_REPORT.md
new_check/phase1/reports/PHASE1_BASELINE_PROBABILITY_REPORT.md
new_check/phase2/reports/PHASE2_CONTROLLED_ABLATION_REPORT.md
new_check/phase3/reports/PHASE3_FULL_DATA_AND_NEGATIVE_SAMPLING_REPORT.md
```

## 当前详细输出

```text
new_check/phase0/outputs/
new_check/phase1/outputs/
new_check/phase2/outputs/
new_check/phase3/outputs/
```

---

# 18. 一句话总结当前研究状态

> Phase 0–3 已经证明，900 条 diagnosis-guided augmented samples 能够为原本接近随机的 18 个方向特定目标标签引入真实但较弱的区分信号；监督策略的效果取决于 340 条稀疏数据与 900 条较完整数据的组成，1:3 负样本下采样可以大幅提高召回但主要改变校准而非学习质量，下一步应使用内部阈值调优和 Liu Prompt verifier 将高召回转化为可用 precision。

---

# 19. 当前最重要的研究判断

当前结果不是“最终模型效果很好”，也不是“研究失败”。

更准确的评价是：

- **模型性能层面：** DeBERTa 的 target precision、stability 和 DRR 仍不足；
- **研究证据层面：** 已完成从单次结果到多 seed、probability-level、factorized ablation 和 negative-sampling mechanism 的较完整验证；
- **论文价值层面：** 最有价值的发现不是某一个最高 F1，而是数据增强信号、数据组成、partial-label supervision、negative imbalance 和 calibration 之间的交互；
- **下一步价值：** N3 已提供过去没有的高召回候选来源，值得重新运行“DeBERTa candidate + Liu verifier”的新版 Hybrid。
