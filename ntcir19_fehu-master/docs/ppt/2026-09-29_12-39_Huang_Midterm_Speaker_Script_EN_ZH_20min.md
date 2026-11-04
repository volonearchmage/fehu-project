# Midterm presentation speaker script / 中期答辩逐页讲稿

对应文件：[Huang_Midterm_Defense_English_Background_Updated.pptx](Huang_Midterm_Defense_English_Background_Updated.pptx)  
版本：2026-09-29；按 PPT 的实际页码逐页对应。第 3 页介绍价值分类的论文来源与 FEHU，第 4 页介绍本研究的输入、输出与任务边界；英文正文与新版 PPT 备注同步。沿用原文件名，本稿当前目标为 21 分钟。

## 使用与计时

- **目标：英文主讲约 21 分钟，不含问答。** 中文帮助理解和练习，现场只讲英文，不需要把中文再读一遍。
- 正常放映顺序为 **1–22 → 25**。第 23 页是隐藏技术附页，第 24 页是隐藏参考文献，只在问答时按需使用。
- 每页 English 下的段落是可直接讲述的正文。“讲述重点与动作”、标题和计时属于排练提示，不朗读。段落之间可以自然停顿，不必逐句停顿。
- 研究动机与问题设定（第 2–7 页）的目标时长为 **4 分 45 秒**。先让听众理解例子和任务，再进入方法与实验。
- 主讲英文共 **2,383 词**，不含两页备用稿、标题、提示和文末备查材料；数字按书面形式计词。按每分钟约 125 词估算，正文约 19.1 分钟，加上指图、数值展开和换页，目标约 **21 分钟**。语速较快时请保留读图停顿，让观众有时间理解分类关系。
- 下表是加总为 21 分钟的排练目标，并非实际朗读测量。第一次请按舒服的语速计时，再调整每页的停顿和指图。若学校正式通知限定 15 分钟，需要另行压缩内容。

### 时间总览

| PPT 页码 | 讲述主题 | 本页时间 | 累计结束时间 |
| --- | --- | ---: | ---: |
| 1 | 开场 | 20 秒 | 00:20 |
| 2 | 新闻例子 | 40 秒 | 01:00 |
| 3 | 价值分类的来源、读图与 FEHU 介绍 | 115 秒 | 02:55 |
| 4 | 任务定义 | 40 秒 | 03:35 |
| 5 | 关键挑战 | 25 秒 | 04:00 |
| 6 | 个人工作与研究思路 | 40 秒 | 04:40 |
| 7 | 研究问题 | 25 秒 | 05:05 |
| 8 | 相关工作与区别 | 50 秒 | 05:55 |
| 9 | 两组实验及其关系 | 60 秒 | 06:55 |
| 10 | 针对错误生成训练样本 | 60 秒 | 07:55 |
| 11 | 如何利用不完整的标签 | 55 秒 | 08:50 |
| 12 | 选择性融合流程 | 95 秒 | 10:25 |
| 13 | 数据与评价指标 | 65 秒 | 11:30 |
| 14 | 文章表示与模型配置 | 60 秒 | 12:30 |
| 15 | 数据增强结果 | 60 秒 | 13:30 |
| 16 | 掩码训练与稳定性 | 45 秒 | 14:15 |
| 17 | 融合各阶段的结果 | 80 秒 | 15:35 |
| 18 | 频次门控的取舍 | 40 秒 | 16:15 |
| 19 | 官方测试结果 | 50 秒 | 17:05 |
| 20 | 方向检查的成功与失败案例 | 65 秒 | 18:10 |
| 21 | 已完成工作与证据边界 | 50 秒 | 19:00 |
| 22 | 下一步实验 | 65 秒 | 20:05 |
| 23 | 融合打分、校准与决策规则 | 主讲跳过；备用约 120 秒 | 不计入 |
| 24 | 任务、方法与评价文献 | 主讲跳过；备用约 30 秒 | 不计入 |
| 25 | 结论 | 55 秒 | 21:00 |

## 第 1 页｜Title / 标题

**建议用时：20 秒；累计结束：00:20。**

讲述重点与动作：报姓名，用一句话说明研究对象。无需完整朗读长标题；看向听众。

### English

Good morning. I'm Peiyang Huang from the Data Engineering Lab. Today, I will present my research on identifying values in news reports, including my current findings and plans for the final thesis.

### 中文对照

大家早上好，我是数据工程实验室的 Peiyang Huang。今天，我会介绍自己关于新闻中价值观识别的研究，包括目前的发现，以及接下来完成学位论文的计划。

## 第 2 页｜A news topic does not identify an actor’s values

**建议用时：40 秒；累计结束：01:00。**

讲述重点与动作：先指摘录中的 public order，再依次指主体、价值和方向。说完例子后停顿，让听众理解标签针对的是报道中的行为。

### English

Consider this report about protests in Chile. The government says it wants to maintain public order. This concerns public security, but whose actions are we describing, and do they support that value?

Here, we focus on the Government and Security Forces. The dataset labels their conduct as aligned with "Have a safe country," meaning that it supports this value.

We are interpreting the conduct described in this report. We are not judging the government's permanent character.

### 中文对照

请看这篇关于智利抗议活动的报道。政府表示，希望维持公共秩序。这涉及公共安全，但我们描述的是谁的行为？这些行为是否支持这个价值？

这里，我们关注的主体是政府与安全部队。数据集把他们的行为标注为与“拥有一个安全的国家”相一致，也就是 aligned，表示这些行为支持这个价值。

我们解释的是这篇报道中描述的行为，并不是在判断政府一贯具有怎样的特征。

## 第 3 页｜Human values and the FEHU task

**建议用时：115 秒；累计结束：02:55。**

