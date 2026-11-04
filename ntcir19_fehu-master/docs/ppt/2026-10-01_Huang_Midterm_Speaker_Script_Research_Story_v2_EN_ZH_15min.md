# Research process and WAIPS-03 / 中期答辩双语讲稿

对应 PPT：[2026-10-01_Huang_Midterm_Defense_Research_Story_v2_15min.pptx](2026-10-01_Huang_Midterm_Defense_Research_Story_v2_15min.pptx)。版本：2026-10-01，v2：方法方程与 pure prompt 参考结果。

## 使用与计时

- **21 页主讲，6 页隐藏备用，共 27 页。** 主讲停在第 21 页结论。配套 PDF 只包含主讲页。
- **主讲预算 14 分钟，另留 1 分钟现场余量。** 逐页时间包括讲述、指图与短暂停顿，是排练目标，不是实测朗读时长。
- 英文主讲 **1,259 词**。只朗读 English 正文；中文、讲述提示、技术备注和备用页不计时。PPT 备注中的 MAIN SCRIPT 与本稿英文一致。
- 第 2–7 页约 **3 分 30 秒**，先讲例子、54 种价值与 20 类、FEHU、用途和目标。第 9、10 页分别介绍数据增强与 WAIPS-02。第 11–13 页集中解释 WAIPS-03。第 19、20 页分别讨论可靠性与 FEHU 之外的应用验证。
- 第 12 页定义支持分数，第 13 页给出校准决策与约束，第 14 页定义评价指标。公式用于说明方法与检验方式，不能替代实验来证明有效性。讲述时先说直观含义，再指公式，不逐符号朗读。
- 第 15 页包含三组有归档记录的**开发结果**，以及用户提供的 **pure prompt 外部参考分数**；第 17 页单独展示两种提交系统的官方测试结果。Pure prompt 的评测划分与协议未提供，不把它称为已核验的同条件消融。
- Pure prompt 的 Micro-F1 为 **0.3787**、Macro-F1 为 **0.2754**。模型由用户称为 GPT5o，页面按要求统一写为 Pure prompt。其 DRR 没有提供，用“—”表示，不能从两个 F1 推算，也不能填成 0。
- WAIPS-03 使用历史增强分类器分数和包括 Liu prompt 在内的辅助预测，并借鉴 WAIPS-02 将标签选择与方向判断分开的思路。**WAIPS-02 的最终输出不是 WAIPS-03 的输入。**

### 时间总览

| 页码 | 主题 | 本页预算 | 累计结束 |
| --- | --- | ---: | ---: |
| 1 | Diagnosis-Guided Augmentation and Frequency-Gated Fusion for Actor-Conditioned Human-Value Recognition | 15 秒 | 00:15 |
| 2 | Whose values does a news report describe? | 40 秒 | 00:55 |
| 3 | A shared vocabulary for human values | 40 秒 | 01:35 |
| 4 | NTCIR-19 FEHU: a shared evaluation task | 40 秒 | 02:15 |
| 5 | My task: labels for each supplied actor | 25 秒 | 02:40 |
| 6 | What these labels could help readers do | 20 秒 | 03:00 |
| 7 | Research goal: fewer wrong and missed labels | 45 秒 | 03:45 |
| 8 | How the classifier supports the decision | 30 秒 | 04:15 |
| 9 | Data augmentation for missed values | 45 秒 | 05:00 |
| 10 | WAIPS-02: prompt agreement and direction choice | 40 秒 | 05:40 |
| 11 | WAIPS-03 combines scores and prompt predictions | 45 秒 | 06:25 |
| 12 | Support scores combine votes and classifier estimates | 55 秒 | 07:20 |
| 13 | Calibrated decisions and direction checks | 45 秒 | 08:05 |
| 14 | Evaluation: recognition and direction errors | 40 秒 | 08:45 |
| 15 | Recognition scores across four approaches | 55 秒 | 09:40 |
| 16 | Fewer extra labels and fewer missed labels | 45 秒 | 10:25 |
| 17 | Official test: better F1, remaining direction errors | 35 秒 | 11:00 |
| 18 | A direction check can introduce an error | 40 秒 | 11:40 |
| 19 | Next: evidence for more reliable direction changes | 40 秒 | 12:20 |
| 20 | Beyond FEHU: value analysis across news sources | 55 秒 | 13:15 |
| 21 | Conclusion: selective fusion improves recognition | 45 秒 | 14:00 |
| 22 | Extra examples improve label recognition | 隐藏备用 | 不计入 |
| 23 | Masking is sensitive to data and random seed | 隐藏备用 | 不计入 |
| 24 | Frequency gating: a Micro–Macro trade-off | 隐藏备用 | 不计入 |
| 25 | Fusion scores, calibration and decision rules | 隐藏备用 | 不计入 |
| 26 | Most gains come from label selection | 隐藏备用 | 不计入 |
| 27 | References: task, methods and evaluation | 隐藏备用 | 不计入 |

