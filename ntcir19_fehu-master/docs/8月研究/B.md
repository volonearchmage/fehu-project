# 方案 B：经文献与 FEHU 特性审计后的研究计划

**暂定英文名：** Evidence-Chain and Attribution-Aware Augmentation for Long-Tailed Human-Value Recognition in News  
**研究对象：** FEHU Task 1，重点是 Task-1b 的低频 `direction:L1` 标签  
**文档性质：** 对方案 A 的批判性审核与收缩版计划；不是已经得到的实验结论  
**审核日期：** 2026-08-17  
**目标时间：** 2026 年 10 月初形成可以汇报或投稿的完整实验结果

## 0. 先给结论

方案 A 的主方向是成立的：现有实验已经说明，LLM 生成数据能够为原本接近随机的低频类别提供可学习信号；而“基于真实证据、针对 actor 和低频标签进行增强”也有合理的文献基础。

但是，A 还不是一份可以直接执行并据此作强结论的研究设计。它混入了若干没有经过 FEHU 验证的通用分类假设和人为公式，也一次性加入了过多变量。最主要的问题有五个：

1. FEHU 的相邻价值不是互斥类别，`neighbor-only` 不能自然地当作 hard negative；
2. FEHU 的方向不是简单的肯定/否定或词语反转，同一 actor–value 在不同事件中甚至可能同时出现两个方向；
3. 单个 subevent 只是证据入口，不等于充分、独立且完整的 gold evidence；
4. 当前 DeBERTa 是重要的诊断工具，但在官方的统一 Llama-3.1-8B LoRA 基线面前，不足以单独承担方法有效性的主要结论；
5. 历史 340/900 增强实验使用的是 article-only DeBERTa；在补齐官方 TRAIN subevents 之前，它们还不能回答“合成数据在完整官方监督之上是否仍有边际收益”。

这里必须先纠正一个会改变实验解释的数字：**177 是 FEHU DEV 的文章数，不是 TRAIN 的规模。** FEHU TRAIN 有 1,228 篇文章，并同时发布了这些文章的 10,822 个 subevents 及相应标签。TRAIN subevents 是官方共享训练资源，organizer baseline 也将 article 与 subevent 实例统一训练；它们不是只能由 Task 2 使用的“专属测试信息”。因此，后续所有主 cells 都以 **FEHU TRAIN article + TRAIN subevent** 为共同的 official-only 基线，而 Task-1 的 DEV/test 推理仍严格保持 article-only。

因此，B 保留 LLM 数据增强，但把主问题收缩为：

> 在相同生成预算和相同学生模型下，以真实新闻中的行为—归因—后果证据链为条件生成的数据，是否比从标签定义自由生成的数据更能改善 FEHU 的低频标签？进一步地，显式构造 actor 归因干预对，是否比继续增加独立正例更有效？

这是一项可证伪的研究。若证据链增强不能超过 matched free-form control，就不能声称“近分布证据增强”有效；若 actor 干预不能超过同数量的普通正例，就不能把归因对比写成贡献。

## 1. 审核依据与证据等级

本次审核只把下列三类材料当作证据：

- **[官方]** 本地 `docs/paperForAug/NTCIR_FEHU_TaskOverview.pdf`、FEHU 官方页面和 NEVU/FEHU 数据论文；
- **[仓库]** 已冻结的训练报告、概率文件、官方结果和当前实现；
- **[文献]** ACL/EMNLP/NAACL/EACL 等论文原文或作者公开的预印本，不把博客或二手概述当作方法依据。

本文中的新方法和预期结果一律视为 **[建议]**，不与已经得到的实验事实混写。

## 2. FEHU 与一般 label-aware 任务的本质差异

“label-aware”只能描述 FEHU 的一部分。它同时是 actor-conditioned、event-centric、multi-label、hierarchical、direction-aware 和 long-context 的任务。下面这些差异直接决定哪些增强方法可以迁移，哪些不可以。

| 维度 | 常见多标签/label-aware 或 ValueEval 任务 | FEHU | 对增强设计的影响 |
|---|---|---|---|
| 预测单位 | 通常是 `document → labels` | `article/subevent × target actor → directed values` | 不能只保证文本包含价值线索，还必须保证线索属于指定 actor |
| 文本形态 | 短文本、论点、商品或主题文档较常见 | 多 actor 的事实新闻，包含行动、引语、制度约束和后果 | 标签词或主题相似度不足以构成正例 |
| 价值表达 | ValueEval 主要识别论点背后的无方向价值 | 价值由行为、言论、立场或结果体现，并区分 aligned/contradictory | 方向不能靠情感词或简单否定生成 |
| 证据范围 | 常把整段文本视为一个语义单位 | 证据可能分散在多个事件；subevent 可定位，但行为链和后果可能跨 unit | 单句改写容易破坏真正决定标签的上下文 |
| 标签关系 | 多标签会共现；部分 XMTC 方法仍可用相似标签做检索或 hard negative | 相邻价值经常同时成立，L1 又映射到 L2；同一价值可出现两个方向 | “邻居成立，因此目标不成立”在 FEHU 中通常不成立 |
| 归因 | 普通 MLTC 没有显式 actor；stance 任务有 target，但通常只有少量互斥立场 | 一个新闻中约有多个规范化 actor，行动者、受影响者和引语来源不同 | actor-role intervention 比通用 label-boundary generation 更贴近错误来源 |
| gold 性质 | 通常在 benchmark 内按完整标签集处理 | gold 经 LLM 提议、QA 验证和定向人工审核；官方明确提醒其不是对现实 actor 的穷尽或唯一道德判断 | LLM verifier 可能复现原标注模型的偏差；必须有盲人工审核 |
| 正式测试 | 输入结构常与训练一致 | Task-1 test 没有官方 subevents；Task-1 与 Task-2 test article 不同 | subevent 只能是训练资源，Task-1 最终推理不能依赖它 |

ValueEval 的结果支持“标签定义对主观价值概念很重要”，但它的输入是 premise、stance 和 conclusion，预测的是 20 个无方向价值类别，并不是 FEHU 的直接方法先例。普通 XMTC 中有效的标签描述检索、distribution-balanced loss 和 label-specific attention 可以作为强基线，却不能替代 actor attribution 和 event grounding。

## 3. 已核实、会改变研究路线的事实

### 3.1 官方任务和数据本身

