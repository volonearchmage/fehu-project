# FEHU Task-1 深度优化方案：数学化分析与路线图

**日期：** 2026-07-24  
**前提约束：** E3/E3a（子事件分解）不可用于 Task-1 test 提交——`test_article_event_base.json` 不含 `subevents` 字段，仅含 `guid/title/content/actors`。所有方案必须在**仅文章级数据**的条件下运行。  
**方法论：** 从概率论、信息论、统计决策理论、最优传输理论和贝叶斯推断出发，推导新的优化方向。

---

## 零、问题空间的形式化定义

### 0.1 核心数学问题

给定文章 $x$（含 $K$ 个 actor），对每个 actor $a$，从 108 维标签空间 $\mathcal{L} = \{0,1\}^{54 \times 2}$ 中预测子集 $S_a \subseteq \mathcal{L}$。目标：

$$\max \Phi(S_a, G_a) = \max \left\{\text{micro-F1}(S, G), \text{macro-F1}(S, G), -\text{DRR}(S, G)\right\}$$

当前 Pareto 前沿：
- E1（prompt 单系统）：micro 0.5480 / macro 0.3719 / DRR 0.035
- Liu Ensemble（4-prompt 迭代）：micro 0.5543 / macro 0.3277 / DRR 0.0345 / 1a macro **0.5366**
- Hybrid H3（DeBERTa + LLM）：micro 0.5474 / macro 0.3385 / DRR 0.031

### 0.2 观测到的关键 gap 分解

| Gap 来源 | 量级 | 数学本质 |
|---|---|---|
| E1 → Liu Ensemble (1b micro) | +0.0063 | 单 prompt 操作点 vs 凸包内部点 |
| E1 → Liu Ensemble (1a macro) | +0.0348 | L2 类别覆盖的互补性 |
| E1 → Oracle (1b macro) | 未知 | 稀有类的系统性遗漏 |
| E1 DRR → Liu DRR | +0.012 | 方向判断的校准差异 |

### 0.3 不可用方案清单

| 方案 | 不可用原因 |
|---|---|
| E3/E3a 子事件分解 | Test 集无 `subevents` 字段 |
| 任何依赖 `test_subevent_event_base.json` 的方案 | 那是 Task-2 输入，不能用于 Task-1 提交 |
| Dev 泄露的 add-list 或阈值调优 | 破坏 test 泛化性 |
| 需要人工标注的 active learning | 无标注预算 |

---

## 一、方向 I：概率校准与决策理论 —— 从点估计到分布估计

### 1.1 核心洞察

E1 的核心局限不是在"理解"层面，而是在**决策规则**层面。LLM 在温度 $T=0.1$ 下的 greedy decode 等价于：

$$\hat{S} = \{c : \log P_{LLM}(c|x) > \tau_{implicit}\}$$

其中 $\tau_{implicit}$ 是 LLM 内部的隐式阈值——由 prompt 中的"证据标准"描述、few-shot demo 的标签密度、和温度 $T$ 共同决定。**这个阈值不可控、不可调、对每个类相同。**

### 1.2 方案 I-A：温度退火多通道集成（TAME）

**数学原理：** 信息瓶颈理论。温度 $T$ 控制压缩与预测的权衡：
- 低 $T$：高压缩 → 仅输出高置信度标签（接近 argmax）
- 高 $T$：低压缩 → 输出更多标签，但噪声增加

**方案：** 用同一 E1 prompt，对每篇文章运行 3 次，仅改变温度：

| Pass | 温度 | 预期行为 |
|---|---|---|
| $P_1$ | $T=0.05$ | 极高精度（~precision 0.62），低召回（~recall 0.48） |
| $P_2$ | $T=0.10$ | 当前 E1 水平（precision 0.54, recall 0.56） |
| $P_3$ | $T=0.30$ | 高召回（~recall 0.64），低精度（~precision 0.46） |