## 第 1 页｜Diagnosis-Guided Augmentation and Frequency-Gated Fusion for Actor-Conditioned Human-Value Recognition

**建议用时：15 秒；累计结束：00:15。**

讲述提示：不要朗读完整论文题目；开场直接说明本次聚焦 WAIPS-03。

### English

Good morning. I'm Peiyang Huang. Today I focus on WAIPS-03, our submission for recognizing human values in news, and explain how selective fusion improves its predictions.

### 中文对照

大家早上好，我是 Peiyang Huang。今天我重点介绍识别新闻中人类价值的参赛系统 WAIPS-03，说明有选择地融合不同预测如何改善结果。

## 第 2 页｜Whose values does a news report describe?

**建议用时：40 秒；累计结束：00:55。**

讲述提示：指 public order，再指政府、价值和方向。这里只解释一次 aligned / contradictory，后面直接使用。

### English

Consider this report about protests in Chile. The government says it wants to maintain public order. The benchmark connects this conduct with 'Have a safe country.' It labels the direction as aligned, meaning that the conduct supports the value. Contradictory means that it goes against the value. Our system must make this judgment for the correct actor.

### 中文对照

请看这篇关于智利抗议活动的报道。政府表示希望维持公共秩序。基准标注把这一行为与“拥有一个安全的国家”联系起来，方向标为 aligned，表示行为支持这一价值；contradictory 则表示与价值相反。系统需要针对正确的主体作出这个判断。

## 第 3 页｜A shared vocabulary for human values

**建议用时：40 秒；累计结束：01:35。**

讲述提示：只指原图和右侧社会安全例子；不再重复方向定义，不提前讲实验分数。

### English

The value names come from an existing research taxonomy. Kiesel and colleagues' ACL 2022 paper groups fifty-four specific values into twenty categories, mainly building on Schwartz's theory. For example, societal security includes having a safe country and a stable society. FEHU adopts this vocabulary.

### 中文对照

这些价值名称来自已有的研究分类。Kiesel 等人在 ACL 2022 的论文主要基于 Schwartz 的理论，把 54 种具体价值归入 20 个类别。例如，社会安全包括拥有安全的国家和稳定的社会。FEHU 沿用这套词汇。

## 第 4 页｜NTCIR-19 FEHU: a shared evaluation task

**建议用时：40 秒；累计结束：02:15。**

讲述提示：机构读一遍，姓名留在页面供查看；时间线只读四个关键节点。

### English

FEHU stands for Fact-based Event-centric Human-value Understanding. It is a pilot shared task in NTCIR-19, an information-access evaluation campaign. The organizers come from Tsukuba, AIST and Innsbruck. The task launched in September twenty twenty-five, released training data in January, and returned results in August twenty twenty-six. The conference is in December. Shared data and scoring allow researchers to compare their systems.

### 中文对照

FEHU 的全称是 Fact-based Event-centric Human-value Understanding，即基于事实、以事件为中心的人类价值理解。它是 NTCIR-19 信息访问评测活动中的一个试点任务。组织者来自筑波大学、AIST 和因斯布鲁克大学。任务于 2025 年 9 月启动，2026 年 1 月发布训练数据、8 月返回结果，会议在 12 月举行。统一的数据和评分让研究者能够比较系统。

## 第 5 页｜My task: labels for each supplied actor

**建议用时：25 秒；累计结束：02:40。**

讲述提示：沿输入输出讲清任务；不再重新解释价值是什么，也不展开 Task 1a。

### English

I focus on the article-level task. The system receives a news article and an actor list. For each actor, it selects relevant values with their directions. Several labels can apply. Fifty-four values with two directions give one hundred and eight possible labels.

### 中文对照

我关注文章层次的任务。系统接收新闻文章和主体列表，为每个主体选择相关价值及其方向。一个主体可以有多个标签。54 种价值与两个方向构成 108 个可能的标签。

## 第 6 页｜What these labels could help readers do

**建议用时：20 秒；累计结束：03:00。**

讲述提示：这是潜在用途，不能说已经部署或验证；讲完立即进入研究目标。

### English

These labels could help readers find reports about public security, or compare how reports portray different institutions. Both uses depend on connecting the value to the right actor and reported conduct. That makes label errors important in practice.

### 中文对照

这些标签可以帮助读者查找涉及公共安全的报道，或者比较新闻如何描述不同机构。这两种用途都依赖于把价值与正确的主体及报道中的行为联系起来，因此标签错误会影响实际使用。

## 第 7 页｜Research goal: fewer wrong and missed labels

**建议用时：45 秒；累计结束：03:45。**

