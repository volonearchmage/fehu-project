# 2026 年 10 月 15 日组会：PPT 设计与演讲稿

**主题：表达反思、Task 1 改进与 Task 2 完成计划**  
**发表人：Peiyang Huang**  
**实验室：Data Engineering Lab, IPS, Waseda University**  
**对应 PPT：[Research Progress（12 页）](2026-10-15_Research_Progress_12slides_task1_task2.pptx)**

## 1. 本次发表的重点与篇幅

总计 12 页。封面之外，用三页讲清上次表达的问题与改法，之后将主要篇幅用于研究。讲述和指图预算为 **12 分 30 秒**，这是排练预算，实际发表只朗读一种语言。

| 页码 | 内容 | 讲述目的 |
| --- | --- | --- |
| 1 | 学校模板封面 | 姓名、日期、实验室与本次目的 |
| 2–4 | 表达反思及具体改法 | 明确哪里没讲清楚，现场示范怎样讲 |
| 5–9 | Task 1 的进一步改进与验证 | 以已有结果为起点，具体讨论 subevent 参考、分类器与 fusion |
| 10–11 | Task 2 的完成路径与比较 | 把实现、完整评价、方法验证分别说清 |
| 12 | 研究优先级与下次交付 | 确定最先完成的实验与输出 |

反思部分到第 4 页结束，不再增加完整末期发表目录、最终论文故事线或重复的方法总览。第 3–4 页是说明改法的短示范。

老师明确给出的反馈是“两位新听众没有听懂”。术语过早、系统名称过多、比较关系不清，是根据原稿作出的自我诊断，不能表述成老师逐项提出的意见。

## 2. 视觉设计与内容边界

直接沿用 [Huang Jiahui 的 PPT](Huang_Jiahui_20261013.pptx) 封面及正文母版，并参考 [Jiang Boyuan 的 PPT](Jiang_Boyuan_20261013.pptx) 的正文风格。

- 16:9 白底。封面保留原模板的红色装饰、学校图标和校名，标题为 Research Progress，姓名为 Peiyang Huang，日期为 2026/10/15，下方保留实验室信息。
- 正文沿用暗红色 Times New Roman 标题、标题下横线和右下角页码。正文为 Arial；母版校名保留原字体。
- 表格沿用浅蓝灰表头和交替底色，保持原生可编辑。主句与表格承担主要信息，完整解释放中英讲稿和 PPT 备注。
- 所有新方法均标为 Proposed 或 Planned，不写成已实现或已验证的效果。
- 工厂与志愿者的文本、标签以及错误候选均为教学示意，不是数据集原文、金标或真实模型错误。

需要持续区分的研究边界：

1. **现有 E6b 已有自主分段。** 新计划是怎样利用事件信息核验修改，以及怎样使用 TRAIN 子事件监督，而不是将“加入 subevent”本身作为新功能。
2. **Task 1 推理保持文章输入。** 可以由输入文章生成事件描述、定位原文；官方 TRAIN subevent 可用于训练。不能把 DEV 子事件或 Task 2 测试子事件接入 Task 1 推理。
3. **局部事件是证据入口。** 它不自动构成完整或正确的依据，仍需核对主体、原文和必要上下文。同一主体、价值也可能在不同事件中支持两个方向。
4. **已有完整系统比较与新消融分开。** 官方分数支持整体系统的表现，不能单独说明规则、分类器、增强或方向检查的因果贡献。
5. **本次交付是演示与实验设计。** 没有启动新的模型训练或 API 实验。

## 3. 12 页设计、逐页概述与中英讲稿

| 页码 | 标题 | 用时 | 累计结束 |
| --- | --- | ---: | ---: |
| 1 | Research Progress | 20 秒 | 0:20 |
| 2 | Presentation Problems | 45 秒 | 1:05 |
| 3 | A Concrete Task Example | 55 秒 | 2:00 |
| 4 | A Clearer Method Explanation | 50 秒 | 2:50 |
| 5 | Task 1: Current Results | 65 秒 | 3:55 |
| 6 | Task 1: Subevent References | 80 秒 | 5:15 |
| 7 | Task 1: Event-based Verification | 80 秒 | 6:35 |
| 8 | Task 1: Fusion and Classifier | 80 秒 | 7:55 |
| 9 | Task 1: Validation Plan | 75 秒 | 9:10 |
| 10 | Task 2: Completion Steps | 75 秒 | 10:25 |
| 11 | Task 2: Evaluation and Fusion | 75 秒 | 11:40 |
| 12 | Research Priorities | 50 秒 | 12:30 |

### 第 1 页：Research Progress

**状态：** 封面；**建议用时：** 20 秒。

**本页概述**

