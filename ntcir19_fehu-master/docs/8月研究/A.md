# 方案 A：证据定位与混淆感知的对比数据增强

**暂定英文名：** Evidence-Grounded, Confusion-Aware Contrastive Augmentation for Long-Tailed Actor-Conditioned Human-Value Recognition  
**研究对象：** FEHU Task 1，重点关注 Task-1b 的低频 `direction:L1` 标签  
**状态：** 研究方案，尚未执行新增生成或训练  
**目标时间：** 2026 年 10 月初形成可投稿的完整实验结果

## 1. 核心判断

中期发表不应以项目的版本迭代顺序为叙事主线，也不应单独以 gate 或投票作为主要贡献。建议将独立研究问题集中在数据增强上，但把“使用 LLM 生成更多低频文本”进一步收紧为：

> 如何从真实新闻中的 actor-specific 价值证据出发，生成接近原始数据分布、能够拉开目标标签与混淆标签边界的对比训练样本？

这里的关键变化不是继续增加自由生成样本的数量，而是改变增强的单位、种子选择方法和生成目标：

- 从“整篇文章”转向“目标 actor 的稀有标签证据”；
- 从“只生成目标类正例”转向“目标类、反方向和近邻标签的对比组”；
- 从“按标签平均分配固定数量”转向“按训练频率、模型困难度和证据覆盖自适应分配”；
- 从“生成后只做格式检查”转向“actor 归属、标签边界、方向和分布一致性的独立验证”。

Gate 和投票仍有价值，但它们在该研究中的位置应当是下游应用或辅助消融：gate 用于保护 macro-F1，投票/LLM verifier 用于消化高召回候选，而不是替代数据增强本身的因果验证。

## 2. 现有证据与真正的瓶颈

### 2.1 已经证明：合成数据包含可学习信号

现有多种子受控实验说明，数据增强并非完全无效：

- 仅使用官方训练数据时，18 个目标类别的平均 AUC 约为 `0.513`，接近随机水平；
- 加入 900 条 Round-2 合成记录后，assume-negative 条件的平均目标 AUC 提高到 `0.624`，相对基线增加 `0.111`，三个种子的方向一致；
- masked 条件也提高到 `0.577`，相对基线增加 `0.064`，同样三个种子方向一致；
- 但固定阈值下的目标真阳性仍然很少，且总体 DRR 从基线约 `0.158` 恶化到 `0.22–0.28`。

证据来源：

- `new_check/phase2/reports/PHASE2_CONTROLLED_ABLATION_REPORT.md`
- `new_check/phase3/reports/PHASE3_FULL_DATA_AND_NEGATIVE_SAMPLING_REPORT.md`

因此，可以较有把握地说：现有合成数据改变了目标类别的分数排序，但尚未形成稳定、可用的低频分类器。

### 2.2 负采样主要改变校准，没有改善类别可分性

Phase 3 中的 1:3 目标类负采样将 target-18 recall 提高到约 `0.593`，覆盖 15–17 个目标类别，但 target precision 只有约 `0.028`，平均目标 AUC 反而由 `0.632` 降至 `0.608`。1:1 负采样进一步把 AUC 降到接近随机的 `0.507`。

这说明现阶段的主要瓶颈不是“模型不愿意输出低频标签”，而是目标标签与非目标/相邻标签之间没有形成足够可靠的排序边界。继续降低阈值或减少负样本只能提高概率，不能解决这一问题。

### 2.3 现有自由生成数据存在明显分布和监督问题

现有 340 + 900 合成数据存在以下限制：

- Round 2 的 900 条记录只通过结构验证，没有经过完整的语义筛选或人工审核；
- 合成文本通常比真实新闻短，actor 数量更少，标签密度更低；
- 单标签合成记录若采用 assume-negative，会把大量未标注但可能成立的标签错误地当作负例；
- masked supervision 可以避免假阴性，但每条 target-only 记录提供的训练梯度又过少；
- 当前 DeBERTa 使用 108 路独立输出、全局 `0.3` 阈值和最多 512 token 输入，且按 dev micro-F1 早停，均不利于低频标签研究。