讲述提示：说明为什么直接问 AI 还不够；把本次聚焦的研究问题讲清，不声称这是论文全部 RQ 的原文。

### English

A language model can produce plausible answers and still miss relevant values or add incorrect ones. Simply accepting more predictions trades one problem for the other. My goal is to reduce both errors. I ask how we should use support from different predictions, and which revision steps actually help. WAIPS-03 tests selective removal, addition and direction checking.

### 中文对照

语言模型能给出看似合理的答案，但仍可能漏掉相关价值，或者添加错误标签。简单地接受更多预测，可能减少一种错误却增加另一种。我的目标是减少这两类错误。我关注如何利用不同预测提供的支持，以及哪些修改步骤确实有效。WAIPS-03 检验有选择的删除、添加和方向复核。

## 第 8 页｜How the classifier supports the decision

**建议用时：30 秒；累计结束：04:15。**

讲述提示：只讲处理顺序与设计区别；不展开文献历史或其他系统的开发过程。

### English

In the related system EAVIT, a trained classifier narrows the value definitions before the language model decides. My design uses classifier scores after the initial predictions, to help decide which labels to revise. It also separates label selection from direction checking. This is a design comparison; I have not run a matched EAVIT benchmark.

### 中文对照

在相关系统 EAVIT 中，训练好的分类器先缩小价值定义的范围，再由语言模型判断。我的设计在初始预测之后使用分类器分数，帮助决定修改哪些标签，并把标签选择和方向复核分开。这是设计上的比较；我尚未进行同等条件下的 EAVIT 性能对照。

## 第 9 页｜Data augmentation for missed values

**建议用时：45 秒；累计结束：05:00。**

讲述提示：讲清目标标签、生成样本、训练分类器及其后续用途。这里不展开 masking 或各轮训练，也不把历史分类器说成已追溯到某次重复实验的检查点。

### English

My first approach was to improve the training data. Error analysis identified eighteen directed labels that the initial classifier failed to recover. I generated news-like examples connecting an actor's conduct to those values and trained a DeBERTa classifier with the additional data. This gives the classifier more relevant examples, but recognizing values on its own remains difficult. In WAIPS-03, an earlier augmented classifier supplies scores for candidates proposed by the language models.

### 中文对照

我的第一个方向是改进训练数据。错误分析找出了初始分类器未能识别出的 18 个定向标签。我生成类似新闻的样本，把主体行为与这些价值联系起来，再用增加后的数据训练 DeBERTa 分类器。这为分类器提供了更多相关样本，但单独完成价值识别仍然困难。在 WAIPS-03 中，一个较早的增强分类器为语言模型提出的候选提供分数。

## 第 10 页｜WAIPS-02: prompt agreement and direction choice

**建议用时：40 秒；累计结束：05:40。**

讲述提示：按表格三行讲流程，强调多数投票可能遗漏的情况。不要把 WAIPS-02 的最终输出画成 WAIPS-03 的输入。

### English

I also developed WAIPS-02 to combine several prompt outputs. Three prompt versions analyze the same article. A directed label needs agreement from at least two of them. An independent language-model prediction then provides a direction choice when available. This separates deciding which values to include from deciding their directions. However, majority voting can discard a correct label found by only one prompt. That limitation motivates more selective use of support in WAIPS-03.

### 中文对照

我还开发了 WAIPS-02，用来结合多个提示的输出。三个提示版本分析同一篇文章，一个定向标签至少得到其中两个支持才能保留。之后，如果独立的语言模型预测提供了方向，就用它来选择方向。这样就把纳入哪些价值与如何判断方向分开了。但多数投票可能丢弃只有一个提示找到的正确标签，这也促使我在 WAIPS-03 中更有选择地利用支持信息。

## 第 11 页｜WAIPS-03 combines scores and prompt predictions

**建议用时：45 秒；累计结束：06:25。**

讲述提示：先指初始预测，再指分类器和四份辅助预测。把 Liu 的一个 prompt 与完整 WAIPS-01 区分开；设计来源不等于数据依赖。

### English

WAIPS-03 brings these lines of work together. It starts with predictions from event descriptions generated from the article. An augmented classifier supplies continuous scores. Four auxiliary predictions provide additional candidates and agreement, including one targeted prompt from Liu Dongyang's work. WAIPS-02 contributes the idea of separating label selection from direction checking. Its final output is not an input here. My fusion method decides when this combined support is strong enough to revise the initial answer.

### 中文对照

WAIPS-03 把这些研究方向联系起来。它先根据从文章生成的事件描述得到初始预测。增强分类器提供连续分数，四份辅助预测提供额外候选和一致性支持，其中包括 Liu Dongyang 工作中的一个针对性提示。WAIPS-02 提供了将标签选择与方向检查分开的设计思路，它的最终输出并不是这里的输入。我的融合方法决定这些支持是否足以修改初始答案。