讲述重点与动作：本页约 1 分 55 秒：先解释价值的含义，再指分类图中心的黑点和第一圈扇区，说明 54 种价值与 20 个大类。用社会安全的两个具体价值承接上一页；不要逐项读图，也不展开外圈的高层分类。随后用约 30 秒介绍 FEHU 的全称、NTCIR-19 试点评测任务身份、评测对象和统一比较的意义。最后解释 108 个带方向标签，把详细输入输出留给第 4 页。本页不讲实验编号、模型分数或错误统计。

### English

Human values describe what people consider important, such as safety, freedom or fairness. They also include personal goals, such as achievement and pleasure.

The diagram comes from Kiesel and colleagues' ACL 2022 paper. They consolidated a taxonomy mainly based on Schwartz's theory of human values. It contains 54 specific values, grouped into 20 broader categories. The small black dots represent specific values, and the surrounding sectors group them into categories.

For example, the category "Security: societal" includes "Have a safe country" and "Have a stable society." This is the category behind the public-order example on the previous slide. These categories give us a shared vocabulary for describing what matters in an action.

My research takes place in FEHU, a pilot task within the NTCIR-19 evaluation campaign. FEHU stands for Fact-based Event-centric Human-value Understanding. It evaluates whether systems can identify values associated with people or organizations in factual news, across whole articles and individual events. The shared data and evaluation rules allow researchers to compare methods on the same problem.

FEHU adopts this taxonomy and distinguishes whether an actor's conduct supports or contradicts each value. The 54 values therefore give 108 possible labels. This can help us compare how reports portray different actors. Because values are often implicit, the system must connect the actor's reported conduct with the relevant value.

### 中文对照

人类价值观描述的是人们认为什么重要，例如安全、自由或公平。它们也包括个人追求，例如成就和享乐。

这张图来自 Kiesel 等人在 ACL 2022 发表的论文。他们主要以 Schwartz 的人类价值理论为基础，整理出了一套分类体系。其中包含 54 种具体的价值，归入 20 个较宽泛的类别。图中的小黑点代表具体价值，周围的扇区则把它们归入不同类别。

例如，“Security: societal”，也就是社会安全，包括“拥有一个安全的国家”和“拥有一个稳定的社会”。上一页维持公共秩序的例子，就涉及这个类别。这些类别为我们提供了一套共同的词汇，用来描述一个行为涉及哪些重要的价值。

我的研究在 FEHU 这一任务中展开。FEHU 是 NTCIR-19 评测活动中的一个试点评测任务，全称为 Fact-based Event-centric Human-value Understanding，可以理解为“基于事实、以事件为中心的人类价值理解”。它评测系统能否从事实性新闻中，识别与人物或组织相关的价值，覆盖整篇文章和具体事件两个层次。统一的数据和评价规则，让研究者能够在同一个问题上比较不同方法。

FEHU 沿用这套分类，并区分一个主体的行为是在支持还是违背某种价值。因此，54 种价值形成了 108 个可能的标签。这能够帮助我们比较不同报道如何描述不同主体。由于价值经常没有在原文中直接出现，系统需要把主体在报道中的行为与相关价值联系起来。

## 第 4 页｜The task predicts values for each supplied actor

**建议用时：40 秒；累计结束：03:35。**

讲述重点与动作：从上一页的 FEHU 背景收窄到本研究的 Task 1b。沿输入到输出的箭头讲，强调主体列表由组织者提供、每个主体可以有多个标签，以及不同的行为可能让同一价值的两个方向都适用。这里不再讲分类来源或 20／54／108 的数字；最后说明测试时不能使用官方按事件整理的描述。

### English

My work focuses on Task 1b, which makes predictions for the whole article. The input includes the article and a list of actors supplied by the organizers. For each actor, the system selects the relevant value-and-direction labels. Several labels may apply, and different actions can even support both directions of the same value. At test time, we use the article itself. The organizers' event-by-event descriptions are unavailable.

### 中文对照

我的研究重点是 Task 1b，也就是在整篇文章的层次上进行预测。输入包括文章本身，以及组织者提供的主体列表。系统需要为每个主体选出相关的“价值加方向”标签。同一个主体可以对应多个标签，而不同的行为甚至可能让同一种价值的两个方向都适用。测试时，我们依据文章本身进行判断，不能使用组织者按事件整理的描述。

## 第 5 页｜Long-tail labels add to actor and direction errors

**建议用时：25 秒；累计结束：04:00。**

讲述重点与动作：沿频率曲线从左指向右，再指增强目标。纵轴为对数刻度，三个零样本标签未画出。主体归属与方向问题已经在第 3 页说明，这里重点补充长尾数据困难。

### English

The training data adds another difficulty. This curve orders labels from common to rare. Many have few examples, and three have none. The marked labels are those I selected for additional examples.

Limited data makes learning these labels harder, alongside the actor and direction problems we just discussed.

### 中文对照

训练数据还带来了另一项困难。这条曲线把标签按常见到稀有的顺序排列。许多标签只有少量样本，还有三个完全没有样本。标出的点是我选择补充样本的标签。

除了刚才讨论的主体和方向问题，有限的数据也让这些标签更难学习。

## 第 6 页｜Individual contribution and working hypothesis

**建议用时：40 秒；累计结束：04:40。**

讲述重点与动作：对应第 3、5 页的困难，解释自己负责的三种方案。说明队友贡献的边界。这里是对已开展工作的概括，具体方法在后面展开。

### English

I investigate these problems through three approaches. DRA-FEHU generates training examples for labels the classifier misses. WAIPS-02 combines language-model predictions and checks their directions. WAIPS-03 uses label frequency and model scores to revise predictions, then checks disputed directions.

WAIPS-01 is my teammate Liu Dongyang's work. I use one fixed prompt from it for auxiliary predictions.