所以，下一轮研究不应简单重复“再生成 900 条”，而应在等数据预算下改变数据的形态和边界信息。

## 3. 一个重要的训练数据机会：subevent 证据定位

对本地官方 TRAIN 文件进行只读统计：

- 文章级共有 `16,905` 个唯一 `(article, actor, direction, L1)` 标签实例；
- 同一文章的 subevent 标注能够定位其中 `12,788` 个，覆盖率为 `75.6%`；
- 对现有 target-18，`804` 个训练实例中有 `589` 个可以定位到同 actor、同标签、同方向的 subevent，覆盖率为 `73.3%`；
- 没有发现 subevent union 中存在、但文章级标签中不存在的 `(article, actor, direction, L1)` 组合。

统计输入：

- `dataset/train/train_event_base.json`
- `dataset/gold_labels/train/train_human_values.json`

这意味着大部分文章级稀有标签已经有可定位的局部证据。增强时无需让 LLM 从零构造整篇短新闻，而可以让它围绕真实事件证据做局部编辑或嫁接，同时保留原新闻的篇章结构、actor 数量、主题和写作风格。

### Task-1 test 合法性约束

Task-1 的正式测试输入 `dataset/test/test_article_event_base.json` 不包含 `subevents` 字段，因此最终推理流程不能依赖官方 test subevents。

本方案只把 TRAIN subevents 用于：

1. 定位训练种子中的 actor-specific evidence；
2. 构造训练期的合成或对比样本；
3. 可选的辅助训练目标。

最终学生模型仍只读取 title、content 和 actors。若规则不允许使用 Task-2 训练标注，则应以当前 E6 的自分段方法在 TRAIN 中生成 evidence units，并保持相同的实验设计。正式执行前需要向教授或任务组织方确认训练标注的允许范围。

## 4. 研究问题与假设

### RQ1：近分布增强是否优于自由生成？

在目标类别、样本数量、学生模型和训练步数完全相同时，从真实新闻上下文局部编辑得到的样本，是否比从标签定义自由生成的短新闻更能提高低频标签的 macro-AUPRC 和 macro-F1？

**H1：** evidence-grounded augmentation 在 target macro-AUPRC 上优于等数量的 free-form augmentation，并产生更小的总体 micro-F1 和 DRR 损失。

### RQ2：边界对比是否比增加正例数量更有效？

在相同生成预算下，目标正例与 closest-neighbor / opposite-direction 对比组，是否比相同数量的独立正例更能提高目标类别的可分性？

**H2：** confusion-aware contrast sets 能提高 target AUPRC、Recall@fixed-precision 和 per-class F1，而不仅仅把目标概率整体抬高。

### RQ3：语义验证和质量加权是否值得？

独立 LLM 验证、少量人工审核和样本权重是否能减少标签漂移、actor 错配及模板重复，并改善下游学生模型？

**H3：** filtered/weighted augmentation 优于未经筛选的同源数据；如果只筛掉数据而没有收益，则说明数量损失超过质量收益。

### RQ4：增强后的学生是否能成为更好的候选召回源？

即使增强后的 DeBERTa 不能独立完成可靠方向判断，它是否能以更高的低频 value recall 为 LLM verifier 或 E7 类融合系统提供更有效的候选？

**H4：** 新学生在固定候选预算下提高 tail recall，并在独立 LLM verifier 后转化为 Task-1b macro-F1 增益。

## 5. 方法设计

### 5.1 正确的增强单位

FEHU 是 actor-specific、多标签、direction-aware 任务。增强和采样的基本单位应定义为：

```text
(article_guid, actor_id, evidence_unit, direction:L1)
```

不能只按文章采样。整篇文章往往同时携带多个高频标签，简单过采样会把共现的高频标签一起放大，掩盖真正的低频学习效果。

### 5.2 TRAIN-only 目标选择

目标选择、增强预算和混淆邻居全部只使用 TRAIN，不使用 DEV 标签。