## 第 12 页｜Support scores combine votes and classifier estimates

**建议用时：55 秒；累计结束：07:20。**

讲述提示：先指两条公式，再解释 e、o、p 和删除、添加的区别。无需逐符号朗读，也不把 0.25 说成理论最优。

### English

These equations define the support used by fusion. The letter e counts predictions that agree on both the value and direction. The letter o counts support for the same value in the opposite direction. The classifier supplies the p scores. Before deleting a label, I allow partial support from the opposite direction because the value itself may still be relevant. Adding a label uses exact direction support. These different scores reflect the different risks of removal and addition.

### 中文对照

这两个公式定义了融合使用的支持分数。e 统计同时认同价值和方向的预测，o 统计支持同一价值但方向相反的预测，分类器则提供 p 分数。在删除标签之前，我允许相反方向提供部分支持，因为这个价值本身仍可能相关。添加标签时，则使用精确方向的支持。两个分数体现了删除与添加面临的不同风险。

## 第 13 页｜Calibrated decisions and direction checks

**建议用时：45 秒；累计结束：08:05。**

讲述提示：q 是估计值，不是真实正确概率。添加条件为大于或等于阈值。只说明规则，不推导全局最优；具体约束留在页面和备用页。

### English

Calibration maps these support scores to estimated correctness, shown as q. Eligible labels below the threshold can be removed, while missing candidates at or above it can be added. Frequency and count limits protect rare labels and restrict changes. The threshold uses half the initial F1 on the fitting data. This is a heuristic whose effect needs testing. Finally, a direction check revisits single-direction outputs when an auxiliary prediction disagrees.

### 中文对照

校准把支持分数映射为估计的正确概率，用 q 表示。符合修改条件、且低于阈值的标签可以删除；遗漏候选达到阈值后可以添加。频次规则与数量限制用于保护稀有标签并约束修改范围。阈值取拟合数据上初始 F1 的一半。这是一项需要通过实验检验的启发式规则。最后，如果辅助预测有分歧，就重新检查当前只有一个方向的输出。

## 第 14 页｜Evaluation: recognition and direction errors

**建议用时：40 秒；累计结束：08:45。**

讲述提示：每个公式只解释统计对象和指标方向。不要把低 DRR 单独等同于好系统，也不要说四组结果都已核实为相同开发口径。

### English

These measures test whether the rules help. Micro-F1 combines correct, extra and missed labels across all actors. Macro-F1 averages the individual label scores, so frequent labels do not dominate it. Direction reversal rate counts opposite predictions among pairs with one reference direction. Higher F1 and lower reversal rate are better. Development results compare our designs, and the separate official test evaluates the submissions.

### 中文对照

这些指标用于检验规则是否有效。Micro-F1 综合所有主体中的正确、额外和遗漏标签；Macro-F1 则平均各个标签的分数，因此不会由高频标签主导。方向反转率统计参考标注只有一个方向的组合中，出现相反预测的比例。F1 越高越好，反转率越低越好。开发结果用于比较设计，独立的官方测试则评价提交系统。

## 第 15 页｜Recognition scores across four approaches

**建议用时：55 秒；累计结束：09:40。**

讲述提示：表中 DRR 以 0–1 表示，讲述时换算为百分比。Pure prompt 来自用户提供的外部结果，不是 Liu 提示，也不是 WAIPS-03 的输入。不要声称其评测设置已经核验。

### English

The table now includes a pure-prompt reference, reported from a separate run. Its reversal rate is unavailable. For our documented development results, WAIPS-03 improves both F1 scores over WAIPS-02. However, the reversal rate rises from about three point four to four point two percent. Fusion therefore improves overall recognition while direction decisions remain a weakness. The next slide examines what changes relative to the fusion system's own initial predictions.

### 中文对照

表中加入了一组来自独立运行的 pure prompt 参考结果，它的方向反转率尚未提供。对于我们有记录的开发结果，WAIPS-03 的两种 F1 都高于 WAIPS-02，但方向反转率从约 3.4% 上升到 4.2%。因此，融合改善了整体识别，而方向判断仍然是一个弱点。下一页进一步说明，相对于融合系统自身的初始预测，具体发生了什么变化。

## 第 16 页｜Fewer extra labels and fewer missed labels

**建议用时：45 秒；累计结束：10:25。**

讲述提示：比较起点是 WAIPS-03 的 E6b 初始预测，不是 WAIPS-02，也不是上一页的 pure prompt。重点讲两类错误的实际含义。

### English