Fusion has improved the development score. I still need to test how much augmented training contributes to that gain.

### 中文对照

我通过三种方案研究这些问题。DRA-FEHU 为分类器容易漏掉的标签生成训练样本。WAIPS-02 整合语言模型的预测，再检查方向。WAIPS-03 利用标签频次和模型分数修改预测，然后检查存在分歧的方向。

WAIPS-01 是队友 Liu Dongyang 的工作。我使用了其中一个固定提示，获取辅助预测。

融合已经提高了开发集分数，但我还需要验证增强训练对这项提升贡献了多少。

## 第 7 页｜Three research questions guide the evaluation

**建议用时：25 秒；累计结束：05:05。**

讲述重点与动作：依次指三个研究问题，说明它们如何组织后面的实验。不要在这里再次展开方法。

### English

I ask three research questions. Where does recognition fail, especially when we change the article representation or judge direction? How do generated examples and incomplete labels affect training? And can selective revision improve an existing set of predictions?

The experiments will address these questions in order.

### 中文对照

我提出了三个研究问题。识别在哪些地方失败，尤其是在改变文章表示方式或判断方向时？生成样本和不完整标签会怎样影响训练？有选择地修改已有预测，能否改善结果？

后面的实验会按顺序回答这些问题。

## 第 8 页｜Related work uses a different information flow

**建议用时：50 秒；累计结束：05:55。**

讲述重点与动作：按箭头说明两种方法先做什么、后做什么。本地分类器与在线语言模型是不同组件；信息流不同不等于已经证明性能更好。

### English

ValueEval studies values behind arguments. FEHU also asks us to connect a value to a particular actor and determine its direction in a news report.

EAVIT is closer to my system design. It first uses a trained local classifier to select relevant value definitions. An online language model then uses those definitions to make the final prediction.

My fusion system starts with language-model predictions. The local classifier supplies scores to help decide which predictions to keep or change. A language model then checks disputed directions.

This explains the design difference. I have not yet compared the two systems under matched experimental conditions.

### 中文对照

ValueEval 研究论证背后的价值。FEHU 还要求我们在新闻报道中，把价值与具体主体联系起来，并判断方向。

EAVIT 与我的系统设计更接近。它先用训练好的本地分类器选出相关的价值定义，再把这些定义提供给在线语言模型，由语言模型作出最终预测。

我的融合系统先取得语言模型的预测，然后利用本地分类器给出的分数，辅助决定保留或修改哪些预测，最后再由语言模型检查存在分歧的方向。

这就是两种方案在设计上的区别。我还没有在相同实验条件下比较它们的性能。

## 第 9 页｜Two experiment tracks answer different questions

**建议用时：60 秒；累计结束：06:55。**

讲述重点与动作：先指训练实验，再指融合实验。random seed 是控制训练随机过程的设置；三次运行用于观察波动。用固定语言模型输出、替换编码器来解释下一步如何验证二者的联系。

### English

I evaluate training and fusion in separate experiments. For training, I use DeBERTa with LoRA, which lets me adapt the model by training a small set of additional parameters. This local classifier, also called the encoder here, scores all 108 labels for each article and actor. For each condition, I repeat training three times with different random seeds to check whether the results are consistent.

For fusion, I combine language-model predictions with previously saved encoder scores. I cannot yet link those scores to a specific training run in the repeated experiments.

So the fusion gain does not establish the contribution of augmentation. I need to keep the language-model predictions fixed and compare encoders trained with and without generated data.

### 中文对照

我把训练和融合分成两组实验来评估。在训练实验中，我使用 DeBERTa 和 LoRA，通过训练少量新增参数来调整模型。这个本地分类器在这里也称为编码器，它会针对每个文章与主体的组合，为全部 108 个标签打分。每种训练条件都使用三个不同的随机种子运行，以检查结果是否一致。

在融合实验中，我把语言模型的预测与此前保存的编码器分数结合起来。目前，我还不能把这些分数对应到重复实验中的某一次具体训练。

因此，融合取得提升，并不能直接说明增强训练贡献了多少。要验证这一点，我需要固定语言模型的预测，再比较使用与不使用生成数据训练的编码器。

## 第 10 页｜Generate training examples for diagnosed failures

**建议用时：60 秒；累计结束：07:55。**

讲述重点与动作：先讲为何选择 18 个标签，再讲生成和检查。这里的零召回对应基线在开发集、阈值 0.30 下的结果。困难负例是容易让模型误判为目标标签、但实际不应赋予该标签的样本。90 是生成请求数，36 是实际带明确负标注的记录数。

### English

I selected 18 labels with few training examples. At the chosen threshold, the baseline missed every positive example for these labels in the development set. I then asked a language model to generate news examples for specified actors, values and directions.

The first round produced 340 records after automated semantic screening. The second added 900 records through the four modes shown here, but I checked only their structure, such as required fields. That does not tell us whether their labels are correct.

Only six records have been checked by hand. Also, 90 requests for hard negatives produced just 36 records explicitly marking a target label as absent. I need a larger review of label correctness before judging the overall data quality.

### 中文对照

我选出了 18 个训练样本较少的标签。在所选阈值下，基线没有识别出开发集中这些标签的任何正例。随后，我让语言模型针对指定的主体、价值和方向生成新闻样本。

第一轮生成后，经过自动语义筛选，保留了 340 条记录。第二轮通过图中的四种方式增加了 900 条记录，但我只检查了它们的结构，例如必要字段是否齐全。这些检查不能说明标签是否正确。

目前只有六条记录经过了人工检查。另外，90 次困难负例生成请求，实际只得到 36 条明确标注目标标签不存在的记录。在判断整批数据的质量之前，我还需要扩大标签正确性的审查范围。