1. 以 `direction:L1` 为原子类别，统计 108 类训练频率；
2. 按 article 分组进行 3-fold cross-fitting，避免同一文章的 actor 或 subevent 跨折；
3. 对每一类计算 out-of-fold AUPRC、假阴性率、正例分数分布及混淆邻居；
4. 以训练频率定义 head/medium/tail，并在看到 DEV 结果前冻结；
5. 按困难度和稀有度自适应分配生成预算。

一个可预注册的基础预算函数为：

\[
B_c \propto \frac{1-\mathrm{AP}_{OOF}(c)}{\sqrt{n_c+1}}
\]

其中 `n_c` 是 TRAIN 支持数，`AP_OOF` 是 TRAIN cross-fit average precision。实际预算需要设置最小值和最大值，防止极少样本类别获得不受控制的放大倍数。

零训练支持类别不能与有真实种子的类别混为一谈，应作为单独的 label-description zero-shot track；本轮核心实验优先研究已有真实正例但模型学习失败的 tail 类别。

### 5.3 证据种子选择

对每个目标类别，候选种子由三部分组成：

1. **Prototype medoids：** 对已定位的 subevent/evidence 做 embedding clustering，选择能够覆盖不同主题、行为类型和文本风格的簇中心；
2. **Hard positives：** gold 为正、但 out-of-fold 模型对目标类别给分较低的实例；
3. **Hard negatives：** gold 不包含目标类别、但模型高分误报，或与目标类别经常混淆的实例。

种子集合还需控制：

- aligned / contradictory 的方向比例；
- actor 类型与数量；
- 文章主题和来源风格；
- 证据位于文章前部、中部或后部的位置；
- 原始文章的标签基数。

### 5.4 TRAIN-only 混淆图

每个目标类别选择 1–3 个 closest neighbors。邻居来源包括：

- TRAIN cross-fit 中的模型误报/漏报共现；
- 标签定义之间的语义相似度；
- 训练数据中较强的互斥或竞争关系；
- 方向反转，即同一 L1 的另一方向。

邻居不应被限制在同一 L2，因为 FEHU 的真实混淆可能跨越 L2。不能仅凭 LLM 常识选择邻居；最终列表需要由 TRAIN 证据冻结。

### 5.5 Evidence-grounded contrast generation

给生成器提供：

- 真实训练文章的 title、content 和 actor 列表；
- 已定位的目标 evidence span / subevent；
- 目标 `direction:L1` 定义；
- closest-neighbor 定义与典型区别；
- 必须保留的上下文和允许修改的 sentence IDs；
- 期望输出的监督模式及已知负标签。

LLM 只对局部证据做编辑或插入，不从零生成完全脱离真实语料的短新闻。每个种子优先生成一个小型 contrast set：

| 成员 | 要求 |
|---|---|
| target-positive | 目标 actor 明确表达指定 `direction:L1` |
| opposite-direction | 同一 L1 成立，但方向相反 |
| neighbor-only | closest neighbor 成立，目标标签明确不成立 |
| both / neither | 只在原始语义允许且验证成本可控时生成 |

输出必须包含：

- 修改后的完整文本；
- canonical actor 与文中自然 mention；
- 修改/插入的 exact sentence IDs；
- target、neighbor 和 direction；
- target evidence 与 neighbor evidence；
- 明确的 known positives、known negatives 和 unknown labels；
- contrast pair/group ID，供训练和分析使用。

### 5.6 验证与筛选

验证分为四层：

1. **确定性结构验证：** JSON Schema、taxonomy、L1→L2、direction、actor mention、evidence verbatim、重复 ID；
2. **近重复与分布检查：** exact hash、token/embedding similarity、模板簇、长度、actor 数、标签基数和 evidence position；
3. **独立语义验证：** 使用不同模型家族分别判断 actor attribution、target support、neighbor competition、direction 和上下文保持；
4. **人工盲审：** pilot 阶段全审或高比例审核，正式批次至少按类别和增强类型分层抽取 10%–20%。

生成器不应验证自己的输出。验证器不看生成器名称、采样温度或原始目标结论，避免确认偏差。