封面沿用学校母版，署名 Peiyang Huang，日期为 2026/10/15，保留实验室信息。开场说明本次重点是 Task 1 的改进与 Task 2 的完成计划。

**页内文案**

Research Progress  
Peiyang Huang  
2026/10/15  
Data Engineering Lab, IPS, Waseda Univ.

**English script**

Today I will briefly explain what made my previous presentation difficult to follow and how I will change it. Most of this talk concerns the next research steps: improving Task 1 with subevent references and better fusion decisions, then completing Task 2.

**中文讲稿**

今天我先简要说明上次发表哪里没有讲清楚，以及准备怎样改。之后把主要时间留给接下来的研究：如何利用 subevent 参考和更好的融合决策改进 Task 1，再说明如何完成 Task 2。

**演讲与备课建议**

封面沿用参考稿的标题、姓名日期和实验室位置。只讲本次目的，不再介绍整个末期发表的目录。

**来源**

- [docs/论文/Huang_FEHU_Midterm_Paper.tex: author Peiyang Huang](../../../docs/论文/Huang_FEHU_Midterm_Paper.tex)
- [docs/ppt/2026-10-02_Huang_Midterm_Defense_Research_Story_v5_15min_ZH_QA.pptx: Data Engineering Lab, IPS, Waseda University](../../../docs/ppt/2026-10-02_Huang_Midterm_Defense_Research_Story_v5_15min_ZH_QA.pptx)
- Presentation date requested by the user: 15 October 2026

### 第 2 页：Presentation Problems

**状态：** Reflection 1 of 3；**建议用时：** 45 秒。

**本页概述**

指出上次的三处表达问题：没有先给出具体输出、系统名称过多、实验比较的含义不够清楚。这些是对老师反馈的自我诊断。

**页内文案**

Feedback: new listeners could not follow the project.

1  Output was not concrete

The taxonomy appeared before a visible example.

2  Too many system names

The role of each component was hard to remember.

3  Comparisons were not clear enough

The baseline, improvement, and remaining error needed explanation.

**English script**

Two teachers who were new to the project said they could not follow the presentation. My diagnosis is that I introduced the taxonomy before showing a concrete output, used too many system names, and moved between experiments without making each comparison clear. As a result, the audience had to remember details before understanding the research question. These are my interpretations of the feedback. The next two slides show the changes I will make.

**中文讲稿**

两位第一次接触项目的老师表示没有听懂。我的判断是，我在展示具体输出之前就介绍了分类体系，使用了太多系统名称，切换实验时也没有先讲清比较对象。听众还没有理解研究问题，就需要记住很多细节。这些是我对反馈的自我诊断，接下来两页直接展示准备怎样改。

**演讲与备课建议**

区分老师实际给出的反馈与自己的原因分析。控制在约 45 秒，不展开整套末期发表安排。

**来源**

- User feedback in this conversation
- [docs/ppt/2026-10-01_Huang_Midterm_Speaker_Script_Research_Story_v4_EN_ZH_15min.md](../../../docs/ppt/2026-10-01_Huang_Midterm_Speaker_Script_Research_Story_v4_EN_ZH_15min.md)

### 第 3 页：A Concrete Task Example

**状态：** Reflection 2 of 3 · illustrative example；**建议用时：** 55 秒。

**本页概述**

用工厂排污与志愿者清理的例子先讲清输入、主体、价值和方向，让新听众看见系统究竟要输出什么。

**页内文案**

A factory releases untreated wastewater into a river.  
Volunteers remove waste to protect the environment.

| Actor | Value shown | Direction |
| --- | --- | --- |
| Factory | Protecting the<br>environment | Contradictory<br>(goes against) |
| Volunteers | Protecting the<br>environment | Aligned<br>(supports) |

Input: article + supplied actors  
Output: values and directions for each actor

**English script**

I will begin with this short example. A factory releases untreated wastewater, while volunteers clean the river. Both actions concern environmental protection, but their directions differ. Task 1 receives an article and supplied actors, and predicts values and directions for each actor. I will show this output before introducing the full taxonomy. The example is illustrative. Its labels describe the reported conduct, rather than a permanent judgment about the actor.

**中文讲稿**

我会先用这个短例子解释任务。工厂排放未经处理的污水，志愿者清理河流，两种行为都涉及环境保护，但方向不同。Task 1 接收文章和给定主体，为各主体预测价值和方向。我会先展示这样的输出，再介绍必要的分类体系。这是教学示意，标签描述的是报道中的行为，不是对主体永久品格的判断。

**演讲与备课建议**

先指主体，再指相同价值和不同方向。Aligned 用“支持”，Contradictory 用“相悖”解释，不在这里展开全部标签数量。

**来源**