## 第 11 页｜An unspecified label is not a verified negative

**建议用时：55 秒；累计结束：08:50。**

讲述重点与动作：指 Unspecified 一行。先说明“没有标注”和“已经确认不存在”的区别，再解释训练时如何处理。无需念损失函数公式。

### English

A generated example may describe several values but include an annotation for only one. If another value is left unannotated, we do not know whether it is absent or simply unrecorded.

I tested two ways to train on these examples. The first treats every unannotated label as negative. The second, called masking, ignores those labels when calculating the training loss. In other words, the model is not penalized for its predictions on labels whose answers are unknown. Both methods still use explicitly positive and negative labels.

Masking avoids treating missing annotations as confirmed negatives, but it also gives the model fewer negative training signals. I will show how this trade-off affected the results.

### 中文对照

一个生成样本可能描述了多个价值，但只附带其中一个价值的标注。如果另一个价值没有标注，我们无法确定它是真的不存在，还是仅仅没有被记录下来。

我测试了两种训练方式。第一种把所有未标注的标签都当作负标签。第二种叫 masking，也就是掩码训练：计算训练损失时，忽略这些未标注的标签。换句话说，对于答案尚不清楚的标签，训练过程不会因为模型的预测而惩罚它。两种方法都会利用明确标注的正标签和负标签。

掩码可以避免把缺失标注当成已经确认的负标签，但也会减少模型获得的负向训练信号。后面的结果会说明，这种取舍产生了什么影响。

## 第 12 页｜Revise eligible labels, then check direction

**建议用时：95 秒；累计结束：10:25。**

讲述重点与动作：沿主预测、删除、添加、方向检查的流程讲。这里只解释校准的用途和文章分组，保序回归公式与决策阈值留在第 23 页回答。

### English

The fusion system starts with E6b. It uses the Flash model to predict values from event descriptions generated from the article. I then combine four auxiliary predictions with the saved encoder scores to assess which labels to remove or add.

The removal and addition steps apply only to labels with more than 130 positive training examples. This frequency gate limits these changes to labels with more data. I chose the cutoff during development; I have not established that it is optimal. All 18 augmentation targets fall outside this gate.

To decide which predictions to change, I calibrate the combined scores: I use development annotations to estimate how likely a prediction is to be correct. I fit the calibration on one group of articles and apply it to the other, then swap the groups.

Finally, if the system predicts one direction and an auxiliary prediction supports the opposite, Flash checks the direction again. This check can also affect the 18 target labels.

### 中文对照

融合系统以 E6b 为起点。E6b 先根据文章生成事件描述，再用 Flash 模型预测价值。接着，我结合四组辅助预测和此前保存的编码器分数，判断哪些标签应该删除或添加。

系统只对训练正例超过 130 个的标签执行删除和添加。这就是频次门控，它把修改范围限制在数据相对充足的标签上。我在开发阶段选定了这个阈值，还没有证明它是最优的。18 个增强目标都不在这个修改范围内。

为了决定修改哪些预测，我会校准组合分数，也就是利用开发集标注，估计一个预测正确的可能性。我用一组文章拟合校准规则，再应用到另一组文章上，然后交换两组的角色。

最后，如果系统只预测了一个方向，而辅助预测支持相反方向，就让 Flash 再检查一次方向。这项检查也可能影响那 18 个目标标签。

## 第 13 页｜Keep data splits and evaluation measures distinct

**建议用时：65 秒；累计结束：11:30。**

讲述重点与动作：文章数量只读一遍，随后移向三个指标。reference annotations 指数据集用于判分的参考标签；不需要朗读公式。

### English

The dataset has 1,228 training articles, 177 development articles and 175 test articles. I use the development set for local comparisons and the official test scores to evaluate the submitted system.

I report three measures. Micro-F1 balances correct predictions against false predictions and missed labels across the dataset. Macro-F1 calculates F1 for each label present in the reference annotations, then averages them equally. This makes poor performance on rare labels easier to see.

Direction reversal rate measures how often a prediction opposes the reference direction when only one direction is annotated. A low reversal rate alone is not enough: a system that predicts very little may avoid reversals while missing many valid labels.

### 中文对照

数据集有 1,228 篇训练文章、177 篇开发文章，以及 175 篇测试文章。我使用开发集进行本地比较，再通过官方测试成绩评估提交的系统。

我报告三个指标。Micro-F1 综合整个数据集中的正确预测、错误预测和遗漏情况。Macro-F1 则先为参考标注中出现的每个标签计算 F1，再对各标签等权平均，因此更容易看出模型在稀有标签上的不足。

方向反转率衡量的是：当参考标注只给出一个方向时，预测与该方向相反的情况有多常见。只看较低的反转率还不够，因为一个几乎不作预测的系统，也可能很少出现反转，同时却漏掉大量正确标签。

## 第 14 页｜Representation and model configuration differ

**建议用时：60 秒；累计结束：12:30。**

讲述重点与动作：先讲左侧 E1、E6、E6b 的文章处理方式，再讲右侧 E6c 的模型变化。E6c 与 E6b 使用相同事件描述。

### English

The first question is whether changing the article representation helps. On the left, all three systems use Flash. E1 reads the article directly. E6 first breaks it into shorter event descriptions. This raises Macro-F1 but lowers Micro-F1.

E6b generates fewer, broader descriptions: the median number falls from twelve to eight. Its Micro-F1 improves from about 0.541 to 0.550 compared with E6.

On the right, E6c uses the same descriptions as E6b but switches the predictor to Pro with thinking disabled. Its Micro-F1 falls to about 0.534.

Based on these comparisons, I chose E6b as the primary system. It still makes direction errors, which the fusion stage tries to address.

### 中文对照

