# 10 月 15 日组会 · Research Progress · 改进版 2 演讲稿

演讲者：Peiyang Huang  
日期：2026 年 10 月 15 日  
实验室：Data Engineering Lab, IPS, Waseda University  
对应文件：[改进版 2 PPT](2026-10-15_Research_Progress_改进版2.pptx)

本稿对应一份独立的 12 页 PPT。保留学校红色横线、校徽和封面信息。第 2–4 页共三页说明表达问题并展示改法，第 5–9 页讨论 Task 1 的结果和改进，第 10–11 页说明 Task 2，第 12 页给出下一阶段的具体交付结果。

## 评审结论与表达原则

本次使用一个 xhigh 子代理模拟“没有项目背景的新听众和 NLP／机器学习评审”，初审不继承对话记忆，先看页面，再看讲稿。它提供独立的模拟评审，并非真实人类专家的评价。初审发现的主要问题是：听众能知道要做什么，却仍难以复述现有 fusion 如何改变预测。定义出现太晚、subevent 来源未区分、Task 2 输出缺少具体例子，也会增加理解负担。

本版采用同一条“工厂排污、志愿者清理”的教学新闻来解释 actor、价值标签、方向、fusion 与证据核验。Task 2 再补充“工厂后来资助清理”，说明同一主体在不同事件中可以呈现不同方向。复审认为这些关键理解断点已经解决，没有需要重构或增加页数的问题；最后将核验方式明确为三组并列比较，并把 Task 1 可保留双方向的说明加入主讲稿。

术语在首次出现时给一句解释，保留必要的学术名称。主讲不展开系统编号、完整公式和所有门控参数。页面明确区分已有结果、教学示例与计划，避免把下一步研究说成已经验证的结果。

## 时间安排

英文主稿共 **902 词**，逐页排练目标合计 **13:50**。按每分钟 85 词并额外留两分钟停顿、换页和指图，约 **12:37**；按较慢的每分钟 75 词估算，约 **14:02**。两种估算均在 15 分钟以内。实际用时仍需本人朗读确认，以上不包含老师提问。

现场只使用英文或中文中的一种，不连续朗读双语。中文是较简短的对照稿。演讲提示、术语表和备用问答不属于主讲正文，不需要全部说出来。

| 页码 | 主题 | 本页预算 | 累计时间 |
| --- | --- | --- | --- |
| 1 | Research Progress | 0:45 | 0:45 |
| 2 | Presentation Lessons | 0:55 | 1:40 |
| 3 | Task 1: A Concrete Example | 1:05 | 2:45 |
| 4 | Fusion: A Worked Example | 1:15 | 4:00 |
| 5 | Task 1b: Results and Remaining Errors | 1:15 | 5:15 |
| 6 | Task 1: Two Uses of Subevents | 1:20 | 6:35 |
| 7 | Task 1: Checking One Label | 1:20 | 7:55 |
| 8 | Task 1: Other Improvements | 1:10 | 9:05 |
| 9 | Task 1: Controlled Comparisons | 1:10 | 10:15 |
| 10 | Task 2: Output and Completion | 1:30 | 11:45 |
| 11 | Task 2: Comparisons and Metrics | 1:05 | 12:50 |
| 12 | Next Steps | 1:00 | 13:50 |

第 5 页只讲“F1 更高，但方向错误仍有问题”，不逐项读小数。第 8 页不临时展开超参数。第 9 页结束时目标为 10 分钟左右，第 11 页结束时目标为 13 分钟以内。若前面讲得较慢，第 12 页仅使用下面约 30 秒的收尾，可减少约 30 秒：

> At the next checkpoint, I aim to show one controlled Task 1 result and a fully scored Task 2 baseline. I would welcome feedback on this priority order.

## 第 1 页 · Research Progress

**本页内容：** 介绍研究对象：识别新闻中各主体的行为与哪些人类价值有关，以及行为支持还是违背这些价值。

**时间预算：** 0:45，包含换页、停顿和指图。

