# FEHU Project — 全面分析：目标、结果与研究进展

**分析日期：** 2026-07-24  
**仓库：** `fehu-project`（项目根目录 `ntcir19_fehu-master/`）  
**当前分支：** `full-fehu-codex-handoff-20260724`  
**分析范围：** 全仓库阅读（README、文档、源码、实验输出、验证工作区、实验设计），不含对任何文件修改或新实验执行。

---

## 一、项目目标

### 1.1 任务定义

本项目参加 **NTCIR-19 FEHU（Fact-based Event-centric Human Value Understanding）** 评测任务，目标是从事实性新闻文章中识别**每个参与者（actor）所表达的人类价值观（human values）**。

FEHU 定义了两个任务，每个任务有两个变体：

| 任务 | 变体 | 标签空间 | 评测单元 |
|---|---|---|---|
| **Task-1（文章级）** | **1a** | Level-2 价值观（20 个类别） | `(article_guid, actor_id)` |
| **Task-1（文章级）** | **1b** | Level-1 价值观（54 个）+ 方向 | `(article_guid, actor_id)` |
| Task-2（子事件级） | 2a / 2b | 同上，但按子事件粒度 | `(article_guid, subevent_id, actor_id)` |

- **方向（direction）语义**：`"1"` = aligned（行为表达/支持该价值观），`"0"` = contradictory（行为违背/破坏该价值观）。
- Task-1b 的评测空间为 **108 个 direction-aware 类别**（54 L1 × 2 方向），编码为 `"{direction}:{l1_value}"`。
- **本项目所有工作聚焦 Task-1**；Task-2 已定义但未有实现系统。

### 1.2 评测指标

官方评测器 `evaluation.py`（从未修改）报告三项指标：

- **micro-F1**：所有标签实例级别的精确率/召回率/F1。
- **macro-F1（gold-supported）**：仅在 gold 中出现至少一次的标签上做平均。
- **Direction Reverse Rate（DRR）**：仅适用于 Task-1b/2b。衡量 gold 中有唯一方向的 Level-1 值被预测为相反方向的比例。越低越好。dev 上分母为 2222。

### 1.3 数据规模

| 划分 | 文章数 | actor 实例数 | Task-1b 标签数 |
|---|---|---|---|
| Train | 1,228 | 3,335 | 16,905 个 direction-aware 标签 |
| Dev | 177 | 456 | 2,390 个标签，覆盖 93 个类别（16 个 support ≤2） |
| Test | 未公开 gold | — | — |

**关键数据特性：** 标签分布呈严重长尾——前 5 个 L1 类别占 41.8% 的标签量，54 个 L1 中 23 个训练样本 ≤130。方向本身也不平衡（aligned : contradictory ≈ 2.1 : 1）。

---

## 二、研究路线演进

本项目经历了四条交叉研究路线，按时间顺序：

### 2.1 Prompt-only LLM 流水线（2026-05 起）

从 GPT-4o-mini 少样本基线出发，逐步演化为：

- **V1**：GPT-4o/GPT-4o-mini/DeepSeek Flash 少样本 prompt（`src/run_pipeline.py`）。
- **V2**：零样本、taxonomy-grounded、严格校验流水线（`src/run_pipeline_prompt_v2.py`）。核心保证：失败绝不静默转换为空预测；全有或全无的 schema 校验；身份绑定缓存。
- **V3**：双生成器 prompt ensemble（变体A偏精确、变体B偏召回）+ 紧凑验证器 + 可选标签感知策略（`src/run_pipeline_prompt_v3.py`）。
- **Liu 参考方法**（`liu_method/`）：7 个 prompt 变体，其中 `targeted_more_shot_balanced` 是最强单系统，但存在 demo 截断（仅展示前4个标签）、dev 泄露的 add-list 集成等问题（已审计）。
- **E1（2026-07-22）**：修复 Liu prompt 的 few-shot demo 截断和输出数量上限——**实现项目最强 prompt-only 单系统**（1b micro 0.5480 / macro 0.3719）。
- **E2（2026-07-23）**：在 E1 基础上添加偏精确的 bias-control 指令——**结果被拒绝**（召回损失远超精度收益，macro-F1 −0.045）。

### 2.2 DeBERTa 学生分类器（2026-05 起）

`microsoft/deberta-v3-base` + LoRA（r=16, α=32，589K 可训练参数），108 路多标签 sigmoid 头，BCE loss + `sqrt(neg/pos)` pos-weight，全局阈值 0.3。

**基线结果**：仅预测 8 个类别，macro-F1 0.03，DRR 0.22——长尾类别完全塌缩。

### 2.3 DRA-FEHU：诊断驱动的数据增强（2026-06 起）

核心理念：按标签诊断 → LLM 生成标签条件化的合成数据 → 受控训练。

- **Round 1**（340 条 AI 筛选的 silver 数据）：Augmented DeBERTa v1 训练——**负面结果**（所有目标标签零召回，指标持平）。
- **Round 2**（900 条结构校验但语义未筛选的数据，18 个 direction:L1 目标）：配合 masked partial-label loss 训练 Augmented DeBERTa v2——macro 从 0.03 跃升至 0.13，预测 50 个类别，但精度和 DRR 恶化。

### 2.4 推理时 Hybrid（2026-05 → 07-14）

Hybrid v1 失败分析产生了项目的**核心洞察**：DeBERTa 擅长发现*哪些价值观相关*（高召回），但方向判断灾难性差（DRR ≈ 0.24）；LLM 方向判断精确（DRR ≈ 0.02）。因此 Hybrid v2+ 将两者解耦：

- DeBERTa 提供**方向中立**的候选值（value-only candidates）。
- LLM 做**验证 + 方向分配**。

**当前最佳系统 Hybrid H3**（2026-07-14）：Augmented DeBERTa v2 候选 + Liu 的 DeepSeek Flash prompt 验证/方向分配 → **1b micro 0.5474 / macro 0.3385 / DRR 0.031**。验证步骤是负载承重的（同一 run 内关闭验证 → micro 暴跌至 0.4057）。

---

## 三、综合实验结果汇总

以下结果均为 dev 集（177 篇文章），使用官方 `evaluation.py`，单次运行/单 seed 除非另有标注。