- Task-1b 的原子输出是 54 个 L1 价值乘两个方向；方向属于特定 scope 中的 actor–value pair，而不是整篇文本的总体情感。
- actor 的证据可能分散在文章中。Task-2 的 subevent 更局部，但官方也明确指出它可能缺少隐含后果、角色信息和上下文。
- TRAIN 和 DEV 同时提供 article 与 subevent scope；使用 TRAIN subevents 做辅助训练不需要再猜测是否合法。官方 organizer baseline 本身就是在两种 scope 上统一训练的。
- Task-1 test 不提供 subevents，Task-1 与 Task-2 test 的 guid 集互不重叠，因此不能把两个正式 test 的分数差当成受控的粒度实验。
- 2026-03-20 之前的 release 存在 actor 对齐错误。所有新实验必须确认数据来自 commit `af52dcb` 或更晚版本，并保存实际文件 hash。
- 官方提醒：FEHU 标签不应被解释成关于现实 actor 的穷尽或唯一正确的道德判断。这不意味着训练时必须把所有官方零标签都改成 unknown；它意味着不能把“gold 未列出”当作现实世界中的绝对反例。对于只标目标值的合成样本，未重新标注的其他类别尤其不能直接当负例。

用于研究设计的规模应按 split 和 scope 分开报告：

| Split / scope | 文本单元数 | 官方 candidate actor pairs | directed L1 assignments |
|---|---:|---:|---:|
| TRAIN article | 1,228 | 3,381 | 16,905 |
| TRAIN subevent | 10,822 | 30,543 | 18,665 |
| DEV article | 177 | 459 | 2,390 |
| DEV subevent | 1,526 | 3,998 | 2,768 |

这些行不能简单相加后宣称得到 12,050 个独立训练样本：subevents 来自同一批源文章，标签构建还包含 cross-level integration。更准确的表述是，TRAIN 提供了**同一批新闻的多粒度辅助监督**。它增加了局部 actor–event observations，却没有凭空增加同等数量的独立新闻主题。

#### Task-1 使用 TRAIN subevents 的严格边界

- **可以使用：** official TRAIN 中的 subevent 文本、actor pairs 和 subevent labels，用作共享编码器或统一生成式模型的辅助训练；
- **不可以使用：** 在 DEV 上评测 Task-1 时训练 DEV subevent labels，或把 `test_subevent_event_base.json` 等 Task-2 test 输入接入 Task-1；
- **推理约束：** Task-1 DEV/test 的每个预测只能读取该 Task-1 article 的 title/content/actors，不读取 subevents；
- **切分约束：** 内部验证必须按 source `guid` 分组，article、其全部 subevents 和所有 synthetic descendants 永远在同一 fold；
- **论文用语：** “We use the subevent-level annotations included in the official FEHU training release as auxiliary multi-granularity supervision. Task-1 inference remains strictly article-only.”

因此，这一做法不是“拿 Task 2 的测试数据帮助 Task 1”，也不应包装成新的数据增强方法。它是首先补齐官方监督、建立可信 B0 的必要步骤。

### 3.2 subevent 覆盖不能被过度解释

A 中统计到：文章级 16,905 个 directed labels 中，12,788 个能在同文章、同 actor 的 subevent 中找到，覆盖率为 75.6%；且没有发现 subevent union 超出 article labels 的组合。

这个统计有用，但它不是独立的证据质量验证。NEVU 的构建流程明确包含从细粒度到粗粒度的 cross-level integration、deduplication 和 consistency checks；文章级标签也更容易吸收 subevent 信息。因此，“没有 subevent-only label”部分是数据构建机制预期产生的结构，不足以证明某个 subevent 就是干净、充分且唯一的因果证据。

更可靠的用法是：

1. 用 subevent 找到候选局部事件；
2. 回到原文寻找 actor mention、行动、对象/受影响者、引语来源和后果；
3. 组成一个可核查的 evidence chain；
4. 不把 article 的全部原标签自动继承给编辑后的文本，而是重新标注合成文本。

官方数据研究还给出更强的提示：真实 BCE/SCE grouping 比同 actor、同数量的随机 subevent 拼接高约 4.7–9.7 个 F1 点，BCE 的收益更稳定；而人工审核中 subevent 的 actor grounding hard score 为 82.0%，human-value correctness 为 81.0%，低于 BCE 的 98.6% 和 88.6%。这说明“紧凑的行为—响应—后果链”比“孤立 subevent”更适合作为增强单位。

### 3.3 当前仓库已经证明什么

在解释 Phase 2/3 之前，必须补全一条关键 provenance：历史的 **340 条**和后续 **900 条**都由当时的 **DeepSeek V4 Pro Preview** 生成，并不是两个不同 LLM 或两个独立生成器的结果。本地运行记录中 API 返回的模型字段为 `deepseek-v4-pro`；340 条是同一生成器产生的候选经筛选后保留的 silver pool，900 条则是同一 Preview 谱系下按第二轮 label-aware 策略生成、只通过结构检查的 pool。论文应同时记录“运行时实际使用的是 V4 Pro Preview”和 API 暴露的模型字段；如果服务端没有返回可复现的 snapshot ID 或 system fingerprint，就应明确写为未提供，不能事后补造一个精确版本号。

因此，340 与 900 之间的差异不能解释为 generator comparison，也不能算作跨模型的独立复现。两批数据同时改变了目标标签、生成策略、语义筛选强度和 supervision completeness。它们能支持的结论是：**来自同一历史 Preview 生成器、但经不同构造流程得到的合成数据，确实能在当前学生模型上产生可学习信号；究竟是哪一种生成机制带来收益，仍需 matched experiment。**

Phase 2 的三种子实验已经把“新增 900 条数据”和 supervision policy 分开：

- official-only 的 target-18 mean AUC 为 `0.513 ± 0.030`；
- `+900 assume-negative` 为 `0.624 ± 0.011`，相对提高 `0.111`，3/3 seeds 同方向；
- `+900 masked` 为 `0.577 ± 0.028`，相对提高 `0.064`，3/3 seeds 同方向。

Phase 3 又显示，加入 340 条单标签数据以后，masked 和 assume-negative 的相对优劣发生反转；也就是说，supervision policy 与合成数据是否完整标注存在交互，不能把某一种 loss 宣布成普遍最好。

可以稳妥地写：

> 现有合成数据为低频类别提供了可学习的 score-level signal。

目前不能稳妥地写：

> 数据增强已经被证明是 WAIPS-03 官方 Macro-F1 优势的原因。