**集成规则：**
$$S_{final} = \{c : \text{votes}(c) \geq 2\} \cup \{c : \text{votes}(c) = 1 \land c \in \text{Verify}(c)\}$$

其中 $\text{Verify}(c)$ 是对仅在 1/3 温度下出现的标签做快速 binary QA。

**数学预期：**
$$R_{TAME} \approx \max(R_1, R_2, R_3) \approx 0.64$$
$$P_{TAME} \approx \text{majority-filtered } P \approx 0.52-0.55$$
$$F1_{TAME} \approx 0.555-0.565 \quad (\text{超越 Liu Ensemble 的 0.5543})$$

**成本：** ~531 Flash 调用（3×177），无额外模型训练。
**风险：** $T=0.3$ 可能产生过多候选，验证器负载大；2/3 majority 可能过滤掉正确的单次预测。

### 1.3 方案 I-B：一致性子采样集成（CSS-E）

**数学原理：** 自助法（bootstrap）的决策理论变体。如果 E1 的预测有随机性（即使 $T=0.1$，不同 few-shot demo 顺序也有微小波动），则可以通过扰动输入来生成多样性。

**方案：** 用 E1 prompt，但每次改变 few-shot demo 的选择（从训练集中随机采样 2 个符合条件的 demo 文章），运行 $K=5$ 次：

$$S_k = \text{E1}(x; \text{demos}_k), \quad k=1,...,5$$

集成：
$$S_{final} = \left\{c : \sum_{k=1}^5 \mathbb{1}[c \in S_k] \geq 3\right\}$$

**为什么这比单次更好：** E1 的 few-shot demo 是固定的（`0-4349-1-t` 和 `0-4352-3-1`），这给 prompt 注入了一个特定的标签分布先验。不同的 demo 对给不同的先验，覆盖更广的标签模式。

**成本：** ~885 Flash 调用（5×177）。
**数学预期：** micro-F1 +0.003-0.008，1a macro +0.01-0.02（不同 demo 覆盖不同 L2 组）。

### 1.4 方案 I-C：保形预测（Conformal Prediction）校准阈值

**数学原理：** 保形预测提供有限样本下的错误率保证。对每个标签 $c$，在**训练集内部划分的校准集** $\mathcal{D}_{cal}$ 上计算不一致性分数：

$$s_i^{(c)} = 1 - P_{model}(y_c = 1 | x_i)$$

对置信水平 $1-\varepsilon$，阈值 $\tau_c$ 为 $\mathcal{D}_{cal}$ 上 $s^{(c)}$ 的 $(1-\varepsilon)$ 分位数：

$$\tau_c = Q_{1-\varepsilon}(\{s_i^{(c)}\}_{i \in \mathcal{D}_{cal}})$$

在 test 时：
$$\hat{y}_c = \mathbb{1}[P_{model}(y_c=1|x) > 1-\tau_c]$$

**关键优势：** 每个标签有独立的理论保证的阈值。高频类 $\tau_c \approx 0.5-0.7$（高阈值，保守），低频类 $\tau_c \approx 0.2-0.4$（低阈值，激进）。

**适用于：** DeBERTa 概率输出的后处理（不适用于 LLM 的离散输出）。
**实现：** 从训练集中切出 15% 的 actor 实例作为 $\mathcal{D}_{cal}$（约 500 个），不参与训练。

---

## 二、方向 II：最优传输与标签分布匹配 —— 从边际分布角度破解长尾

### 2.1 核心洞察

E1 和 DeBERTa 都存在**标签边际分布的系统性偏移**：预测分布 $P_{pred}(c)$ 比训练分布 $P_{train}(c)$ 更集中于头部类。这暗示我们可以通过**强制边际分布匹配**来提升低频类的召回。

### 2.2 方案 II-A：最优传输 Logit 调整（OT-LA）