拒绝样本必须保留并记录原因，以便区分：

- actor attribution 错误；
- 目标标签漂移；
- target/neighbor 同时成立；
- direction 模糊；
- 文章形态偏离真实分布；
- 模板重复。

### 5.7 监督与训练

第一轮应保持现有 DeBERTa backbone 尽量不变，以便隔离数据设计的作用，同时加入审稿人会要求的标准长尾基线。

训练监督原则：

- 官方 TRAIN 继续使用完整 108 维监督；
- 对经过验证且保留原标签的局部编辑，保留确定不受影响的原标签；
- 对 target-positive、opposite-direction 和 neighbor-only 明确监督 target/neighbor 两侧；
- 其他可能受编辑影响但没有验证的类别使用 loss mask；
- 不把所有未列出的类别自动当作负例；
- 对合成样本使用独立权重 `w_syn < 1`，并对 verifier confidence / distribution distance 做预注册的分档，而不是训练后搜索最优权重。

可以增加一个与 contrast group ID 对应的 pairwise ranking loss：

\[
L = L_{masked\_BCE} + \lambda \max(0, m-z_{pos,c}+z_{neg,c})
\]

但该损失必须作为单独消融，不能与新数据同时加入后只报告组合结果。

## 6. DeepSeek 的角色

### 6.1 DeepSeek 不是方法本身

本研究需要 LLM 进行局部文本编辑和语义验证，但不要求最终方法绑定 DeepSeek。模型品牌不能成为主要贡献。

建议角色分配：

- **目标/种子选择：** TRAIN cross-fit 程序，不使用 LLM；
- **生成器：** DeepSeek Pro 或一个固定权重开源模型；
- **验证器：** 与生成器不同的模型家族；
- **学生：** DeBERTa 或后续 label-aware encoder；
- **最终方向判断：** 若进入 hybrid，则由冻结的 LLM verifier 处理。

### 6.2 为什么不能只依赖当前 DeepSeek API

现有 E7-G4 refresh 已显示，同一核心 prompt 在 DeepSeek 服务版本和 inference mode 变化后会发生较大输出漂移。因此任何新调用都必须保存：

- API 时间；
- 请求模型名与响应模型名；
- system fingerprint；
- thinking on/off；
- temperature、top_p 和最大输出长度；
- prompt hash；
- 原始响应和 repair history。

### 6.3 小规模生成器选择实验

正式生成前，建议选择 6 个代表性目标类别，每类覆盖两个方向和至少一个混淆邻居，用 DeepSeek 与一个固定权重模型各生成 40–60 条候选。匿名比较：

- actor attribution fidelity；
- target/neighbor separability；
- direction fidelity；
- evidence grounding；
- 与真实 TRAIN 的 embedding/length/actor-count 距离；
- 模板重复率；
- 人工接受率；
- 单条通过样本的实际成本。

选择生成器时以 FEHU pilot 的质量为准，不以通用 benchmark 或直接分类能力为准。

## 7. 必要的强基线与消融矩阵

以下实验需要使用相同的 TRAIN split、训练步数、学生 backbone、生成数量和随机种子：

| Cell | 数据与方法 | 回答的问题 |
|---|---|---|
| A0 | 官方 TRAIN + 当前 BCE | 历史锚点 |
| A1 | 官方 TRAIN + Distribution-Balanced Loss + internal per-class thresholds | 不生成数据能否解决问题？ |
| A2 | A1 + 旧 free-form synthetic，按新实验数量做 matched subset | 自由生成基线 |
| A3 | A1 + 等数量 evidence-grounded target positives | 近分布生成是否更好？ |
| A4 | A3 + confusion-aware contrast sets | 边界对比是否提高 separability？ |
| A5 | A4 + independent filtering / quality weighting | 筛选和加权是否有贡献？ |
| A6 | A5 + pairwise ranking loss | 对比结构是否需要专门 loss？ |
| A7（可选） | 将最佳学生接入冻结 verifier/hybrid | 学生改善能否转化为最终 Task-1b 增益？ |