原因是 WAIPS-03 同时包含增强 DeBERTa、E6b、多个 juror、gate 和方向修复，最终缺少 no-DeBERTa/no-augmentation 的干净消融。N3 的高 recall 也主要来自 calibration shift，因为其 target AUC 没有超过 F′，并伴随约 3% target precision 和更差 DRR。

### 3.4 官方强基线改变了 backbone 的地位

官方 Task Overview 的 organizer baseline 使用：

- `meta-llama/Llama-3.1-8B-Instruct`；
- article 和 subevent 的统一训练；
- actor、scope、文本和完整 L1 taxonomy 作为输入；
- aligned/contradictory 两个 JSON value sets 作为输出；
- LoRA `r=16, alpha=32, dropout=0.05`；
- 最大长度 4,096，训练 6 epochs。

它在正式 Task-1b 上得到 `62.84 Micro-F1 / 44.02 Macro-F1 / 3.86 DRR`。WAIPS-03 为 `58.08 / 39.52 / 4.77`。虽然 organizer baseline 不参与排名，但它说明：

1. 当前 512-token、108 个独立 sigmoid 输出的 DeBERTa 不是足够强的论文主基线；
2. subevent 辅助训练本身不是新贡献；
3. 新增强方法至少应在 organizer-style LoRA 或同等级 label-aware 模型上验证一次；
4. 只有两个参赛团队的“排名”不能替代方法消融，真正有说服力的是与强基线的受控差值。

当前 DeBERTa 仍然很有价值：训练快、已有 masked trainer 和多种子分析代码，适合做数据 sanity check、分数分离诊断和历史连接。但如果增强只对该弱架构有效而不能迁移到强 LoRA，结论必须限定为“小模型的样本效率改善”。

### 3.5 NEVU 与 FEHU 语义兼容，但不是同一个实验 split

NEVU 与 FEHU 共享 54 个 L1 taxonomy、aligned/contradictory 方向和 actor-conditioned 标注框架，因此 NEVU 可以成为有意义的跨数据集预训练来源；但二者的目标和评测集不能混称：

- NEVU 研究 Article、Subevent、BCE 和 SCE 四种 scope，论文内部划分为 2,005/286/574 篇；
- FEHU 只保留 Article 和 Subevent 两种正式任务 scope，划分为 1,228 TRAIN、177 DEV，以及两个 guid 不重叠的 175 篇 Task-1/Task-2 test；
- 公开 NEVU release 合并了其论文中的内部 train/dev/test，并排除了 350 个 FEHU 正式 test guid；因此 NEVU 的原 dev 不能被当成 FEHU DEV，公开文件也不能不经审计就直接称为“额外 FEHU gold”。

即使从公开 NEVU 中清理后得到约 1,110 篇不属于 FEHU TRAIN/DEV 的文章，它们也只能被称为 **NEVU-extra cross-dataset data**。核心 B0–B3 不直接混入它们；可选的次要分支应当先排除 FEHU DEV/test guid、内容近重复和事件簇泄漏，再在兼容的 Article/Subevent scopes 上预训练，最后只用 FEHU TRAIN 微调并只在 FEHU DEV 评价。这样才能把“跨数据集迁移”与“FEHU 内部 LLM 增强”分开。

## 4. 对方案 A 的逐项审核

| A 中的设计 | 审核结论 | 原因与 B 中的处理 |
|---|---|---|
| TRAIN-only 选目标、分组划分 | **保留** | 防止继续用 DEV 选择容易改善的类别；所有派生样本跟随源 guid 所在 fold |
| 用 subevent 定位证据 | **保留但改义** | subevent 是 seed，不是充分 gold；需扩展成行为—归因—后果链 |
| 75.6% 覆盖说明证据干净 | **删除该推论** | cross-level integration 使这一覆盖并非独立验证 |
| 从真实文章做局部 graft 并保留其他标签 | **改写** | 一次编辑可能改变其他 actor、后果和多个价值；B 改为匿名化 evidence-template generation，并对新文本重新标注 |
| `neighbor-only` hard negative | **从主实验删除** | FEHU 标签可共现，相邻价值不是互斥类；邻居只用于错误分析和 verifier 提醒 |
| opposite-direction pair | **降为可选实验** | 方向是行为/立场/结果关系，不是词语否定；同一 value 也可能双向成立 |
| `both/neither` 作为可选生成成员 | **改为 verifier 必须允许的判断** | 它们是合法审核结果，不必人为分配生成配额 |
| 预算公式 `B_c ∝ (1-AP)/sqrt(n+1)` | **删除** | 这是未经验证的启发式，极小支持下 OOF AP 方差很大；B 对所有预定义 tail labels 分配相同 accepted budget |
| embedding distance、长度、actor 数构成质量分 | **仅保留诊断** | 这些量不证明标签正确，不能未经校准合成一个训练权重 |
| `w_syn < 1` 与 verifier-confidence weighting | **从核心删除** | 权重数值没有先验依据，会引入新的调参自由度；先用 accepted/rejected 二元池验证数据本身 |
| pairwise ranking loss | **从核心删除** | 与新数据同时加入会再次产生因果混淆；若数据实验成功，再单独研究 loss |
| 不同模型家族即“独立验证” | **改写** | FEHU gold 本身由 GPT、Gemini、DeepSeek、Claude 参与构建；模型不同不等于误差独立，仍需盲人工审核 |
| 正式数据抽查 10%–20% | **改写** | 百分比没有统计依据；B 使用固定分层样本和 Wilson CI，必要时扩样 |
| A0–A7 八个 cells | **缩减** | 变量过多且在 10 月前统计功效不足；B 只保留四个 matched-budget 主 cells |
| DeBERTa 为唯一学生 | **降为诊断学生** | 主结论需在 organizer-style 8B LoRA 上验证；否则明确限定适用范围 |
| 历史 target-18 继续作为主要 target | **仅作回顾性分析** | 其形成使用过 DEV 支持度和历史错误，不再是独立 confirmatory set |
| 把 340/900 当作两个生成器或跨模型复现 | **删除该解释** | 两批数据均来自 DeepSeek V4 Pro Preview；它们还同时改变了生成策略、筛选和标注完整性，只能作为同一历史生成器谱系下的两轮证据 |
| 把 177 当作 FEHU TRAIN 的规模 | **纠正** | 177 是 DEV；TRAIN 有 1,228 篇 article，并附 10,822 个 subevents |
| 把 TRAIN subevents 视为 Task-2 专属 | **删除该限制** | 它们属于官方共享 TRAIN，organizer baseline 已在 article+subevent 上统一训练；Task-1 推理仍必须 article-only |
| 把 subevents 计作 10,822 篇独立新文章 | **删除该解释** | subevents 与源文章同源且经过跨层整合，只能称为多粒度辅助监督 |
| 把 NEVU-extra 直接并入 FEHU gold | **移到独立迁移实验** | taxonomy 兼容不等于 split 相同；必须先去除 FEHU DEV/test guid 与近重复，再做 NEVU pretrain → FEHU fine-tune |
| `micro drop ≤ 0.01` 作为成功线 | **删除** | 0.01 是人为阈值；B 报告 micro–macro Pareto、基线方差和 paired CI，不用单一容忍值掩盖权衡 |
| DeepSeek 与另一生成器大规模竞赛 | **移出主问题** | generator comparison 会消耗预算且不回答增强机制；只做一次小 pilot 后冻结一个生成器 |