### 英文主讲稿

Good morning. I study how to identify human values in news, such as protecting the environment, for each person or organization. Today I will briefly explain how I will make the project clearer. Then I will discuss improvements to Task 1 and the steps needed to complete Task 2.

### 中文对照稿

大家好。我研究如何识别新闻中各个人物或机构的行为涉及哪些人类价值，例如保护环境。今天先简要说明怎样把项目讲清楚，再讨论 Task 1 的改进，以及完成 Task 2 所需的工作。

### 演讲提示

用开场第一句交代项目主题。保留学校母版、姓名、日期与实验室，不逐项朗读封面信息。

## 第 2 页 · Presentation Lessons

**本页内容：** 把上次的表达问题与对应改法放在一起：先给输出例子，用作用介绍组件，明确实验比较。

**时间预算：** 0:55，包含换页、停顿和指图。

### 英文主讲稿

Two teachers who were new to the project said the previous talk was difficult to follow. I think I showed too many terms before showing the output, used too many system names, and did not explain comparisons clearly enough. I will begin with one example, explain each component by what it does, and state what each result can tell us. The next two slides demonstrate these changes.

### 中文对照稿

两位新老师表示上次很难听懂。我的判断是，具体输出出现太晚，系统名称太多，实验比较也没有解释清楚。这次先给一个例子，用作用介绍组件，再说明结果能够支持什么。接下来两页直接展示这些改法。

### 演讲提示

这些原因是自我诊断，不冒充老师逐项给出的意见。控制在一分钟以内，随后直接演示任务与方法。

## 第 3 页 · Task 1: A Concrete Example

**本页内容：** 定义 actor 和 Task 1，用同一新闻中的两个主体解释固定价值标签与 Aligned／Contradictory 方向。

**时间预算：** 1:05，包含换页、停顿和指图。

### 英文主讲稿

An actor is a person, organization, or group named in the news. Here, a factory puts polluted water into a river, while volunteers clean it. Both actions concern environmental protection. The factory acts against that value, so its direction is Contradictory. The volunteers support it, so their direction is Aligned. Task 1 reads the whole article and gives each supplied actor a set of value labels and directions. Several labels may apply. This is a teaching example.

### 中文对照稿

Actor 指新闻中的人物、机构或群体。这个例子中，工厂排放污水，志愿者清理河流。两种行为都涉及环境保护，但工厂的方向是 Contradictory，也就是相悖；志愿者是 Aligned，也就是支持。Task 1 阅读整篇文章，为给定主体预测价值和方向，同一主体可以有多个标签。这是教学示例。

### 演讲提示

指表格的主体、同一价值、不同方向。标签针对报道行为，不是对人物或机构永久品格的评价。这里以 Task-1b 的细粒度价值和方向说明 Task 1。

## 第 4 页 · Fusion: A Worked Example

**本页内容：** 展示初始漏标、其他预测与分类器提供支持、规则决定添加的实际过程，同时说明删除与方向检查。

**时间预算：** 1:15，包含换页、停顿和指图。

### 英文主讲稿

Selective fusion starts with one prediction and makes selected changes. Suppose the initial output misses the volunteers supporting environmental protection. Other predictions and classifier scores may support this missing label. A classifier is a trained model that scores labels. Fusion can add the label if its score and the existing limits allow it. It can also remove weak labels, then recheck directions when predictions disagree. Voting counts agreement. Our method revises an initial set of labels.

### 中文对照稿

选择性融合从一份初始预测开始，有选择地修改它。假设初始输出漏掉志愿者支持环境保护的标签，其他预测和分类器分数可能提供支持。分类器是为标签评分的训练模型。分数达到规则且符合现有限制时，fusion 可以补入标签；也可以删除支持较弱的标签，再复查有分歧的方向。投票统计一致意见，fusion 则修订初始标签集合。

### 演讲提示

本页给实际处理关系，不再讲“以后准备如何讲”。例子只说明决策，不虚构票数或概率。当前添加／删除有训练频次门控和数量限制，详细规则留问答。