**数学原理：** 最优传输理论。设预测的经验标签分布为 $\hat{P}_{pred}$，训练标签分布为 $\hat{P}_{train}$。寻找最小代价传输计划 $\pi$ 将 $\hat{P}_{pred}$ 映射到 $\hat{P}_{train}$：

$$\pi^* = \arg\min_{\pi} \sum_{i,j} \pi_{ij} \cdot d(i,j)$$

其中 $d(i,j)$ 是类 $i$ 和类 $j$ 之间的语义距离（可用 L1→L2 taxonomy 的树距离）。

**简化实现（对角近似）：** 如果假设类间传输代价很高（不同类不能互相替代），则最优传输退化为 per-class 的缩放：

$$z_c^{adjusted} = z_c + \lambda \cdot \log\frac{\hat{P}_{train}(c)}{\hat{P}_{pred}(c)}$$

其中 $\lambda \in [0.5, 1.5]$ 是缩放强度。

对低频类 $c$：$\hat{P}_{pred}(c) \ll \hat{P}_{train}(c)$ → $\log$ 项为**正** → logit 被**提升**。
对高频类 $c$：$\hat{P}_{pred}(c) > \hat{P}_{train}(c)$ → $\log$ 项为**负** → logit 被**压低**。

**适用于：** DeBERTa 概率输出的后处理。$\hat{P}_{pred}$ 在 dev 集上估计。
**数学预期：** target-18 recall +0.05-0.15，1b macro +0.02-0.04。
**风险：** 如果预测偏差不是单调的（有些低频类已经被过度预测），logit 调整会适得其反。需要先在 dev 上验证方向。

### 2.3 方案 II-B：事后标签频率对齐（Post-hoc FreqAlign）

这是 OT-LA 的一个更简单的特例，仅对 DeBERTa 的输出概率做 per-class 的幂次缩放：

$$\hat{y}_c^{calibrated} = \sigma\left(\frac{z_c}{T_c}\right)$$

其中 per-class 温度：
$$T_c = T_0 \cdot \left(\frac{n_c^{train}}{\max_j n_j^{train}}\right)^{-\gamma}$$

$n_c^{train}$ 为训练集中类 $c$ 的正样本数，$\gamma \in [0.1, 0.3]$ 控制调整强度。

**直觉：** 低频类用更高的有效温度（更大的 $T_c$ → 更低的决策阈值），高频类用更低的温度。

**完全无需训练，仅需 $\sim 10$ 行代码。**

---

## 三、方向 III：贝叶斯先验校准 —— 用 actor 类型信息引导预测

### 3.1 核心洞察

FEHU 数据中，不同 actor 类型的价值分布截然不同。例如：
- 警察/执法机构 → 高频："Be just (45)", "Be responsible (37)", "Behave properly (32)"
- 犯罪者 → 高频："Be just (45)" 的 contradictory 方向
- 政府机构 → 高频："Have a safe country (31)", "Be responsible (37)"

但 E1 和 DeBERTa 都未显式利用 actor 的**类型先验**。

### 3.2 方案 III-A：Actor-Type 条件化贝叶斯先验

**数学原理：** 贝叶斯定理。给定 actor 类型 $t$ 和文章内容 $x$：

$$P(y_c=1 | x, t) = \frac{P(x | y_c=1) \cdot P(y_c=1 | t)}{P(x | t)}$$
$$\propto P(y_c=1 | x) \cdot \frac{P(y_c=1 | t)}{P(y_c=1)}$$

其中：
- $P(y_c=1 | x)$：E1 或 DeBERTa 的当前预测
- $P(y_c=1 | t)$：训练集中 actor 类型 $t$ 下标签 $c$ 的经验频率
- $P(y_c=1)$：训练集中标签 $c$ 的全局经验频率