## 5. 修订后的研究问题与可接受主张

### 前置审计：完整官方监督是否已经改变“数据不足”的判断？

先在同一 backbone、训练预算、阈值协议和 seeds 下比较 article-only 与 article+subevent 两个 official-only 模型。这个比较不是论文的新方法贡献，而是后续增强实验的必要校准：历史 340/900 实验只证明合成数据能改善 article-only DeBERTa，尚未证明它能超过充分使用官方多粒度监督的模型。

若加入 TRAIN subevents 已经显著修复 tail labels，则新的增强研究要回答的是更严格的“边际收益”问题；若提升很小，才能更有把握地说低频瓶颈不只是漏用了官方数据。无论结果如何，B0 都固定为 article+subevent，不能让较弱的 article-only 模型继续承担主基线。

### RQ1：真实 evidence-chain conditioning 是否优于自由生成？

在目标标签、生成器、通过样本数、文本长度、actor 数量、训练步数和学生模型完全匹配时，使用真实 TRAIN 的事件结构作为模板，是否比仅使用标签定义的 free-form generation 更好？

**H1：** evidence-chain augmentation 相比 matched free-form augmentation，提高 train-defined tail Macro-F1 和官方 Task-1b Macro-F1；在能够输出连续分数的 DeBERTa 诊断中，还应提高 tail macro-AUPRC，而不只是整体抬高概率。

### RQ2：actor attribution intervention 是否有额外价值？

在 synthetic actor–unit 实例总数相同的前提下，一部分预算用于构造成对的 actor-role / quote-source intervention，是否优于把全部预算继续用于独立 target-positive 生成？

**H2：** attribution intervention 主要降低 wrong-actor false positives，并进一步提高 tail precision 或 macro-F1；若只提高训练集准确率而不改善 held-out article，就判定不成立。

### RQ3：收益能否迁移到强模型？

当前 DeBERTa 上的 score-level 改善，能否在统一 article+subevent 的 8B LoRA 上仍然观察到？

**H3：** 若方法捕捉的是 FEHU 数据问题而非弱模型的校准缺陷，则 B2/B3 相对 B1 的方向应在强模型上保持。这里不预先假定效果大小。

本研究不把“方向对比一定降低 DRR”列为核心假设。现有 LoRA 基线已经显著改善方向，且方向翻转样本的语义风险最高；只有主实验完成后仍观察到明确的 direction-specific failure，才启动该扩展。

## 6. 修订后的方法

### 6.1 数据冻结和研究 split

1. 保存 corrected TRAIN/DEV 文件的 SHA-256、仓库 commit 和生成脚本 commit；
2. FEHU 内部的所有选择和训练只使用 TRAIN article 及其 TRAIN subevents；
3. DEV article 和 DEV subevent labels 都不进入训练，DEV Task-1 最终只用 article input 评价；
4. 按 `guid` 分组，并把近重复新闻或同一事件簇尽可能放在同一 fold；
5. article、其全部 subevents 和所有 synthetic descendants 永远属于同一 fold，先划分再增强；
6. 建立 TRAIN 内部的 development/holdout，DEV 只在方法、预算、筛选规则和模型选择全部冻结后运行一次；
7. Task-1 test 不读取 Task-2 test subevents；正式 test gold 不可用，新研究不能把历史官方 test 总分冒充新方法结果；
8. 若启动 NEVU-extra 分支，先按 guid、内容近重复和事件簇排除所有 FEHU DEV/test 重叠，再做预训练；该数据不进入核心 B0–B3。

本地 TRAIN 的 108 个潜在 directed classes 中，105 个有文章级训练支持，3 个为 zero-support。非零类别中，当前计数为：

- `<10`：17 类；
- `10–80`：40 类；
- `81–300`：33 类；
- `>300`：15 类。

这些数字用于描述，不再直接变成带小数权重的预算公式。

### 6.2 TRAIN-only tail 定义与预算

为避免再挑选“在 DEV 上刚好容易恢复”的 18 类：

1. 先排除 zero-support 类，它们单列为 label-description zero-shot analysis；
2. `n_c < 5` 的 directed classes 定义为 ultra-tail exploratory group，因为无法可靠地在 TRAIN 内同时形成种子、训练和验证；
3. 对 `n_c ≥ 5` 的非零 directed classes 按 TRAIN 支持度排序，最低三分之一构成 primary tail group；
4. 这一组在查看新 DEV 结果前冻结，并同时报告不同 cutoff 下的敏感性分析；
5. 每个 primary tail class 获得相同数量 `N` 的 accepted actor–unit instances，而不是由 OOF AP 决定预算；
6. 推荐 pilot 后冻结 `N=20`。这个数只是成本约束，不声称是理论最优，并且四个实验 cells 使用完全相同的总预算。

历史 target-18 继续报告，便于连接 Phase 2/3，但只标为 retrospective subset，不承担主要显著性结论。

### 6.3 Evidence package：从 subevent 到行为链

每个 seed package 至少包含：

- source guid、target actor id 和 actor 的原文 mentions；
- 匹配的 subevent summary；
- gold explanation，只作为定位线索，不允许复制进生成文本；
- 从原文回取的 exact evidence sentences；
- actor 在事件中的角色：agent、speaker、institutional decision-maker、recipient/affected party 或 observer；
- action/position、对象、直接结果和必要的后续后果；
- 引语属于谁、报道者是谁；
- 目标 directed L1 及定义；
- 可能需要共同核查但不预设互斥的相邻价值。