We can also ask what the fusion steps change in practical terms. Compared with its own initial predictions, WAIPS-03 produces one hundred and seventy fewer unmatched labels and misses fifty fewer reference labels on the same development articles. These are net changes in actor-value-direction labels. Most of the score gain comes from label removal and recovery. The detailed stage comparison is available for questions.

### 中文对照

我们还可以具体来看融合步骤改变了什么。与它自己的初始预测相比，WAIPS-03 在同一批开发文章上少产生了 170 个未匹配标签，也少漏掉了 50 个参考标签。这些是主体、价值、方向标签的净变化。大部分分数提升来自标签的删除与补充，详细阶段比较留在问答中。

## 第 17 页｜Official test: better F1, remaining direction errors

**建议用时：35 秒；累计结束：11:00。**

讲述提示：明确从开发集切换到官方测试。不要扩展其他团队排名；这页不出现组织者 baseline。

### English

The official test uses different articles. WAIPS-03 improves both F1 scores over WAIPS-02, reaching about zero point five eight Micro-F1. However, direction reversals become more frequent. This means better overall recognition still comes with a remaining weakness in deciding whether conduct supports or contradicts a value.

### 中文对照

官方测试使用另外的文章。WAIPS-03 的两种 F1 都高于 WAIPS-02，Micro-F1 达到约 0.58。但是方向反转更频繁了。这意味着整体识别有所改善，但在判断行为支持还是违背某个价值时，仍然存在不足。

## 第 18 页｜A direction check can introduce an error

**建议用时：40 秒；累计结束：11:40。**

讲述提示：与开场呼应，不重新介绍事件。不推测模型出错的心理过程，也不把一个例子当作整体性能结论。

### English

The Chile example shows this remaining problem. The reference connects the government's stated aim of maintaining public order with having a safe country. The initial direction is correctly aligned. The checking step changes it to contradictory. The saved answer gives no explanation. This case motivates checking whether a revision follows the actor's reported conduct in the source passage.

### 中文对照

智利的例子展示了这个问题。参考标注把政府所说的维持公共秩序，与拥有安全的国家联系起来。初始方向正确地标为 aligned，但检查步骤把它改成了 contradictory。保存的回答没有解释原因。这个案例促使我进一步检查：修改是否依据了原文中该主体被报道的行为。

## 第 19 页｜Next: evidence for more reliable direction changes

**建议用时：40 秒；累计结束：12:20。**

讲述提示：保留一个核心问题和检验办法。不能只比较反转率，还要看有用纠正是否被阻止及整体 F1。

### English

My first next step is to make revisions more dependable. I will inspect both useful corrections and introduced errors against the article. I then plan to require supporting passages for proposed direction changes and test this rule on separate articles. I will measure whether it prevents harmful changes while preserving useful corrections. This is planned work, and its effectiveness still needs evaluation.

### 中文对照

下一步首先是让修改更可靠。我会对照文章检查有用的纠正和新增的错误，然后计划要求系统为拟议的方向修改提供支持段落，并在另外的文章上检验这项规则。我会评价它能否减少有害修改，同时保留有用的纠正。这是后续计划，效果仍然需要验证。

## 第 20 页｜Beyond FEHU: value analysis across news sources

**建议用时：55 秒；累计结束：13:15。**

讲述提示：明确说 planned，尚未实现跨领域应用。先检验新来源和新事件，再考虑其他语言或标签体系；不承诺当前阈值可直接迁移。

### English

The broader goal is to use this method beyond the FEHU collection. I plan to evaluate it on news from new sources and later events, first keeping the same value definitions. A possible application is helping researchers compare how reports describe different actors' conduct. I would assess label accuracy and supporting passages against human annotations, together with review time. This would test whether selective revision transfers to new material and makes analysis easier, rather than only raising a shared-task score.

### 中文对照

更长远的目标是把这个方法用于 FEHU 数据集之外。我计划先保持价值定义一致，在新的新闻来源和后续事件上评价它。一个可能的用途是帮助研究者比较报道如何描述不同主体的行为。我会依据人工标注评价标签准确性和支持段落，并考察人工审阅时间。这样才能检验有选择的修改是否适用于新材料，以及是否真正帮助分析，而不仅仅提高共享任务中的分数。

## 第 21 页｜Conclusion: selective fusion improves recognition

**建议用时：45 秒；累计结束：14:00。**

讲述提示：停在结论页。不要再补讲已移到备用页的参数步骤；最后一句落在可靠性与扩展用途。

### English

To conclude, my work connects training-data augmentation with prompt aggregation and selective fusion. WAIPS-03 uses classifier scores and auxiliary predictions, including Liu's targeted prompt, to revise labels and check disputed directions. It improves development and official-test F1 over WAIPS-02, and reduces unmatched and missed labels relative to its own initial predictions. My next steps are to make revisions better supported by the text and evaluate the method on news beyond FEHU.

### 中文对照