**实现：**
1. 从训练集的 actor 名称中自动聚类 actor 类型（或用 LLM 做类型标注）
2. 估计 $P(y_c=1 | t)$ 和 $P(y_c=1)$
3. 对 E1 的 logit 做贝叶斯调整：
$$\text{logit}_c^{adjusted} = \text{logit}_c^{E1} + \alpha \cdot \log\frac{P(y_c=1 | t) + \epsilon}{P(y_c=1) + \epsilon}$$

其中 $\alpha \in [0.3, 0.7]$ 控制先验强度，$\epsilon = 0.01$ 做拉普拉斯平滑。

**数学预期：**
- 对高频于该 actor 类型的标签 → logit 提升 → 更多 TP
- 对低频于该 actor 类型的标签 → logit 压低 → 更少 FP
- 预期 1b micro +0.003-0.008, 1b macro +0.01-0.03

**关键优势：** 完全是后处理，零 API 调用增量，不改变 E1 prompt。

### 3.3 方案 III-B：Actor-Type 导向的 Few-Shot Demo 选择

在 E1 的 few-shot demo 选择中，优先选择与当前 test 文章 actor 类型分布相似的训练文章：

$$\text{sim}(x_{test}, x_{train}) = \text{cosine}(\mathbf{t}_{test}, \mathbf{t}_{train})$$

其中 $\mathbf{t}$ 是 actor 类型的分布向量（如 {police: 0.3, government: 0.3, civilian: 0.4}）。

**成本：** 零额外 API 调用（仅改变 demo 选择逻辑）。

---

## 四、方向 IV：证据锚定 —— 用句子级信号替代子事件级信号

### 4.1 核心洞察

E3 的核心威力来自**细粒度文本单元的预测后聚合**——在 $K$ 个子事件上的预测 union 比全文章单次预测有更高的召回。虽然 test 集没有子事件标注，但我们可以用**句子**作为替代的基本预测单元——句子分割是语言的基本属性，不需要任何标注。

### 4.2 方案 IV-A：句子级证据聚合（Sentence-Level Evidence Aggregation, SLEA）

**数学原理：** 多实例学习的统计聚合。将文章 $x$ 分割为 $M$ 个句子 $\{s_1, ..., s_M\}$（$M$ 通常为 15-40）。对每个句子 $s_i$，模型判断：该句子是否为 actor $a$ 关于价值 $c$ 的证据？

**方案设计：**
1. **不改变 E1 的 prompt 结构**，但改变输入格式：
   - 传统：`文章全文 + actor 列表 → 所有 actor 的所有标签`
   - SLEA：`文章全文 + actor 列表 → 每个 actor 的每个标签需附对应的证据句编号`

2. **或者更简单**：用 E1 对整篇文章做预测（保持现有流程），然后用一个轻量级的**证据验证器**对每个预测标签做句子级证据检查：
   - 对每个预测标签 $(a, c)$，在所有句子中搜索支持证据
   - 如果无任何句子包含该标签的证据 → 可能为假阳性，标记低置信度

**实现选项 B（更低成本）：** 反其道而行——用句子级分类替代文章级分类。无需 E1 的 177 次调用：
1. 将每篇文章的每个 actor 的相关句子提取出来（通过关键词匹配或 actor 名出现位置）
2. 对每个 actor 的每个句子，用轻量 prompt 判断该句表达了哪些价值
3. 在 actor 级做 union 聚合

**成本分析：** 若每篇文章平均 25 句，每 5 句合并为一次调用（batch），每篇文章 5 次调用 → 总计 ~885 Flash 调用。

**数学预期：** 信号稀释比从 $1/K_{subevent}$ 逆转为 $\text{union}(M \text{ sentences})$——recall 有望 +0.05-0.10。

### 4.3 方案 IV-B：两阶段摘要-分类（Summarize-then-Classify）

**方案：**
1. 先用 LLM 将文章浓缩为 actor 相关的关键行为摘要（不是生成子事件，而是提取 actor 的行为描述）
2. 再用 E1 prompt 对摘要做分类

