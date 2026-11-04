# Task 2 方法复审：Prompt 成本与精度、ModernBERT 正例学习

日期：2026-11-05，Asia/Tokyo。性质：基于已归档结果和一手文献的复审及有限实验建议，不是新实验成绩，也不自动授权付费调用。

## 1. 决策及证据范围

当前最有依据的方向是：先用现有缓存完成诊断；ModernBERT 先做两个稀疏多标签损失对照；未来若恢复付费试验，先比较非思考与 low，再加入固定 fit 示例。暂不继续优化 S、扩展大量 seed、增加多阶段 API 流程或整批重跑 DEV。

这修正了此前只依据摘要便优先转向 8B 模型的判断。新上传的完整曲线揭示了值得先检验的优化问题。Llama 生成式任务微调仍是有官方依据的强基线候选，但不是“用了 LoRA 就能好”，也不保证超过筑波。

本轮直接阅读了研究分支提交 `0da5687da453dc3f891468c19e8e80c4024d2618` 的 v2 源码、完整报告、曲线、指标可用性表、逐标签统计，以及 v2 依赖的 v1 模型和损失文件。主分支仍为 `d9d070ba1290c30520f8a56c053fb753fe30e956`。此前“报告未上传”的限制现已解除。

- [已核查的 PILOT_RESULTS](https://github.com/volonearchmage/fehu-project/blob/0da5687da453dc3f891468c19e8e80c4024d2618/ntcir19_fehu-master/research/task2_scope_local_v2/review/pilot_20261105-023648/PILOT_RESULTS.md)
- [真实学习曲线 CSV](https://github.com/volonearchmage/fehu-project/blob/0da5687da453dc3f891468c19e8e80c4024d2618/ntcir19_fehu-master/research/task2_scope_local_v2/review/pilot_20261105-023648/learning_curves.csv)
- [已记录与缺失指标](https://github.com/volonearchmage/fehu-project/blob/0da5687da453dc3f891468c19e8e80c4024d2618/ntcir19_fehu-master/research/task2_scope_local_v2/review/pilot_20261105-023648/METRIC_AVAILABILITY.md)

本轮新做的统计均为离线汇总。复算脚本为 `research/task2_scope_diagnostics/review_evidence.py`；输出为 `output/task2_scope_diagnostics/review_20261105/offline_review.json`。同目录的 `source_snapshot/` 保存所用远端表格和原始 Git blob 标识，文本副本统一 LF；这些是审阅副本，不是训练输入。

USER_STOP 继续有效。本轮没有读取凭据、查询账户、调用模型 API、训练模型或评估新的 holdout/DEV/TEST 预测；没有修改旧实验和系统环境。下面的 API 方案须在以后明确授权和冻结预算后执行。

## 2. DeepSeek 实际能调什么

截至本次核查，官方接口如下。其他服务商的版本名、档位映射不可直接套用。

| 用户意图 | 官方接口实际行为 |
| --- | --- |
| 使用当前 Flash | `deepseek-flash` 对应 DeepSeek-V4.1-Flash-1017 |
| 换回 V4 Flash | 原模型已退役；旧名 `deepseek-v4-flash` 仍接受，但转到同一 V4.1-Flash-1017，不是旧权重对照 |
| 减少思考 | 正规档位 `low / high / max`，默认 high；显式关闭为 `thinking.type=disabled` |
| 思考模式 temperature=0 | 参数被忽略；不会因为传了 0 就获得低温思考模式 |
| 非思考模式 temperature=0 | 有效的低随机性设置，但不保证准确、保守或逐位可复现 |
| 改 top_p | Flash 思考模式有效范围 0.95–1；非思考模式固定 1，传值被忽略 |

当前 Chat endpoint 还接受 `reasoning_effort=none` 关闭思考；显式 thinking 对象优先决定开关。`medium`、`xhigh` 映射到 high，不是额外实验档位。没有核实到可通过官方 API 固定调用旧 V4 Flash 的 ID。

来源：[官方模型/版本说明](https://api-docs.deepseek.com/quick_start/pricing/)、[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)、[Chat 参数](https://api-docs.deepseek.com/api/create-chat-completion/)、[模型列表](https://api-docs.deepseek.com/api/list-models/)。必须记录执行时文档、请求/返回模型、时间、system_fingerprint（若返回）；别名无法证明远程权重永久不变。

旧实验实际显式设置了 `max_tokens=32768`，并没有设置 temperature/top_p。不能把目前 max 档的默认 128K 输出预算当成那次运行的预算。推理 token 也计入生成用量；降低输出上限不等同于减少 reasoning_effort，可能只是截断答案。

## 3. Prompt：成本问题已证实，质量原因仍需对照

成功的 508 个响应用量为：

| 项目 | 离线实测 |
| --- | ---: |
| 总输出 tokens | 8,669,748 |
| 其中 reasoning tokens | 8,606,301 |
| 可见答案 tokens | 63,447 |
| 推理占总输出比例 | 99.268% |
| 每事件平均推理 tokens | 16,941.5 |
| 每事件中位推理 tokens | 17,160.5 |
| 成功请求中位耗时 | 117.36 秒 |

这里只统计成功响应，不包括失败/截断的额外成本。高推理量是研究降成本的直接理由；它与误报同时存在，并不能证明 max 导致误报。Liu 的设置还同时改变了示例、标签上限、思考开关，且历史权重身份不确定，不能用两人的总分孤立估计思考量效应。

现有 prompt 已写明 actor 归属、当前事件范围、空列表、隐含价值、受害者与行动者、引语主体、禁止主题联想。增加类似“再仔细核查、不要误报”的文字并不是解决这些问题的新机制。

已有结果 TP/FP/FN=597/2701/384，P=18.10%、R=60.86%、F1=27.90%。716 个空金标候选贡献 964 个 FP；非空金标候选仍贡献 1737 个 FP。因此只判断主体是否参与事件，解决不了大多数误报。

| 每个主体—事件的标签数 | 金标候选数 | 预测候选数 |
| --- | ---: | ---: |
| 0 | 716 | 527 |
| 1 | 302 | 64 |
| 2 | 257 | 130 |
| 3及以上 | 53 | 607 |

模型不仅把一些空候选判为非空，还对非空候选扩展出很多关联标签。不能简单取 JSON 前两项：输出没有置信度排名，金标也允许超过两个标签。需要用 fit 示例展示标注边界，并检验价值、方向及目标事件是否得到同一证据支持。

1393 个 FP 的有向标签存在于同 actor 的文章 gold，却不存在于当前事件 gold；另外 1308 个连文章 gold 也没有。这是集合关系诊断，不是逐例人工认定的语义错误原因。前一类满足 child⊆article，单靠文章—事件包含约束无法排除。

如果完美删除全部 FP 而保留597个TP，既有候选的理论 F1 上限为75.67%、Recall仍为60.86%。这只是 oracle 上限，不是预计效果、算法或运行目标。

## 4. Prompt 的有限开发顺序

### 4.1 先比较运行配置，不同时重写 prompt

优先对同一冻结输入集合、原 prompt、JSON schema、候选覆盖运行两组：

| 组 | 请求配置 | 目的 |
| --- | --- | --- |
| A | `model=deepseek-flash`，`thinking.type=disabled`，`temperature=0` | 低成本候选 |
| B | 同模型，`thinking.type=enabled`，`reasoning_effort=low`，省略 temperature，固定 `top_p=1.0` | 低强度推理是否值得额外成本 |

例如通过 OpenAI SDK 构造请求时，thinking 应放入 extra_body。不要发出相互矛盾的开关：

```python
# 配置示意，不在本轮调用 API；messages、输出上限、预算另行冻结。
nonthinking = dict(model="deepseek-flash", temperature=0,
                   extra_body={"thinking": {"type": "disabled"}})
low_thinking = dict(model="deepseek-flash", reasoning_effort="low", top_p=1.0,
                    extra_body={"thinking": {"type": "enabled"}})
```

A 与 B 比较的是完整运行配置，不能将全部差异归因于思考量，因为只有 A 的温度可控。若需要分离温度效应，再加“非思考 temperature=1”；若需要严格归因于 effort，再在同一服务版本和批次、同 prompt/输入/top_p/预算/重试/选择规则下比较 low/high/max。不要一开始铺开所有档位。

历史 max 缓存保留为参考。只有在完全相同事件上才做配对分析；旧508子集已经被诊断使用，不能再称未见确认集。新 tune 样本上的成绩也不能与旧508分数直接相减。

建议未来先用固定64个 tune 子事件作运行配置筛选（例如对 `(seed=11,guid,event_id)` 做 SHA-256 排序取前64，选择时不读 gold，保留所有给定 actor）；这仅是开发诊断，不能保证代表长尾或全体新闻。主要比较保留到完整 tune，holdout继续封存。

必须在实际调用前选定并记录预算政策：

- 若要隔离 effort，low/high/max 用相同输出上限，且报告截断；上限相同也不等于实际耗费相同。
- 若目标是成本约束下的部署，可预设 A 4096、B 8192 的总输出上限，明确这是配置包比较，不能称纯 effort 消融。
- 64事件×2配置按上述上限，输出最多786,432 tokens；按本次官方高峰价 $1.20/百万计算，输出部分上界约 $0.944。输入、任何重试、后续配置另计；这不是账单或执行授权。[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)
- 用全局调用数、输出token预留和金额上限共同约束；重试也扣预算，不因失败自动增加总额度。保守控制并发，停止提交新请求时计入已在途请求。保留 finish_reason/usage/失败日志。
- JSON截断、空白或漏 actor 都是失败，不转换为空标签。报告完成率及失败分布；不能只挑各配置成功交集宣称胜出。完整固定集合未取得有效结果时，主比较标为不完整。

本轮 USER_STOP 未解除，故这些条件没有运行。

### 4.2 再增加固定的 fit-only 对比示例

选定一个运行配置后，只新增一包固定的4个简短示例，分别覆盖：提及但无标签；行动者与受影响者不同；同文其他事件有标签但目标事件没有；没有价值关键词仍有具体行为支持的隐含正例。只使用当前 fit 的真实标签，检查证据；不把已分析 DEV 错例改写成示例，不根据 tune gold检索演示。

示例包保持输入上下文、推理设置、输出格式不变。比较的是整个示例包，不把收益单独归功于某个例子。保留任意数量、多方向和空集合，不加固定2标签上限。

### 4.3 再考虑证据绑定或独立候选验证

每个保留标签可附短的原文句子ID，导出官方格式时去除证据字段。必须检查ID合法、引用存在；引用存在不证明判断正确，隐含价值也不要求价值词逐字出现。这个改动改变输出任务与token成本，应单独比较。

更进一步的验证器只看目标actor、目标事件、必要原文证据和一个候选价值定义，判断是否被支持；不把原始长推理作为核验依据。先冻结候选再评估保留TP/删除FP、召回上限、时延及总费用。每事件批量核验与每标签独立核验不同，要如实描述；无需默认四阶段多次API。

[Chain-of-Verification（ACL Findings 2024）](https://aclanthology.org/2024.findings-acl.212/)支持独立核验减少对初答的依赖，其实验是事实问答与生成，不是FEHU成绩保证。[Lost in the Middle（TACL 2024）](https://aclanthology.org/2024.tacl-1.9/)支持检查证据位置和局部输入，但不能证明2026年的DeepSeek具有同样故障。局部/全文对照与Liu路线相交，可作共享控制，不能再把“添加上下文”作为新颖性主张。

## 5. ModernBERT：新的诊断证据

| 方法 | 第1→3轮：正标签BCE | 第1→3轮：负标签BCE | tune选阈值F1 | tune AP |
| --- | --- | --- | ---: | ---: |
| T | 3.084→4.021 | 0.120→0.007 | 10.58% | 4.20% |
| J | 2.443→3.601 | 0.129→0.009 | 10.92% | 4.82% |
| S | 2.533→3.519 | 0.128→0.010 | 11.28% | 4.99% |

fit损失是训练模式下变化参数的累计值，不是固定checkpoint评估损失。它支持正例学习不足的疑虑，却不能据此单独确定欠拟合或唯一成因。fit AP/F1没有记录，需要补做本地固定checkpoint诊断；不需要访问holdout。

fit有23783个候选×108=2568564个二元位置，其中14624个为正，约0.569%；负/正约174.6:1。当前普通BCE在这种密度下可能主要通过压低分数改善总损失。BCE本身并非必然失败，负例不平衡也不是已经证明的唯一原因。

逐类表进一步显示：

- 在各自选定checkpoint/阈值下，T仅预测6个有向类，其中4个类命中过gold；它对全部3843个候选都预测 aligned:42（Be responsible），单类TP319、FP3524。这与频率基线的决策高度接近。
- 同样口径下J预测31类，S预测17类；micro-AP略高于fit频率基线，但实例区分仍弱。
- 本轮新增统计：在86个tune有正支持的类上，逐类AP平均为 T1.45%、J2.24%、S2.53%；同样类集合上的恒定分数AP均值0.70%。这是补充排序诊断，不是官方Macro-F1或训练先验。
- 四个fit无正例的类在tune合计只有1个金标，不能用“零样本标签学不了”解释整体低分。

模型已有主体条件：一个bag对应一个文章和一个actor，目标名称位于输入开头；事件各自mean pooling，共享108维线性头。不能说“所有主体一次输出相同向量”或“模型看不到actor”。ModernBERT包含周期性的全局注意力，长距离通路存在。[ModernBERT论文](https://arxiv.org/abs/2412.13663)

同文更换actor后的预测集合高度相似，是待核查线索。应按两个actor的gold本来是否不同分层，并查看原始分数差异；大量同为负例也会自然造成高相同率。

S最终checkpoint的正文章项2025个全部由article承接max，负项99.46%由article承接。这不是训练全过程统计，但不足以支持结构机制已充分发挥。加上child⊆article无法排除文章内错事件标签，继续只调S优先级较低。

## 6. ModernBERT 的最小优化研究

先补齐固定checkpoint的fit AP/F1、正负分数分布及gold不同actor对的辨别诊断。然后以T为共同架构，做两个新条件；现有T-BCE作为原基准，若实现重构改变基础行为，则必须补同代码路径BCE控制，不能只复用旧分数。

| 条件 | 变化 | 保持不变 |
| --- | --- | --- |
| T-WBCE | 只对正项加权，w=min(10,max(1,sqrt(Nneg/Npos)))；只由fit计数，Npos=0时w=1 | 输入、head、初始化、seed、有效batch和三轮预算 |
| T-ASL | gamma_pos=0，gamma_neg=4，margin=0.05 | 同上，保留所有空候选，不额外过采样 |

ASL用于削弱容易负标签的影响。数值取自[ASL论文附录B](https://arxiv.org/html/2009.14119v4)，证据主要来自图像多标签任务，须检验能否迁移到FEHU。WBCE是朴素控制，且旧Task1已使用过类似权重，它不是新的研究贡献。

实施时预先明确以下细节，避免把工程差异误当方法收益：

1. 新目录、新配置、新代码绑定；不修改冻结v2代码/receipt来假装旧验收适用。输入/原始ModernBERT revision与head初始化相同。seed11、3epochs、498更新、encoder2e-5/head1e-4、batch16、warmup及衰减沿用v2。没有按分数提前停或临时加轮数。
2. ASL使用FP32稳定计算，令p=sigmoid(z)、p_neg=max(p-margin,0)。正项数学上为-log(p)，实施用 `F.softplus(-z)`，避免极负logit经概率clamp后丢失正例纠错梯度；负项用 `-p_neg**4 * log1p(-p_neg)`，本配置p_neg不超过0.95。本建议固定对focal权重求导，不stop-gradient。只改负例形式，不叠加pos_weight。
3. [作者实现](https://github.com/Alibaba-MIIL/ASL/blob/main/src/loss_functions/losses.py)的两个类默认gamma_pos=1，且disable_torch_grad_focal_loss默认值不同，返回的是sum；不能靠默认值复现这里的设计。显式设置gamma_pos=0，记录采用的梯度语义和来源blob `72117224267978bd136908432e3a244d74baecaf`。避免拷贝全局set_grad_enabled写法改变调用方状态。
4. 继续按每bag有效事件数×108归一化，再平均bag；padding不产生梯度。WBCE仅乘正项，不把整个loss乘权重。ASL负例低于margin时应无梯度，正例梯度方向正确；这些做针对性的检查。
5. 每组继续记录无权重正/负BCE、每类AP、官方micro/macro-F1、P/R、预测数量、空候选FP、梯度裁剪前norm及触发比例。不同loss总值不直接比较；提升Recall却大幅增加FP不是自动成功。
6. tune阈值/checkpoint选择仍是v2精确全局扫描。fit的固定checkpoint指标用于诊断，用同一tune阈值可辅助报告fit F1；不能用fit最优阈值代替tune选择。保存失败和全部尝试。
7. 按原单组约13.2分钟，两个条件的训练与原验证量级约26分钟；新诊断、实现、编译和保存另计，ASL实际吞吐必须重测。这不是承诺总墙钟时间。

不把正例BCE/Recall设置成新的任意数值准入门槛。完成预算后，无收益也报告；如果只把分数整体抬高而AP/实例区分不改善，就不能称学到了更多语义。若有一致改善，再在选定共同配置上比较J/S及新seed，而非只替S扩大搜索。

## 7. 如果损失对照仍然弱，优先改什么

下一层是表示，而不是继续盲调阈值：

- **主体与事件显式交互**：把目标actor表示和事件表示一起交给分类器，或用actor条件池化。输入已含actor不代表充分利用它；须有容量匹配的事件-only head对照，并按gold不同actor对检查辨别。不能仅因扩大分类头变好就归因于主体。
- **单actor—单事件实例**：输入目标actor、事件及预定的必要上下文，减少多个事件之间的混合。改变了训练单位和计算量，不把相同epoch数称为相同计算预算。与Liu的上下文方向区分合作范围。
- **标签语义建模**：将54个价值定义和方向假设作为输入，通过共享的支持判断学习；比108个不带定义的输出节点更有语义共享机会。可参考[NLI文本分类](https://aclanthology.org/D19-1404/)和[GLiClass](https://arxiv.org/html/2508.07662v1)，但它们没有证明FEHU有效。候选裁剪可能损失召回，必须记录候选覆盖上限。

特别注意：FEHU的contradictory是“主体行为违背某个价值”，不等于NLI的contradiction类。要分别判断“该行为支持价值”和“该行为违背价值”两个假设；无证据可以是neutral，支持/违背可以同时存在，不能强制互斥。

在这些有限诊断之后，组织方风格Llama-3.1-8B-Instruct的任务微调是重要强对照：scope文本＋actor＋价值体系，文章和子事件分别监督，输出两组价值。4090上的4-bit QLoRA属于实现调整，应先核实显存与速度，不能声称精确复现未公开细节。LoRA只是更新手段，不是性能保证；旧DeBERTa本来就是LoRA。

## 8. 研究和评价边界

现在要区分两条不同失败形态：Prompt有候选覆盖但过度扩展；ModernBERT则主要依赖高频标签、正例学习弱。不能期待同一条“减少标签/增加召回”的规则同时解决二者。

所有新方法在fit/tune开发，示例/类频率从fit取；holdout未用于模型效果开发，应继续保留。旧508 DEV已被诊断使用，不能重新标为未见确认集。官方DEV中正文重叠层按既有审计单列。

最终比较需要同一集合、完整候选覆盖、同一官方评分器。Tune上的11.37%、旧508的27.90%、组织方TEST35.33%、筑波TEST46.68%不可相减宣称效果差距或领先。没有Liu同集合原始预测时不能声称已超过Liu；得到其缓存后可离线配对，无需新API。

方法贡献需要显示相对强对照的稳定增益与清楚机制；降低推理费用、换损失、加示例、LoRA、局部上下文本身都不是自动成立的创新。可以把“在指定成本下提高主体—事件—价值归属的可靠性”作为研究问题，结果决定采用哪种机制，不要求S必须胜出。

本轮完成点是这份审阅、可复算离线统计及新上传源码的核查；没有声称任何建议已经改善成绩。后续优先顺序：固定模型诊断 → 两个ModernBERT损失对照 → 有付费授权时做Prompt配置/示例对照 → 必要的表示或生成式强基线 → 冻结确认方案后才评估保留集。