## 第 5 页 · Task 1b: Results and Remaining Errors

**本页内容：** 明确已有结论：完整融合系统的 F1 更高，但 DRR 更差；这些结果不能单独归因于融合规则。

**时间预算：** 1:15，包含换页、停顿和指图。

### 英文主讲稿

The fusion submission has higher Micro-F1 and Macro-F1. F1 balances finding correct labels and avoiding wrong ones. Micro-F1 uses overall counts. Macro-F1 averages across labels present in the reference. However, DRR increases from about four percent to about five percent. It counts opposite directions where the reference gives only one direction. Lower is better. So recognition improves, but direction errors remain. These systems use different sources and costs. This table alone cannot identify the effect of the fusion rule.

### 中文对照稿

融合提交的 Micro-F1 和 Macro-F1 更高。F1 综合考虑找对标签和避免误报；Micro-F1 汇总整体计数，Macro-F1 对参考标注中出现的各标签分别计算后平均。但 DRR 从约 4% 上升到约 5%。它统计参考只给一个方向时，预测出现相反方向的情况，越低越好。识别效果有改善，方向错误仍存在。两套系统的来源和成本不同，这张表不能单独说明融合规则的贡献。

### 演讲提示

不逐个朗读六个小数。DRR 的分母不是所有预测；参考双方向的组合不进入分母。没有局部测试金标，不声称已完成新方法的官方测试或显著性检验。

## 第 6 页 · Task 1: Two Uses of Subevents

**本页内容：** 定义 subevent，并区分 Task 1 推理时的模型生成事件、TRAIN 中的官方子事件监督，以及后续 Task 2 给定的子事件。

**时间预算：** 1:20，包含换页、停顿和指图。

### 英文主讲稿

A subevent is one smaller event described in an article. The current predictor already creates event descriptions from the article. The new idea is to use them with the original text to check a disputed label. A second idea is to train the classifier with official TRAIN subevent labels, as well as article labels. TRAIN means the training set. We will test these ideas separately. Task 1 prediction still receives only the article and supplied actors. Task 2 will use supplied subevents.

### 中文对照稿

Subevent 是文章中描述的一件较小事件。当前预测器已经生成事件描述；新的问题是，能否把它和原文一起用于核验有争议的标签。另一条路线是在文章标签之外，用官方 TRAIN 子事件标签训练分类器。TRAIN 指训练集。两条路线分别检验。Task 1 预测仍只接收文章和给定主体，Task 2 才使用任务提供的子事件。

### 演讲提示

清楚区分三类信息的来源。TRAIN subevent 是既有官方监督资源，使用它本身不作为创新；不能接入 DEV 标注或 Task 2 测试子事件来做 Task 1 预测。

## 第 7 页 · Task 1: Checking One Label

**本页内容：** 对“工厂支持环保”这个待核验标签，用原文明确主体和行为，展示应支持相反方向，并给出三种检查方式。

**时间预算：** 1:20，包含换页、停顿和指图。

### 英文主讲稿

A candidate is a predicted label selected for checking. Suppose it says the factory supports environmental protection. The wastewater sentence supports the opposite direction. The volunteers’ cleanup belongs to another actor. The current check reads the article and asks for a direction. I will compare it with a check that must quote supporting text, and a check that also receives generated events. All use the same candidates. We count both wrong predictions corrected and correct predictions made worse, together with F1, DRR, and cost.

### 中文对照稿

Candidate 是选出来复查的预测标签。假设它认为工厂支持环保，排污的原文实际上支持相反方向，志愿者的清理也不能归给工厂。当前检查读取文章并回答方向。新实验比较当前检查、要求引用原文、再加入生成事件三种设置，固定同一批候选。同时统计改对和改错的数量，以及 F1、DRR 和成本。

### 演讲提示

表内关系是教学解释，不是模型输出或实验结果。新方案的原文引用要可定位，语义是否支持主体与方向还需人工抽查。仅引用原文与事件加原文使用同一模型及候选，分离事件信息的增量；保留“不检查”的基线用于计算净收益。