如果一个 subevent 不足以支持方向或归因，就扩展到最小的相关 sentence chain；如果仍无法形成明确证据包，就不用它做生成种子。这里宁可减少 seed 数量，也不把 explanation 当作事实证据本身。

### 6.4 三种生成数据

所有 arm 使用同一个冻结生成器、相同 decoding 设置、相同输出 schema 和相同 actor–unit 数量。生成内容使用虚构或匿名化实体，避免把虚构行为附着在真实个人和机构上。

这里的“同一个冻结生成器”指新实验期间实际调用的同一服务版本，而不是只比较 API 返回的营销名称。历史 340/900 不直接充当 B1 的 matched free-form control：它们来自已经变化的 V4 Pro Preview 部署，且两批数据的筛选和 supervision policy 与新设计不匹配。若保留它们，只把它们作为带固定文件 hash 的 historical anchor，不能用“旧 Preview 数据对新版本 evidence-chain 数据”的差值回答 RQ1。

#### F：Matched free-form control

输入 target label 定义、方向、长度/actor 数/新闻体裁约束，但不提供真实 evidence package。它回答“只增加目标类文本”能够做到什么。

#### E：Evidence-chain positive augmentation

输入抽象化后的真实 evidence package。生成器保留事件角色和因果结构，但更换实体、时间、地点和表面表达，形成新的 coherent news passage。要求价值线索来自行动、立场或后果，而不是直接写出标签名称。

这里不再把原文章的 labels 自动搬到新文本。每条新 passage 都重新做 actor-conditioned 全标签标注。

#### A：Attribution-intervention augmentation

从 evidence-chain passage 构造成对干预，例如：

- 保持事件主题和结果，交换谁实施行动、谁受到影响；
- 保持引语内容，改变 quote source 与被报道对象；
- 保持制度决定，改变负责执行与仅在场的 actor；
- 保持价值相关行为，改变该行为归属于哪个 canonical actor。

干预后必须完整修复代词、别名、因果链和后果，不能只替换名字。两个版本都重新标注；只有 blind annotation 确认目标 value 的 actor attribution 按预期改变时，pair 才进入训练。

标签邻居和 opposite direction 可以出现在重新标注结果中，但不被强迫为互斥。若 target 和 neighbor 同时成立，保留 `both`，而不是把样本判成失败。

### 6.5 Blind relabeling，而不是 generator self-confirmation

生成后的标签流程为：

1. **结构检查：** schema、taxonomy、L1→L2、actor mention、evidence exact match、ID 和 hash；
2. **盲全标签重标注：** annotator 看不到生成 arm、原始 intended target 和 prompt，重新输出 target actor 的全部 aligned/contradictory L1 sets 及 evidence；
3. **candidate QA：** 对 intended target、方向和 actor attribution 做逐候选核查；允许 `aligned`、`contradictory`、`both`、`unsupported/unclear`；
4. **去重和分布诊断：** exact/near duplicate、长度、actor 数、显式价值词、topic、evidence position；这些指标只用于报告和发现模板坍缩，不合成任意质量权重；
5. **盲人工审核：** 按 arm、方向和支持度分层。

人工审核不用“随便抽 10%”。建议 pilot 各 arm 先审 30 条；正式 accepted pool 各 arm 固定抽 60 个 actor–unit instances，由两名审核者独立判断 actor grounding、value identity、direction、evidence sufficiency 和新闻连贯性。报告原始一致率、分歧类型和适合该量表的一致性统计。

官方 subevent 的 hard human-value correctness 为 81.0%，可以作为外部质量锚点。若 60 条的 Wilson interval 尚不能判断合成数据是否明显低于这一锚点，再扩到 120 条，而不是在看到下游分数后改变筛选标准。若 synthetic data 明显低于官方局部单元的质量水平，则停止正式生成。

需要明确：DeepSeek、Gemini 或 Claude 的“通过”不能代替这个人工检查。NEVU 的原始标注池已经包含 GPT-4o、Gemini-2.5-Pro、DeepSeek-Reasoner，以及 GPT-5、Gemini-2.5-Flash、Claude-Sonnet-4；重复使用相同模型家族可能带来相关偏差。

### 6.6 学生模型与当前代码的关系

#### 主模型：复现 organizer-style unified LoRA

第一优先级是按官方 recipe 复现一个统一 article+subevent 的 8B LoRA。模型、prompt、max length、训练 epoch、JSON schema 和 Level-1→Level-2 mapping 应尽可能与官方一致。若原 Llama 权重或算力不可用，可以使用同等级开源 8B backbone，但必须把它写成“同协议强基线”，不能声称复现了 organizer 数字。

训练输入显式携带 `scope=Article/Subevent`；两种 scope 共用 taxonomy 和参数。主实验的所有 cells 固定同一 backbone、训练步数、official-data sampling、scope sampling 和 decoding，只有 synthetic pool 改变。Task-1 DEV 评价只构造 `scope=Article` 的输入，不在推理时先生成或检索 subevents。

#### 诊断模型：现有 DeBERTa

当前 `src/train_deberta.py` 只读取 `article_human_values`，所以现有 official-only 结果仍是 **article-only legacy baseline**，不能直接改名为下面的 B0。进入新实验前，需要最小幅度扩展训练数据适配器：从 TRAIN 的 article 与 subevent labels 构造同一输出空间的实例，加入明确的 scope 标记，并固定两个 scope 的采样比例；DEV Task-1 指标仍只在 article instances 上计算。

复用当前 masked trainer、概率导出和 Phase 2/3 分析代码进行：

- 生成池进入训练前的快速 smoke test；
- target AUPRC、score distribution 和 seed variance 检查；
- official-only BCE 与 distribution-balanced loss 的非生成对照，避免把弱 loss 的问题误归因于数据不足；
- 与历史 340/900 数据连接的回顾性实验。

DeBERTa 的 512-token 截断、108 个互不共享 label semantics 的 sigmoid heads、全局阈值和高 seed variance 都必须在论文限制中出现。不要根据 DeBERTa smoke 分数筛掉某个 generation arm 后，再只把获胜 arm 送给强模型；否则强模型比较又会带入选择偏差。四个主 cells 必须预先冻结。

### 6.7 四个主实验 cells