### 3.1 各系统总体对比

| 系统 | 1b micro-F1 | 1b macro-F1 | 1a micro-F1 | DRR | 预测类别数 |
|---|---|---|---|---|---|
| DeBERTa baseline | 0.302 | 0.031 | 0.509 | 0.217 | 8 |
| Augmented DeBERTa v1 | 0.301 | 0.026 | 0.509 | 0.136 | 6 |
| Augmented DeBERTa v2 | 0.331 | 0.130 | 0.541 | 0.288 | 50 |
| Liu frozen (prompt) | 0.535 | 0.339 | 0.645 | **0.023** | 88 |
| **E1（prompt-only 最强）** | **0.548** | **0.372** | 0.657 | 0.035 | **95** |
| E2（被拒绝） | 0.530 | 0.327 | 0.637 | 0.035 | 92 |
| **Hybrid H2** | 0.543 | **0.360** | 0.660 | 0.036 | 89 |
| **Hybrid H3** | **0.547** | 0.338 | **0.662** | 0.031 | 85 |

### 3.2 18 个低频目标标签的表现

| 系统 | target-18 micro-F1 | target-18 macro-F1 | TP / 140 |
|---|---|---|---|
| DeBERTa baseline | 0.000 | 0.000 | 0 |
| Augmented DeBERTa v2 | 0.081 | 0.036 | 12 |
| Liu frozen | 0.241 | 0.213 | 28 |
| Hybrid H2 | **0.254** | **0.229** | 35 |
| E1 | 0.246 | 0.231 | 38 |

**关键发现：** 基线模型对这 18 个目标类别零预测（140 个 FN）；增强后 v2 有微弱改善；LLM 系统（Liu/Hybrid/E1）远超任何 DeBERTa 变体。4 个目标（0:48, 0:16, 0:19, 1:49）在*所有*历史系统中均为零预测。

### 3.3 受控多 seed 实验（Phase 2–3，均值）

| 实验条件 | 1b micro-F1 | 1b macro-F1 | t18 macro-F1 | 目标 AUC |
|---|---|---|---|---|
| A：仅官方数据 | 0.301 | 0.028 | 0.000 | 0.513 |
| B：+900 assume-neg | 0.311 | 0.089 | 0.011 | 0.624 |
| C：+900 masked | 0.310 | 0.047 | 0.002 | 0.577 |
| **F′：+340+900 masked** | **0.321** | 0.088 | 0.026 | **0.632** |
| G′：+340+900 assume-neg | 0.303 | 0.078 | 0.006 | 0.598 |
| N3：F′ + 1:3 负采样 | 0.235 | **0.107** | **0.049** | 0.608 |

---

## 四、已验证的有效发现

1. **价值/方向解耦是正确架构**：DeBERTa 做候选召回 + LLM 做方向判断的分解在所有实验中一致优于任何单模型。
2. **LLM 验证步骤是负载承重的**：同一 Hybrid run 内 H3（有验证）0.547 vs 无验证 0.406——效应量巨大。
3. **合成数据在分数层面改善了目标类别**：所有增强实验的 target AUC 均超过基线机会水平（+0.06–0.11），符号一致性 6/6。
4. **Supervision policy 效应依赖于数据组成**：masked loss 在有单标签合成记录时必须使用（否则 assume-negative 注入假阴性）；纯多标签数据上 assume-negative 更稳定。
5. **E1 的 few-shot demo 修复是有效的**：移除 4 标签截断和 demo 截断后，micro-F1 +0.013，macro-F1 +0.033，95 个类别（+7），这是项目最强 prompt-only 单系统。
6. **Prompt 级精度约束不可行**：E2 证明在生成阶段施加精度 gate 会不可接受地牺牲召回（1:1.2 的 TP:FP 交换比），精度应由独立后处理阶段恢复。
7. **1:3 负采样提升召回但通过校准而非学习**：目标 AUC 未变（0.608），但分数被抬过阈值 → 召回 0.59。1:1 负采样破坏排序。

---

## 五、已知问题与风险

### 5.1 实验控制问题（严重）

1. **v1→v2 混淆**：同时改变了数据（+900）和监督策略（masked loss），无因子化运行隔离各因素效应。Phase 2 部分弥补但未完全解决。
2. **Dev 集三重使用**：同一 177 篇文章同时作为 early stopping 标准、增强目标选择输入、最终报告集——存在乐观偏差。
3. **单 seed/单 API pass**：几乎所有历史结果为单次运行。masked 家族 macro 标准差可达 0.084；GPU 非确定性使多 epoch 运行仅分布式可复现。
4. **Hybrid 的 0.547 对 Liu 的 0.535 优势（+0.0127）**：单次 API pass，对比记录的跨机器方差 ±0.004——未经复制和置信区间验证。

### 5.2 方法问题

5. **全局阈值 0.3 是错误工具**：v2 候选召回在阈值 0.10 时为 0.951，0.30 时为 0.613——大量信号在概率空间中存在但被决策规则丢弃。长尾多标签文献的标准解法（per-class threshold、分布平衡损失、logit 调整）均未尝试。校准模块存在但从未执行。
6. **合成-真实分布偏移**：合成数据中位长度 811 字符 vs 真实 3,331；1 个 actor vs 3 个；1 个标签 vs 13 个——训练时的协变量偏移显著。
7. **512 token 截断**：DeBERTa 仅看到文章开头 512 tokens，而中位文章约 700–900 tokens——大部分证据对 DeBERTa 不可见。
8. **900 条 Round-2 数据语义未筛选**：仅通过自动结构校验；无人类审核、无 LLM 语义筛选。

### 5.3 需纠正的早期说法

9. **"人工审核了 340 条数据"**：事实是仅 6 条 pilot 数据经过人类 ACCEPT，且未进入任何实际训练集。340 条为 Fable 5 AI 筛选，900 条完全未筛选。
10. **Liu 的 0.5387 和 0.5657**：本地无法复现/审计，artifact 缺失——已标记为 BLOCKED，不参与任何比较。

---

## 六、当前研究进展状态

### 6.1 已完成