## 第 8 页 · Task 1: Other Improvements

**本页内容：** 保留 threshold 和 calibration 的学术含义，用简短解释说明分别调整添加／删除阈值、增加子事件监督及可选的来源裁减。

**时间预算：** 1:10，包含换页、停顿和指图。

### 英文主讲稿

A threshold is the cutoff used to make a decision. Here, it applies to a calibrated support score, adjusted using labeled examples. I will test separate thresholds for adding and removing labels. For the classifier, I will compare article training with article plus TRAIN subevents, using the same model and training budget. Only then will I test its scores inside fusion. Removing one prediction source is an optional cost experiment. Each change needs a separate comparison.

### 中文对照稿

Threshold 是作决策的分数界限，这里作用于经过标注样本校准的支持分数。我会比较分别选择添加、删除阈值的方案。分类器方面，固定模型和训练预算，比较文章训练与文章加 TRAIN 子事件训练，再检验分数接入 fusion 的增量。移除一路预测来源是可选的成本实验，每项改动分别比较。

### 演讲提示

添加分数与删除分数构成不同，各自有校准映射。不要把“分别选择阈值”说成当前只有一种分数。当前启发式阈值来自初始 F1，细节留问答；不同时改变骨干、增强数据与候选来源。

## 第 9 页 · Task 1: Controlled Comparisons

**本页内容：** 用相同预测、相同候选或相同训练条件分别做对照，并将调参文章与评价文章分开，避免将多个改动混成一个结论。

**时间预算：** 1:10，包含换页、停顿和指图。

### 英文主讲稿

Each comparison changes only the part we want to test. To study the fusion rule, voting and selective addition or removal use the same saved predictions. Neither uses classifier scores or extra direction checks. To study events, both checks use the same selected labels and original text. To study training data, the model and budget stay fixed. We choose settings using separate articles before evaluation, repeat the main tests, and report both benefits and harmful changes.

### 中文对照稿

每个比较只改变要检验的部分。检验融合规则时，投票和选择性添加、删除使用相同保存预测，两边都不用分类器分数或额外方向检查。检验事件参考时，固定待检查标签与原文。检验训练数据时，固定模型和预算。在独立的文章上选择设置，再评价和重复主要实验，同时报告改善与误改。

### 演讲提示

沿用同一官方评分器。五份预测多数投票至少三份精确支持同一主体、价值、方向。旧开发集已被多次使用，重新分折不能称为全新评价；资料中保留这个限制，现场不展开全部统计方法。

## 第 10 页 · Task 2: Output and Completion

**本页内容：** 用工厂先排污、后资助清理的两个事件展示 Task 2 输出，并说明从已有代码到完整直接评分的完成路径。

**时间预算：** 1:30，包含换页、停顿和指图。

### 英文主讲稿

Task 1 gives an actor labels for the whole article. Task 2 gives labels for each supplied subevent and actor. Extend the example: the factory later funds a river cleanup. Its direction can differ between the two events. Task 1 may keep both directions. Task 2 links each one to its event. We must keep the event ID with each prediction. Earlier code already predicts subevents, but the reported evaluation combined them into Task 1. I will check those outputs, build a single-predictor baseline, and score all evaluation examples directly as Task 2.

### 中文对照稿

Task 1 为主体给出整篇文章范围的标签，Task 2 为每个给定子事件中的主体分别给出标签。假设工厂后来资助清理河流，它在两个事件中的方向就可以不同。Task 1 也可能保留两个方向，而 Task 2 将各方向对应到所属事件，因此每项预测必须保留事件 ID。已有代码能预测子事件，但以前主要聚合后评价 Task 1。下一步核对旧输出，建立单预测器基线，直接评价完整的 Task 2 样本。

### 演讲提示