第一个问题是，改变文章的表示方式是否有帮助。左边三个系统都使用 Flash。E1 直接读取文章；E6 先把文章整理成较短的事件描述。这种处理提高了 Macro-F1，但降低了 Micro-F1。

E6b 生成的事件描述更少，每条覆盖的内容更广，描述数量的中位数从十二条减少到八条。与 E6 相比，它的 Micro-F1 从约 0.541 提高到了 0.550。

右边的 E6c 使用与 E6b 相同的事件描述，但把预测模型换成关闭 thinking 的 Pro，Micro-F1 降到了约 0.534。

根据这些比较，我选择 E6b 作为主系统。不过，它仍然会判断错方向，后面的融合阶段会尝试处理这些错误。

## 第 15 页｜Ranking improves; target prediction remains weak

**建议用时：60 秒；累计结束：13:30。**

讲述重点与动作：依次指两个图和 Target F1。强调“分数排序改善”与“在阈值下正确输出标签”是不同问题；两图纵轴范围不同。最后的重复已有样本就是过采样。

### English

For the training question, I compare two conditions: official data alone, or official data plus 900 generated records. Here, I treat unannotated labels as negative. Across three runs, mean Macro-F1 rises from about 0.028 to 0.089. Target AUC rises from about 0.513 to 0.624, and both measures improve in every run.

AUC tells us whether the classifier gives positive examples higher scores than negative examples. However, better ordering does not necessarily produce correct labels at the chosen cutoff. At threshold 0.30, target F1 is still only about 0.032.

Generated data helps in this comparison. To test whether targeting particular labels matters, I still need comparisons with equally sized generic generation and repeated copies of existing examples.

### 中文对照

对于训练方面的问题，我比较了只用官方数据，以及额外加入 900 条生成记录这两种条件。这里把未标注的标签当作负标签。三次运行的平均 Macro-F1 从约 0.028 提高到 0.089，目标标签的 AUC 从约 0.513 提高到 0.624，而且每次运行的这两项指标都有改善。

AUC 反映分类器能否给正例打出比负例更高的分数。不过，排序更好，并不意味着在选定的分数阈值下就能正确输出标签。在 0.30 的阈值下，目标标签的 F1 仍然只有约 0.032。

在这个比较中，生成数据确实有帮助。但要判断针对特定标签生成样本是否有额外作用，我还需要与同等规模的一般生成，以及重复使用已有样本进行比较。

## 第 16 页｜Masking is sensitive to data and random seed

**建议用时：45 秒；累计结束：14:15。**

讲述重点与动作：每个点是一轮训练。指表现特别高的那个点，再讲两个没有正确目标预测的结果。这里比较的是相同数据量下两种标签处理规则。

### English

Each point represents one training run. With the same 900 records, masking gives a lower mean Macro-F1 than treating unannotated labels as negative.

When I combine both generation rounds, giving 1,240 records, masking has a higher mean than the negative-label rule. But one unusually strong run raises that average. In two of the three masked runs, the classifier makes no correct predictions for the target labels.

So I cannot recommend masking based on the average alone. Its benefit is inconsistent, and I need to understand why changing the data or random seed changes the result so much.

### 中文对照

每个点代表一次训练。使用相同的 900 条记录时，掩码训练的平均 Macro-F1 比把未标注标签当作负标签更低。

当我合并两轮数据，使用 1,240 条记录时，掩码训练的平均值又高于把未标注标签当作负标签的方式。但这个平均值主要是被一次表现特别好的运行拉高的。在三次掩码训练中，有两次没有正确预测出任何目标标签。

因此，我不能只根据平均值就推荐掩码训练。它的收益并不稳定，我还需要弄清楚，为什么更换数据或随机种子会让结果产生这么大的变化。

## 第 17 页｜Removal and addition provide most of the gain

**建议用时：80 秒；累计结束：15:35。**

讲述重点与动作：沿四个阶段解释分数变化，再指总体差值区间。重采样比较的是同一批文章上的两个已保存输出，不是重新训练模型。

### English

For fusion, the primary system starts at 0.5496 Micro-F1. The system first removes predictions with weak support. This reduces false predictions, but also loses some correct ones. It then adds missing labels supported by the auxiliary predictions and classifier scores. This step gives a larger further improvement. Checking disputed directions adds a smaller gain, bringing the final score to 0.5817.

The total increase is 3.21 percentage points. To estimate uncertainty, I repeatedly resample articles and compare the two systems on the same sampled articles. The resulting 95 percent interval is 2.09 to 4.33 percentage points, entirely above zero.

This interval describes the overall difference between the saved outputs. It does not tell us how much new training or language-model runs would vary. It also does not remove the effect of selecting the system on development data, or establish a separate significant gain for each stage.

### 中文对照

在融合实验中，主系统的 Micro-F1 起点是 0.5496。系统先删除支持较弱的预测，这减少了错误预测，但也损失了一些正确预测。随后，系统根据辅助预测和分类器分数，添加遗漏的标签。这一步带来了更大的后续提升。最后，检查存在分歧的方向又带来了一点改善，使最终分数达到 0.5817。

整体提升是 3.21 个百分点。为了估计这个差值的不确定性，我反复对文章进行重采样，每次都在同一批抽样文章上比较两个系统。得到的 95% 区间为 2.09 到 4.33 个百分点，整个区间都高于零。

这个区间描述的是已保存输出之间的整体差值。它不能说明重新训练或重新运行语言模型后，结果会有多大波动；也不能消除在开发集上选择系统的影响，更不能据此认定每个阶段都单独取得了显著提升。

## 第 18 页｜The frequency gate protects label balance

**建议用时：40 秒；累计结束：16:15。**

讲述重点与动作：指两个方向相反的指标变化，说明为什么这是一个取舍。这个实验只比较删除阶段，不代表完整系统的门控贡献已经测清。