最重要的因果比较是：

- `A3 − A2`：等数量、等训练成本下，near-distribution 是否优于 free-form；
- `A4 − A3`：边界对比是否优于继续增加独立正例；
- `A5 − A4`：验证和质量权重是否值得；
- `A6 − A5`：收益来自数据本身还是专门的排序损失。

每个 Cell 至少运行 seeds 42/43/44。进入论文主表的核心对比若仍存在明显方差，应增加到 5 个种子。

## 8. 评测协议

### 8.1 数据使用

- target 选择、混淆图、early stopping、阈值和所有超参数只使用 TRAIN 内部划分；
- 按 article 分组划分，禁止同一文章的 actors/subevents 跨 train/validation；
- DEV 只在方法、预算和阈值冻结后评估；
- 不以 DEV 结果反向修改 target set 或生成预算。

### 8.2 主要指标

**Primary：**

- train-defined tail classes 的 macro-AUPRC；
- target macro-F1；
- Recall@fixed-precision 或 candidate Recall@K。

**Secondary：**

- 全部 108 类 micro/macro precision、recall、F1；
- head / medium / tail 分组指标；
- DRR 与 reversal count；
- per-class threshold 后的预测类别覆盖数；
- value-only candidate recall（用于 hybrid 场景）。

保留 ROC-AUC 以便与 Phase 1–3 对照，但不再把它作为唯一的 score-level 证据。

### 8.3 统计报告

- 所有训练结果报告 mean ± SD；
- 对最终预测按 article 做 paired bootstrap；
- 同时报告 point delta、95% CI 和差值方向在各 seed 中是否一致；
- 不选择单个最好 seed 代表方法；
- 合成数据质量报告接受率、错误类型、模板簇、分布距离和人工一致性。

## 9. 非 LLM 方法必须作为对照

为避免把所有低频问题错误归因于数据不足，本研究至少需要以下非生成基线：

1. Distribution-Balanced Loss；
2. internal per-class threshold calibration；
3. macro/tail-aware checkpoint selection；
4. 现有 512-token 输入与更合理的 actor-evidence input 对照；
5. 可选的 label-description scorer 或 document-to-label retrieval。

如果 A1 已经达到或超过新增强方法，则论文结论应诚实转为：标准长尾训练比昂贵的 LLM augmentation 更有效。这个结果仍然有研究价值，但不能继续声称生成是主要改善来源。

Label-description 方向是高价值 Plan B：让模型直接比较 actor evidence 与标签定义，用共享的 binary/entailment scorer 代替完全独立的 108 路输出。它可以利用标签语义，在极低频类别上共享监督；但为了避免同时改变数据和模型，第一轮不应与 A3 一起加入。

## 10. 时间表

### 8 月 17–23 日：协议和强基线

- 冻结 TRAIN-only head/medium/tail 定义；
- 建立按 article 分组的 cross-fit split；
- 实现 macro-AUPRC、per-class AP 和 confusion graph；
- 跑 A0/A1；
- 对旧 900 条数据做分层人工质量抽样。

### 8 月 24–31 日：种子选择与生成器 pilot

- 完成 subevent/evidence seed selector；
- 冻结每类预算和 neighbors；
- 完成两个生成器的 40–60 条 pilot；
- 盲审并检查分布、重复和类别边界；
- 根据预先定义的质量指标选择正式生成器。

### 9 月 1–10 日：正式生成与验证

- 生成 matched-budget A3/A4 数据；
- 完成结构验证、独立语义验证和人工分层审核；
- 冻结 accepted/weighted training pool；
- 不因 DEV 结果重新生成。

### 9 月 11–20 日：主要训练实验

- 完成 A2–A6 三种子训练；
- 导出全部概率并做 threshold-independent 分析；
- 检查数据确实进入训练和每次运行的 hash/provenance。

### 9 月 21–27 日：统计与下游验证

- 对核心 Cell 增加种子；
- paired bootstrap；
- head/medium/tail 和 per-target error analysis；
- 视时间完成 A7，下游 verifier/hybrid 保持冻结。