- [dataset/hv_categories/human_value_level1_values.json](../../../dataset/hv_categories/human_value_level1_values.json)
- [dataset/hv_categories/direction_mapping.json](../../../dataset/hv_categories/direction_mapping.json)
- Illustrative example, not a dataset record or saved system output

### 第 4 页：A Clearer Method Explanation

**状态：** Reflection 3 of 3；**建议用时：** 50 秒。

**本页概述**

用一个漏标说明 fusion 的用途，再解释辅助预测如何支持修改，最后明确比较对象与结果边界。主讲用组件作用代替实验编号。

**页内文案**

1  Show one error

The initial prediction misses the  
volunteer–environment label.

2  Explain one change

Auxiliary predictions can support adding it.  
Explain the role before the formula.

3  Explain the result

Name the baseline and data split.  
State the improvement and remaining error.

Check: can a new listener explain why fusion is needed?

**English script**

For the method, I will continue with the same example. Suppose the initial prediction misses the volunteers supporting environmental protection. I can then explain why auxiliary predictions may justify adding that label. This introduces the purpose of fusion before its formulas or system identifiers. When I show a result, I will first name the baseline and data split, then explain the improvement and remaining error. I will check whether a new listener can restate the task and the purpose of fusion.

**中文讲稿**

讲方法时继续用同一个例子。假设初始预测漏掉了志愿者支持环境保护的标签，就解释为什么辅助预测可能支持补上它。这样听众先理解 fusion 要解决什么问题，再接触公式和系统编号。讲结果时先说明基线和数据划分，再说明改善与剩余错误。最后请新听众用自己的话复述任务和 fusion 的作用，检验是否真的讲清楚。

**演讲与备课建议**

到本页结束反思部分。后面直接进入研究计划，不再增加末期发表结构、叙事原则或完整方法介绍页。

**来源**

- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: fusion method and comparison limits](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)
- Presentation changes proposed for this seminar

### 第 5 页：Task 1: Current Results

**状态：** Observed · official test, 175 articles；**建议用时：** 65 秒。

**本页概述**

用一张官方结果表交代改进起点：融合提高了两项 F1，但方向反转率上升。接下来重点解决修改是否可靠，以及收益来自哪些部分。

**页内文案**

| System | Micro-F1 | Macro-F1 | DRR |
| --- | --- | --- | --- |
| Majority-based<br>WAIPS-02 | 0.5496 | 0.3580 | 0.0395 |
| Selective fusion<br>WAIPS-03 | 0.5808 | 0.3952 | 0.0477 |

F1: label recognition, higher is better.  
DRR: direction reversal rate, lower is better.

Next problem: make label revisions and direction changes more reliable.

Complete systems differ in prediction sources and inference cost.

**English script**

The official Task 1b results give us a starting point. Selective fusion has higher Micro-F1 and Macro-F1 than the majority-based submission, but its direction reversal rate is also higher. Lower DRR is better. This motivates more careful decisions about which labels to revise and which directions to change. These are complete systems with different sources and costs, so the result does not isolate the fusion rule. The following experiments will test both the proposed improvements and the reasons for the gain.

**中文讲稿**

官方 Task 1b 结果是下一阶段的起点。选择性融合的 Micro-F1 和 Macro-F1 高于多数投票提交，但方向反转率也更高，DRR 是越低越好。因此，后续要更仔细地判断哪些标签值得修改、哪些方向应该改变。这里比较的是来源和成本不同的完整系统，还不能单独证明融合规则的贡献。接下来的实验既检验改进方案，也分析收益来自哪里。

**演讲与备课建议**

只放官方测试结果。开发集与官方测试分开；DRR 降低必须与 F1、召回及有效覆盖一起判断。

**来源**

- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: official Task 1b results, WAIPS-02 and WAIPS-03](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)

### 第 6 页：Task 1: Subevent References

**状态：** Proposed extensions to the current method；**建议用时：** 80 秒。

**本页概述**

区分两种 subevent 用法：推理时用文章生成的事件片段核验修改；训练时加入 TRAIN 子事件监督改进分类器。现有 E6b 已有自主分段，新工作在于怎样使用这些局部信息。

**页内文案**

The initial predictor already generates event descriptions from the article.

At inference

Use generated events and original passages  
to verify a disputed actor–value label.

During training

Add official TRAIN subevent supervision  
to strengthen the classifier.

Task 1 inference remains article-only. Test the two routes separately.

**English script**

The current initial predictor already generates event descriptions from the article. Simply adding segmentation would not be a new contribution. I propose two more specific uses of subevents. At inference, generated event descriptions can help locate the actor and the original passage when checking a disputed label. During training, official TRAIN subevent annotations can provide additional supervision for the classifier. We should test these routes separately. Task 1 inference still reads only the article and supplied actors. It must not receive official DEV or Task 2 test subevents.