### English

Here, I compare the removal step with and without the frequency gate. Without the gate, the system can also remove rare labels. Micro-F1 rises by 0.95 percentage points, but Macro-F1 falls by 2.46 points.

Keeping the gate therefore gives better average performance across labels in this comparison, although the overall Micro-F1 is lower.

This experiment covers removal only. I still need to repeat the comparison in the complete system to measure the gate's full contribution.

### 中文对照

这里，我比较删除阶段保留和去掉频次门控的结果。去掉门控后，系统也可以删除稀有标签。Micro-F1 提高了 0.95 个百分点，但 Macro-F1 下降了 2.46 个百分点。

因此，在这个比较中，保留门控可以获得更好的标签平均表现，但整体 Micro-F1 会低一些。

这项实验只考察了删除阶段。要确定门控对整个系统的贡献，我还需要在完整系统中重复这个比较。

## 第 19 页｜Official test results show strengths and limits

**建议用时：50 秒；累计结束：17:05。**

讲述重点与动作：先指 WAIPS-03，再指 IIUoT-01 和组织者基线。清楚区分 Macro-F1 的数值最高与官方按 Micro-F1 排名。

### English

On the official test, WAIPS-03 achieves about 0.581 Micro-F1 and 0.395 Macro-F1. Its Macro-F1 is the highest score among the participant submissions shown here, but the difference from IIUoT-01 is only 0.22 percentage points. I have not established whether that small difference is statistically significant.

The official ranking uses Micro-F1, where IIUoT-01 scores higher. The organizer baseline scores higher on both measures.

Compared with WAIPS-02, WAIPS-03 improves both F1 measures but makes more direction reversals. The systems also use different numbers of model calls, so this comparison does not isolate the benefit of the fusion rule itself.

### 中文对照

在官方测试中，WAIPS-03 的 Micro-F1 约为 0.581，Macro-F1 约为 0.395。它的 Macro-F1 在这里列出的参赛提交中数值最高，但只比 IIUoT-01 高 0.22 个百分点。我还没有确定这个很小的差异是否具有统计显著性。

官方排名使用 Micro-F1，而 IIUoT-01 的这项分数更高。组织者基线在这两个指标上都更高。

与 WAIPS-02 相比，WAIPS-03 的两项 F1 都有所提高，但方向反转也更多。此外，两个系统调用模型的次数不同，因此不能用这个比较单独确定融合规则本身带来了多少收益。

## 第 20 页｜Direction checks can fix or introduce an error

**建议用时：65 秒；累计结束：18:10。**

讲述重点与动作：分开讲左右两个例子，每次都说清主体、价值、修改前后方向及参考答案。右侧回扣开场的智利案例。

### English

These examples show why direction checking still needs work. On the left, the article discusses sanctions on Venezuela. A quoted speaker expects the situation to deteriorate. For the US Government and Allied Nations, the checker changes "Have a stable society" from aligned to contradictory. This matches the dataset annotation and corrects the earlier prediction.

On the right, we return to the Chile example. The Government and Security Forces state an intention to maintain public order. The checker changes "Have a safe country" from aligned to contradictory, although the reference label is aligned. It turns a correct prediction into an error.

The saved decision does not explain that change. I need to examine the supporting passage and distinguish the actor's stated intention from actions and expected consequences.

### 中文对照

这两个例子说明，方向检查还有需要改进的地方。左边的文章讨论对委内瑞拉的制裁，引文中的发言者预计局势会恶化。对于美国政府及其盟国，检查模型把“拥有稳定的社会”从 aligned 改成 contradictory。这与数据集标注一致，修正了原来的预测。

右边回到智利的例子。政府与安全部队表达了维持公共秩序的意图。检查模型把“拥有一个安全的国家”从 aligned 改成 contradictory，但参考标签是 aligned。也就是说，它把原本正确的预测改错了。

保存的决策没有解释为什么要这样修改。我需要进一步检查支持判断的原文，区分主体表达的意图、实际行为，以及预期后果。

## 第 21 页｜What the current evidence can establish

**建议用时：50 秒；累计结束：19:00。**

讲述重点与动作：先交代已经实现和测量了什么，再说明仍需验证的贡献，以及实验选择和记录方面的限制。语气平实，不长篇自我辩解。

### English

At this stage, I have implemented the methods and measured their performance. The next step is to identify which components cause the gains.

I used the development set to select target labels, choose trained models and design decision rules, as well as to fit calibration. Fitting calibration on separate article groups does not undo those earlier choices, so the development results may be optimistic.

I also have a gap in the experiment records. The final list of 18 targets is available, but the full procedure for reducing 39 candidates to 18 was not preserved. I need to document that selection in future experiments.

### 中文对照

目前，我已经实现了这些方法，并测量了它们的表现。下一步需要确认，哪些组件真正带来了这些提升。

我既使用开发集选择目标标签、挑选训练好的模型和设计决策规则，也用它来拟合校准。即使校准时使用不同的文章组，也不能消除之前那些选择带来的影响，因此开发集结果可能偏乐观。

实验记录也有一处缺口。最终的 18 个目标标签清单还在，但从 39 个候选缩减到 18 个的完整过程没有保留下来。后续实验中，我需要完整记录这个选择过程。

## 第 22 页｜Eight-week plan to test the contributions

**建议用时：65 秒；累计结束：20:05。**

讲述重点与动作：每个阶段讲清准备比较什么、它回答什么问题。八周是暂定工作安排，具体根据中期反馈调整。

### English

I propose an eight-week plan, subject to midterm feedback. In the first two weeks, I will fix the prompt outputs and compare fusion without an encoder, with an encoder trained on official data, and with one trained on augmented data. I will use the same calibration procedure and report score differences with uncertainty intervals.