### 9 月 28 日–10 月初：冻结与写作

- 停止方法搜索；
- 固定主表、消融表和失败案例；
- 完成论文叙事、图表和复现实验说明。

## 11. 预注册的继续与停止条件

Pilot 进入正式生成的建议条件：

- actor attribution 与 direction fidelity 均达到人工审核设定的最低标准；
- target/neighbor ambiguous 比例可控；
- 相比旧 free-form 数据，长度、actor 数和 embedding 分布更接近真实 TRAIN；
- 模板近重复率明显低于旧数据；
- 每个目标类别至少有足够通过样本组成方向或邻居对比组。

核心实验的建议成功条件：

- A3 相对 A2 在至少 3/3 seeds 上提高 tail macro-AUPRC；
- A4 相对 A3 提高 target precision/AUPRC，而不是只提高平均概率；
- 总体 micro-F1 平均损失不超过预注册容忍值，例如 `0.01`；
- DRR 不出现无法由下游 verifier 吸收的大幅恶化；
- A7 若执行，必须用 no-new-student 或 no-augmentation 对照证明学生信号确实进入最终系统。

若近分布增强仍不能稳定超过 matched free-form baseline，则停止继续扩大生成量，优先转向：

1. label-description cross-encoder / retrieval；
2. 对真实新闻进行 teacher annotation，而非继续生成完整合成新闻；
3. actor-evidence selector 与更长输入；
4. 固定候选预算下的 verifier 研究。

## 12. 预期论文贡献

如果实验支持假设，论文可以形成三项清晰贡献：

1. **TRAIN-only diagnosis and selection：** 面向 actor-conditioned direction-aware 长尾标签的目标、证据种子和混淆邻居选择方法；
2. **Evidence-grounded contrast augmentation：** 以真实新闻结构和局部价值证据为基础，生成目标/邻居/反方向对比组；
3. **Controlled empirical findings：** 在相同数据预算下区分自由生成、近分布生成、边界对比、独立筛选和专门 loss 的实际作用，并同时报告 tail、整体 F1 和 DRR。

相较于“我们进行了多轮迭代”，这个叙事提出了一个可证伪、可复现且能推广到其他 actor-conditioned 长尾多标签任务的问题。

## 13. 相关研究入口

- Peng et al. **Text Grafting: Near-Distribution Weak Supervision for Minority Classes in Text Classification.** EMNLP 2024. 真实语料模板与近分布少数类生成。  
  <https://aclanthology.org/2024.emnlp-main.219/>
- Sahu et al. **PromptMix: A Class Boundary Augmentation Method for Large Language Model Distillation.** EMNLP 2023. 类别边界生成与重新标注。  
  <https://aclanthology.org/2023.emnlp-main.323/>
- Huang et al. **Balancing Methods for Multi-label Text Classification with Long-Tailed Class Distribution.** EMNLP 2021. Distribution-Balanced Loss。  
  <https://aclanthology.org/2021.emnlp-main.643/>
- Zhang et al. **Long-tailed Extreme Multi-label Text Classification by the Retrieval of Generated Pseudo Label Descriptions.** Findings of EACL 2023. 标签描述检索与 tail prediction。  
  <https://aclanthology.org/2023.findings-eacl.81/>
- Liu et al. **SEP-MLDC: A Simple and Effective Paradigm for Multi-Label Document Classification.** Findings of NAACL 2025. 标签语义扩展、tail pseudo-samples 与对比表示。  
  <https://aclanthology.org/2025.findings-naacl.212/>
- Kim et al. **Evaluating Language Models as Synthetic Data Generators.** ACL 2025. 生成能力与任务求解能力并不等价，需按数据质量选择生成器。  
  <https://aclanthology.org/2025.acl-long.320/>
- Wang et al. **Event-Centric Human Value Understanding in News-Domain Texts: An Actor-Conditioned, Multi-Granularity Benchmark.** 2026. FEHU/NEVU 的 actor-conditioned、direction-aware 与多粒度任务背景。  
  <https://arxiv.org/abs/2603.17838>