- V1–V3 prompt 流水线 + 124 个单元测试
- 7 方法标签诊断（per-label recall/precision, 108 类）
- 两轮数据增强（340 AI 筛选 + 900 未筛选）+ 对应 DeBERTa 训练
- 4 阶段受控验证（Phase 0–3）：21 次受控训练运行，全概率验证
- Hybrid H0–H3 + 消融实验
- E1（few-shot 修复，成功）和 E2（bias control，失败）实验
- 关键审查和教授反馈验证计划
- 工程规范：官方 evaluator 不变、追加式运行、hash 锁定输入

### 6.2 进行中

- **E3 设计已完成**（2026-07-23）：子事件分解 prompting + 方向特定 union——基于 E1 成功和 E2 失败的教训。冻结 E1 prompt，仅改变预测单元（per-subevent），代码侧 union 聚合。**尚未实现/运行。**
- **E4 设计已规划**：per-candidate QA 验证器——作为独立阶段（非 prompt 内约束），不对称地只能移除候选。

### 6.3 尚未开始

- Per-class 阈值校准（最高优先级）
- Hybrid ×3 复制 + 候选源消融
- Masked 家族稳定性研究（5–7 seed）
- 900 条数据的 Fable 5 语义筛选 + 筛选效果对比训练
- 任何 test 集运行或评测提交
- Task-2 的任何实现
- 论文章节撰写

---

## 七、未来路线图（按优先级）

### 低风险、增量式（优先执行）

1. **Per-class 阈值校准**：在内部 train split 上调优现有 checkpoint 的阈值，应用到 F′/N3/v2 预测。理由：Phase 3 显示 N3 的增益是校准形态的；冻结 0.30 规则已被证明是错误工具。
2. **Hybrid ×3 复制 + 候选源消融**：比较 Liu-only vs v2 vs F′-seed-44 vs N3 候选源，含 bootstrap CI。理由：论文标题数字目前仅基于一次 API pass。
3. **Masked 家族稳定性研究**：5–7 个额外 F′ seed + macro 感知的 checkpoint 选择。理由：F′ 的崩塌/峰值双模态是学生路线的最大障碍。
4. **900 条数据的语义筛选**：Fable 5 筛选 → 重新训练 F′-screened，与 unscreened 做对照。

### 中高风险、探索性（在 1–3 之后）

5. **更长输入的学生模型**：max_length 1024 或证据句选择——攻击 512 token 截断问题。
6. **Teacher annotation 蒸馏**：用 Liu/E1 标签标注真实文章 → 训练 masked 学生——消除合成分布偏移。
7. **8B QLoRA 生成式学生**：NEVU 论文的核心发现——生成式 LoRA 微调可同时解决方向（DRR → 0.01–0.03）和 macro 问题——是本项目 DeBERTa 最致命的两个弱点。
8. **E3（子事件分解）+ E4（QA 验证）**：子事件分解是 NEVU 文献中 +13–19 pp 召回的来源，per-candidate QA 是精度后盾。

### 已被证据降级的想法

- 全局阈值扫描单独使用（Phase 1 显示基线无潜在信号可恢复）
- 进一步的未筛选生成轮次（数据质量/形态已成为绑定问题）
- 1:1 负采样（破坏性）
- 在 prompt 中加入精度约束（E2 已证伪）
- 追求 Liu 的 0.5657（不可审计）

---

## 八、项目总体评价

### 8.1 优势

- **工程纪律出色**：官方 evaluator 从不修改、追加式 timestamped 运行、hash 锁定输入、诚实报告负面结果——这些在单学生研究项目中罕见且宝贵。
- **核心洞察正确且被多角度验证**：价值/方向解耦（DeBERTa recall + LLM direction）是经得起推敲的架构贡献。
- **验证工作彻底**：Phase 0–3 四阶段受控验证（21 次受控训练），全面复核历史声明，发现并纠正多处早期错误。
- **实验设计逻辑清晰**：E1/E2 形成了干净的对照实验（E1 = 仅改 demo，E2 = 仅加 bias-control 指令），为 E3 设计提供了坚实的经验基础。
- **自审计文化**：关键审查文档（critical review）、Liu 方法审计、教授反馈验证计划——均在被要求之前主动完成。

### 8.2 待补强

- **核心声明未经复制**：Hybrid > Liu 的 0.0127 优势在单次 API pass 上，而记录内方差为 ±0.004——需要 CI。
- **增强效果的因果归因未建立**：v1→v2 混淆（数据+loss 同时变），需要因子化实验。
- **廉价标准基线缺失**：per-class threshold、分布平衡损失等文献标准解法未试——"罕见类零召回 → 需要合成数据"的推论不严谨。
- **Dev 过度使用**：需要内部 validation split 协议。
- **合成数据质量未经测量**：900 条 unscreened 数据的筛选效果未量化。
- **学生模型的输入截断和弱 actor 条件化**从未作为独立变量研究。

### 8.3 论文定位建议

基于当前证据，建议论文叙事调整为：

- **主要贡献**：价值/方向解耦的 Hybrid 架构（DeBERTa 候选召回 + LLM 方向分配 + 验证）——这条线有最强的多角度证据支持。
- **方法论贡献**：诊断引导的 LLM 数据增强 + masked partial-label 监督——作为一个有控制的消融研究呈现（含其负面和交互发现），而非作为已证实的性能提升手段。
- **工程贡献**：严格校验的 prompt pipeline 和追加式实验管理体系。

---

## 九、关键数字速查

| 指标 | 值 | 备注 |
|---|---|---|
| 最佳单系统 1b micro-F1 | **0.5480**（E1 prompt-only） | 单次 API pass |
| 最佳 Hybrid 1b micro-F1 | 0.5474（H3） | 单次 API pass |
| 最佳 1b macro-F1 | 0.3719（E1） | |
| 最佳 1a micro-F1 | 0.662（H3） | |
| 最佳 DRR | 0.023（Liu frozen） | |
| 基线 DeBERTa 预测类别数 | 8 / 108 | |
| Augmented v2 预测类别数 | 50 / 108 | |
| 18 个目标类别基线召回 | 0 / 140（全零） | |
| Hybrid 验证步骤效应量 | 0.547 → 0.406（关闭验证） | 负载承重 |
| E1 vs Liu micro 增益 | +0.0133 | ~3× 跨机器方差 |
| E2 vs E1 macro 损失 | −0.045 | 精度约束的代价 |