| Cell | 训练数据 | synthetic actor–unit 预算 | 回答的问题 |
|---|---|---:|---|
| **B0** | 官方 article + subevent | 0 | 强无增强基线 |
| **B1** | B0 + F | `N × tail classes` | matched free-form 生成能否帮助？ |
| **B2** | B0 + E | 与 B1 完全相同 | evidence-chain conditioning 是否优于自由生成？ |
| **B3** | B0 + E/A 混合 | 与 B1/B2 完全相同；以 actor–unit 数而非 API call 数匹配 | attribution intervention 是否优于继续增加独立 positives？ |

B3 中建议一半预算为 E positives，另一半为 attribution pair 产生的 actor–unit instances。所有 cells 使用相同的盲重标注流程，避免 B2/B3 的收益其实来自更严格筛选。

四个 cells 都包含完全相同的 FEHU TRAIN articles、TRAIN subevents 和 scope sampling。B0 不包含 DEV subevents、Task-2 test inputs、NEVU-extra 或历史 340/900；B1–B3 也不改变这些 official-data 条件。这样 `B2−B1` 才能解释为生成条件的差异，而不是是否使用了官方 subevent supervision。

每个 cell 至少运行 3 个训练 seeds。若关键差值的 seed 方向不一致，不挑最佳 seed，而是增加到 5 seeds 或把结论降级为“不稳定”。不在核心实验中同时加入 quality weighting、ranking loss、per-cell 不同阈值策略或不同生成器。

### 6.8 数据充分性与 NEVU 迁移审计（次要分支）

在生成新数据前先做一个便宜但关键的 scope preflight：

| Preflight | FEHU TRAIN supervision | Task-1 DEV 输入 | 目的 |
|---|---|---|---|
| **P0** | article only | article only | 复现历史数据条件 |
| **P1** | article + subevent | article only | 测量官方多粒度辅助监督的增量；P1 即 B0 的数据条件 |

P0/P1 使用相同 model、steps、seeds 和评价代码，并报告整体及 tail 指标。它不把 subevent 当作增强贡献，只用于解释为什么“900+340 大于 177”不是有效的数据量比较：177 属于 DEV，且历史 synthetic units 与 official article/subevent actor pairs 也不是同一统计单位。

若时间与算力允许，再把 NEVU 作为独立的 2×2 exploratory audit，而不是塞进 B0–B3：

| Cell | NEVU-extra compatible-scope pretraining | 历史 synthetic pool | FEHU final fine-tuning |
|---|---|---|---|
| **C0** | 无 | 无 | TRAIN article + subevent |
| **C1** | 无 | 有 | TRAIN article + subevent |
| **C2** | 有 | 无 | TRAIN article + subevent |
| **C3** | 有 | 与 C1 完全相同 | TRAIN article + subevent |

这个设计分别估计历史 synthetic effect、NEVU transfer effect 及二者的交互。为避免再次混淆，`historical synthetic pool` 必须在运行前固定为一个带 hash 的版本；建议用已有完整三种子对照的 900 pool 作为主历史锚点，340 pool 只作回顾性敏感性分析，不把两者直接拼接。NEVU 只做 pretrain → FEHU fine-tune，不能用 NEVU 的内部 dev 选择 FEHU 的阈值，也不能把 C2/C3 的结果写成“增加了 FEHU gold”。如果资源不足，优先完成 P0/P1 与 B0–B3，C0–C3 可以删去而不损害核心论文。

## 7. DeepSeek 是否还需要

需要的是一个可靠的文本生成器，不是必须使用 DeepSeek。不过，本项目并非尚未尝试 DeepSeek：历史 340 条和 900 条都已经由 **DeepSeek V4 Pro Preview** 生成。这一事实应进入方法和有效性威胁，而不只是放在运行日志中。

DeepSeek 可以继续使用，条件是：

- pilot 中 actor grounding、direction 和 full-label reannotation 的通过率足够；
- 保存请求时间、请求/响应模型名、thinking on/off、temperature、top-p、token limit、prompt hash、raw response 和 repair history；
- 正式生成开始后不因为 API 模型更新而在同一个数据 cell 中混用版本；
- 生成数据冻结后，以文件 hash 而不是服务名称定义实验输入。

AgoraBench 的结果说明，模型直接解题能力与它作为 data generator 的能力并不必然相关。因此，旧 Preview 在 FEHU 直接分类上更好或更差，不能单独决定它是否是更好的数据生成器；反过来，340/900 的下游收益也不能证明当前同名 API 仍会生成同分布的数据。即使 prompt 完全相同，只要服务端 Preview 已更新，就应把重跑视为新的 generator condition。

新的 F/E/A pilot 必须在同一个当前版本、同一时间窗口完成盲评，然后冻结生成器。不能把旧 V4 Pro Preview 的 900 条作为 B1，却让 B2/B3 使用更新后的 DeepSeek，再把差值归因给 generation method。除非论文问题本身改成 generator comparison，否则不需要再做 Flash、Pro、thinking on/off 的大规模网格；若确实比较，也必须把它放在独立实验中，不能与 F/E/A 的方法变量混在一起。

为了可复现性，也可以优先考虑固定权重的开源 generator；但这不是必须条件。真正不可省略的是 raw data provenance 和人工质量估计。

## 8. 评测协议

### 8.1 主要结果

**Primary：**

- 官方定义的 Task-1b gold-supported Macro-F1；
- train-defined primary tail group 的 Macro-F1。

这两个指标可以在 DeBERTa 和生成式 LoRA 间使用同一个 set-level 定义。

**Secondary：**

- Task-1b Micro-P/R/F1 和 DRR；
- DeBERTa 诊断中的 train-defined tail macro-AUPRC，用于区分“排序真正改善”与“整体抬高概率”；
- Level-2 映射后的 Task-1a Micro/Macro-F1；
- head/medium/tail 与 aligned/contradictory 分组；
- wrong-actor、wrong-value、wrong-direction 和 unsupported-spillover 错误；
- historical target-18；
- synthetic acceptance rate、人工正确率、模板重复率和每条 accepted sample 成本。

### 8.2 统计报告

- 训练报告 mean ± SD，不以单一最佳 seed 代表方法；
- 在相同 held-out articles 上做 paired article bootstrap，报告 delta 和 95% CI；
- per-label 结果同时列出 gold support，极小支持类不作单类强结论；
- 比较 `B2−B1` 和 `B3−B2`，而不仅是每个方法对 B0；
- 报告 Micro–Macro–DRR 的完整 Pareto，不用人为的 `micro loss ≤ 0.01` 宣布成功；
- DEV 结果只在全部规则冻结后导出一次，并把之前曾反复使用 DEV 的历史写入 threat to validity。