In weeks three and four, I will compare equal amounts of targeted generation, generic generation and repeated existing examples, using three training runs per condition. This will test whether targeting helps beyond adding more data.

In weeks five to eight, I will separate system selection from evaluation, audit generated labels and check rerun stability. These comparisons remain useful even if they show no gain. Task 2 and further evidence studies come after these core tests.

### 中文对照

我提出了一个八周计划，具体安排还会根据中期反馈调整。前两周，我会固定提示输出，比较三种融合条件：不用编码器、使用官方数据训练的编码器，以及使用增强数据训练的编码器。我会采用相同的校准流程，报告分数差值及其不确定性区间。

第三至第四周，我会使用同等数量的数据，比较针对性生成、一般生成，以及重复已有样本。每种条件训练三次，以检验针对性生成是否比单纯增加数据更有帮助。

第五至第八周，我会分开用于系统选择和评估的数据，检查生成标签的正确性，并检验重复运行是否稳定。即使没有得到提升，这些比较仍然能回答研究问题。Task 2 和进一步的证据研究会放在这些核心检验之后。

## 第 23 页｜Fusion scores, calibration and decision rules

**默认主讲跳过；问答备用约 120 秒。**

讲述重点与动作：问到规则时使用，只回答相关部分即可。e、o、p 是变量名，公式按句子解释。若完整讲完本页，预留约两分钟。

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

## 第 24 页｜References: task, methods and evaluation

**默认主讲跳过；问答备用约 30 秒。**

讲述重点与动作：按问题指向相应文献，不逐条念标题或网址。

### English

This page lists the main references. The FEHU overview and WAIPS manuscript provide the task setting and official scores. I use EAVIT to explain the design comparison, and build on established methods such as DeBERTa, LoRA and partial-label learning. The evaluation references explain the issues of system selection and uncertainty discussed earlier.

### 中文对照

这一页列出了主要参考文献。FEHU 综述和 WAIPS 稿件提供了任务设定与官方成绩。我用 EAVIT 说明设计上的区别，也使用了 DeBERTa、LoRA 和部分标签学习等已有方法。评价方面的文献则解释了前面讨论的系统选择与不确定性问题。

## 第 25 页｜Conclusion: recover values and control the errors

**建议用时：55 秒；累计结束：21:00。**

讲述重点与动作：回到研究目标，再总结结果与下一步。最后一句说完后停顿，将结论页留在屏幕上供提问。

### English

My goal is to identify the values associated with each actor's reported conduct and determine whether that conduct supports or contradicts them.

Generated examples help the classifier rank positive examples above negative ones, but it still misses many target labels at the chosen threshold. Fusion improves development Micro-F1 by 3.21 percentage points and reaches about 0.581 on the official test.

My approach combines targeted training, selective prediction changes and a separate direction check. For the final thesis, I will test their individual contributions under matched conditions and examine the evidence behind direction judgments.

### 中文对照

我的目标是识别新闻所描述的各主体行为涉及哪些价值，并判断这些行为是在支持还是违背这些价值。

生成样本帮助分类器把正例排在负例之前，但在所选阈值下，它仍然会漏掉许多目标标签。融合使开发集 Micro-F1 提高了 3.21 个百分点，并在官方测试集上达到约 0.581。

我的方案结合了针对性训练、有选择地修改预测，以及单独的方向检查。在最终学位论文阶段，我会在相同条件下检验它们各自的贡献，并检查方向判断背后的文本证据。

## 排练时的重点

1. **先理解每页的解释顺序。** 方法页讲清“我遇到了什么问题、让哪个组件做什么、为什么这样做”；结果页讲清“比较了什么、数字怎样变化、能得出什么结论”。中英文段落一一对应，可以先用中文复述，再练英文。
2. **用五个时间点检查节奏。** 第 7 页结束约 05:05，第 12 页约 10:25，第 17 页约 15:35，第 22 页约 20:05，结论结束约 21:00。先完成一遍计时彩排，再判断是否需要缩短某页。
3. **练熟数字读法。** “3.21 percentage points” 读作 three point two one percentage points，表示百分点差值。0.5808 在主讲稿中简读为 about zero point five eight one，精确值仍在 PPT 中。表格里没有写进口头稿的数值无需全部朗读。
4. **保持术语一致。** actor 是人物或组织；label 是价值与方向的组合；本地 classifier 在本研究中也称 encoder；reference annotations 是数据集用于判分的参考标注。第一次出现时讲清含义，之后沿用相同称呼。
5. **解释方法时留出听众跟上的时间。** 第 11 页说完“没有标注不代表不存在”后停一下；第 12 页指到对应模块再讲下一步；第 15 页说完 AUC 后，再解释为什么 F1 仍然低。这些停顿比逐句换词更能改善听感。
6. **保留结论的适用范围。** 训练增强与融合是两组实验，当前不能直接把融合收益归因于增强；18 个增强目标不参与删除和添加，方向检查仍可能影响它们；Macro-F1 数值最高不等于官方排名第一；bootstrap 区间针对保存输出的整体差值。正文已经说明这些限制，问答时按相同口径回答。

内容依据：上述 PPT 的页面、图表，FEHU 本地价值分类文件，`RH_test/E1_fewshot_repair/reports/E1_REPORT.md` 第 2 节，以及已提交论文 `HUANG_midterm.pdf` / `Huang_FEHU_Midterm_Paper.tex`。本稿未加入新的实验结果；未来实验均按计划表述。