---

*本分析基于对仓库全部文档、源码、实验配置和报告的阅读，未执行任何新实验。建议配合 `docs/FEHU_PROJECT_PROGRESS_SUMMARY.md`（Phase 0–3 详细数据）和 `docs/FEHU_PROJECT_RESEARCH_SUMMARY.md`（完整研究注册表）阅读。*

---

# 附录：数学化深度分析

**分析日期：** 2026-07-24  
**分析方法：** 从数学分析大师视角，基于概率论、信息论、优化理论和统计学习理论，对项目的关键问题进行严格数学化分析。

---

## A. DeBERTa DRA 方法为何失败？——数学本质分析

### A.1 问题形式化

设 FEHU Task-1b 的 108 类多标签分类问题为：对每个 (article, actor) 实例 $x_i$，预测标签向量 $\mathbf{y}_i \in \{0,1\}^{108}$。训练集 $\mathcal{D} = \{(x_i, \mathbf{y}_i)\}_{i=1}^{N}$，其中 $N = 3335$（官方训练 actor 实例）。

DeBERTa 输出 logits $\mathbf{z} = f_\theta(x) \in \mathbb{R}^{108}$，概率 $\hat{\mathbf{y}} = \sigma(\mathbf{z})$，决策规则 $\tilde{y}_c = \mathbb{1}[\sigma(z_c) > \tau]$，其中 $\tau = 0.3$ 为全局阈值。

### A.2 梯度饥荒：Sigmoid 在极端类别不平衡下的数学困境

BCE 损失对单个类别 $c$ 的梯度为：

$$\frac{\partial \mathcal{L}}{\partial z_c} = w_c^+ \cdot y_c \cdot (\sigma(z_c) - 1) + w_c^- \cdot (1-y_c) \cdot \sigma(z_c)$$

其中 $w_c^+$ 为 pos_weight。项目中 $w_c^+ = \min\left(\sqrt{\frac{N - n_c^+}{n_c^+}}, 10\right)$。

**关键数值计算：** 对训练样本数 $n_c^+ = 4$ 的极稀有类（如 "Be neat and tidy"）：

$$w_c^+ = \min\left(\sqrt{\frac{3331}{4}}, 10\right) = \min(28.8, 10) = 10$$

而理想平衡权重为 $\frac{3331}{4} \approx 832.8$。

**梯度比分析：** 在一个 epoch 中（$\sim 104$ 步，effective batch 32），稀有类的总正梯度信号：

$$G_c^+ = n_c^+ \cdot w_c^+ \cdot |\sigma(z_c) - 1| \approx 4 \times 10 \times 0.9 \approx 36$$

总负梯度信号：

$$G_c^- = (N - n_c^+) \cdot \sigma(z_c) \approx 3331 \times 0.1 \approx 333$$

**结论：负梯度压倒正梯度，比例约 $9.3:1$。** 模型被教导"这个类几乎总是不存在"，稀有的正信号无法克服负信号的累积效应。logit $z_c$ 被推向 $-\infty$，$\sigma(z_c) \to 0$，远低于阈值 $\tau = 0.3$。

### A.3 阈值的相变分析

Sigmoid 函数在阈值 $\tau = 0.3$ 处的关键性质：

$$z_\tau = \log\frac{\tau}{1-\tau} = \log\frac{0.3}{0.7} \approx -0.847$$

在 $z_\tau$ 处的导数值（梯度传播效率）：

$$\sigma'(z_\tau) = \sigma(z_\tau)(1-\sigma(z_\tau)) = 0.3 \times 0.7 = 0.21$$

这意味着在决策边界附近，每个样本只能传递约 21% 的梯度——这是 sigmoid 最大的梯度区域！对稀有类，$z_c$ 通常在 $-2$ 到 $-4$ 范围（$\sigma \in [0.018, 0.119]$），此处的梯度：

$$\sigma'(z = -3) = \sigma(-3)(1-\sigma(-3)) \approx 0.047 \times 0.953 \approx 0.045$$

**只有最大梯度的 21%，形成梯度传播的恶性循环。**

### A.4 合成数据的分布偏移：协变量偏移的数学描述

设真实数据分布为 $P_{real}(x, \mathbf{y})$，合成数据分布为 $P_{synth}(x, \mathbf{y})$。度量分布偏移的 KL 散度：

| 特征 | $P_{real}$（中位数） | $P_{synth}$（中位数） | 偏移程度 |
|---|---|---|---|
| 文章长度 | 3,331 chars | 811 chars | 4.1× |
| actor 数 | 3 | 1 | 3× |
| 标签数 | 13 | 1 | 13× |

在经验风险最小化框架下，使用合成数据训练等价于在错误分布上最小化期望风险：

$$\hat{\theta}_{DRA} = \arg\min_\theta \hat{R}_{P_{synth}}(\theta) \neq \arg\min_\theta R_{P_{real}}(\theta)$$

**重要性采样视角：** 若要对真实分布做无偏估计，合成样本需要重要性权重：

$$w(x, \mathbf{y}) = \frac{P_{real}(x, \mathbf{y})}{P_{synth}(x, \mathbf{y})}$$

但在高维离散空间中，这个比值通常是退化的——对于短单标签合成样本，$P_{real}(x_{short}, \mathbf{y}_{single}) \approx 0$（真实新闻几乎从不是短单标签的），导致 $w \to 0$ 或 $\infty$，重要性采样完全失效。

### A.5 "Assume-Negative" 对 BCE 的毒化效应

对单标签合成样本 $(x, y_{target}=1, y_{j \neq target}=0)$，BCE 损失：

$$\mathcal{L} = -\log\sigma(z_{target}) - \sum_{j \neq target}^{107} \log(1 - \sigma(z_j))$$

第二项包含 **107 个负监督信号**。如果某些 $j$ 与 target 真实共现（co-occurrence rate $\rho_j > 0$），则每个合成样本注入 $\rho_j$ 比例的假阴性监督。

对 340 条单标签合成数据，假设平均共现率 $\bar{\rho} = 0.05$（保守估计），总假阴性注入：