## 9. 结果如何决定结论

### 情形 1：B2 > B1，B3 > B2，且跨 seed 稳定

可以提出：真实 evidence-chain conditioning 比同预算自由生成更有效，actor attribution intervention 还有额外收益。此时论文贡献是 FEHU-specific augmentation，而不是“使用了 DeepSeek”。

### 情形 2：B2 > B1，但 B3 ≈ B2 或更差

只保留 evidence-chain augmentation；诚实报告 actor counterfactual 没有转化为收益。不要把失败组件留在最终方法图中。

### 情形 3：B1、B2、B3 都没有稳定超过 B0

结论是 LLM 生成更多文本并非当前瓶颈。停止扩大生成量，转向：

1. label-definition conditioned cross-encoder / entailment scorer；
2. 用 teacher 给真实 TRAIN 新闻补充候选标注，而不是生成新新闻；
3. actor-evidence retrieval 与长上下文建模；
4. 当前 DeBERTa 的 distribution-balanced loss 和 threshold calibration，作为小模型路线。

### 情形 4：只在 DeBERTa 上有效，在 8B LoRA 上无效

可以写成 small-student/sample-efficiency finding，但不能宣称这是 FEHU 的普遍增强方法，也不能把官方 WAIPS-03 macro 归因给它。

## 10. 建议时间表

### 8 月 17–23 日：先解决强基线和协议

- 验证 corrected dataset commit 与 hashes；
- 冻结 TRAIN internal split、tail group 和 evaluation scripts；
- 在 DeBERTa 和/或强模型上完成 P0 article-only 与 P1 article+subevent 的同条件比较；
- 复现或搭建 organizer-style unified 8B LoRA；
- 确认 B0 实际读取 TRAIN article + TRAIN subevent，而 Task-1 DEV loader 只读取 article；
- 只跑 B0，不生成新数据，也不接入 NEVU-extra；
- 若 B0 无法稳定训练，先解决该问题，暂缓生成。

### 8 月 24–31 日：evidence package 与三臂 pilot

- 构建可追溯 evidence packages；
- F/E/A 各生成 30 条 pilot；
- 完成 blind relabeling 和双人人工审核；
- 冻结 generator、prompt、screening rule、`N` 和总预算。

### 9 月 1–10 日：正式生成和重标注

- 生成 B1/B2/B3 matched pools；
- 结构检查、盲全标签重标注、candidate QA、去重；
- 完成人工分层审核并冻结 accepted pool hash；
- 不根据 DEV 或学生得分返工某一个 arm。

### 9 月 11–22 日：主训练

- B0–B3 各 3 seeds；
- 同步跑 DeBERTa 诊断但不据此删除主 cells；
- 检查训练实际读取的数据 hash、scope 配比和样本数。

若主实验按期完成且资源仍充足，C0–C3 的 NEVU 迁移审计可在这一阶段追加；它不阻塞 B0–B3，也不进入核心方法比较。

### 9 月 23–30 日：统计与错误分析

- paired bootstrap、support-stratified 分析；
- 人工复核 wrong-actor、value inflation 和 direction cases；
- 对不稳定的核心差值补到 5 seeds；
- 决定只保留 E，还是保留 E+A。

### 10 月初：冻结叙事

- 不再增加模型或 prompt 变体；
- 主表只保留 B0–B3 和必要历史锚点；
- 将负面结果和不支持的假设一并写入；
- 明确区分新研究的 TRAIN/DEV 结果与已经冻结的 NTCIR 正式 test 结果。

## 11. 最小实现范围

当前仓库已有且应复用：

- corrected FEHU dataset 和官方 evaluator；
- official TRAIN 的 article/subevent 文本、actor pairs 与两级标签；
- TRAIN 标签频率、per-class 指标与 Phase 2/3 多种子分析；
- augmentation schema、local validator、provenance 和 timestamped-output 习惯；
- DeBERTa masked loss、概率导出与 hard validation；
- L1→L2 mapping、DRR 和 gold-supported macro 实现。

真正需要新增的只有：

1. TRAIN-only tail group 与 grouped split manifest；
2. FEHU article/subevent 统一 example builder、scope-aware sampler，以及 P0/P1 数据审计；
3. evidence-package extractor；
4. F/E/A 三种同 schema generator；
5. blind full-label annotator 与 candidate QA；
6. matched-pool builder；
7. organizer-style unified LoRA training/evaluation entry point；
8. paired bootstrap 和 wrong-actor error report。

NEVU adapter、去重 manifest 和预训练入口属于可选 C0–C3 分支，不是上述最小核心实现的一部分。

先不要实现 quality score weighting、pairwise loss、自动自适应预算、五种生成器 ensemble 或复杂 gate。它们都可以在主因果关系成立后成为后续工作。

## 12. 研究伦理与有效性威胁

- 生成 passage 使用虚构实体，不制造关于真实 actor 的新负面事实；真实文章只用于抽象事件结构和证据模板。
- gold 与 synthetic annotation 都有 LLM-related bias；不同模型家族不是统计独立性证明。
- TRAIN subevents 与 1,228 篇源 articles 不是独立同分布样本，且标签经过 cross-level integration；论文必须把它们称为多粒度辅助监督，不能把 10,822 当作新增新闻数来夸大数据规模。
- 使用 TRAIN subevents 合规不代表可以跨 split 使用 subevents。DEV subevent labels、Task-2 test inputs 和同事件近重复都可能造成 Task-1 泄漏，数据 manifest 必须按 `guid` 审计。
- NEVU 与 FEHU taxonomy 兼容但 split 和 scope 不同；公开 NEVU 混合了原论文内部划分。任何 NEVU-extra 结果都是跨数据集迁移证据，不是 FEHU gold augmentation，且依赖去重质量。
- 历史 340/900 共享 DeepSeek V4 Pro Preview provenance，而 `deepseek-v4-pro` 这一 API 字段本身不足以锁定可复现的后端 snapshot。同名服务更新会形成 generator drift；旧数据只能由内容 hash 固定，新主实验的各 arm 必须在同一冻结版本和时间窗口生成。
- 价值判断具有主观性。人工审核应判断“是否按 FEHU taxonomy 和 evidence rules 可支持”，而不是审核者个人是否赞同该价值判断。
- official DEV 已被历史实验多次使用，不能再称为完全盲 test；TRAIN internal holdout 和全部规则预冻结是必要补救，但无法彻底消除历史选择偏差。
- 只用两个 participant teams 的排名不能推断方法普适性；organizer baseline、受控 ablation、多个 seed 和 case analysis 更重要。
- 若生成 arm 的通过率不同，主训练按 accepted actor–unit 数匹配，同时报告达到该数量所需的 raw candidates 和成本，不能把“更严格筛选后样本更少”与方法效果混在一起。