**为什么可能更好：** 摘要步骤强制 LLM 提取与 actor 行为最相关的信息，去除了文章中与价值判断无关的背景内容。这等价于提高了分类器的信噪比。

**成本：** +177 次摘要调用（~354 Flash 调用总计）。

---

## 五、方向 V：混淆矩阵分解与系统性纠偏

### 5.1 核心洞察

108 个类别之间的混淆不是随机的——存在系统性的混淆模式（如 "Be just" aligned 与 "Be fair" aligned 经常混淆）。如果我们能识别并纠正这些系统性混淆，可以在不牺牲召回的情况下提升精度。

### 5.2 方案 V-A：混淆矩阵的谱分解纠偏（Spectral Debiasing）

**数学原理：** 奇异值分解（SVD）。在 dev 集上构建 E1 的混淆矩阵 $C \in \mathbb{R}^{108 \times 108}$：

$$C_{i,j} = P(\text{predict } j | \text{gold } i)$$

对 $C$ 做 SVD：$C = U\Sigma V^T$。

前 $r$ 个奇异向量捕捉了最主要的混淆方向（如"所有 Security 类之间容易混淆"）。对每个预测，减去在混淆方向上的投影：

$$\mathbf{z}^{debiased} = \mathbf{z} - \eta \cdot U_r U_r^T \mathbf{z}$$

其中 $U_r$ 是前 $r$ 个左奇异向量，$\eta$ 是纠偏强度。

**直觉：** 如果"Be just"和"Be fair"总是被一起预测（混淆方向），而实际只有一个是 gold，则减去该方向上的投影会降低其中一个的概率。

### 5.3 方案 V-B：标签共现图正则化（Label Co-occurrence Graph）

**数学原理：** 图正则化。从训练集中构建标签共现图 $\mathcal{G} = (\mathcal{V}, \mathcal{E})$，其中边权重 $w_{ij} = P(y_j=1 | y_i=1)$。

**方案：** 对 E1 的预测做图扩散：
1. 初始预测向量 $\mathbf{p}^{(0)} = \text{E1 的 one-hot 预测}$
2. 图扩散：$\mathbf{p}^{(t+1)} = (1-\alpha)\mathbf{p}^{(0)} + \alpha \cdot D^{-1/2}WD^{-1/2} \mathbf{p}^{(t)}$
3. 最终：$\hat{y}_c = \mathbb{1}[p_c^{(T)} > 0.5]$

**直觉：** 如果一个标签经常与另一个标签共现（高 $w_{ij}$），且另一个标签被预测了，则通过图扩散提升该标签的概率——弥补 E1 的单次遗漏。

**成本：** 零 API 调用，纯后处理矩阵乘法。

---

## 六、方向 VI：反事实数据增强 —— 在真实分布上做增强

### 6.1 核心洞察

DRA 失败的根本原因是 $P_{synth} \neq P_{real}$。但增强不一定需要生成新文章——我们可以对**真实文章**做结构保持的变换，在不改变语义的前提下增强训练数据的多样性。

### 6.2 方案 VI-A：Actor 遮蔽增强（Actor Masking Augmentation）

**方案：** 在 DeBERTa 训练时，以概率 $p=0.3$ 随机遮蔽一个 actor 的名字（替换为 `[MASK]`）。模型被迫学习不依赖 actor 名本身的特征，而是从文章内容中推断该 actor 的价值。

**数学原理：** 这等价于在 actor 维度上做 dropout 正则化，防止模型过拟合特定的 actor-价值映射。

### 6.3 方案 VI-B：负样本重标定（Negative Relabeling）

**方案：** 对 DeBERTa 训练，当一条训练样本的**某个标签未被标注为 positive**时，不默认它是 negative。而是：
- 对每个 actor，用 E1 对其做预测
- 如果 E1 预测了标签 $c$ 但训练 gold 中没有 → 该标签从 "assume negative" 变为 "soft negative"（降低负样本权重）
- 如果 E1 和 gold 都预测了标签 $c$ → positive
- 如果 E1 和 gold 都未预测标签 $c$ → negative

