# FEHU 中期论文：英文语言与行文审校

审校日期：2026-09-15

## 1. 总体判断

**当前版本整体可读，比前次审阅时自然。仍有局部英文搭配、指代和句间衔接问题，部分说明段带有模板感；没有必要为了“去 AI 感”重写整篇。建议先修正下列 6 处，再处理其余 9 处表达。**

这里的“AI 感”只指阅读时感受到的行文风格，不能用来判定写作来源。规范语法、技术术语、三项研究问题，以及有依据的局限说明，都不是 AI 写作的证据。

| 检查项 | 本轮判断 |
|---|---|
| 基本语法与可理解性 | 大多数句子完整、能够理解；没有发现贯穿全文的严重语法问题 |
| 英文自然度 | 方法段有几处动词与宾语搭配生硬，另有叙述对象不准确的问题 |
| 句间逻辑 | 最明确的问题在 §5.6：前半句报告 AUC，冒号后的数字却属于 Macro-F1 |
| 模板化表达 | 主要表现为抽象概括、同义反复和编辑提醒，不再是密集夸大研究贡献 |
| 建议修改规模 | 局部校订，保留已有技术细节、结果条件和必要的局限说明 |

### 审校对象与定位

- 完整阅读了当前 [英文 PDF](/Users/lloydhuang/Documents/GitHub/fehu-project/ntcir19_fehu-master/docs/论文/Huang_FEHU_Midterm_Paper.pdf) 的 27 个物理页面，包括摘要、正文、图表文字、附录和参考文献，并对本清单主要引句所在页面进行了渲染核对。
- 用同目录 [英文 LaTeX](/Users/lloydhuang/Documents/GitHub/fehu-project/ntcir19_fehu-master/docs/论文/Huang_FEHU_Midterm_Paper.tex) 辅助定位。下文所有 `L542` 等行号均指英文源码，不是中文译稿。
- “PDF 第 19 页”指阅读器从封面开始计数的页码；它对应页脚正文页码 `p.16`。正文页码与阅读器页码相差 3 页。
- 审阅时 PDF 的 SHA-256：`f364846bc848512ef81c5994a7a23ec59fd635c056fcf95367166f92c385b171`。
- 本轮范围是语言、指代和论述衔接。改写中使用的数值均来自当前论文；未重新运行实验或开展外部文献核验。

## 2. 优先修改的 6 处

### 1）先说 AUC，随后却用 Macro-F1 解释

位置：PDF 第 19 页，正文 p.16，§5.6，英文源码 L542。

原句：

> On the same 900 records, masking lowers target AUC in all three seeds: C has mean Macro-F1 0.0470 versus B’s 0.0890, although its DRR is lower.

问题：冒号让读者期待看到 AUC 的证据，后面却突然切换到 Macro-F1。这是实际的衔接问题。两个指标可以共同报告，但需要分别说明。

建议替换为：

> With the same 900 records, masking lowers target AUC in all three seeds; the mean falls from 0.6242 in B to 0.5770 in C. Mean Macro-F1 also falls from 0.0890 to 0.0470, while DRR decreases.

新增到句子中的两个 AUC 均值来自同页表 5。保留后文关于 Fp 的种子差异和掩码效果依赖数据组成的讨论。

### 2）把“未来版本应该写清楚”留在论文正文中

位置：PDF 第 11 页，正文 p.8，§4.4，英文源码 L238。

原句：

> This order-sensitive case is a limitation of the retained procedure and should be made explicit in a future revision.

问题：前一句已经明确解释了“最后一个方向覆盖先前方向”。这里再说“未来版本应该写清楚”，像尚未清理的编辑备注。真正需要保留的是顺序依赖这一局限。

建议将本句与前一句合并为：

> The lookup stores one direction per article-actor-value key. If Flash returns both directions, the last entry is used, making arbitration sensitive to output order.

这保留了实现行为，不额外承诺某种尚未完成的修复。

### 3）“spend an additional decision”搭配不自然

位置：PDF 第 14 页，正文 p.11，§4.7，英文源码 L339。

原句：

> The rationale is to spend an additional decision only where the ensemble exposes a disagreement.

问题：英语中通常花费的是时间、预算或计算资源。这里实际增加的是一次模型调用，`spend a decision` 让动作变得抽象。

建议替换为：

> The system makes an additional Flash call only when the members disagree about direction.

前文已给出单方向预测和辅助成员反向支持的完整触发条件，因此这里可以简短总结。后一句关于“成员一致不保证方向正确”的限制可以保留。

### 4）“macro coverage”没有清晰定义

位置：PDF 第 21 页，正文 p.18，§5.7，英文源码 L612。

原句：

> Frequency gating supports macro coverage.

问题：正文定义了 Macro-F1，也讨论了标签覆盖，但没有定义 `macro coverage`。这类压缩出来的抽象表达容易显得模板化，也可能把“Macro-F1 更高”误写成“正确覆盖了更多类别”。

建议将它与后面的数值比较合并为：