## 13. 本次审核使用的主要一手文献

### FEHU、NEVU 与 human-value recognition

- Wang et al. **Event-Centric Human Value Understanding in News-Domain Texts: An Actor-Conditioned, Multi-Granularity Benchmark.** 2026. FEHU/NEVU 的核心任务差异、标注流程、多粒度证据和 LoRA 结果。  
  <https://arxiv.org/html/2603.17838>
- NTCIR-19 FEHU official site.  
  <https://sites.google.com/view/ntcir19fehu>
- NTCIR-19 FEHU Formal Data. TRAIN/DEV article 与 subevent 文件及正式 test scope 的官方说明。  
  <https://sites.google.com/view/ntcir19fehu/formal-data>
- Public NEVU dataset release. 用于核对公开文件、guid 排除范围与可选跨数据集预训练；不能代替 FEHU split。  
  <https://huggingface.co/datasets/WangYao-GoGoGo/NEVU>
- Kiesel et al. **SemEval-2023 Task 4: ValueEval: Identification of Human Values Behind Arguments.** 2023. 说明此前 value task 的 argument、undirected 和长尾背景。  
  <https://aclanthology.org/2023.semeval-1.313/>
- Fang et al. **Epicurus at SemEval-2023 Task 4: Improving Prediction of Human Values behind Arguments by Leveraging Their Definitions.** 2023. 支持将明确标签定义纳入模型，而不是只依赖类别 ID。  
  <https://arxiv.org/abs/2302.13925>

### 长尾、多标签与标签语义

- Huang et al. **Balancing Methods for Multi-label Text Classification with Long-Tailed Class Distribution.** EMNLP 2021. 说明普通 oversampling 会把共现 head labels 一起放大，distribution-balanced loss 是必要对照。  
  <https://aclanthology.org/2021.emnlp-main.643/>
- Xiao et al. **Label-Specific Document Representation for Multi-Label Text Classification.** EMNLP-IJCNLP 2019. 标签语义和 label-specific document representation 对低频类别有效。  
  <https://aclanthology.org/D19-1044/>
- Zhang et al. **Long-tailed Extreme Multi-label Text Classification by the Retrieval of Generated Pseudo Label Descriptions.** Findings of EACL 2023. 说明 label-description retrieval 是 tail prediction 的强替代路线。  
  <https://aclanthology.org/2023.findings-eacl.81/>
- Liu et al. **SEP-MLDC: A Simple and Effective Paradigm for Multi-Label Document Classification.** Findings of NAACL 2025. 结合标签语义扩展、tail pseudo-samples 与 contrastive representations；但其 document-level 假设不能原样搬到 FEHU。  
  <https://aclanthology.org/2025.findings-naacl.212/>
- Xu et al. **Noisy Multi-Label Text Classification via Instance-Label Pair Correction.** Findings of NAACL 2024. 说明 multi-label 噪声发生在 instance–label pair 层，false negatives 尤其难识别。  
  <https://aclanthology.org/2024.findings-naacl.93/>

### 数据增强、反事实与生成质量

- Li et al. **Synthetic Data Generation with Large Language Models for Text Classification: Potential and Limitations.** EMNLP 2023. LLM synthetic data 的效果并不稳定，任务和实例主观性越高，效果越差；这是 FEHU 必须认真对待的反证。  
  <https://aclanthology.org/2023.emnlp-main.647/>
- Peng et al. **Text Grafting: Near-Distribution Weak Supervision for Minority Classes in Text Classification.** EMNLP 2024. 支持从真实 corpus template 获得近分布 minority supervision，但论文场景不是 actor-conditioned multi-label news，故 B 只借鉴 template conditioning。  
  <https://aclanthology.org/2024.emnlp-main.219/>
- Sahu et al. **PromptMix: A Class Boundary Augmentation Method for Large Language Model Distillation.** EMNLP 2023. 支持“边界样本必须重新标注”，但其四个实验任务主要是少样本分类，不能证明 FEHU 的相邻 values 互斥。  
  <https://aclanthology.org/2023.emnlp-main.323/>
- Li and Caragea. **Target-Aware Data Augmentation for Stance Detection.** NAACL 2021. 支持增强时显式条件化 target；FEHU 进一步需要区分 actor role、value identity 和 direction。  
  <https://aclanthology.org/2021.naacl-main.148/>
- Ding et al. **A Rationale-centric Counterfactual Data Augmentation Method for Cross-Document Event Coreference Resolution.** NAACL 2024. 支持围绕 rationale 做受控事件反事实，而不是任意改写；任务不同，因此只作为 attribution intervention 的方法动机。  
  <https://aclanthology.org/2024.naacl-long.63/>
- Kim et al. **Evaluating Language Models as Synthetic Data Generators.** ACL 2025. generator 的数据生成能力不等于直接解题能力，真正的比较应看固定学生上的下游效用和数据质量。  
  <https://aclanthology.org/2025.acl-long.320/>

## 14. 最终建议

如果只保留一句话，这份计划应当是：

> 不再研究“多生成一点低频标签是否有用”，而研究“保留 FEHU 的行为链和 actor attribution 后，生成数据是否比同预算自由生成更有用”。

在问这句话之前，先完成 P0/P1，并把完整的 FEHU TRAIN article+subevent 作为 B0。这样既保留了教授提出的 LLM 数据增强方向，也避免把“补用了官方 subevent supervision”误写成合成数据的效果。NEVU-extra 只作为可选的跨数据集预训练因素，不与 FEHU gold 混称。

最终主张的逻辑顺序应是：**先建立完整官方多粒度基线，再测试 matched LLM augmentation 的边际收益，最后才询问 NEVU transfer 是否还会与增强互补。** 这也把 FEHU 相比一般 label-aware classification 最重要的特点放进了方法本身，并使 10 月前得到一个清楚的正面或负面结论成为可能。