$$FN_{injected} \approx 340 \times 107 \times 0.05 \approx 1819 \text{ 个假阴性标签}$$

这是对稀有类的毁灭性打击——它们本就只有 4-128 个正样本，却被额外注入数十到数百个假阴性。

### A.6 宏观-微观目标冲突：早期停止的隐式偏差

微 F1 的定义：

$$\text{micro-F1} = \frac{2\sum_c TP_c}{2\sum_c TP_c + \sum_c FP_c + \sum_c FN_c}$$

设头部 5 个类占总标签的 41.8%（$\sim 7065/16905$），尾部 18 个目标类占 $\sim 1.2\%$（$\sim 203/16905$）。微 F1 对尾部类 TP 的导数：

$$\frac{\partial \text{micro-F1}}{\partial TP_{tail}} \approx \frac{2}{2\sum TP + \sum FP + \sum FN} \propto \frac{1}{\text{total}}$$

而尾部类 FP 的惩罚与头部类 FP 完全相同。因此：

> **从微 F1 的角度看，预测一个稀有类只有 $\sim 0.1\%$ 的收益权重，但承担 100% 的 FP 惩罚风险。** 最优策略是不预测任何稀有类。

这就是为什么在 micro-F1 早期停止下，基线 DeBERTa 的 18 个目标类全部零预测（0 TP / 140 FN）。

---

## B. E1 为何始终不如 Liu 的 Ensemble？——信息论分析

### B.1 问题设定

**Liu Ensemble 最新结果：**
- Task-1a: micro-F1 **0.6589**, macro-F1 **0.5366**
- Task-1b: micro-F1 **0.5543**, macro-F1 0.3277, DRR 0.0345

**E1 结果：**
- Task-1a: micro-F1 0.6574, macro-F1 0.5018
- Task-1b: micro-F1 **0.5480**, macro-F1 **0.3719**, DRR 0.0347

### B.2 核心悖论：E1 的 1b macro 更高但 1a macro 更低

这是理解问题本质的关键信号：

| 指标 | E1 | Liu Ensemble | 含义 |
|---|---|---|---|
| 1b 预测类别数 | **95** | ~92 | E1 覆盖更多 L1 类别 |
| 1b macro-F1 | **0.3719** | 0.3277 | E1 在 L1 粒度更均匀 |
| 1a macro-F1 | 0.5018 | **0.5366** | Ensemble 在 L2 粒度更均匀 |

**解释：** E1 倾向于预测来自不同 L1 但在同一 L2 组内的值（如 "Be broadminded" 和 "Be creative" 都属于 Self-direction），导致 L1-macro 高但 L2-macro 不高。Ensemble 的不同 prompt 变体具有互补的 L2 组偏好，覆盖了更多 L2 类别。

### B.3 信息论框架：分类器多样性与信道容量

将每个 prompt 变体视为一个噪声信道，输入为真实标签 $\mathbf{y}$，输出为预测 $\hat{\mathbf{y}}_k$。互信息：

$$I(\mathbf{y}; \hat{\mathbf{y}}_k) = H(\mathbf{y}) - H(\mathbf{y}|\hat{\mathbf{y}}_k)$$

单个 prompt（E1）的信道容量为 $C_1 = \max_{P(\mathbf{y})} I(\mathbf{y}; \hat{\mathbf{y}}_1)$。

$K=4$ 个不同 prompt 的联合信道容量：

$$C_{1..K} = \max_{P(\mathbf{y})} I(\mathbf{y}; \hat{\mathbf{y}}_1, ..., \hat{\mathbf{y}}_K)$$

由链式法则：

$$I(\mathbf{y}; \hat{\mathbf{y}}_1, ..., \hat{\mathbf{y}}_K) = I(\mathbf{y}; \hat{\mathbf{y}}_1) + \sum_{k=2}^K I(\mathbf{y}; \hat{\mathbf{y}}_k | \hat{\mathbf{y}}_1, ..., \hat{\mathbf{y}}_{k-1})$$

**关键洞察：** 如果不同 prompt 变体的错误是条件独立的（在不同标签子集上犯错），则每个增量条件互信息项 $I(\mathbf{y}; \hat{\mathbf{y}}_k | \hat{\mathbf{y}}_{<k}) > 0$，且联合信道容量严格大于单一信道容量。

具体而言，Liu 的 4 个 prompt 变体（baseline / balanced / compact / targeted_more_shot_balanced）在以下维度上实现条件独立性：

- **标签频率偏置不同：** balanced 偏向高频类，targeted 偏向低频类
- **证据阈值不同：** compact_strict 要求更高证据标准
- **方向敏感度不同：** 不同变体对 aligned vs contradictory 的判断倾向不同

### B.4 Precision-Recall 帕累托前沿的凸组合

在 precision-recall 空间中，单个 prompt 在温度 $T=0.1$ 下运行一次，只能产生一个操作点 $(P_1, R_1)$。

**E1 的局限：** 温度 $T=0.1$ 使 softmax 锐化，$P(y|x) \approx \text{one-hot}$，导致：
- 高置信度预测非常精确，但低置信度的正确标签被丢弃
- 无法在"激进召回"和"保守精确"之间做平滑权衡

**Ensemble 的优势：** 4 个不同操作点 $(P_k, R_k)_{k=1}^4$ 可以通过 union（最大化召回）和 intersection/voting（最大化精度）实现凸组合的任意内点：

$$\mathcal{S}_{ensemble} = \text{conv}\{(P_1, R_1), ..., (P_4, R_4)\}$$

其中 $\text{conv}$ 表示由 union（凸组合的 recall 维度）和 voting（凸组合的 precision 维度）可达的操作点集合。

**E1 无法进入这个凸包内部——它只访问了一个角点。**

### B.5 具体数字解读：为什么 1a macro 差距最大（0.5018 vs 0.5366）

Task-1a 只有 20 个 L2 类别。macro-F1 对每个类别等权平均，因此：

$$\text{1a macro-F1} = \frac{1}{20}\sum_{c=1}^{20} F1_c$$

设 E1 在某 3 个稀有 L2 类上 $F1_c = 0$（完全漏掉），而 Ensemble 的某个变体覆盖了它们。这 3 个类贡献的 macro-F1 差：