最后总结一下，我的研究把训练数据增强、提示聚合和有选择的融合联系起来。WAIPS-03 使用分类器分数及包括 Liu 针对性提示在内的辅助预测，修改标签并检查有分歧的方向。它提高了相对 WAIPS-02 的开发与官方测试 F1，并减少了相对于自身初始预测的未匹配标签和遗漏。下一步是让修改更有原文依据，并在 FEHU 之外的新闻上评价这个方法。

## 第 22 页｜Extra examples improve label recognition

**隐藏备用，不计入主讲。**

讲述提示：隐藏备用，仅在相关问题出现时使用。

### English

With the extra examples, the classifier's average Macro-F1 rises from about zero point zero three to zero point zero nine. This suggests better recognition across labels. But the eighteen target labels still have a very low F1 at the chosen threshold, and more predictions oppose the reference direction. Extra practice helps, but it does not make this classifier reliable on its own.

### 中文对照

加入额外样本后，分类器的平均 Macro-F1 从约 0.03 上升到约 0.09，说明按标签平均的识别表现改善了。但在所选阈值下，那 18 个目标标签的 F1 仍然很低，而且更多预测与参考方向相反。补充学习样本有帮助，但还不足以让这个分类器单独可靠地完成任务。

## 第 23 页｜Masking is sensitive to data and random seed

**隐藏备用，不计入主讲。**

讲述提示：隐藏备用，仅在相关问题出现时使用。

### English

Each point represents one training run. With the same 900 records, masking gives a lower mean Macro-F1 than treating unannotated labels as negative.

When I combine both generation rounds, giving 1,240 records, masking has a higher mean than the negative-label rule. But one unusually strong run raises that average. In two of the three masked runs, the classifier makes no correct predictions for the target labels.

So I cannot recommend masking based on the average alone. Its benefit is inconsistent, and I need to understand why changing the data or random seed changes the result so much.

### 中文对照

每个点代表一次训练。使用相同的 900 条记录时，掩码训练的平均 Macro-F1 比把未标注标签当作负标签更低。

当我合并两轮数据，使用 1,240 条记录时，掩码训练的平均值又高于把未标注标签当作负标签的方式。但这个平均值主要是被一次表现特别好的运行拉高的。在三次掩码训练中，有两次没有正确预测出任何目标标签。

因此，我不能只根据平均值就推荐掩码训练。它的收益并不稳定，我还需要弄清楚，为什么更换数据或随机种子会让结果产生这么大的变化。

## 第 24 页｜Frequency gating: a Micro–Macro trade-off

**隐藏备用，不计入主讲。**

讲述提示：隐藏备用，仅在相关问题出现时使用。

### English

Here, I compare the removal step with and without the frequency gate. Without the gate, the system can also remove rare labels. Micro-F1 rises by 0.95 percentage points, but Macro-F1 falls by 2.46 points.

Keeping the gate therefore gives better average performance across labels in this comparison, although the overall Micro-F1 is lower.

This experiment covers removal only. I still need to repeat the comparison in the complete system to measure the gate's full contribution.

### 中文对照

这里，我比较删除阶段保留和去掉频次门控的结果。去掉门控后，系统也可以删除稀有标签。Micro-F1 提高了 0.95 个百分点，但 Macro-F1 下降了 2.46 个百分点。

因此，在这个比较中，保留门控可以获得更好的标签平均表现，但整体 Micro-F1 会低一些。

这项实验只考察了删除阶段。要确定门控对整个系统的贡献，我还需要在完整系统中重复这个比较。

## 第 25 页｜Fusion scores, calibration and decision rules

**隐藏备用，不计入主讲。**

讲述提示：隐藏备用，仅在相关问题出现时使用。

### English

For each actor, value and direction, e counts auxiliary predictions that support the exact label. The variable o counts predictions that support only the opposite direction for the same value. The encoder probability is p.

For removal, I add e, one quarter of o, and the larger encoder probability across the two directions. For addition, I use e plus the probability for the proposed direction. This lets removal consider support for the value even when auxiliary systems disagree about its direction.

I fit separate isotonic regression maps for removal and addition. Each map converts a combined score into estimated correctness, while preserving the score order. During development evaluation, I divide articles into two groups. I fit on one group and score the other, then swap them. All actors in an article stay together.

The decision threshold is half the primary system's Micro-F1 on the fitting group. This is a heuristic, not a proven optimal threshold. For test inference, I fit on the full development set.

The system keeps at least one prediction when the primary set is nonempty. It adds at most two actor-value-direction combinations per actor, for values absent after removal. Direction checking skips a value if both directions are already predicted.

### 中文对照

对于每个主体、价值和方向的组合，e 表示支持完全相同标签的辅助预测数量。o 表示支持同一价值、但只支持相反方向的辅助预测数量。编码器给出的概率用 p 表示。