**中文讲稿**

当前的初始预测器已经会从文章生成事件描述，因此单纯增加分段并不是新贡献。我想更具体地研究两种用法：推理时，用生成的事件描述定位主体和原文，核验存在争议的标签；训练时，用官方 TRAIN 子事件标注为分类器提供额外监督。两条路线需要分别检验。Task 1 推理仍只读取文章和给定主体，不能接入官方 DEV 子事件或 Task 2 测试子事件。

**演讲与备课建议**

明确区分生成事件与官方标注。TRAIN subevent 是已有官方监督资源，使用它本身不作为创新主张；作用需在相同骨干和预算下比较。

**来源**

- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: E6b autonomous segmentation and future work](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)
- [docs/8月研究/B.md: sections 3.1, 3.2 and 6.3](../../../docs/8月研究/B.md)
- [docs/FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md: section 4, local evidence proposals](../../../docs/FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md)

### 第 7 页：Task 1: Event-based Verification

**状态：** Proposed experiment · illustrative candidate；**建议用时：** 80 秒。

**本页概述**

用事件和原文核验“是谁做了什么”，避免把志愿者的环保行为归给工厂。固定候选，对比当前方向检查与加入事件及原文依据的检查，统计纠正和误改。

**页内文案**

Candidate to verify: Factory / environment / aligned

| Event in the example | Actor | Direction |
| --- | --- | --- |
| Discharges untreated wastewater | Factory | Contradictory |
| Removes waste from the river | Volunteers | Aligned |

Use the event to locate evidence, then check the original passage.  
Keep the full article for context.

Compare: current check / source passage / event + source passage

Measure useful corrections and harmful changes, plus F1, DRR, and cost.

**English script**

Consider a candidate saying that the factory supports environmental protection. Here, the cleanup belongs to the volunteers, while the factory discharged wastewater. A local event reference could help distinguish those roles. The verifier must return a passage from the article and explain how it supports the target actor and direction. The full article remains available. On fixed candidates, I will compare the current check, a source-passage check, and an event-plus-passage check. Insufficient evidence leaves the previous label unchanged and records uncertainty. We will count useful corrections and harmful changes, together with F1, DRR, and cost.

**中文讲稿**

假设有一个候选认为工厂支持环境保护。在这个例子中，清理行为属于志愿者，工厂实施的是排污。局部事件参考可能帮助核验器分清角色，但它仍需给出可定位的原文，并说明原文如何支持主体与方向，同时保留全文。我会固定候选，对比当前检查、仅要求原文依据、事件加原文依据三种设置。证据不足时保留原标签并记录不确定性，同时统计有效纠正、有害修改、F1、DRR 和成本。

**演讲与备课建议**

这是新实验而非已验证效果。引用能定位不等于语义支持正确，要抽样审核；两个方向都成立时不强制二选一。此处“保留原标签”是明确提出的研究规则，不是掩盖执行错误。

**来源**

- [docs/8月研究/B.md: subevent as evidence seed, actor attribution and context](../../../docs/8月研究/B.md)
- [docs/FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md: evidence verification proposals](../../../docs/FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md)
- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: direction error case](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)
- Illustrative candidate, not an observed prediction

### 第 8 页：Task 1: Fusion and Classifier

**状态：** Planned comparisons · one change at a time；**建议用时：** 80 秒。

**本页概述**

补充其他 Task 1 优化：分别选择添加与删除阈值；比较文章监督与文章加 TRAIN 子事件监督；必要时移除冗余预测来源，检查效果与成本的取舍。

**页内文案**

| Component | Proposed change |
| --- | --- |
| Addition / removal | Select the two thresholds separately |
| Classifier training | Article only vs article + TRAIN subevents |
| Prediction sources<br>(optional) | Remove one source at a time and recalibrate |

Evaluate the classifier first, then its contribution to fusion.

Separate experiments. Choose parameters using fitting data only.

**English script**

There are also improvements we can test without making the whole system more complicated. First, select the addition and removal thresholds separately using a small predefined search. Second, compare article-only classifier training with article plus TRAIN subevent supervision, while holding the backbone and training budget fixed. We should evaluate the classifier itself before measuring its contribution to fusion. Finally, as an optional cost study, remove one prediction source at a time and recalibrate. Each change needs its own comparison, so we can identify which part actually helps.

**中文讲稿**

此外，也可以从现有融合决策和分类器入手。第一，在预先限定的小范围内分别选择添加、删除阈值。第二，固定骨干和训练预算，比较仅文章监督与文章加 TRAIN 子事件监督；先评价分类器本身，再看分数接入 fusion 后的增量。第三，作为可选的成本实验，逐一移除预测来源并重新校准。每次只改变一项，才能判断究竟是哪部分有效。