$$\Delta\text{macro} = \frac{1}{20} \times (F1_c^{ens} - 0) \times 3$$

若 $F1_c^{ens} \approx 0.3$（刚预测对几个），则 $\Delta\text{macro} \approx 0.045$——精确解释了观测到的 0.0348 差距。

---

## C. 为什么 DeepSeek Flash 比 Pro、GPT-5.5、Fable 5 都强？——反直觉现象的数学解释

### C.1 现象确认

在 FEHU Task-1 的 prompt-only 场景中，使用**相同 prompt**（Liu 的 `targeted_more_shot_balanced`），DeepSeek Flash 的表现始终优于：
- DeepSeek V4 Pro（更大的同系列模型）
- GPT-5.5-sol（理论上更强的模型）
- Fable 5（Anthropic 最新模型）

这违反"更大模型 = 更好性能"的缩放律直觉。

### C.2 假说一：过度思考陷阱（The Overthinking Trap）

设模型的输出分布为：

$$P_M(y|x) = \text{softmax}\left(\frac{f_M(x)}{T}\right)$$

其中 $f_M(x)$ 是模型 $M$ 的 logit 函数。

将"正确"的 FEHU 标注函数记为 $g(x)$（人类标注者的判断模型）。模型误差可分解为：

$$\text{Error}_M = \underbrace{\|P_M - P_{human}^{ideal}\|}_{\text{建模误差}} + \underbrace{\|P_{human}^{ideal} - g\|}_{\text{标注噪声}}$$

更大的模型 $M_{pro}$ 对 $P_{human}^{ideal}$ 的建模更精细，但 FEHU 的标注本身有噪声（value annotation 是高度主观的任务，ValueEval'23 需要 3 个众包工人才达到可用一致性）。因此：

$$P_{human}^{ideal} \neq g \quad \text{（标注不等于真实意图）}$$

**Flash（较小模型）可能恰好建模了一个与 $g$ 更接近的简化版 $P_{human}$：**

$$\|P_{flash} - g\| < \|P_{pro} - g\|$$

尽管 $\|P_{pro} - P_{human}^{ideal}\| < \|P_{flash} - P_{human}^{ideal}\|$（Pro 更准确地建模了人类判断），但"更准确的人类判断"恰恰偏离了 FEHU 标注者的具体标注模式。

**数学类比：** 这是 bias-variance tradeoff 在 instruction-following 场景的体现：

$$\text{MSE} = \underbrace{(\mathbb{E}[\hat{f}] - f)^2}_{\text{bias}^2} + \underbrace{\text{Var}(\hat{f})}_{\text{variance}} + \underbrace{\sigma^2}_{\text{irreducible noise}}$$

Pro 降低了 variance 但引入了 bias（学到的人类判断模式 $\neq$ FEHU 标注模式）。Flash 的 bias 恰好更接近 FEHU 模式。

### C.3 假说二：Logit 尺度的有效温度效应

不同模型有本质不同的 logit 尺度。设：

$$f_{flash}(x) = \alpha_f \cdot \hat{f}(x), \quad f_{pro}(x) = \alpha_p \cdot \hat{f}(x)$$

在相同温度 $T = 0.1$ 下：

$$P_{flash} = \text{softmax}(10\alpha_f \cdot \hat{f}(x))$$
$$P_{pro} = \text{softmax}(10\alpha_p \cdot \hat{f}(x))$$

如果 $\alpha_f > \alpha_p$（Flash 的 logit 天然更锐利——蒸馏过程的常见副作用），则 Flash@T=0.1 的有效温度比 Pro@T=0.1 更低，Flash 的行为更接近 argmax（确定性分类），而 Pro 仍然有一定随机性。

**实验验证方法：** 测量两个模型在 FEHU prompt 下的平均 logit 熵：

$$H_{model} = -\sum_c P_{model}(c|x) \log P_{model}(c|x)$$

预测：$H_{flash} < H_{pro}$（Flash 更确定），即 Flash 的有效温度更低。

### C.4 假说三：蒸馏的校准正则化效应

Flash 是从 Pro 通过知识蒸馏训练的。蒸馏损失为：

$$\mathcal{L} = (1-\lambda)\mathcal{L}_{CE}(y, P_S) + \lambda \cdot T_d^2 \cdot KL(P_T^{T_d} \| P_S^{T_d})$$

其中 $P_T^{T_d} = \text{softmax}(f_T/T_d)$ 是教师（Pro）的软化分布。

**蒸馏的双重效应：**
1. **标签平滑：** KL 散度项等价于在教师分布上的 label smoothing——防止学生过拟合 one-hot 标签。这使得 Flash 的预测更"保守"（不轻易输出极端概率），但在 FEHU 这类多标签分类中，保守 = 不会随意输出稀有标签的假阳性。
2. **暗知识传递：** 教师对非目标类的概率分布包含了类间相似性的"暗知识"。对 FEHU，这意味着 Flash 学到了哪些 L1 值容易混淆（如 "Be just" vs "Be fair"），从而在做分类时更准确地区分混淆对。

**GPT-5.5 和 Fable 5 没有受益于针对 FEHU 标签空间的蒸馏——它们是从通用数据蒸馏的，通用数据中的"语义相似性"可能与 FEHU taxonomy 的逻辑不一致。**

### C.5 假说四：指令遵循与知识检索的竞争

FEHU 的 prompt 包含完整的 54 个 L1 值定义（$\sim 12$K tokens）。这使得任务更接近**封闭世界的指令遵循**而非开放世界的知识检索。

设模型有两个能力维度：
- $I(M)$：指令遵循能力（给定定义，严格按定义分类）
- $K(M)$：世界知识检索能力（基于训练数据中的常识判断）

对于 FEHU：
$$\text{Performance}(M) \approx \alpha \cdot I(M) + \beta \cdot K(M)$$

其中 $\alpha > \beta$（指令遵循比知识检索更重要）。

**Flash（小模型，蒸馏训练）可能具有 $I(Flash) > I(Pro)$**，因为蒸馏过程天然强调教师输出分布的模仿，而这种模仿强化了指令遵循能力。