> In the removal-only comparison, gated G1 has higher Macro-F1 than ungated G5 (0.4146 versus 0.3900), while G5 has higher Micro-F1 (0.5703 versus 0.5608).

这句话明确了比较范围和指标，没有引入新的覆盖率结论。

### 5）“fitting folds”不是这里要表达的操作

位置：PDF 第 7 页，正文 p.4，§2.5，英文源码 L111。

原句：

> This preserves the unit of dependence when fitting folds and computing paired intervals.

问题：通常划分 folds、拟合 models 或 calibrators；`fitting folds` 容易让读者停下来解释。`preserves the unit of dependence` 也比实际操作更抽象。

建议将本句与前一句合并为：

> Grouping by article keeps all actors from the same article together during calibration cross-fitting and paired bootstrap resampling.

将现有参考文献 [15] 保留在这句话后面。这里改写的是论文已经描述的分组与重采样操作。

### 6）证据是提供给模型，不是提供给新闻中的 actor

位置：PDF 第 6 页，正文 p.3，§2.4，英文源码 L104。

原句片段：

> Its granularity affects the evidence available to each actor

问题：`available to each actor` 的字面意思是“每个行为主体能够获得的证据”。本节讨论的实际是模型在判断某个主体的价值观时可以使用的上下文。

建议将冒号前的部分替换为：

> Segmentation granularity affects the context available to the model when predicting values for each actor

后面关于分段过细或过粗的说明可以接着保留。这处属于语义角色表达不准确，值得优先改。

## 3. 其余 9 处局部表达

这些问题的严重程度不同，其中有些只是可以写得更直接，不应全部称为“语病”。

| 编号与位置 | 原句或片段 | 问题与建议 |
|---|---|---|
| 7 · PDF 第 4 页，p.1，§1.2，L51 | `under a small, imbalanced training set and the official input protocol` | `under` 同时支配数据集与协议，搭配别扭。改为 `using a small, imbalanced training set while following the official input protocol`。 |
| 8 · PDF 第 5 页，p.2，§1.3，L68 | `DRA-FEHU generates examples for a frozen set of 18 diagnosed labels.` | `diagnosed labels` 没有把诊断发现说清楚，`frozen` 在这里也可以更平实。建议：`DRA-FEHU generates examples for a fixed set of 18 directed labels selected through baseline error analysis.` |
| 9 · PDF 第 6 页，p.3，§2.4，L101 | `These members share the article and taxonomy, so agreement is used as a support score rather than as independent observations.` | `agreement`、`score` 和 `observations` 的比较对象不一致。建议：`The members process the same article and use the same taxonomy, so their predictions may be correlated. Their agreement is used as a support score.` |
| 10 · PDF 第 9 页，p.6，§4.2，L161 | `Generation requests news-like records in which an identified actor expresses a target directed value.` | 用 `Generation` 充当“发出请求”的主语生硬。建议：`The generation prompt asks for news-like records that link a specified actor to a target value and direction.` |
| 11 · PDF 第 11 页，p.8，§4.4，L240 | `Legal dual-direction predictions remain where the procedure retains them.` | 基本等于“被保留的预测会留下”，没有说明条件。依据本节已经描述的查表规则，可具体写为：`If Flash provides no direction for an actor-value pair, WAIPS-02 retains both directions when both pass the majority vote.` 这是对本节规则的展开，不是新增实验结果。 |
| 12 · PDF 第 12 页，p.9，§4.5，L249 | `They are heterogeneous in this practical sense, but their errors may still be strongly dependent.` | `in this practical sense` 像是在解释为何可以使用“异构”这个名字。与前一句合并更直接：`The jurors differ in prompts, intermediate representations, or model configurations, but their errors may still be strongly dependent.` |
| 13 · PDF 第 14 页，p.11，§4.7，L341 | `Development QA checks 176 cases: 46 directions change, 123 remain unchanged, and seven failed requests retain the current direction.` | “失败的请求保留方向”主语不准确；已完成结果用过去时更顺。建议：`In the 176 development cases, QA changed 46 directions and left 123 unchanged. The other seven requests failed, and the system retained the directions from before QA.` 测试集一句可同样处理，保持 207、77、125、5 不变。 |
| 14 · PDF 第 17 页，p.14，§5.5，L480 | `Self-segmentation affects different metrics differently.` | 没有明显语法错误，但 `different ... differently` 是信息量较低的概括。删去这句即可，直接从 E6 与 E1 的比较开始；也可把前两句合并为：`Compared with E1, E6 raises Task-1b Macro-F1 but lowers Micro-F1 and increases DRR.` |
| 15 · PDF 第 24 页，p.21，§6.2，L682 | `Aggregation will retain the full article because its labels need not equal the union of local predictions.` | `retain` 指保留全文作为输入，还是保留文章级标签，不够明确；`its` 和 `local` 也需要读者补足。这里需由作者确认设计含义。若确实指聚合时仍使用全文，可写：`For article-level prediction, the aggregation step will use the full article as context, because article-level labels may differ from the union of subevent-level predictions.` |

## 4. 剩余“AI 感”的主要来源