**演讲与备课建议**

主实验先做事件核验与阈值对照；子事件监督单独训练、单独评价，不同时叠加新生成数据或新骨干。来源裁减为可选项。

**来源**

- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: current fusion heuristic and future supervision comparison](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)
- [docs/8月研究/B.md: official-only article versus article-plus-subevent audit](../../../docs/8月研究/B.md)
- [docs/seminar_pre/10.15/2026-10-15_seminar_ppt_design_and_script.md: detailed experiment controls](../../../docs/seminar_pre/10.15/2026-10-15_seminar_ppt_design_and_script.md)

### 第 9 页：Task 1: Validation Plan

**状态：** Planned · controlled comparisons；**建议用时：** 75 秒。

**本页概述**

为 Task 1 改进设置共同验证标准：先固定来源检验融合规则，再固定候选检验事件参考，固定训练条件检验子事件监督。报告 F1、方向错误、纠正与误改、稳定性及成本。

**页内文案**

| Question | Comparison with fixed conditions |
| --- | --- |
| Does the rule help? | Same cached outputs: voting vs removal/addition |
| Do event references help? | Same candidates: passage vs event + passage |
| Does subevent training help? | Same model and budget: article vs mixed scope |

Fusion-rule comparison: no classifier or extra direction calls.

Separate fitting and evaluation articles. Repeat key comparisons.  
Report F1, precision/recall, DRR, revision outcomes, and cost.

**English script**

The comparisons should separate three questions. For the fusion rule, reuse the same five cached prompt outputs and compare voting with selective removal and addition. Neither branch uses classifier scores or extra direction calls. For event references, hold the candidate labels fixed and compare a source-passage check with an event-plus-passage check. Both are also compared with the current check. For supervision, hold the model and training budget fixed and change only the training scope. Calibration and evaluation use separate article groups. I will repeat the key comparisons and report F1, precision and recall, DRR, revision outcomes, and cost.

**中文讲稿**

验证时要分开回答三个问题。检验融合规则时，复用相同五份缓存预测，对比投票和选择性删除、添加，两边都不使用分类器分数或额外方向调用。检验事件参考时，固定候选，对比仅要求原文依据和事件加原文依据，并把二者与当前检查比较。检验监督信息时，固定模型和训练预算，只改变训练范围。校准与评价按文章分开，重复关键比较，报告 F1、精确率、召回率、DRR、修改结果和成本。

**演讲与备课建议**

旧开发集已参与多次选择，重新分折不能让它成为全新数据。主要比较至少重复三次，明确哪些来源重新生成。事件核验还应加入“仅要求原文证据”的控制，以分离事件结构与提示要求。

**来源**

- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: limitations and controlled validation needs](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)
- [docs/8月研究/B.md: article-grouped splits and matched comparisons](../../../docs/8月研究/B.md)
- [RH_test/E7_calibrated_jury_fusion/reports/E7_REPORT.md: existing cached comparisons and caveats](../../../RH_test/E7_calibrated_jury_fusion/reports/E7_REPORT.md)

### 第 10 页：Task 2: Completion Steps

**状态：** Planned · reuse existing subevent work；**建议用时：** 75 秒。

**本页概述**

说明 Task 2 的具体完成路径：核对子事件和主体 ID，复用可恢复的历史预测，建立单预测器，保留子事件单位，完成 Task-2a/2b 全划分评价。

**页内文案**

Output unit: article + supplied subevent + actor

1  Audit existing work

Check saved E3 predictions,  
identifiers, and coverage.

2  Build the baseline

Keep official subevent IDs.  
Export predictions directly for Task 2.

3  Score the full split

Run Task-2a and Task-2b evaluation.  
Record failures separately from empty labels.

Earlier E3 reports evaluated aggregated Task 1 outputs.

**English script**

Task 2 changes the output unit to an article, supplied subevent, and actor. Earlier E3 work already produced subevent predictions, but the reported scores came after aggregation into Task 1. I will inspect the saved outputs and reuse them where the identifiers and coverage are valid. Then I will establish a single-predictor baseline, keep the official subevent identifiers, and export Task 2 predictions directly. A successful run must cover the selected full split and produce reproducible Task-2a and Task-2b scores. Request failures must remain distinguishable from valid empty predictions.

**中文讲稿**

Task 2 的输出单位是文章、给定子事件和主体。早期 E3 已产生过子事件预测，但报告的是聚合成 Task 1 后的分数。下一步先检查保存输出，在标识与覆盖完整的地方复用；随后建立单预测器基线，保留官方子事件 ID，直接导出 Task 2 预测。完成标准是覆盖所选完整划分，并能重算 Task-2a、Task-2b 指标。请求失败和合法空预测必须分别记录。