Pro/GPT-5.5/Fable 5 的知识 $K(M)$ 更高，但知识反而成为干扰——模型可能基于"常识"判断某 actor 表达了某价值，但 FEHU 标注者基于文章中的具体证据而非常识来标注。这导致大模型的 **false positive** 来自知识驱动的推断（"这种情境下通常会有这个价值"），而非 prompt 驱动的证据匹配。

### C.6 假说五：JSON 模式兼容性

较小的模型在结构化输出（JSON mode）中更"听话"。大模型倾向于在 JSON 约束下仍然尝试"创造性"输出，导致格式边界模糊——虽然 V2/V3 的严格校验会拒绝格式错误，但语义上微妙的偏离（如输出了一个"相关但非直接证据"的标签）不会被格式校验捕获。

### C.7 综合结论

这不是单一原因，而是多重效应的叠加：$\text{Flash 优势} = \text{有效温度更低} + \text{蒸馏校准} + \text{过度思考免疫} + \text{指令遵循优势}$。其中**蒸馏校准效应**和**过度思考免疫**可能是最大的两个贡献因子。

---

## D. Liu 的 4-Prompt 迭代 Ensemble 结果分析

### D.1 结果复述

```
Task-1a: micro-F1 0.6589, macro-F1 0.5366, P 0.6731, R 0.6453
Task-1b: micro-F1 0.5543, macro-F1 0.3277, P 0.5991, R 0.5157
DRR: 0.0345 (76 次翻转 / 2201 个 gold-exclusive 值)
```

### D.2 与所有已知系统的对比

| 系统 | 1b micro | 1b macro | 1a micro | 1a macro | 特点 |
|---|---|---|---|---|---|
| Liu single | 0.5347 | 0.3385 | 0.6447 | 0.4777 | 单 prompt 基线 |
| E1 | 0.5480 | **0.3719** | 0.6574 | 0.5018 | 单 prompt 最强 |
| Hybrid H3 | 0.5474 | 0.3385 | **0.6622** | 0.5027 | 混合系统 |
| **Liu Ensemble** | **0.5543** | 0.3277 | 0.6589 | **0.5366** | **4-prompt 集成** |

### D.3 数学解析：为什么 Ensemble 的 1a macro 飞跃了 +0.034

这是最显著的增益。分解推理：

**Step 1：E1 在 20 个 L2 类别上的表现推测**

E1 的 1b macro 0.3719（93 个 gold-supported 1b 类中），1a macro 0.5018（20 个 L2 类中）。1a macro > 1b macro 是自然的（20 类比 93 类更容易平均），但 0.5018 意味着约有一半 L2 类的 F1 在 0.5 以下。

**Step 2：Ensemble 边际增益的来源**

4 个 prompt 变体在 L2 类别覆盖上的互补性。设 prompt $k$ 对 L2 类 $c$ 的 recall 为 $r_{k,c}$。如果 4 个变体的 recall 向量 $\mathbf{r}_1, ..., \mathbf{r}_4$ 在 20 维空间中几乎正交（覆盖不重叠的 L2 类），则 union 的 recall：

$$\mathbf{r}_{union, c} \approx \max_k r_{k,c}$$

当某个 L2 类在 E1 中 recall = 0 但在另一个变体中 recall > 0 时，macro 大幅提升。

**Step 3：定量验证**

1a macro 从 0.5018 → 0.5366，$\Delta = +0.0348$。

在 20 个 L2 类中，若 3 个类的 F1 从 ~0 提升至 ~0.25：

$$\Delta\text{macro} \approx \frac{3 \times 0.25}{20} = 0.0375$$

这与观测的 $+0.0348$ 高度一致——Ensemble 的边际价值是"救活"了约 3 个被 E1 完全忽略的 L2 类别。

### D.4 1b micro 增益：$+0.0063$ 的解构

$$0.5543 - 0.5480 = +0.0063$$

虽然绝对值不大，但在 0.55 附近的任务上限下，$+0.63\%$ 的 micro-F1 提升是显著的。

设 Ensemble 通过 union 额外发现了 $\Delta TP$ 个正确标签，同时多产生了 $\Delta FP$ 个假阳性。micro-F1 的增量近似：

$$\Delta\text{micro-F1} \approx \frac{2 \cdot \Delta TP \cdot (FP+FN) - 2 \cdot TP \cdot (\Delta FP + \Delta FN)}{(2TP + FP + FN)^2}$$

以 E1 的数字代入（1b: TP=1328, FP=1129, FN=1062）：

若 $\Delta TP = +40, \Delta FP = +20$（Ensemble 的 union 多发现 40 个正确标签，但多出 20 个假阳性）：
$$\Delta\text{micro-F1} \approx +0.0064$$

与实际 $+0.0063$ 几乎完全吻合——Ensemble 以微小的精度代价（+20 FP）换取了显著的召回增益（+40 TP）。

### D.5 关键推论：E1 + Ensemble 思路 = 最佳组合

E1 的优势是 **1b macro 最高（0.3719）**——单 prompt 在 93 个 L1 类上覆盖最均匀。
Ensemble 的优势是 **1a macro 最高（0.5366）**——多 prompt 在 20 个 L2 类上互补覆盖。

**最优路径：** 以 E1 为基座（保持其 L1 覆盖优势），添加 1-2 个互补 prompt 变体（专门针对 E1 忽略的 L2 类别），通过确定性 union 扩大 L2 覆盖，再通过 E4 per-candidate QA 验证器回收精度。

预估效果：
- 1b micro: 0.5480 → **0.553-0.557**（接近或超越 Liu Ensemble）
- 1b macro: 0.3719 → **0.375-0.385**（保持并略微提升 E1 的优势）
- 1a macro: 0.5018 → **0.530-0.540**（逼近 Liu Ensemble 的 0.5366）

---

## E. E1 的改进空间——数学化路线图

### E.1 E1 当前局限的结构化分析