计算删除分数时，我将 e、四分之一的 o，以及两个方向中较大的编码器概率相加。计算添加分数时，我使用 e 加上候选方向的编码器概率。因此，在判断是否删除时，即使辅助系统对方向有分歧，系统仍然可以考虑它们对这个价值本身的支持。

我分别为删除和添加拟合保序回归映射。每个映射都把组合分数转成对正确性的估计，同时保留分数的顺序。在开发集评估中，我把文章分成两组，用一组拟合，再给另一组打分，然后交换两组。同一篇文章里的所有主体都在同一组。

决策阈值是拟合组上主系统 Micro-F1 的一半。这是一项启发式规则，并不是已经证明的最优阈值。测试推理时，我使用整个开发集拟合校准。

如果主预测集合非空，系统至少保留一个预测。对于删除后尚未出现的价值，每个主体最多增加两个“主体、价值、方向”的组合。如果某个价值已经同时预测了两个方向，方向检查就会跳过它。

## 第 26 页｜Most gains come from label selection

**隐藏备用，不计入主讲。**

讲述提示：隐藏备用，仅在相关问题出现时使用。

### English

The stages explain where the gain comes from. Removal improves precision but loses some recall. Addition recovers missing labels. The final direction check brings a smaller net gain. Overall, development Micro-F1 rises from about zero point five five to zero point five eight. Most of the improvement comes from label selection.

### 中文对照

阶段结果说明了提升来自哪里。删除提高了精确率，但损失了一些召回；添加找回了遗漏标签；最后的方向复核带来较小的净收益。总体上，开发集 Micro-F1 从约 0.55 提高到约 0.58。大部分提升来自标签选择。

## 第 27 页｜References: task, methods and evaluation

**隐藏备用，不计入主讲。**

讲述提示：隐藏备用，仅在相关问题出现时使用。

### English

This page lists the main references. The FEHU overview and WAIPS manuscript provide the task setting and official scores. I use EAVIT to explain the design comparison, and build on established methods such as DeBERTa, LoRA and partial-label learning. The evaluation references explain the issues of system selection and uncertainty discussed earlier.

### 中文对照

这一页列出了主要参考文献。FEHU 综述和 WAIPS 稿件提供了任务设定与官方成绩。我用 EAVIT 说明设计上的区别，也使用了 DeBERTa、LoRA 和部分标签学习等已有方法。评价方面的文献则解释了前面讨论的系统选择与不确定性问题。

## 排练与问答安排

- 第 7 页结束约 **03:45**，第 13 页结束约 **08:05**，第 17 页结束约 **11:00**，第 21 页结束约 **14:00**。最后 1 分钟用于节奏波动。
- 第 4 页读机构和关键节点，姓名留在页面上；第 15 页解释趋势，不逐个读分数；第 16 页读净减少量 170 和 50；第 17 页只讲测试改善与方向问题。
- 如果第 17 页结束已超过 12 分钟，第 18 页直接指出“原本正确，复核改错”；第 19 页保留原文依据与独立评价；第 20 页保留新新闻来源和人工评价。不要删掉完整未来工作，也不要临时补讲参数历史。
- 备用页定位：**22** 重复训练增强结果；**23** masking 与种子波动；**24** 频次门控取舍；**25** 精确公式；**26** 融合阶段结果；**27** 文献。
- 应急结论（约 20 秒）：“WAIPS-03 combines classifier scores and prompt predictions to revise value labels. It improves recognition, but direction errors remain. Next, I will strengthen the evidence for revisions and test the method on news beyond FEHU.” 中文：WAIPS-03 结合分类器分数与提示预测修改价值标签。识别有所改善，但方向错误仍然存在。接下来，我会加强修改的原文依据，并在 FEHU 之外的新闻上检验方法。

## 比较口径与证据边界（备答，不朗读）