这利用了 E1 作为弱监督信号来软化 BCE 的硬负标签假设。

---

## 七、方向 VII：方向特异化 —— 独立解决 DRR 问题

### 7.1 核心洞察

DRR（方向翻转率）是最容易被独立优化的指标。E1 的 DRR 0.035 = 77 次翻转 / 2201 个 gold-exclusive 值。如果能把 DRR 降到 Liu 单系统的 0.023，micro-F1 约 +0.003-0.005。

### 7.2 方案 VII-A：高风险类定向方向 QA（Targeted Direction QA）

**方案：**
1. 从 dev 集上统计 E1 的每个类别的翻转率，选出翻转率最高的 8-10 个类别
2. 在 test 时，对 E1 预测的这 8-10 个类别的实例，额外调用一次方向 QA（binary：aligned or contradictory?）
3. 其他类别保持 E1 的方向判断

**成本：** 每篇文章额外 0-3 次方向 QA 调用（取决于该文章是否触发了高风险类）→ 总计 ~80-150 Flash 调用。

**数学预期：** DRR 0.035 → 0.025-0.028，77 次翻转 → 55-62 次翻转。

### 7.3 方案 VII-B：方向置信度加权

**方案：** E1 输出时增加 `direction_confidence` 字段（让 LLM 自评）。如果 confidence 低，标记为需验证。对低置信度的方向，用独立的更详细的方向 prompt 重新判断。

---

## 八、方向 VIII：DeBERTa 的拯救 —— 从概率空间到决策规则

### 8.1 核心洞察

Phase 1 已证明：基线 DeBERTa 的基线目标 AUC 仅为 0.536（≈ 随机），但 v2 的目标 AUC 为 0.697——增强确实改善了**概率排序**，但全局阈值 0.3 阻止了这些改进转化为预测。

### 8.2 方案 VIII-A：Per-Class 阈值 + 内部校准集

**方案：** 在训练集中切出 15% 的 actor 实例作为内部校准集 $\mathcal{D}_{cal}$。对每个标签 $c$，在 $\mathcal{D}_{cal}$ 上做阈值扫描，选择最大化 per-class F1 的阈值 $\tau_c^*$。

应用现有的 F′ 或 N3 checkpoint（无需重新训练），仅改变推理时的阈值。

**数学预期：** v2 的 1b macro 0.088（F′ 均值）→ 0.12-0.15；18 目标类 TP 从 12.3 → 25-40。

**与方案 I-C（保形预测）的关系：** I-C 提供理论保证，VIII-A 提供经验最优。可两者结合：以保形预测阈值为下限，经验最优阈值为目标。

### 8.3 方案 VIII-B：混合推理 —— DeBERTa 候选 + E1 基座 + 一致性

**方案：** 同时运行 E1 和 DeBERTa（per-class 阈值版），对每个标签：
1. **Both agree（positive）：** 高置信度保留
2. **Both agree（negative）：** 丢弃
3. **E1 positive, DeBERTa negative：** 标记为 E1-only，保留（E1 比 DeBERTa 更可靠）
4. **DeBERTa positive, E1 negative：** DeBERTa 可能发现了 E1 遗漏的标签 → 进行快速 QA 验证

**成本：** E1 ~177 Flash 调用 + DeBERTa 零成本推理 + ~100-300 QA 验证调用。

---

## 九、综合方案排序：Pareto 最优组合

### 9.1 成本-收益矩阵