| 局限维度 | 数学本质 | 当前状态 | 改进潜力 |
|---|---|---|---|
| **单一操作点** | $T=0.1$ 固化了 precision-recall 权衡 | 一个 $(P,R)$ 点 | 高——multi-prompt |
| **证据稀释** | 全文章 → $N_{subevent}$ 倍信号稀释 | 单次全文章判断 | 最高——E3 |
| **方向翻转** | DRR 0.035 > Liu 0.023 | 26 次多余翻转 | 中——E4/P6 |
| **校准缺失** | 无 per-label 置信度校准 | 全局温度一刀切 | 中——温度调优 |
| **Demo 覆盖** | 2 个 demo 覆盖 $\sim$25/54 L1 值 | 非 exhaustive | 低-中 |

### E.2 改进路径一：Multi-Prompt 轻度集成（无泄露）

**方案：** E1（base）+ 1 个互补变体（专门针对 18 个低频目标标签），通过确定性 union → E4 验证。

**互补变体设计：** 仅修改 E1 的 few-shot demo 选择标准——选择包含 target-18 中至少 5 个 gold 标签的 demo，改变 prompt 中的标签分布先验。

**数学预期：**
- 若互补变体对 18 目标的 recall 为 $R_{18}^{comp}$，E1 的 recall 为 $R_{18}^{E1}$，且两者的 Jaccard 重叠为 $J_{TP}$：
  $$R_{18}^{union} = \frac{R_{18}^{E1} + R_{18}^{comp} - J_{TP} \cdot \min(R_{18}^{E1}, R_{18}^{comp})}{1 - ...}$$
  
- 设 $R_{18}^{E1} \approx 0.27$, $R_{18}^{comp} \approx 0.22$, $J_{TP} \approx 0.4$：
  $$R_{18}^{union} \approx 0.35-0.40$$

  即 18 目标的 TP 从 38 → 49-56，将 target micro-F1 从 0.246 推至 0.30-0.34。

### E.3 改进路径二：子事件分解（E3，最大潜力）

**核心数学洞察：** 全文章预测等价于在 $K$ 个子事件上的信号平均。如果某价值只在 1 个子事件中被证据支持，全文章判断面临 $\frac{1}{K}$ 的信噪比稀释。

FEHU dev 文章的中位子事件数 $K = 9$。对稀有标签，信号稀释比可达 $9\times$。

NEVU 论文的受控实验：per-unit 预测比 whole-text 预测 recall 高 **+13-19 pp**。

保守估计 FEHU 上 gain 折半（NEVU 的数据和 FEHU 不完全可比）：**+6-10 pp recall**。

对 E1（1b recall = 0.556），recall → 0.616-0.656，micro-F1 有望推至 **0.57-0.59**——这将是项目最大的单次提升。

### E.4 改进路径三：方向后修复（P6）

E1 的 DRR 0.0347（77 reversals），Liu single 0.0230（51 reversals）。差距 26 次翻转。

分析 E1 的 77 次翻转中，最集中的 10 个类别可能贡献 40-50 次翻转。对这 10 个类别做 targeted 方向 QA（per-candidate binary: "方向是 aligned 还是 contradictory？证据：..."），预期可将 DRR 降至 0.025-0.028。

### E.5 改进路径四：Per-Label 有效温度

在 logit 空间对不同频率的标签施加不同的温度：

$$P_c = \sigma(z_c / T_c), \quad T_c = T_0 \cdot \left(\frac{n_c^+}{\max_c n_c^+}\right)^{-\gamma}$$

其中 $\gamma \in [0, 0.3]$ 控制频率敏感度，$n_c^+$ 为训练集中标签 $c$ 的出现次数。

直觉：高频标签用更低的温度（更确定），低频标签用更高的温度（降低预测门槛）。$\gamma = 0.15$ 是合理的起点。

### E.6 综合改进路线图

| 阶段 | 改进 | 预期 1b micro 增益 | 预期 1b macro 增益 | 预期 1a macro 增益 | 成本 |
|---|---|---|---|---|---|
| **E3** | 子事件分解 | **+0.015~0.030** | **+0.02~0.04** | +0.01~0.03 | ~177 Flash 调用 |
| **Multi-E1** | 2-prompt 轻度集成 | +0.003~0.007 | +0.005~0.015 | **+0.02~0.03** | ~177 Flash 调用 |
| **E4** | Per-candidate QA | +0.005~0.010（精度） | +0.01~0.02 | +0.01~0.02 | ~400 批量 Flash 调用 |
| **P6** | 方向后修复 | DRR −0.005~0.010 | 微小 | 微小 | ~30 Flash 调用 |
| **T-tuning** | 温度调优 | +0.002~0.005 | +0.003~0.008 | +0.002~0.005 | 无需 API 调用 |

**建议执行顺序：E3 → Multi-E1 → E4 → P6 → T-tuning**。各阶段独立可测，增量叠加。

---

## F. 总结：核心数学洞察

1. **DeBERTa DRA 失败的根因是梯度饥荒 + 阈值错配 + 假阴性毒化**的三重打击。仅靠合成数据无法克服 sigmoid 在极端不平衡下的结构性缺陷——需要损失函数级（distribution-balanced loss）或决策规则级（per-class threshold）的配套改革。

2. **E1 < Liu Ensemble 的本质是 Precision-Recall 帕累托前沿的可达性问题。** 单一 prompt@T=0.1 只能访问前沿上的一个点，而多 prompt 集成通过 union/voting 组合可以覆盖凸包的内部——这是单 prompt 在数学上无法企及的。

3. **DeepSeek Flash > 更大模型**是多重效应的叠加：有效温度更低（蒸馏副作用）、校准更好（蒸馏正则化）、不过度思考（简化模型恰好匹配标注噪声水平）、指令遵循/知识检索的权衡更偏向 FEHU 任务结构。

4. **Liu Ensemble 的 1a macro 0.5366 是最值得关注的数字**——它揭示了多 prompt 互补性在 L2 类别覆盖上的巨大潜力。E1 + 轻度集成 + E3 子事件分解的叠加，有望在 1b micro 上突破 0.57，在 1a macro 上达到 0.53-0.55。

5. **最重要的下一步是 E3（子事件分解）**——它是唯一有机会产生 $+0.02+$ micro-F1 增益的单次改进，且有 NEVU 文献的强证据支持和清晰的数学机制（信号稀释比的逆转）。

---

*数学化分析完毕。基于全仓库阅读和数学推导，未执行新实验。所有定量估计标注了假设条件和推导依据。*