**演讲与备课建议**

不能把文章标签复制给每个子事件，也不能把仅跑通几个样本视为 Task 2 已完成。2b 预测按官方层级映射、去重后输出 2a。

**来源**

- [RH_test/E3_subevent_decomposition/reports/E3_REPORT_vs_E3a.md](../../../RH_test/E3_subevent_decomposition/reports/E3_REPORT_vs_E3a.md)
- [RH_test/E3_subevent_decomposition/scripts/run_pipeline_e3.py](../../../RH_test/E3_subevent_decomposition/scripts/run_pipeline_e3.py)
- evaluation.py: parse_task2a and parse_task2b
- [dataset/evaluation_test_data_examples/pred/task2/pred_task2b.json](../../../dataset/evaluation_test_data_examples/pred/task2/pred_task2b.json)

### 第 11 页：Task 2: Evaluation and Fusion

**状态：** Planned · compare within Task 2；**建议用时：** 75 秒。

**本页概述**

在 Task 2 内比较单预测器、投票与 fusion，并检验补充文章上下文是否有帮助。Task 2 单独校准，不能用它与 Task 1 的分数差宣称粒度改善。

**页内文案**

| Comparison | Question |
| --- | --- |
| One predictor vs voting | Do additional predictions help? |
| Voting vs selective fusion | Does the revision rule help at subevent level? |
| Subevent only vs + article context | Does context recover missing information? |

First fusion comparison: same sources, no classifier or direction calls.

Calibrate for Task 2. Report Task-2a/2b F1, Task-2b DRR, and cost.  
Task 1 vs Task 2 scores do not isolate a granularity benefit.

**English script**

After establishing the baseline, I will compare one predictor, voting, and selective fusion under the same Task 2 input protocol. Voting and fusion use the same source outputs, initially without classifier scores or extra direction checks. A separate comparison tests supplied subevents alone against subevents with article context. Task 2 requires its own calibration and, if later added, a classifier appropriate to this unit. We will report Task-2a and Task-2b F1, Task-2b DRR, and cost. A score difference between Task 1 and Task 2 is not a controlled measure of the benefit of finer granularity.

**中文讲稿**

基线完成后，在相同 Task 2 输入协议下比较单预测器、投票和选择性融合。投票与融合使用相同来源输出，第一轮都不加入分类器或额外方向检查。再单独比较只用给定子事件和补充文章上下文。Task 2 需要自己的校准，如果之后加入分类器，也要适配这个评价单位。报告 Task-2a/2b F1、Task-2b DRR 和成本，不能根据 Task 1 与 Task 2 的分数差直接认定细粒度更好。

**演讲与备课建议**

同主体在不同子事件可以有不同方向。现有文章分类器分数不能未经验证当作子事件标签的正确概率。

**来源**

- evaluation.py: Task 2 evaluation keys and metrics
- [docs/论文/Huang_FEHU_Midterm_Paper_zh.tex: Task 2 extension](../../../docs/论文/Huang_FEHU_Midterm_Paper_zh.tex)
- [docs/8月研究/B.md: context and granularity limits](../../../docs/8月研究/B.md)

### 第 12 页：Research Priorities

**状态：** Proposed next steps；**建议用时：** 50 秒。

**本页概述**

收束研究顺序：先做 Task 1 事件核验的小规模实验，再完成关键受控比较，同时准备 Task 2 的输出流程，最后交付完整 Task 2 方法比较。

**页内文案**

| Priority | Deliverable |
| --- | --- |
| 1  Task 1 evidence pilot | Event verification, corrections, and harmful changes |
| 2  Task 1 controlled tests | Fusion baseline and one classifier or threshold test |
| 3  Task 2 completion | Full-split baseline, fusion comparison, and metrics |

Task 2 data checks and baseline preparation can proceed in parallel.

Next checkpoint: one controlled Task 1 result + valid Task 2 outputs.

**English script**

My first priority is a small controlled test of event and source-passage verification for Task 1. I will then complete the main fusion comparison and test the most promising classifier or threshold change separately. Task 2 identifier checks and baseline preparation can proceed alongside this work, followed by a full Task 2 comparison. The next checkpoint should contain a controlled Task 1 result and valid Task 2 baseline outputs. If an improvement does not help, I will report the failed conditions instead of adding more components. I would like feedback on this scope and order.

**中文讲稿**

第一优先级是先做一个受控的小实验，检验事件与原文核验能否改进 Task 1。然后补齐主要融合对照，再单独测试最有依据的分类器或阈值改动。Task 2 的标识核对和基线准备可以同步推进，之后完成全划分的方法比较。下一次检查应拿出一项受控 Task 1 结果和有效的 Task 2 基线输出。优化没有帮助时报告失败条件，不继续堆叠组件，也请老师评价这个范围和顺序。