| 方案 | 预期 1b micro 增益 | 预期 1a macro 增益 | API 调用增量 | 实现复杂度 | 数学风险 |
|---|---|---|---|---|---|
| **I-A 温度退火** | +0.007-0.017 | +0.01-0.02 | +354 | 低 | 中（$T=0.3$ 噪声） |
| **I-B Demo 集成** | +0.003-0.008 | +0.01-0.02 | +708 | 低 | 低 |
| **II-A OT Logit调整** | +0.002-0.005 | +0.02-0.04 | 0 | 低 | 中（方向不确定） |
| **III-A 贝叶斯先验** | +0.003-0.008 | +0.01-0.03 | 0 | 中 | 低 |
| **IV-A 句子级聚合** | +0.005-0.015 | +0.02-0.05 | +708 | 高 | 中（FP 累积） |
| **V-B 标签共现图** | +0.002-0.005 | +0.005-0.015 | 0 | 低 | 低 |
| **VI-B 负样本重标定** | —（重训练） | +0.01-0.03 | 0 | 中 | 中 |
| **VII-A 方向QA** | +0.003-0.005 | 0 | +150 | 低 | 低 |
| **VIII-A Per-class阈值** | +0.002-0.005 | +0.03-0.06 | 0 | 低 | 低 |
| **VIII-B 混合推理** | +0.005-0.012 | +0.02-0.04 | +300 | 中 | 低 |

### 9.2 建议执行路径

**路径 A（低成本先行，当天完成）：**
1. **VIII-A Per-Class 阈值**（零 API 成本）→ 立即提升 student 的 macro
2. **III-A 贝叶斯先验**（零 API 成本）→ 轻量后处理
3. **V-B 标签共现图**（零 API 成本）→ 轻量后处理
4. 三者叠加 → 预期 micro +0.005-0.012, macro +0.03-0.06

**路径 B（中等成本，2-3 天）：**
5. **I-A 温度退火**（+354 调用）→ 单模型多温度集成
6. **VII-A 方向 QA**（+150 调用）→ DRR 修复
7. 叠加路径 A + B → 预期 micro 0.555-0.565, 1a macro 0.52-0.54

**路径 C（探索性，1-2 周）：**
8. **IV-A 句子级聚合**（+708 调用）→ 替代子事件分解的细粒度方法
9. **VI-B 负样本重标定**（重训练 DeBERTa）→ 修复 BCE 假阴性问题
10. **VIII-B 混合推理** → 最强 ensemble 方案

### 9.3 理论最优上界估计

假设所有方案完全正交（增益可加），理论上界：
- 1b micro-F1：$0.5480 + 0.017 + 0.008 + 0.005 + 0.008 + 0.005 + 0.005 + 0.005 + 0.012 \approx 0.613$

实际上方案间存在重叠效应，保守估计可达 $0.565-0.575$——显著超越 Liu Ensemble 的 $0.5543$。

---

## 十、结论

在 E3/E3a 不可用的约束下，我们识别了 **8 个方向、14 个具体方案**，全部可在仅文章级数据的条件下实现。核心数学洞察是：

1. **决策规则优于模型能力：** E1 的概率空间可能已经包含正确的低频标签预测，但隐式阈值将它们过滤掉了。温度退火、per-class 阈值和贝叶斯先验都是在**不改变模型理解**的前提下优化决策规则。
2. **信息存在于不同粒度：** 即使没有子事件标注，句子级聚合可以近似子事件分解的效果——信号的细粒度聚合是普遍原理。
3. **先验信息是免费的午餐：** Actor 类型的标签分布先验存在于训练数据中，但从未被利用。贝叶斯融合仅需查表和加法。
4. **零成本改进空间巨大：** Per-class 阈值、OT logit 调整、贝叶斯先验、标签共现图正则化——四个方案的 API 调用增量均为零。

**推荐立即执行：** 路径 A 的四个零成本方案 + 路径 B 的温度退火（最高单次增益），预期将 1b micro 推至 $0.555-0.565$，1a macro 推至 $0.52-0.54$，同时仅增加约 500 次 Flash 调用。

---

*本分析基于全仓库阅读和严格数学推导，所有方案均可验证、可复现、可叠加。未执行任何新实验。*