第 3 页图像与任务来源（2026-09-29 核查）：[Kiesel 等，ACL 2022](https://aclanthology.org/2022.acl-long.306/)；[NTCIR-19 试点评测任务列表](https://research.nii.ac.jp/ntcir/ntcir-19/tasks.html)；[FEHU 当前任务说明](https://sites.google.com/view/ntcir19fehu/task-description)。NTCIR 总览页仍保留早期生成子任务的介绍，本稿关于文章／子事件识别的说明依据 FEHU 当前任务页面及正式资源。

## 备查：20 个大类与完整 54 种价值

本节供准备和问答使用，不计入主讲时间。英文名称逐字保留 FEHU 文件中的写法；中文为理解用释义，并非官方译名。分类的论文来源是 [Kiesel 等，ACL 2022，图 1 与表 1](https://aclanthology.org/2022.acl-long.306/)，主要基于 Schwartz 等人的价值理论并整合其他价值清单。FEHU 沿用该体系；本地名称与映射可查 [human_value_taxonomy.json](../../dataset/hv_categories/human_value_taxonomy.json)。这是一套有文献依据的研究分类，不应表述为全世界唯一的 54 项价值标准。

每一种细粒度价值都对应 aligned 和 contradictory 两个标签。因此，**108 指 54 × 2 个带方向标签，不是 108 种独立价值，更不是 108 条道德准则**。论文中的 Level 1 是细粒度的 54 项，Level 2 是较粗的 20 类。

| 序号 | 大类 | 细粒度价值及中文释义 |
| --- | --- | --- |
| 1 | Self-direction: thought（自主：思想） | Be creative（有创造力）；Be curious（有好奇心）；Have freedom of thought（拥有思想自由） |
| 2 | Self-direction: action（自主：行动） | Be choosing own goals（选择自己的目标）；Be independent（独立自主）；Have freedom of action（拥有行动自由）；Have privacy（拥有隐私） |
| 3 | Stimulation（刺激与新奇） | Have an exciting life（拥有令人兴奋的生活）；Have a varied life（拥有多样化的生活）；Be daring（敢于冒险） |
| 4 | Hedonism（享乐） | Have pleasure（享有乐趣） |
| 5 | Achievement（成就） | Be ambitious（有抱负）；Have success（取得成功）；Be capable（有能力）；Be intellectual（重视智识）；Be courageous（有勇气） |
| 6 | Power: dominance（权力：支配） | Have influence（拥有影响力）；Have the right to command（拥有发号施令的权力） |
| 7 | Power: resources（权力：资源） | Have wealth（拥有财富） |
| 8 | Face（面子与声誉） | Have social recognition（获得社会认可）；Have a good reputation（拥有良好声誉） |
| 9 | Security: personal（安全：个人） | Have a sense of belonging（拥有归属感）；Have good health（拥有健康）；Have no debts（没有债务）；Be neat and tidy（整洁有序）；Have a comfortable life（拥有舒适的生活） |
| 10 | Security: societal（安全：社会） | Have a safe country（拥有安全的国家）；Have a stable society（拥有稳定的社会） |
| 11 | Tradition（传统） | Be respecting traditions（尊重传统）；Be holding religious faith（持有宗教信仰） |
| 12 | Conformity: rules（遵从：规则） | Be compliant（遵守规则）；Be self-disciplined（自律）；Be behaving properly（举止得当） |
| 13 | Conformity: interpersonal（遵从：人际） | Be polite（有礼貌）；Be honoring elders（尊敬长者） |
| 14 | Humility（谦逊） | Be humble（谦逊）；Have life accepted as is（接受生活原本的样子） |
| 15 | Benevolence: caring（仁爱：关怀） | Be helpful（乐于助人）；Be honest（诚实）；Be forgiving（宽恕他人）；Have the own family secured（保障自己的家庭）；Be loving（关爱他人） |
| 16 | Benevolence: dependability（仁爱：可靠） | Be responsible（负责任）；Have loyalty towards friends（忠于朋友） |
| 17 | Universalism: concern（普遍主义：关切） | Have equality（享有平等）；Be just（公正）；Have a world at peace（拥有和平的世界） |
| 18 | Universalism: nature（普遍主义：自然） | Be protecting the environment（保护环境）；Have harmony with nature（与自然和谐共处）；Have a world of beauty（拥有美好的世界） |
| 19 | Universalism: tolerance（普遍主义：宽容） | Be broadminded（思想开明）；Have the wisdom to accept others（有接纳他人的智慧） |
| 20 | Universalism: objectivity（普遍主义：客观） | Be logical（讲逻辑）；Have an objective view（保持客观看法） |

### 问答准备：为什么不能直接让语言模型判断？

**English**

I do use a language model as a baseline. The question is whether its labels are reliable enough for this task. In the archived E1 development run, it produced 1,129 unmatched predictions and missed 1,062 reference labels. I study whether targeted examples and selective revision can reduce these errors. These results describe that model and prompt on this benchmark. They do not show that every current language model performs poorly, and they do not establish the cause of every error.

**中文对照**

我已经把语言模型作为基线使用。研究问题是，它给出的标签对这项任务而言是否足够可靠。在保存的 E1 开发集运行中，它产生了 1,129 个未匹配的预测，并漏掉了 1,062 个参考标签。我研究针对性样本与选择性修改能否减少这些错误。这些结果对应的是该模型和提示在本基准上的表现，不能说明所有当前语言模型都表现很差，也没有确定每个错误的具体成因。

**证据口径**

- E1 的匹配单位是文章中的主体、价值、方向组合。2,457 个预测中有 1,328 个正确匹配，1,129 个未匹配；2,390 个参考标签中有 1,062 个被遗漏。
- E1 的 Micro-F1 为 0.5480；F1 不是“判断正确率”，不能说成“54.8% 的文章判断正确”。
- 隐含价值、多主体、意图与结果差异是任务中的理解困难。当前没有逐项受控实验来证明它们各自造成了多少 E1 错误。
- 参考标注是本基准的评价依据，不是关于某个主体道德品质的绝对裁决。