**演讲与备课建议**

不承诺未经确认的完成日期。明确下一次检查的产物，不再重复整套末期发表规划。

**来源**

- Research priorities proposed for this seminar

## 4. Task 1 实验的落实方式

### 4.1 事件与原文核验：优先试验

**问题：** 在同一批需要复查的标签上，增加局部事件参考，能否减少错误归因和有害方向修改，同时保留有效纠正？

从同一份冻结的初始输出与辅助输出生成候选。保存修改前的主体、价值、方向，以及触发检查的原因。第一轮聚焦当前进入方向检查的候选；误标删除、漏标补回的扩展另做实验，不同时改变候选池。

| 条件 | 可用信息与要求 | 用途 |
| --- | --- | --- |
| 不检查 | 保留修改前标签 | 计算任何复查的净收益 |
| 当前检查 | 现有文章上下文与方向提示 | 当前方法基线 |
| 原文核验 | 同样全文，要求可定位原文与主体、方向理由 | 分离“要求证据”本身的作用 |
| 事件加原文核验 | 同样全文与要求，另提供文章生成的事件参考 | 检验事件结构的增量 |

最后两项保持模型设置、候选、决策规则和调用次数一致，分别记录实际 token 与时间。不能因为加入事件摘要改变了提示长度，就声称两者实际成本相同。已有生成事件可以复用，但仍需计入完整系统成本。

核验时需要区分行动者、受影响者、引语发出者以及报道者。返回的引用必须在原文中可定位；语义支持正确与否通过预先确定的抽样审核判断。不能把“引用存在”当成“方向判断正确”。原文引用不足或无法支持修改时，保留原标签并记录不确定性，这是本实验事先明确的决策规则。API 失败单独计数，不归入“不确定”或合法空标签。

比较正确变错误、错误变正确、两边都正确、两边都错误；允许金标双方向，不把所有方向切换都当成纠错。一起报告 Micro/Macro-F1、P/R、DRR、修改率、有效覆盖、成本。只有在评价前约定的取舍下有稳定收益，才纳入主系统。

### 4.2 TRAIN subevent 监督：先改善分类器，再检验 fusion 增量

**问题：** 在同一分类器骨干和训练预算下，文章加子事件监督是否改善 Task 1 的文章级预测？这种变化是否对 fusion 有帮助？

| 条件 | 训练监督 | Task 1 评价输入 |
| --- | --- | --- |
| A | 官方 TRAIN article | 文章和给定主体 |
| B | 官方 TRAIN article + 同源 TRAIN subevents | 相同文章和主体 |

保持骨干、输入长度、标签定义、训练预算、种子集合和选择协议一致，明确混合采样比例。先按 source guid 切分，再加入该文章的全部子事件，避免同源文章跨折。两组先不额外加入新合成数据；历史增强分类器可以另列连接实验，不能替代此对照。

先评价分类器的文章级 F1、P/R、DRR 与必要的逐标签诊断，再固定辅助预测比较“不使用分类器、使用 A 分数、使用 B 分数”。每种设置只在相同拟合协议下校准，评价文章不参与选择。不能因为 B 的分类器单项分数更高，就直接宣称 fusion 必然改善。

官方 TRAIN subevents 是已有共享监督，使用它们本身不是新方法贡献。若后续更换为更强的指令模型，需要在同一骨干内重新比较 A/B，不能用两个骨干的分数差解释子事件作用。完整训练设计沿用 [研究方案 B](../../8月研究/B.md)，本次不并行展开全部增强方法。

### 4.3 Fusion 决策与来源

| 优先级 | 比较 | 固定条件与解释 |
| --- | --- | --- |
| 必须 | 同来源投票 vs 选择性删除、添加 | 相同五份缓存预测，双方均无分类器和额外方向调用，分离规则作用 |
| 优先 | 当前阈值启发式 vs 分别选择添加、删除阈值 | 小范围预定搜索，固定支持分数、候选池、门控与添加数量上限 |
| 优先 | 不使用分类器 vs 使用文章分类器 vs 使用文章加子事件分类器 | 相同提示输出，固定方向设置，分别校准 |
| 可选 | 完整来源 vs 逐一移除一个来源 | 每次只移除一路并重新校准，联合报告效果与成本 |

五来源多数投票使用至少三份预测精确支持同一主体、价值、方向元组的规则，评价前固定。各来源误差可能相关，因此不能直接把票数解释为独立证据的数量。先完成简单对照，再考虑逐标签自由参数或更复杂权重。

### 4.4 评价与历史结果的解释