### 4.1 概括句先评价，后面的句子才提供信息

代表性表达包括 §4.4 的 `The rationale is conservative.`、§5.5 的 `Self-segmentation affects different metrics differently.`，以及 §5.7 的 `Table 7 is the central component comparison.`。

它们单独出现并不严重。问题在于连续几个段落都采用“抽象概括 → 方法或数字 → 再次概括”的顺序，会产生模板感。可删去没有独立信息的开头，让具体观察直接承担段落主题。例如 §5.5 从 E6 相对 E1 的指标变化开始，读者更容易跟进。

这不意味着每个段落都要从数字开始。解释问题、定义术语和提出假设时，概括句仍然有用。

### 4.2 同一对象有多个名称，增加了句子负担

WAIPS-03、FGHF、E7 和 E7-G4 在文中频繁切换。它们分别涉及提交系统、融合方法和实验配置，不能全部当作同义词替换。

建议在首次介绍时写清关系：WAIPS-03 是提交系统，采用 FGHF 方法，对应 E7-G4 配置。之后，讲官方成绩用 WAIPS-03，讲融合规则用 FGHF，讲阶段对照用 G0/G1/G3/G4。FGHF 首次出现在 §1.3，完整名称到 §4.1 才给出，可以将全称提前。

同样，`diagnosed labels`、`target labels` 和 `directed labels` 所指不同：前两者涉及目标选择，第三个涉及价值观与方向的组合。应按实际含义使用，不能为了避免重复而轮换术语。

### 4.3 归档说明有必要，但普通方法句不必反复带上归档修饰语

`retained`、`historical`、`archived`、`saved` 在这篇论文中有真实用途，尤其是历史 v2 编码器与重复训练的对应关系不完整。不能把这些词全部删掉。

可以压缩的是不影响理解的重复修饰，例如已经说明具体版本后，后文的 `retained procedure` 通常直接写 `procedure` 即可。完整实验环境没有全部保存、官方测试分数来自任务材料等事实，仍应在对应设置或附录中交代清楚。

### 4.4 §5.10 与 §6.1 的任务可以再分清

§5.10 先总结“增强改善编码器、融合改善系统”，紧接着 §6.1 又概括相同两条结果。重复不多，属于可选压缩。

建议 §5.10 集中解释证据边界：增强对融合的贡献尚未隔离、开发集参与选择、历史运行记录不完整。§6.1 保留主要发现及下一组对照实验。这样相邻两节的信息推进更清楚。

## 5. 摘要的专项意见

当前摘要的基本语法和衔接是通顺的，第一段对新闻、行为主体和价值方向的解释也比较自然。主要可读性问题是第二段最后一句同时串联分段、初始预测、标签修订、两类辅助信息、频次门控和方向检查。

原句位于 PDF 第 2 页，英文源码 L32。可以拆成两句：

> WAIPS-03 first segments each article to obtain initial value predictions. It then uses frequency-gated fusion to revise these predictions with auxiliary prompt outputs and encoder scores, followed by selective checks of direction disagreements.

此外，`compares full and partial-label supervision` 可以更明确地表述为：

> compares treating unspecified labels as negative with masking them during training

这能直接说明本篇实验比较的操作。它不意味着所有生成记录都已经获得完整人工标注。

当前摘要只介绍背景与方法，没有阶段结果。**这属于摘要功能上的可选调整，不是语病，也不是 AI 写作证据。** 如果学院允许摘要报告已完成的研究，可以补一句来自正文的主要观察；如果当前要求就是背景与计划型摘要，可保留现状，不必为此恢复一大段成绩数字。

## 6. 建议保留的自然表达与必要限制

- §1.1 从早期编码器漏检、提示系统误报，再引出研究问题，信息具体，具有研究过程感。
- §2.3 对“未提及标签不一定是负例”的解释清楚，不必为了去掉否定句而改写。
- §5.6 已经明确报告 B/C 的差异和 Fp 的不稳定性。保留这些不整齐的结果，比增加笼统的“有效性”评价更有说服力。
- §5.9 同时给出纠正、双方向和误改案例，保留新闻引文与金标准解释的区分。
- `frequency-gated`、`actor-conditioned`、`Macro-F1`、`cross-fitting` 等技术表达可以保留。需要改的是不明确的搭配和指代，不能机械替换术语。
- 关于 F1 阈值是启发式、历史编码器来源不完整、测试标签不可用、开发集选择偏差等限制，应继续保留。

## 7. 修改顺序

1. 先处理第 1 至第 6 条，修正指标衔接、语义对象和不自然搭配。
2. 处理第 7 至第 14 条；其中同义反复可以直接合并，不需要扩写。
3. 第 15 条先明确未来聚合步骤的实际含义，再定稿。
4. 最后通读摘要、§4.4、§4.7、§5.6 和结论，确认方法名称稳定、每句都增加信息，并保留所有实验条件与必要限制。

本轮建议是有针对性的英文校订。优先写清楚“谁做什么、在什么条件下、哪个指标发生什么变化”，就能同时改善流畅度和模板感。