1. **第 15 页四组分数，依次为 Micro / Macro / DRR。** 增强分类器历史 v2：**0.3306 / 0.1303 / 0.2880**；pure prompt：**0.3787 / 0.2754 / 未提供**；WAIPS-02 选定开发策略：**0.5560 / 0.3816 / 0.0338**；WAIPS-03：**0.5817 / 0.4308 / 0.0419**。Pure prompt 为用户于 2026-10-01 提供的外部成绩，不是 Liu 提示、不来自本机文件，也不是 WAIPS-03 的输入。该行没有已确认的划分、覆盖口径、评价器和 DRR 信息。
2. **历史覆盖差异。** 三个有归档记录的系统使用相同的 177 篇开发文章，但编码器历史口径只构造 456 个有正例主体，WAIPS 系统使用 459 个提供主体。额外 3 个主体没有正例，却仍可能产生假阳性。Pure prompt 的对应口径未提供。系统调用预算也不同，不将此表称为完全控制条件的消融。
3. **增强实验与融合输入。** 主比较使用历史 v2 增强分类器，备用第 22 页展示另一个三种子训练对照。二者的检查点关联尚不完整，不能把历史 v2 分数与 900 条增强实验均值混用，或把全部融合提升归因于增强。
4. **WAIPS-02 的关系。** 三个 Pro 提示先进行精确定向标签多数投票，再利用独立 Flash 完整预测作方向查询。WAIPS-03 的初始输出是 E6b，辅助输出是 E1、E6、E6c 和 Liu 的一个 frozen targeted prompt；并不读取 WAIPS-02 最终集成结果。
5. **第 16 页计数。** 比较 E7-G0 初始输出与 E7-G4 完整融合：FP 1,442 到 1,272，FN 938 到 888。是标签的净变化，不是文章数量，也不等于人工确认的幻觉数量。第 26 页给出同组固定输出的阶段分数。
6. **第 17 页官方测试。** WAIPS-02 为 **0.5496 / 0.3580**，WAIPS-03 为 **0.5808 / 0.3952**。方向反转率为 **0.0395 / 0.0477**。这是同团队两次提交的比较，不宣称官方全体系统最高。方向反转率只检查参考标注为单一方向的主体–价值组合，缺失预测不计反转，因此需要与 F1 一起读。
7. **第 19–20 页为计划。** 先检查修改是否得到主体相关原文支持，再在独立新闻来源与后续事件中检验迁移。先保持同一价值定义与主体输入条件，避免同时改变太多因素。跨语言、新价值体系、自动主体识别都需要单独验证。FEHU 的 130 次频数门槛与其他阈值不能假设可以直接迁移。
8. **第 12–14 页公式的含义。** 删除支持为精确方向票数 e，加 0.25×仅支持相反方向的票数 o，再加该价值两方向最大编码器概率。添加支持为 e 加候选方向的概率。两种分数分别校准为估计正确性 q。标签需有 >130 个训练正例才能删除或添加；删除保留至少 1 个原始标签（原集合非空），每个主体最多新增 2 个定向标签。θ 为拟合组初始 F1 的一半，是启发式，不是全局最优定理。方程说明可复现的算法，不能仅凭写出方程证明分数必然提高。
9. **指标口径。** Micro-F1 = 2TP/(2TP+FP+FN)。Macro-F1 为有正例标签集合 L 上的逐标签 F1 均值。DRR = R/|E|，其中 E 仅包含参考标注为单一方向的文章–主体–价值组合，R 为其中预测相反方向的组合数量。预测双方向仍可能计反转，缺失预测不计，因此不能单独优化 DRR 而忽略 F1。
10. **为什么阈值与 F1/2 有关（可选备答，不朗读）。** 这是从 F1 定义得到的简化代数解释，不是论文中已证明的方法有效性定理。设正确标签数为 T、参考标签总数为 G、预测标签数为 N，当前 f=2T/(G+N)。固定这些计数，新增候选的正确概率为 q，则新增后的代入期望分数为 2(T+q)/(G+N+1)。该值大于 f，当且仅当 q>f/2。实际系统不知道真实 q 和测试标签计数，而是用校准估计与拟合组初始 F1 近似，并加入频次和数量约束，所以这个直觉不保证测试 F1 必然提高。英文解释也放在第 13 页技术备注中。

## 来源

- 已提交论文：[Huang_FEHU_Midterm_Paper.tex](../论文/Huang_FEHU_Midterm_Paper.tex)，方法第 4 节、开发系统表 4、独立增强表 5、融合表 7、官方结果表 8、案例表 9。
- Pure prompt：用户提供的外部结果，模型称为 GPT5o，Micro-F1=0.3787、Macro-F1=0.2754；本轮不搜索或重跑这组结果。它替换了第 15 页中的 Liu 分数，但不改变第 11 页的真实融合输入说明。
- WAIPS-02 开发指标：[DS_final/outputs/dev_metrics.json](../../DS_final/outputs/dev_metrics.json)。同目录中的 pred_task1b.json 是测试预测，不混作开发输出。
- 分类与原图：[Kiesel 等，ACL 2022，图 1](https://aclanthology.org/2022.acl-long.306/)。相关方法：[EAVIT，IJCAI 2025](https://doi.org/10.24963/ijcai.2025/934)。
- FEHU：[任务说明](https://sites.google.com/view/ntcir19fehu/task-description)、[组织者](https://sites.google.com/view/ntcir19fehu/organziers)、[时间线](https://sites.google.com/view/ntcir19fehu/important-dates)、[会议](https://research.nii.ac.jp/ntcir/ntcir-19/conference.html)。于 2026-10-01 核对。