Task-2a 是较宽的 Level-2 价值类别，不含方向；Task-2b 是更具体的 Level-1 价值与方向。页内保留这一区别，下一页使用缩写。文章可能同时体现同一价值的两个方向，不能将事件冲突直接当作错误。

## 第 11 页 · Task 2: Comparisons and Metrics

**本页内容：** Task 2 内部比较单预测器、投票、选择性融合及文章上下文，明确要报告的指标和完整评价标准。

**时间预算：** 1:05，包含换页、停顿和指图。

### 英文主讲稿

Within Task 2, I will compare one predictor, voting, and selective fusion. Voting and fusion use the same prediction sources. I will also compare a subevent alone with the subevent plus the whole article, to test whether context helps. Task-2a reports broad values without directions. Task-2b reports specific values with directions. We report F1 for both and DRR for Task-2b. Completion means valid predictions for every evaluation example and a comparison against the baseline.

### 中文对照稿

在 Task 2 内比较单预测器、投票和选择性融合，投票与融合使用相同预测来源。另行比较只读子事件与补充整篇文章，检验上下文是否有帮助。Task-2a 输出较宽的价值类别，不含方向；Task-2b 输出具体价值和方向。两者都报告 F1，2b 还报告 DRR。完成标准是所有评价样本都有合法输出，并完成基线比较。

### 演讲提示

第一次规则比较不加入分类器或额外方向调用。Task 2 单独选择阈值，不能直接把文章分类器分数当作子事件正确概率。失败请求与合法空输出分开记录，Task 1／2 总分之差不是粒度收益的受控证据。

## 第 12 页 · Next Steps

**本页内容：** 以具体交付结果结束：Task 1 的受控事件核验结果与 Task 2 的完整基线评分，其他优化随后逐项检验。

**时间预算：** 1:00，包含换页、停顿和指图。

### 英文主讲稿

I will first run a small Task 1 event-verification test, then test the fusion rule and one other change separately. Task 2 data checks and baseline work can proceed alongside this. At the next checkpoint, I aim to show one controlled Task 1 result and a fully scored Task 2 baseline. We will keep changes only when the comparison supports them. I would welcome feedback on this priority order.

### 中文对照稿

先做小规模 Task 1 事件核验，再分别检验融合规则和一项其他改动。Task 2 数据核对与基线可以同步推进。下一次检查希望交付一项受控 Task 1 结果和完整评分的 Task 2 基线。根据比较结果决定保留哪些改动，也请老师评价这个优先顺序。

### 演讲提示

在具体检查点结束，不重复全部计划。不承诺未确认的完成日期，未改善的实验也应报告失败条件。


## 术语速查（不逐项朗读）

| 学术词汇 | 本次演讲中的直白解释 |
| --- | --- |
| Actor | 新闻中任务给定的人物、机构或群体。 |
| Human value / value label | 从任务规定的价值类别中选择标签，例如保护环境。一个主体可以有多个标签。 |
| Aligned / Contradictory | 报道行为支持／违背某个价值。评价对象是报道中的行为，不是主体永久的品格。 |
| Selective fusion | 从一份初始预测出发，参考其他预测与分类器分数，有选择地添加或删除标签，并检查有分歧的方向。 |
| Classifier | 经过训练、为各个标签评分的模型。 |
| Subevent | 一篇文章内描述的一件较小事件。生成事件、训练集标注事件和 Task 2 给定事件具有不同来源。 |
| Candidate | 选出来准备复查的预测标签。 |
| Threshold | 用于决定保留、添加或删除的分数界限。 |
| Calibration | 利用有标注的样本调整原始支持分数，使它更适合后续决策。 |
| Micro-F1 / Macro-F1 | Micro 汇总整体计数计算 F1；本项目的 Macro 对参考标注中出现的各标签分别计算 F1 后平均。 |
| DRR | Direction Reversal Rate。参考标注对某个主体和价值只给一个方向时，预测出现反方向的比例。分母不是所有预测。 |
| Task-1a / Task-1b | 全文范围、按主体输出。1a 使用较宽的 Level-2 类别，不含方向；1b 使用更具体的 Level-1 类别和方向。本次例子与结果重点是 1b。 |
| Task-2a / Task-2b | 按给定子事件及主体输出。2a 使用 Level-2，不含方向；2b 使用 Level-1 和方向。 |
| Baseline / controlled comparison | 基线是比较起点；受控比较保持其他条件一致，只改变要检验的部分。 |