- 校准、参数选择与最终评价按文章分开。同文章的主体、子事件及派生样本保留在同一组。
- 旧开发集参与过多次设计，重新分折不能将其变成从未见过的数据。新结果明确探索与确认范围，条件允许时增加未参与设计的保留文章。
- 关键比较至少做三次独立运行或配对训练种子，分别列出结果。若只重生成初始预测而复用辅助缓存，明确这种重复的范围。
- 保存预测的文章级 bootstrap 与重新调用模型衡量不同来源的不确定性，不互相替代。
- DRR 的分母是参考方向唯一的主体、价值组合。少输出也可能降低 DRR，因此必须同时检查 F1、P/R 和覆盖。
- 早期 E3/E3a 使用了官方 DEV 子事件，具有 Task 1 正式推理不可用的中间信息；旧比较还同时改变示例监督和输出聚合方式。只把它作为设计线索与可复用代码，不声称已经证明当前 Task 1 事件核验有效。
- 不沿用旧优化计划中未经验证的召回提升预期、推测性置信度或收益幅度。新实验结果出来后再决定保留哪些改动。

## 5. Task 2 的完成路径

1. **核对单位。** 对照官方文件，建立文章、给定 subevent、actor 对应关系。内部生成片段不能冒充官方 subevent ID。
2. **检查已有产物。** 审计 E3 保存响应，确认子事件预测是否可恢复、ID 是否正确、覆盖是否完整。恢复结果作为历史起点，不自动称为新协议的最终基线。
3. **建立单预测器。** 固定给定子事件、主体及文章上下文协议，输出 Task-2b。按官方层级映射、去重后输出 Task-2a，保留合法空预测并单列失败。
4. **完成全划分评分。** 报告 Task-2a/2b Micro-F1、Macro-F1、P/R，以及 Task-2b DRR。保存能重算的预测、配置、指标和成本。
5. **比较投票与 fusion。** 使用相同来源输出，第一轮均无分类器、无额外方向调用，先判断选择性修改是否优于投票。Task 2 单独拟合和校准。
6. **检验上下文。** 固定模型和输入上限策略，比较给定子事件与给定子事件加文章上下文。不能根据 Task 1 与 Task 2 的 F1 差直接判断粒度收益。

**完成标准：** 所选完整评价划分有合法输出、可重算分数和同条件基线比较，并能说明改善及仍然失败的情形。少量样本跑通只代表实现检查。文章分类器未经验证不能直接用于子事件评分。

## 6. 工作顺序与范围控制

| 顺序 | 工作 | 下一步需要看到的产物 |
| --- | --- | --- |
| 1 | Task 1 事件与原文核验 pilot | 固定候选、四种检查设置、纠正与误改记录 |
| 2 | Task 1 同来源规则对照；单独做一项阈值或分类器实验 | 明确控制变量的结果表、成本及重复结果 |
| 同步准备 | Task 2 数据核对、旧输出审计、单预测器 | 合法输出、缺失和失败记录、完整基线分数 |
| 3 | Task 2 投票与 fusion、上下文对照 | 全划分比较、错误分析及可重算产物 |
| 结果明确后 | 保留有效修改，整理最终研究结论 | 每项结论对应实验和适用范围 |

不在资源与末期日期尚未确认时承诺全部实验的精确完成日。下一次检查优先交付“一项受控 Task 1 结果 + 有效 Task 2 基线输出”。来源裁减、更复杂权重、新增大批合成数据都放在必要对照之后。

## 7. 主要依据

- [既有中期讲稿](../../ppt/2026-10-01_Huang_Midterm_Speaker_Script_Research_Story_v4_EN_ZH_15min.md)：原表达方式及理解负担。
- [中期论文中文稿](../../论文/Huang_FEHU_Midterm_Paper_zh.tex)：当前方法、官方结果、错误案例及研究边界。
- [中期论文英文稿](../../论文/Huang_FEHU_Midterm_Paper.tex)：作者与学校署名。
- [研究方案 B](../../8月研究/B.md)：TRAIN subevent 辅助监督、证据链与主体归因的边界。
- [早期深度优化计划](../../FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md)：句子证据核验与主体相关内容提取的候选思路，效果预测不视为事实。
- [E3 报告](../../../RH_test/E3_subevent_decomposition/reports/E3_REPORT_vs_E3a.md)及[流水线](../../../RH_test/E3_subevent_decomposition/scripts/run_pipeline_e3.py)：已有子事件预测与 Task 1 聚合。
- [E7 报告](../../../RH_test/E7_calibrated_jury_fusion/reports/E7_REPORT.md)：当前融合及已有阶段比较。
- [官方评价代码](../../../evaluation.py)及[Task-2b 格式示例](../../../dataset/evaluation_test_data_examples/pred/task2/pred_task2b.json)：Task 2 输出与评价。

每页对应来源与中英讲稿同时保存在 PPT 备注中。