## 备用问答（不计入主讲时间）

**1. 现在已经证明 fusion 比投票好吗？**

已有官方 Task-1b 结果表明，完整融合提交的 Micro-F1 和 Macro-F1 更高，但 DRR 更差。两套完整系统的预测来源和成本不同，所以仍需固定预测来源，单独比较投票与选择性修改，才能判断融合规则的作用。不能把这张表说成新的规则消融或显著性验证。

**2. 不是已经用过 subevent 了吗？新工作在哪里？**

当前初始预测器已经生成事件描述。下一步检验的是：把生成事件和原文一起提供给检查步骤，是否比仅要求原文证据更容易改正方向和主体归属错误。利用官方 TRAIN 子事件标签训练分类器是另一项单独实验，使用现有监督资源本身不作为创新主张。

**3. Task 1 会不会借用不允许的事件信息？**

Task 1 推理只接收文章与给定主体；需要事件描述时由模型从文章生成。官方 TRAIN 子事件标签用于训练。不能把 DEV 标注或 Task 2 测试输入中的给定子事件接到 Task 1 推理流程中。

**4. 方向冲突是否都应该改成一个方向？**

不是。文章可以包含同一主体支持和违背同一价值的不同事件，两个方向都可能成立。核验要看主体、事件和原文证据；Task 2 进一步保留每个方向所属的事件。仅 DRR 降低也不够，还要检查是否因为少预测了标签。

**5. 已经有子事件预测，为什么 Task 2 仍未完成？**

已有代码能够做子事件预测，但此前报告的评价主要把结果聚合回 Task 1。完成 Task 2 需要保留官方事件及主体标识，导出合法的 2a／2b 预测，对完整评价样本直接评分，并和单预测器基线比较。

**6. 怎么避免核验步骤把正确答案改错？**

三组使用相同候选，并保留不检查的起点。分别记录错误改对、正确改错、未改变的情况，同时报告 F1、DRR 和成本。原文引用还需检查能否定位，以及语义是否确实支持该主体和方向；能够输出引用并不等于引用正确。

**7. 为什么分别选择添加和删除阈值？**

现有添加、删除支持分数的构成不同，也各有校准映射。研究计划是在其他条件固定时，比较分别选择两个决策阈值的效果。当前方法还包含训练频次门控与数量限制，示例中的“可添加”以满足这些规则为前提。具体公式见论文，不在主讲逐项展开。

**8. 后续验证能否直接称为全新测试？**

选择设置和评价应按文章分开，同一篇文章的子事件不能散到两边。旧开发集已经多次使用，重新分折也不能抹去历史使用，因此需要如实说明限制。当前没有本地官方测试金标，不能声称已经完成新方法的官方测试评价。

## 内容依据

以下路径相对于仓库，PPT 的每页备注也保留对应来源。新闻与漏标例子为教学示例，不冒充数据集记录或实际预测。

- [论文：任务定义、官方结果和现有融合方法](../../论文/Huang_FEHU_Midterm_Paper_zh.tex)
- [任务解析与官方评价实现](../../../evaluation.py)
- [子事件监督与评价边界研究记录](../../8月研究/B.md)
- [当前方向检查实现](../../../RH_test/E7_calibrated_jury_fusion/scripts/run_direction_qa_e7.py)
- [已有子事件预测实验](../../../RH_test/E3_subevent_decomposition/reports/E3_REPORT_vs_E3a.md)
- [人类价值 Level-1 类别](../../../dataset/hv_categories/human_value_level1_values.json)
- [方向映射](../../../dataset/hv_categories/direction_mapping.json)
