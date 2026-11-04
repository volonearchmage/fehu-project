# Codex SOL 思考：用 SOL-ACE 纯 Prompt 集成超过 WAIPS/Liu

**日期：** 2026-07-24

**范围：** NTCIR-19 FEHU Task-1，DeepSeek V4 Flash，文章级输入

**方法边界：** 不训练 DeBERTa/LoRA；允许多次 Prompt、确定性集合运算、仅用 TRAIN 内部校准得到的聚合规则

**状态：** v2 研究设计；已纳入用户提供的 WAIPS Dev/Test 完整矩阵及 2024–2026 一手论文，尚未执行新 API 实验

---

## 技术结论

新提供的 WAIPS 矩阵增强了、而不是推翻了原来的主线：真正有效的不是普通 majority，而是以高 precision 核心为底，再按标签选择性补回 recall。结合最新多标签与 test-time ensemble 论文，更有希望的路线升级为：

> **Codex-SOL-ACE（Structured Orthogonal Labeling + Atomic Candidate Ensemble）：让 precision、recall、结构化遗漏检索三个 Prompt view 产生互补候选；在 `(article, actor, L1, evidence)` 原子级融合，而不是对整份答案投票；用 TRAIN-only 的 source routing、局部标签似然和盲式 aspect verifiers 决定新增、替换及方向。**

其中 SOL 的三个核心词是：

- **Structured：** actor 独立、L2→L1 层级化、句子证据定位；
- **Orthogonal：** 不依赖三个高度相关的同 Prompt 样本，而让 precision view、recall view、actor 层级遗漏检索承担不同任务；
- **Atomic：** 合并单位是有 actor 与 evidence 的候选原子，不是一个完整 JSON 集合；
- **Likelihood-calibrated：** 不凭直觉做 union/majority，而按 source/vote pattern、局部竞争 logprob 与 TRAIN-calib 真实正确率决定加入、验证或拒绝。

这条路线将当前一个复杂决策拆成四个更容易校准的决策：

1. 引用证据是否真的属于这个 **actor**？
2. 该证据是否支持某个 **L1 value**？
3. 如果支持，target 是否可独立成立；与 top-k confusion neighbors 是 target-only、neighbor-only、both 还是 neither？
4. 该 value 的 **direction** 是 aligned、contradictory、both 还是 absent？

推荐的 Dev 工程目标仍是三次独立运行 Task-1b micro-F1 均值 **≥0.570**，但理由已经修正：它要越过同一 Dev 上的 label-aware 0.5657，并留下 0.0043 余量。正式 Test 目标另列为超过 WAIPS-1 的 0.5543；Dev 与 Test 不再混在同一排行榜里。

---

## 1. WAIPS 矩阵纠正了 Dev/Test 口径

[FEHU_PROJECT_PROGRESS_SUMMARY.md](./FEHU_PROJECT_PROGRESS_SUMMARY.md) 写于 2026-07-22，早于 E1、E3a、E4，也没有用户本轮提供的 WAIPS 完整矩阵。新证据表明：**0.5657 是 label-aware ensemble 的 Dev 成绩；0.5543 是该方案的 WAIPS-1 Test 提交成绩。** 旧文档把 0.5543 当成另一个 Dev “4-prompt ensemble”，这是本报告 v1 最重要的口径错误，现已更正。

### 1.1 用户提供的 WAIPS Full Experiment Matrix

Task-1b：

| Method | Set | Precision | Recall | Micro-F1 | Macro-F1 | DRR |
|---|---|---:|---:|---:|---:|---:|
| GPT-4o A0 | Dev | 0.5696 | 0.2448 | 0.3424 | 0.1496 | 0.0212 |
| DeepSeek baseline | Dev | 0.5716 | 0.4845 | 0.5245 | 0.3599 | 0.0243 |
| compact | Dev | 0.5698 | 0.4887 | 0.5261 | 0.3511 | 0.0261 |
| compact_strict | Dev | 0.6247 | 0.4255 | 0.5062 | 0.3234 | **0.0180** |
| majority vote | Dev | **0.6350** | 0.4636 | 0.5359 | 0.3532 | **0.0180** |
| Targeted balanced | Dev | 0.5750 | 0.5067 | 0.5387 | 0.3679 | 0.0302 |
| **label-aware ensemble** | **Dev** | **0.6149** | **0.5238** | **0.5657** | **0.3870** | **0.0279** |
| **WAIPS-1 submitted result** | **Test** | **0.5991** | **0.5157** | **0.5543** | **0.3277** | **0.0345** |

Task-1a：

| Method | Set | Precision | Recall | Micro-F1 | Macro-F1 |
|---|---|---:|---:|---:|---:|
| GPT-4o A0 | Dev | — | — | 0.4810 | — |
| DeepSeek baseline | Dev | 0.6846 | 0.6169 | 0.6490 | 0.5065 |
| compact | Dev | 0.6790 | 0.6126 | 0.6441 | 0.4871 |
| compact_strict | Dev | 0.7207 | 0.5325 | 0.6125 | 0.4576 |
| majority vote | Dev | — | — | 0.6507 | — |
| Targeted balanced | Dev | 0.6828 | 0.6303 | 0.6555 | 0.5044 |
| label-aware ensemble | Dev | — | — | 0.6555 | 0.5044 |
| **WAIPS-1 submitted result** | **Test** | **0.6731** | **0.6453** | **0.6589** | **0.5366** |

Test 行橙色第二行不是置信区间，而是相对 label-aware Dev 的差值；逐项相减完全吻合：1b micro −0.0114、macro −0.0593、precision −0.0158、recall −0.0081、DRR +0.0066；1a micro +0.0034、macro +0.0322。

Task-1a 的 label-aware precision/recall 在截图中未记录；本表保留为 `—`。现有外层代码显示其 Task-1a 输出直接继承 Targeted balanced，因此两者 P/R 应相同，但这是代码推断，不伪装成矩阵直接观测。

仓库本地冻结的 Liu single run 仍应独立保留：Task-1b micro/macro 为 0.5347/0.3385、DRR 0.0230。它与 WAIPS 矩阵中的 Targeted balanced 0.5387/0.3679 是两个不同 run，不合并、不当成四舍五入差异。

### 1.2 矩阵真正证明的是选择性 source routing

label-aware 相对 majority：

- precision −0.0201；
- recall **+0.0602**；
- micro-F1 **+0.0298**；
- macro-F1 **+0.0338**；
- DRR +0.0099。

label-aware 相对 Targeted balanced，则 precision +0.0399、recall +0.0171、micro +0.0270、macro +0.0191、DRR −0.0023。Task-1a 的 micro/macro 在矩阵中不变；结合 [label_aware_ensemble.py](../liu_method/label_aware_ensemble.py) 的外层逻辑，可确认 1a 直接取 targeted，1b 从 majority base 出发，仅为选定的 `direction:L1` 加入 targeted 候选。

因此最该复用的不是那十个 dev-derived label，而是机制：**precision core + class/source-conditional recall recovery**。新方案应在 TRAIN-calib 上学习带 shrinkage 的 source routing，再对分歧候选做 evidence-grounded QA，避免把 Dev add-list 直接搬到 Test。

另一个重要互补关系是：WAIPS label-aware 的 P/R 为 0.6149/0.5238，而 E1 为 0.5405/0.5556；E3a 更达到 0.5216/0.6201、macro 0.4173。WAIPS 擅长 precision/direction，E1/E3a 擅长 recall/tail。拿到各自 prediction JSON 后，首先应计算原子级 oracle union 和 source pattern，而不是立即再付费生成更多相似答案。

### 1.3 Dev 与 Test 应使用不同成功线

1. **Dev 冻结目标：** Task-1b micro 三次均值 ≥0.570；macro >0.3870，理想 ≥0.400；Task-1a macro >0.5044；DRR ≤0.0279。
2. **正式 Test 目标：** 只有提交后才能与 WAIPS-1 的 1b micro/macro 0.5543/0.3277、1a macro 0.5366、DRR 0.0345 比较。
3. **泛化风险：** WAIPS 的 1b macro 从 Dev 到 Test 下降 0.0593，远大于 micro 的 0.0114。这与 label-specific routing 对 tail/domain shift 敏感相一致，但仅凭一组 Dev/Test 不能证明因果。新方案必须把 macro、label-frequency bucket 与方向鲁棒性作为门槛，而不能只追 Dev micro。

还要区分“冲榜版本”和“论文级 clean 版本”：E1 继承了此前针对 dev 错误整理的 target-label recovery wording；WAIPS add-list 也来自 Dev 互补性分析。论文级版本必须只用 TRAIN 选择 demos、label cards、source routing 与阈值，Dev 只评一次。

### 1.4 当前可提交的本地 Prompt 证据

严格限制输入为 Task-1 test 可用的 `guid/title/content/actors` 后，本地最强文章级纯 Prompt 基座仍是 E1：

$$P=0.5405,\quad R=0.5556,\quad F_1=0.5480$$

E3a 的 0.5666/0.4173 证明结构化阅读对 recall 与 tail 有效，但它使用了 Test 不存在的官方 `subevents`。我们的任务不是复制 E3a 输入，而是用确定性原文分块、actor focus 和 label-wise audit，在合法字段上恢复同类信号。

---

## 2. 在做任何新实验前，必须先修复实验基座

### 2.1 当前 `Mathematical_optimization` 的 E1 基线是无效的全空运行

实测当前目录：

`Mathematical_optimization/runs/20260724_e1_baseline/`

- cache 有 177 个 guid；
- 177 个 value 全部是空列表；
- `pred_task1a.json` 和 `pred_task1b.json` 共 0 个预测；
- 用 `evaluation/eval_full.py` 重算得到 Task-1a/1b 全部 0 分。

这不是 E1 的 0.5480 结果，而是 API 失败产物。当前 runner 在三次失败后返回 `[]`，随后仍把该 `[]` 写入 cache；下次运行会将它当成功预测复用。这会让 A3/A4/A5 在一个全空输入上运行，却看起来“流程完成”。

**第 0 阶段必须做到：**

- cache entry 记录 `status=success|failure`；
- 合法的模型答案 `{"items": []}` 与调用失败严格区分；
- failure 不能进入成功 cache；
- cache identity 必须包含模型、prompt hash、文章 hash、temperature、thinking mode、max tokens；
- 完整运行前先做 5–10 篇 smoke，要求 schema 通过、非空率合理、失败数为 0；
- 旧全空 cache 只标记为 invalid，不参与任何比较；重新运行时使用新的 run id 或显式 refresh。

### 2.2 DeepSeek V4 的 thinking mode 会让现有“三温度”计划失效

这是当前方案中最重要的模型配置问题。

DeepSeek 官方文档说明：

- V4 thinking mode **默认 enabled**；
- thinking enabled 时，`temperature`、`top_p` 等参数**不会生效**，即使 API 为兼容性不报错；
- 要研究温度，必须显式设置 `thinking: {type: disabled}`。

官方来源：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)。

当前 `base/run_pipeline_e1_base.py` 只传了 `temperature`，没有固定 thinking mode。因此直接跑 `T={0.05,0.1,0.3}` 很可能只是三个名义标签，不能形成有效温度消融。相反，仓库的 `src/run_pipeline_prompt_v2.py` 已经显式使用 `{"thinking":{"type":"disabled"}}`，这部分 provider 处理值得复用。

**正确顺序不是先扫温度，而是：**

1. 同一 E1 prompt 做 thinking enabled vs disabled 干净对照；
2. 只有 thinking disabled 的质量可接受且输出确有多样性，才做三温度实验；
3. thinking enabled 的调用不传 temperature，把它当独立“推理模式”而非一个温度点；
4. run manifest 和 cache key 必须记录 thinking mode，以及响应中返回的 `system_fingerprint`（若有）。

### 2.3 A3/A4/A5 当前不能被当成已准备好的有效数学后处理

| 方法 | 当前问题 | 结论 |
|---|---|---|
| A3 Actor-Type Bayes | 推理阶段拿不到 actor name，代码把每个 actor type 固定为 `Unknown`；只遍历已有预测中的 actor；离散 E1 输出也不是可直接做 Bayes 乘法的概率 | 当前实现不能验证 Actor prior 假设 |
| A4 共现图扩散 | 用非对称 $P(j\mid i)$ 构造 $W$，却按对称图做 $D^{-1/2}WD^{-1/2}$；对 E1 二值输出直接加标签，没有文章证据 | 容易扩散头部共现和错误方向，不应直接 auto-add |
| A5 SVD 去偏 | 当前明确用 dev gold 构造混淆矩阵；这是 dev 泄露；把 gold-side 左奇异子空间直接投影到 prediction vector 上也没有保证能指出该删哪个 sibling | 不可用于正式比较或 test |
| `sweep_params.py` | 目前没有真正计算 calib F1，只统计 additions，主程序写出 `framework_ready` 占位结果 | 尚不是可用参数扫描器 |

这些方法不是完全没有价值，但应从“自动改预测”降级为“提出需要 Prompt 审查的 challenge candidate”，详见第 8 节。

---

## 3. 一个决定后处理成败的 F1 数学边界

E1 在 Task-1b 上：

$$TP=1328,\quad FP=1129,\quad FN=1062$$

记：

$$D=2TP+FP+FN=4847,\qquad F_1=\frac{2TP}{D}=0.5480$$

### 3.1 新增候选何时一定改善 micro-F1

假设加入 $n$ 个原本未预测的候选，其中真实正确率为 $q$，则：

$$TP'=TP+qn$$
$$FP'=FP+(1-q)n$$
$$FN'=FN-qn$$

新分母为 $D'=D+n$。可推出：

$$F_1'>F_1 \iff q>\frac{TP}{D}=\frac{F_1}{2}\approx 0.274$$

也就是说，**针对最终 direction-aware 的真正遗漏候选，只要接受后的 precision 高于约 27.4%，E1 的 micro-F1 就会上升。** 这解释了为什么 recall-oriented residual generator 是合理的。约 30%/35% 只能作为基于现有 Dev 的规划敏感性分析；clean 决策使用第 7 节由 TRAIN OOF anchor 与 article-cluster 下界得到的 $\tau_{add}$，不能把这里的 Dev 数字直接写入正式 selector。

### 3.2 删除 E1 预测为何非常危险

反过来，若删除 $n$ 个 E1 已有预测，其中真实正确率为 $q$，可推出：

$$F_1'>F_1 \iff q<\frac{F_1}{2}\approx0.274$$

即只有当被删组的真实正确率低于 27.4% 时，删除才值得。E2 和 E4c 的失败正符合这个条件：通用严格指令或 bulk verifier 删除了大量正确率远高于 27.4% 的候选，所以 precision 虽上升，F1 反而下降。

**因此，以 E1 为基座的 SOL-ACE 第一版不删除 E1 anchor 标签。** 27.4% 只描述这组 Dev 计数；clean 轨道只有当 TRAIN-calib 的 article-cluster upper bound 低于冻结 TRAIN anchor 的 $F^{TRAIN\text{-}OOF}/2$ 时，才允许针对可识别 strata 做删除实验。

### 3.3 要跨过同一 Dev 的 WAIPS 目标线，需要多少高质量新增候选

若只靠新增、其平均 precision 为 $q$，达到目标 $F^*$ 所需候选数：

$$n\geq\frac{F^*D-2TP}{2q-F^*}$$

| 新增候选 precision $q$ | 超过 Dev 0.5657 约需 | 达到 Dev 0.570 约需 | 达到 Dev 0.575 约需 |
|---:|---:|---:|---:|
| 0.40 | 367 | 465 | 583 |
| 0.50 | 198 | 249 | 309 |
| 0.60 | 136 | 170 | 210 |
| 0.70 | 104 | 129 | 159 |

这张表只在 E1 的同一 Dev 计数上成立。若 residual + verifier 能找到约 140 个、precision 约 60% 的净新增标签，就足以越过 WAIPS Dev 0.5657；若只能做到 40% precision，则需要近 370 个。WAIPS Test 0.5543 属于不同集合，不能代入这张 Dev 增益预算。

### 3.4 Direction 修正的价值可以独立计算

把一个“错误方向”改成正确方向时：

$$\Delta TP=+1,\quad\Delta FP=-1,\quad\Delta FN=-1$$

此时 $D$ 不变，每个净正确修正带来：

$$\Delta F_1=\frac{2}{4847}\approx0.000413$$

若 direction judge 对 $n$ 个被触发样本的修正正确率为 $r$，期望增益近似：

$$E[\Delta F_1]\approx\frac{2n(2r-1)}{4847}$$

所以方向翻转只有在 $r>0.5$ 时才有正期望；工程上应要求 TRAIN-calib 上 $r\geq0.65$ 才启用。Direction QA 不能因“模型有解释”就自动可信。

E1 报告中有 77 个 direction reversal，而 WAIPS label-aware Dev 的 DRR 为 0.0279。按理想“每次修正恰好把一项 FP+FN 变成 TP”的上界估算，净修正 **43** 个可跨过 Dev 0.5657，约 **54** 个可达到 Dev 0.570。因此 direction-only repair 是高杠杆实验；但这只是增益预算，不代表 77 个 reversal 都能被稳定识别。

上述推导假设新增候选确为当前预测外的唯一标签，且不存在 duplicate/conflict；真实实现必须先按 `(guid, actor, l1)` 去重，再单独处理 direction。

---

## 4. Codex-SOL-ACE 的推荐架构

```text
Task-1 article fields only
         │
         ├── P0: precision core（majority/strict 型）────────────┐
         ├── P1: recall core（E1/targeted 型）───────────────────┤
         └── P2: actor-isolated L2→L1 residual audit ───────────┘
                                                               │
                              atomic candidates                │
                    (guid, actor, L1, evidence_ids)             │
                                                               ▼
                    TRAIN-calib source-pattern routing
                     ├── high-confidence accept
                     ├── low-confidence reject
                     └── disagreement / singleton
                                  │
                                  ▼
              U: shortlisted label-wise local-likelihood QA
                                  │
                                  ▼
      A/V/S: blind actor attribution / value / sibling verifiers
                                  │
                                  ▼
                D: independent direction adjudication
                                  │
                                  ▼
                    final direction:L1 + derived L2
```

### 4.1 两条实现轨道：先用结果工件求上界，再做独立复现

刘的完整代码不是必要条件。只要能提供各方法在 Dev 的 prediction JSON 和 ensemble member 输出，就可以先走 **artifact-assisted 轨道**：把 WAIPS majority/label-aware 当作 precision source，把 E1/E3a 或我们自己的 recall 输出当作补充 source，直接计算交集、差集、oracle union、source-pattern precision 和逐标签互补性。它能最快回答“现有候选池是否已经足以超过 0.5657”。

同时保留 **clean reproducible 轨道**：不依赖刘的私有实现，只用公开方法描述和 TRAIN-only 校准，自己构造 P0/P1/P2。两条轨道必须分别报告，避免把“借用 WAIPS 预测后再增强”和“完全独立复现”混成同一个结论。

这里还有两条合法性边界：E3a 使用 Test 不存在的 `subevents`，只能参与 Dev diagnostic oracle，不能进入最终 Task-1 Test 系统；WAIPS label-aware 的十标签路由来自 Dev 分析，也只能作为既有竞赛工件或对照，不能用来证明 clean pipeline 无 Dev 调参。clean 轨道从 majority/自建 P0 起步，所有 routing 只在 TRAIN 内学习。

同理，拿 WAIPS Dev prediction 配 Dev gold 做 W0 是极有价值的**探索性诊断**，但一旦用它选择新架构，Dev 就不再是 untouched holdout。论文级 clean 结论必须在 TRAIN-calib 上重做同构的 source-mask/oracle 分析，冻结方案后才一次性评 Dev；artifact-assisted 结果与 clean 结果分表报告。

第一优先级不是多跑 API，而是拿现有输出做以下上界分析：

1. 在 `(guid, actor, direction:L1)` 和 direction-neutral `(guid, actor, L1)` 两个粒度分别算 pairwise overlap；
2. 对每种非空 source mask 统计 TP/FP、precision、覆盖标签和独有 TP；
3. 计算 union oracle、逐候选 oracle selector 和仅修 direction 的 oracle；
4. 若合理短名单的 oracle micro-F1 仍低于 0.570，则必须增加新 Prompt view；若已明显高于 0.570，重点应转向 selector，而不是 generator。

### 4.2 P0/P1/P2：功能正交，而不是三个近似副本

- **P0 precision core：** 优先使用 WAIPS majority/label-aware 预测工件；独立复现时使用 compact-strict 风格的 evidence gate 加三次低随机性 consensus。目标是提供高 precision anchor，而不是覆盖全部标签。
- **P1 recall core：** 使用 E1/Targeted-balanced 风格，保留完整 few-shot demos、无输出数量 cap，并显式固定 thinking mode。它负责发现 P0 漏掉的常规与尾部标签。
- **P2 structured rescue：** 每次只聚焦一个 actor，在确定性句子编号后的全文上执行 L2→L1 检索和 residual audit。它不再生成另一份完整答案，而只找 P0∪P1 尚未覆盖、且有精确证据的候选。

第一版把 P0/P1 已有预测视作 anchor，不做全局删除。只有 TRAIN-calib 能把某个可识别 source/label/evidence strata 的 direction-aware joint correctness **article-cluster upper bound** 压到冻结 TRAIN anchor 的 $F^{TRAIN\text{-}OOF}/2$ 以下，才允许做删除或替换实验。这比“永远保留 E1”更一般，也能利用 WAIPS 已显示出的 precision core。

### 4.3 P2 的 actor-isolated、L2→L1 value-only 检索

P2 每次只判断一个 actor，但仍给完整文章和所有 actor 名单用于归属消歧。关键区别是：**先不判断 direction。**

输入侧先做完全确定性的原文 scaffold：按自然段和句子边界编号；常规文章保留全文，超长文章才合并为约 120–220 token 的连续块并让相邻块重叠一句。它不调用 LLM 摘要、不删除中间句，也不把分块结果直接 union；模型仍需在看完所有编号块后输出一个 article-level consolidated set。这是在 Task-1 合法字段上逼近 E3a 的“局部结构”，同时避开 E4 自生成 evidence units 的信息瓶颈。

建议输出结构：

```json
{
  "actor_id": "...",
  "candidates": [
    {
      "l2_value_id": "...",
      "l1_value_id": "...",
      "evidence_sentence_ids": ["S12", "S13"],
      "confusion_neighbor_ids": ["...", "..."],
      "contrast": "why proposed label fits better"
    }
  ]
}
```

Prompt 的推理顺序应是：

1. 遍历该 actor 的 actions / statements / intentions / consequences；
2. 多选一个或多个可能的 L2 作为检索提示，而不是硬门控；未选中 L2 不能令其 L1 永久不可达；
3. 在候选 L2 的 children 中检索精确 L1，最后再做一次 flat L1 residual fallback；
4. 若多个 L1 各自满足定义，可同时保留；“各自有证据”不要求 sentence ID 不同，同一句行为可能支持多个 value；否则必须做 contrast；
5. 输出句子 ID，禁止用 actor 身份本身作为证据。

这比 E4 的 family scan 更安全：所有 20 个 L2 仍在一个全局竞争空间里，不把某一 family 单独拿出来强迫模型“必须找到点什么”。L2 只用于导航，flat fallback 防止 path-wise 早期错误级联；完整 taxonomy definition 不必一次塞给生成器，候选 verifier 再只加载 proposed label 与 confusion neighbors 的官方定义，降低注意力负担。

### 4.4 残差遗漏审计，而不是第二个完整分类器

P2 接收 P0/P1 已覆盖的 **value-only** 集合，任务只有一个：

> 找出文章中有明确 actor-specific evidence、但现有候选尚未覆盖的 L1 value；如果没有，返回空集。

每个新增候选必须同时给：

- exact sentence IDs；
- proposed L1；
- 1–3 个最可能混淆的 neighbor（允许跨 L2）；
- 对每个 neighbor 做一句反事实检查：“如果把 proposed 换成这个 neighbor，哪条定义不成立？”

P2 不做 4 个 family 的独立 exhaustive scan，不接受“常见 actor 通常有该价值”作为证据，也不对 P0/P1 候选做批量删除。它的目的不是再次生成一份完整预测，而是制造与已有 source 错误更低相关的 residual candidates。

### 4.5 U0/U1：先 unary support，再做局部 sibling competition

对每个 actor 建立候选集：

$$C_a=C_{P0}\cup C_{P1}\cup C_{P2}\cup C_{retrieval}$$

`retrieval` 只能从 TRAIN-only 标签卡或混淆邻居提出候选；它不能硬裁掉 generator 已发现的候选。固定“closest sibling”也不够：FEHU 的混淆可能跨 L2，且多个 L1 可以同时成立。正确顺序是：

1. **U0 unary support：** 对每个待审 target 独立判断 `SUPPORTED | ABSENT`，用单 token A/B 得到 $m_0=\log p(A)-\log p(B)$；按 TRAIN cross-fit 冻结的 `reject/accept` 两阈值分成 absent、uncertain、provisionally-supported，避免 sibling 竞争把可共存标签压掉；
2. **U1 sibling contrast：** 当 target 与某 neighbor 都 provisional support，或至少一个仍处在 uncertainty band 且二者有 TRAIN confusion edge 时，一次调用只比较一个 `(target, neighbor)`，判断 `target_only | neighbor_only | both | neither`；neighbor 可跨 L2，输出必须回显 `neighbor_id`；
3. 不同 competitor set 分开校准，不能共用一个全局 margin 阈值。

U1 可把四个答案映射为候选单 token A/B/C/D。若 A=`target_only`、B=`neighbor_only`、C=`both`、D=`neither`，target 的 one-step local margin 为：

$$m_{target}=\operatorname{logsumexp}(\ell_A,\ell_C)-\operatorname{logsumexp}(\ell_B,\ell_D),\qquad \ell_o=\log p(o\mid x)$$

这只是受 OPINE 的 label-wise 分解和 SCOTTA 的 local competition 启发的 **one-step constrained-choice scorer**，不是 OPINE 或 L3R 的直接复现：OPINE 还包含 scalar affinity、全标签 calibration/decoding；L3R 在原始标签生成路径的共享前缀分叉位置跨 token 聚合。

DeepSeek 官方接口支持 `logprobs` 与最多 20 个 `top_logprobs`，但**不保证**所有 A/B/C/D 都进入 top-20，也不保证带前导空格后的选项是单 token。正式使用前先在当前 V4 Flash 上对 thinking on/off 做 live smoke：确认 tokenizer/首个非空白 token、记录有效选项概率质量 $Z=\sum_{o\in O}p(o)$，并用成对交换或 Latin-square 平衡标签与选项位置；最终 margin 取平衡位置的均值。任一有效选项缺失、或 $Z$ 低于 TRAIN-calib 预注册的 schema-following 阈值时，把该观测标为 censored 并回退文本 verifier；不得把缺失项当成零概率。U 的 logprob 版本显式关闭 thinking，thinking-enabled verifier 作为另一个独立 cell。

逐候选调用不对全部 54 个 L1 暴力扫描。8–15 个/actor 只是 pilot 上限，不能成为硬剪枝规则；TRAIN-calib 必须验证 shortlist 保留未剪枝 source union 中至少 99% 的真阳性，否则扩大候选集。成本也要求先 routing：456 个 Dev gold actor × 8–15 候选 × 两个顺序已经约 7,300–13,700 次判断，尚未包含 A/V/S/D。因此高/低可靠 source pattern 直接跳过 U，只把分歧、singleton、tail 与高混淆项送入；代词、引语来源或跨段 attribution 不清时，从局部窗口回退到 actor mention chain，再回退全文。

### 4.6 A/V/S：拆开的盲式 aspect verifier

E4c 的 bulk verifier 从 8.44 labels/actor 的高噪 union 出发，并对整个候选池做删除，最终把 recall 和 F1 一起删掉。SOL-ACE 与它有四个本质区别：

1. **重点审查新增/分歧候选，高可靠 P0/P1 anchor 默认不删；**
2. **一个候选一个判断**，或最多很小的同类 batch；
3. verifier 不看 proposer、温度、vote count，避免确认偏差；
4. 只给 proposed/neighbor definitions 与最小充分证据上下文；归属不清时按 actor mention chain→全文回退。

与其让同一次调用同时证明所有事情，更稳的是把失败模式拆开：

- **A（attribution）：** 这段证据说的是目标 actor，还是报道者/受害者/对手？
- **V（value support）：** 去掉标签名后，这段行为或陈述是否满足目标定义的必要条件？
- **S（neighbor contrast）：** 对当前 `(target, neighbor)` 判断 target-only、neighbor-only、both、neither；
- **D（direction）：** 在 value 已成立的条件下才判断 aligned/contradictory/both/absent。

verifier 不看 proposer 名称、温度、vote count、原始方向或“请修正之前答案”之类暗示。只有发生争议的候选才串行调用多个 aspect；明显高可靠 source pattern 可跳过 value verifier、直接保留 anchor 或进入 D，低可靠新增项可在 value stage 拒绝，但最终新增仍不能绕过 direction-aware joint gate。

Verifier 输出使用一致的结构化字段：

```json
{
  "actor_attribution": "yes|no|uncertain",
  "proposed_supported": "yes|no|uncertain",
  "neighbor_id": "...",
  "l1_choice": "proposed_only|neighbor_only|both|neither|uncertain",
  "proposed_evidence_ids": ["S12"],
  "neighbor_evidence_ids": []
}
```

状态机固定如下，不能让低样本 posterior 绕过硬语义否决：

- `actor_attribution=no`、`proposed_supported=no`、`neighbor_only` 或 `neither`：拒绝 target；
- `uncertain`：按局部窗口→actor mention chain→全文升级一次；仍 uncertain 的新增候选拒绝，高可靠 anchor 保持原样；
- `neighbor_only`：可另建 neighbor candidate，但必须重新走其 U0 与 D，不能直接接受；
- `proposed_only` 或 `both`：target 才进入 D 与最终 joint threshold；
- `both` 中 neighbor 也需另建原子并独立走 U0/D，不能把两个标签压成一个答案。

### 4.7 D：value 接受后再判断 direction

项目最稳定的架构洞察一直是“value discovery 与 direction assignment 应解耦”。这个洞察不只适用于 DeBERTa×LLM，也适用于纯 Prompt。

- 三个 generator 的投票先全部降为 `(actor, l1)`，不让 direction disagreement 把同一 value 拆成两个低票候选；
- P0/P1-only 且无方向冲突的高可靠 anchor 默认保留原方向；
- 所有新增候选必须走单独的 direction judge；
- 任意 generator 间 direction 冲突、或同一 actor/L1 两方向同时出现时，走 direction judge；
- direction judge 只看文章证据、actor、value definition，不看原方向票数；
- TRAIN-calib 上修正准确率不足 0.65 时，只给新增候选定方向，不翻转已有 anchor。

若 direction judge 输出 `both`，必须分别给 aligned 与 contradictory 的证据 IDs，并展开成两个最终 108 类原子；没有两组可区分证据时返回 `uncertain`，不能用一个模糊的 `both` 同时加两类。

这既降低 DRR，也避免把“发现 value”和“判断 aligned/contradictory”两个误差源混在同一 vote 中。

### 4.8 TRAIN-only 标签卡与 coverage-diverse demos

对高混淆标签，从 TRAIN-core 的 FP/FN/near-miss 中生成并人工抽查一张冻结标签卡：官方定义、必须满足、明确排除、top confusion-neighbor 边界、正例证据、近似但不成立的反例。TRAIN 内还要拆 refinement fold 与 calibration fold，或做 nested cross-fitting，禁止用同一批错误同时改卡并验收。标签卡只服务于 U/V/S，不把全部长定义一次塞回全局 generator。

few-shot demo 也不应只按语义最近选择。可用覆盖—冗余目标从 TRAIN-core 选一个小集合 $S$：

$$J(S)=\sum_{l\in L}w_l\min(1,n_l(S))+\lambda\,\mathrm{DirCov}(S)+\eta\,\mathrm{ActorCov}(S)-\mu\,\mathrm{Redundancy}(S)$$

其中 tail label 权重 $w_l$ 更高；再用 MMR 或次模贪心选择兼顾当前文章相似度与全局覆盖的 demos。所有标签卡、混淆边和 demo bank 必须在看 Dev 结果前冻结。

---

## 5. 三温度方案：可以做，但应是受控子实验而非主假设

### 5.1 先纠正一个错误直觉

“低温必然高 precision、高温必然高 recall”在这种结构化多标签生成中没有理论保证。Temperature 只改变 token sampling 的随机性，不直接控制输出集合基数。高温可能：

- 找到新的真阳性；
- 只换一种 JSON 表述；
- 增加错误 sibling；
- 减少而非增加标签；
- 在 thinking enabled 时完全不起作用。

因此旧方案中预设 `T=0.05→P≈0.62`、`T=0.30→R≈0.64` 的数字应视为假设，不应写成数学预期。

### 5.2 正确的 temperature-only control

显式关闭 thinking，用完全相同的 E1 prompt 运行：

| 通道 | thinking | 初始候选温度 | 用途 |
|---|---|---:|---|
| T0 | disabled | 0.00 | 近确定性锚点 |
| T1 | disabled | 0.25 | 中等扰动 |
| T2 | disabled | 0.70 | 高多样性探索 |

这组值只是首轮 pilot，不是最终值。只改变 temperature，不同时改 top_p。先在 TRAIN-calib 的 30–50 篇分层小样本上测：

- 每个温度的 labels/actor、P/R/F1；
- value-level 与 direction:L1-level 的 pairwise Jaccard；
- 每个通道独有的 TP / FP；
- union oracle 能比 T0 多找多少 TP；
- 7 种非空 vote pattern `001…111` 的 empirical precision；
- 高温重复两次后的自身一致性；
- JSON empty/parse/truncation 率。

只有同时满足以下条件才扩到 full calib：

1. T1/T2 相对 T0 有非平凡 unique TP；
2. 新增 vote strata 的 direction-aware joint precision 有希望超过冻结 TRAIN anchor 的 $F_{OOF}/2$；
3. diversity 不是主要来自格式错误或方向随机翻转；
4. 单位新增 TP 的调用成本优于新 prompt view。

### 5.3 推荐的 DeepSeek 模式组合

相比“三个温度的同 Prompt”，我更推荐如下职责分工：

| 角色 | thinking | temperature | 原因 |
|---|---|---:|---|
| P0 precision core | enabled 与 disabled 先做基线对照后冻结 | enabled 时不传 | 复现历史行为并确定当前 V4 的最佳 precision 模式 |
| P1 recall core | disabled | 0.20–0.30 | 需要稳定结构，同时保留少量探索 |
| P2 residual auditor | disabled | 0.55–0.75 | 任务被限制为“只找遗漏”，更高多样性风险可控 |
| U/A/V/S/D verifier | enabled 与 disabled+logprobs 分开做 | enabled 时不传 | 推理 verifier 与可读局部似然是两种不同信号，不能混成同一配置 |

这不是把模型“当四个模型用”，而是让同一模型的 stochastic search 与 deliberate verification 各做擅长的部分。最终参数仍须在 TRAIN-calib 冻结。

### 5.4 如果三温度没有互补性，就改做 demo/prompt diversity

温度只是采样扰动，Prompt view 才能改变模型检索证据的条件信息。[HiEPS](https://aclanthology.org/2025.emnlp-main.918/) 在层级文本分类中集成不同 prompting strategy，[DIPPER](https://aclanthology.org/2025.emnlp-main.1801/) 则在推理任务中主动优化 Prompt 多样性；它们的任务并非 FEHU，但共同支持“功能差异比随机副本更值得优先验证”这一迁移假设。若 tri-temp 的 unique TP 很少或主要带来 unique FP，应停止温度扩展，改比较三种互斥 view：

1. E1 原始密度校准 demos；
2. 只从 TRAIN 检索、与当前文章语义接近但标签分布不同的 demo pair；
3. 只从 TRAIN 选择、最大化 L2 与 direction:L1 覆盖且惩罚 token 重复的 taxonomy-coverage demo pair。

推荐同时保留一个 `SC-3` 对照：将 TRAIN 内冻结的最佳 **thinking-disabled** 单一 policy 置于非零采样温度，同 prompt、同 sampler 独立运行三次。若总体最佳 policy 是 thinking-enabled（temperature 被忽略），另报 `Repeat-3`，不能把它冒充温度 self-consistency。`SC-3`、tri-temp 与 multi-view 必须在相同 article、相同调用数下比较，并同时报告等 token/费用预算的敏感性分析。归因不能只看 unique TP：用 paired article bootstrap 比较 candidate-oracle、accepted TP/FP、最终 direction-aware micro/macro F1 与 cost/accepted-TP；只有 multi-view 的完整 policy 在等预算下越过 SC-3，才能把收益归因于 Prompt 结构。

同一配置至少重复两次还可做一个受限诊断。2026 年 5 月的预印本 [Two Calls, Two Moments](https://arxiv.org/abs/2605.03379) 研究的是固定 model/prompt/sampler/parser、给定样本难度后 conditional-i.i.d. 的**二元正确性**调用；两次调用都必须有 gold。迁移到 FEHU 时，只对 TRAIN-calib 上预先定义的一个 direction-aware atom 判断“该原子成立/不成立”，估计两次 correctness bit 的相关性。它不覆盖集合 F1、union/plurality、不同温度或不同 Prompt view 的异质投票，也不能用输出 Jaccard 代替 correctness correlation。30–50 篇只够粗 pilot；本文只借用“稳定错误不会被重复票修复”的诊断思想，不用它认证 tri-temp ensemble。

---

## 6. 最新一手论文把方案从“生成标签集”推向“原子评分”

下表左栏是论文在各自数据集上的结果或机制，右栏是本文据此做出的 **FEHU 迁移推断**；后者尚未在 FEHU 上验证，不能把跨任务论文结果当成本项目的预期增益。

| 一手论文与直接证据 | 对 SOL-ACE 的迁移推断 | 边界 |
|---|---|---|
| [Large Language Models Do Multi-Label Classification Differently（EMNLP 2025）](https://aclanthology.org/2025.emnlp-main.126/) 发现自回归 LLM 在每个标签生成步会压制多数其他标签，且早期分布不代表最终集合 | 不让模型一次决定整套标签；对短名单做 label-wise/sibling-wise 问答，并 counterbalance 标签顺序 | 论文聚焦主观多标签任务；FEHU 的层级与 actor 归属更复杂 |
| [OPINE（Findings of ACL 2026）](https://aclanthology.org/2026.findings-acl.1617/) 将多标签分类改写为 scoring–calibration–refinement，并用独立 label affinity 与 pairwise refinement 处理共存和混淆 | 优先消融 U0 label-wise unary；只有 unary 均高的混淆项再进 U1/S。结构先验只参与校准，不直接替代文章证据 | 其 DeepSeek 消融最稳定支持的是 label-wise 分解；完整 prior/refinement 并非总能超过 label-wise，且部分设置 micro 上升时 macro 下降，所以 prior/pairwise 不默认全开 |
| [SCOTTA（Findings of ACL 2026）](https://aclanthology.org/2026.findings-acl.822/) 用 Label-set Local Likelihood Ratio 比较关键分支的有效竞争标签，并用次模目标平衡 exemplar 质量、覆盖与多样性 | 只迁移“局部竞争置信度”和“coverage/diversity demo 目标”，实现为 U1 one-step scorer 与 TRAIN-only demo bank | L3R-only 增益在论文消融中较小且不总为正，主要结果包含在线 memory；本文不采用顺序相关的 test pseudo-label cache，也不声称复现 SCOTTA |
| [Atomic Self-Consistency（EMNLP 2024）](https://aclanthology.org/2024.emnlp-main.706/) 在长答案任务中融合跨样本一致性较高的原子，而非挑选一份完整回答 | FEHU 原子定义为 `(guid, actor, L1, evidence_ids)`；先合并 value atom，再独立定 direction | 跨样本重复不等于真实，系统性幻觉也可能一致；每个 FEHU 原子仍需 article-evidence verification |
| [HiEPS（EMNLP 2025）](https://aclanthology.org/2025.emnlp-main.918/) 和 [DIPPER（EMNLP 2025）](https://aclanthology.org/2025.emnlp-main.1801/) 都从不同 prompting strategy 获取 ensemble diversity | 只迁移 prompt-view diversity：使用 precision/recall/structured 三个功能 view，并衡量 unique TP/FP | HiEPS 的 path-valid vote 假设每层一个 true label；FEHU 每层 cardinality 未知且可多标签，不能用 path frequency，必须逐 atom 判断。DIPPER 的数学推理结论也不直接迁移 |
| [Error-Driven Class Description Refinement（ACL Industry 2026）](https://aclanthology.org/2026.acl-industry.137/) 用误分类实例迭代修正 class description 与类别边界 | 从 TRAIN FP/FN 生成 inclusion、exclusion、sibling distinction 和 near-miss 标签卡，人工抽查后冻结 | 原论文会反复使用 validation 选弱类并验收更新；本文是重大改造，须在 TRAIN 内再拆 refinement/calibration fold 或 nested cross-fitting，论文增益不可直接迁移 |
| [Multi-Agent Verification（2025 预印本）](https://arxiv.org/abs/2502.20379) 把 verifier 数量/类型作为额外 test-time scaling axis；[Intrinsic Self-Correction（ACL 2025）](https://aclanthology.org/2025.acl-long.1314/) 发现无 oracle 自修正会摇摆并引入 Prompt bias | 使用 A/V/S/D 四种 fresh/blind verifier；每次从原文与定义重新判断，不展示 proposer 答案史 | MAV 没有证明 aspect 错误统计独立，同一 DeepSeek 的 A/V/S/D 仍可能强相关；自修正论文对 DeepSeek 的直接实验范围也不足以背书 FEHU，必须本地消融 |
| [Confidence-Informed Self-Consistency（Findings of ACL 2025）](https://aclanthology.org/2025.findings-acl.1030/) 对互斥 final answer 的多条 reasoning path 做 confidence-weighted vote，并强调 within-question ranking | 只在同一 `(actor,L1,direction)` 原子的多次/多源二元 verdict 内比较或加权，不采用无上下文的自报绝对概率 | 不把不同 L1 的 likelihood 归一化后互相竞争；TRAIN source reliability 是本文自己的迁移设计，不是 CISC 已验证结论 |

由这些证据导出的最关键变化是：**generator 的工作只到“提出有证据的原子”为止；真正的集合决策发生在候选层。** 这也是超越 WAIPS 的主要差异——继承它的 source routing 优点，但把固定十标签 add-list 升级为 TRAIN-calibrated、evidence-conditioned 的动态 selector。

---

## 7. 不假设 ensemble members 独立的可靠性聚合

同一 DeepSeek、相近 Prompt 产生的错误高度相关，因此不能把 2/3 vote 当成三个独立 Bernoulli classifier 的多数投票。正确做法是直接估计 vote pattern 的经验可靠性。

对每个候选定义特征组 $g$：

- value-level source mask，如 `P0=1,P1=0,P2=1`；
- 是否有两个通道指向重叠证据句；
- 是否存在 sibling 冲突；
- 是否存在 direction 冲突；
- 标签 TRAIN support bucket（只用于 shrinkage/分析，不做 dev add-list）；
- 局部 likelihood margin bucket；
- verifier verdict pattern；
- direction judge/source pattern。

value-level reliability 只负责决定“直接进入 D、送 U/A/V/S，还是放弃”；第 3 节的 $F_1/2$ 条件不能直接用于 direction-neutral L1，因为 value 正确但 direction 错误在 Task-1b 中仍产生一项 FP 和一项 FN。最终门槛必须作用在 direction-aware 原子：

$$q_{joint}=P(\text{value correct}\land\text{direction correct}\mid g)$$

样本足够时直接在 `(actor,L1,direction)` 上估计 $q_{joint}$；稀疏时可按概率链式分解：

$$q_{joint}=q_{value}\cdot P(\text{direction correct}\mid\text{value correct},g)$$

这里第二项是条件概率，不是假设 value 与 direction 独立。

直接给每个细标签一套独立阈值会在 tail 上过拟合。先定义 value 父组 $h_v=$ `(source mask, support bucket, U/A/V/S bucket)`；完成 D 后再定义 joint 父组 $h_j=$ `(h_v, direction source, direction thinking mode, direction verdict bucket)`。这避免把不同 direction judge 的正确率错误合并。对任一 child $c=(l,d)$，用当前训练折中**排除该 child**的父组后验均值：

$$\hat q_{h_j,-c}=\frac{t_{h_j,-c}+\alpha_{h_j}}{t_{h_j,-c}+f_{h_j,-c}+\alpha_{h_j}+\beta_{h_j}}$$

child 的经验 Bayes shrinkage point estimate 为：

$$\hat q^{EB}_{h_j,c}=\frac{t_{h_j,c}+\kappa\hat q_{h_j,-c}}{t_{h_j,c}+f_{h_j,c}+\kappa}$$

其中 $\kappa$ 控制收缩强度；tail child 主要继承父组，证据充足时由自身数据主导。$\alpha,\beta,\kappa$ 均只在当前训练折估计，并在每个 outer fold/bootstrap 内重拟合。候选层仍近似假设同组观测 exchangeable，而同一 article 内多个 actor/label 明显相关，所以 $\hat q^{EB}$ 只作 routing score，不能直接把候选数当独立样本算窄区间。

article-level 5-fold cross-fitting 必须覆盖**整条流水线**：每个 outer fold 的 prompt/view/temperature 选择、demo bank、label cards、retrieval index、confusion graph、neighbor list、source reliability 与阈值，只能由其他四折构建；held-out article 及可识别的同源文档不得作为其 demo/retrieval evidence。收集 OOF 结果后，才在全部 TRAIN 上重建供一次性 Dev 使用。

单个 child 的单侧 95% article-cluster lower bound 只作 routing heuristic，不声称同时覆盖所有被尝试 strata；每个直通 child 至少覆盖 30 个不同 article，否则回退父组或进入 verifier。最终 deployment gate 在完整 outer-fold OOF prediction 上做**成对 article-cluster bootstrap**：每次同时携带 anchor 与完整 policy 的同一批 article，重算去重、direction、全部已选 strata 的 micro/macro F1，要求 $\Delta$micro-F1 的单侧 95% 下界 >0 且 macro guardrail 通过。这样把 anchor 不确定性、两系统协方差和多 strata 合并效果放进最终判断；若要对每个 child 声称同时 95% 保证，则另需 max-t 或多重校正，本文不作该声明。

聚合决策：

- **高可靠 P0/P1 anchor：** 默认保留；
- **P2/retrieval 新候选：** 完成 D 后，若 $\hat q^{EB}_{h_j,c}$ 的 cluster routing bound 高于 $\tau_{add}$，可暂纳入 policy；
- **value 边界组：** 进入 U/A/V/S；通过硬状态机后再进入 D；
- **verifier 后组：** 完成 D 后，joint cluster routing bound 越过 $\tau_{add}$ 才暂纳入 policy；
- **任何自动删除：** 只有单侧 95% cluster upper bound 低于冻结 anchor 的 $F^{TRAIN\text{-}OOF}/2$ 才允许试验；第一版禁用；
- **样本过少的组：** 合并 strata 或一律走 V，不做 per-label 过拟合。

clean 轨道定义：

$$\tau_{add}=\frac{F^{TRAIN\text{-}OOF}_{anchor}}{2}+\delta$$

默认 $\delta=0$；若要额外 domain-shift margin，$\delta$ 必须在 TRAIN repeated split 上预注册。文中 0.274、约 0.283 和 0.30 都来自既有 Dev 结果，只能作为 artifact-assisted 的规划数字，不能声称是 clean 阈值。$\tau_{add}$ 是 child routing heuristic，完整 policy 仍必须通过上述 paired $\Delta F_1$ gate；macro 是独立 guardrail，因为 micro 的加入条件不能保证 tail label 改善。

### 7.1 先 value vote，后 direction vote

聚合顺序必须是：

1. 将所有 `direction:L1` 投影成 value-only L1；
2. 对 value vote pattern 做可靠性判断；
3. value 通过硬状态机后才收集方向意见；
4. 冲突、新增 singleton 和未被高可靠 anchor 覆盖的候选走 D；
5. 任何“同方向 ≥2 view”也只是一个 source mask，不视为独立投票，必须由 TRAIN-calib 的 joint precision 决定是否保留。

这避免正确 value 因方向分歧从 `2 votes` 被错误拆成两个 `1 vote`。

---

## 8. 如何保留 A3/A4/A5 的数学思想，但不让先验替代证据

### 8.1 Actor-Type prior：从 auto-add 改为 challenge routing

可以从 TRAIN-core 估计：

$$BF(c,t)=\frac{P(c\mid actor\ type=t)+\epsilon}{P(c)+\epsilon}$$

但 $BF$ 高只表示统计相关，不表示当前文章有证据。正确用途是：

- 若 $BF$ 高且 P0/P1 均未找到 $c$，把 $c$ 放入 P2 的 challenge list；
- Prompt 必须在当前文章中找到 exact evidence；
- 最终仍走 V；
- actor type 必须由原始 actor name/文章角色确定，不能使用当前 A3 的 `Unknown` fallback；
- `Criminal→contradictory just` 等身份先验只能触发检查，不能成为预测。

### 8.2 共现图：用 NPMI 提挑战，不直接扩散预测

直接用 $P(j\mid i)$ 会偏向高频标签。更稳的是 TRAIN-core 上带最小支持约束的 normalized PMI：

$$NPMI(i,j)=\frac{\log\frac{P(i,j)}{P(i)P(j)}}{-\log P(i,j)}$$

若已接受 $i$、且 $NPMI(i,j)$ 高而 $j$ 缺失，只把 $j$ 作为一条证据问题送入 P2/U/V。这样共现负责提高 candidate recall，文章证据负责 precision。

第一版应先做 direction-neutral L1 共现；direction 在 D 中判断。否则稀疏的 108 类共现矩阵会把统计噪声与方向噪声同时放大。

### 8.3 混淆矩阵：从 SVD 删除改为 contrastive sibling QA

混淆最有价值的信息不是一个全局奇异向量，而是“模型常在 c 与 d 之间混淆”。pairwise confusion graph 必须来自 TRAIN-core 的 OOF 错误；做 outer cross-fitting 时，每一折只能用其他折建立 graph/neighbor list，不能让 held-out fold 的 gold 错误参与它自己的 U1 验收。冻结后才用全部 TRAIN 重建供 Dev。随后：

- 若候选 c 的高混淆 sibling d 也被提出，V 直接回答 `c|d|both|neither`；
- 提供两者官方 definitions 和同一证据窗口；
- 不用 dev gold 建矩阵；
- 不从二值预测向量减去一个难解释的 SVD 投影。

这种改法保留了数学诊断能力，同时将最终语义判断交回 evidence-conditioned Prompt。

---

## 9. 最小高信息量实验矩阵

所有 prompt、demo、温度、thinking mode、聚合规则必须在 TRAIN 内部确定。建议不要只做随机 hash 15%：采用 article-level multi-label iterative stratification，使 calib 尽量覆盖方向、tail label、actor 数和文章长度；few-shot demos 只能从 TRAIN-core 选择，不能落入 calib。

### Phase 0：可信运行基座（必须先完成）

| 编号 | 实验/检查 | API | Go 条件 |
|---|---|---:|---|
| W0.1 | 导入 WAIPS majority/targeted/label-aware 与现有 E1/E3a prediction artifacts | 0 | schema、guid、actor、label 映射全部一致 |
| W0.2 | source mask、交并差、unique TP/FP、direction-neutral overlap | 0 | 能解释 label-aware 相对 majority 的增益来自哪些原子 |
| W0.3 | union oracle、selector oracle、direction-only oracle | 0 | 判断现有候选池是否有 ≥0.570 的可实现空间 |
| R0.1 | failure-aware cache + identity manifest | 0 | failure 不再被缓存成成功空集 |
| R0.2 | 5–10 篇 DeepSeek smoke | 5–10 | 0 unrecovered failure；响应和 schema 合理 |
| R0.3 | 当前 V4 上重跑 P1/E1 anchor | calib + Dev 后置 | 得到非空且指标可解释的新基线 |

WAIPS Dev 上的 W0 不需要刘的代码，也不需要新的 API 费用，可决定 artifact-assisted 探索的预算方向；clean 轨道必须在 TRAIN-calib 上复制 W0 逻辑，不能用 Dev oracle 决定正式架构。若对应候选池的 oracle 已经充足，就把预算花在 selector；若 oracle 都不够，再构造 P2。不要继续使用 `20260724_e1_baseline` 全空 cache，也不要把历史 0.5480 与当前升级后的模型调用混在同一 paired comparison 中。

### Phase 1：先验证模式与温度是否真的产生有用多样性

在 30–50 篇分层 TRAIN-calib pilot 上：

| Cell | Prompt | Thinking | Temperature | 回答的问题 |
|---|---|---|---:|---|
| M0 | E1 | enabled | 无效/不传 | 当前默认推理基线 |
| M1 | E1 | disabled | 0.00 | 非思考确定性基线 |
| M1R | E1 | disabled | 0.00，独立重复 | 在有 gold 的预定义二元原子上做相关性粗诊断 |
| M2 | E1 | disabled | 0.25 | 中温是否产生 unique TP |
| M3 | E1 | disabled | 0.70 | 高温多样性是否有正净值 |
| M3R | E1 | disabled | 0.70，独立重复 | 高温自身稳定性与投票潜力 |
| L0 | U0/U1 option smoke | disabled | 0.00 | 选项是否单 token、是否全部出现在 top-logprobs、counterbalance 是否稳定 |

主输出不是“哪个单点 F1 最高”，而是 pairwise overlap、unique TP/FP、vote-pattern precision 和 oracle union ceiling。若温度只制造相关噪声，立即停止 tri-temp，不扩全量。

30–50 篇 pilot 只能判断 schema、成本和多样性是否值得扩展；不能用七种稀疏 vote pattern 的点估计直接冻结 routing。正式阈值必须满足第 7 节的 cross-fit、distinct-article 与 cluster interval 要求。

### Phase 2：区分“温度多样性”和“Prompt 视角多样性”

| Cell | 组成 | 目的 |
|---|---|---|
| C0 | 新鲜 P1/E1 anchor | 当前模型基线 |
| C1 | 同 P1 prompt 的 tri-temp 与 SC-3 | 温度是否优于普通随机重复 |
| C2 | P0 + P1 + P2，全部同一低温 | Prompt view 单独效应 |
| C3 | P0 + P1 + P2，角色化 mode/temp | mode/temp 在正交视角上的边际效应 |
| C4 | C3 + value-level source reliability | 证明校准 routing 优于 union/majority |
| C5 | C4 + U0 unary support | label-wise 独立判断是否改善分歧项且保持 shortlist recall |
| C6 | C5 + U1 sibling/both contrast | 局部竞争相对 unary 的独立边际效应 |
| C7 | C6 + A/V/S aspect verifiers | value precision/attribution/sibling error 是否改善；此时不使用 $\tau_{add}$ |
| C8 | C7 + 单独 D + joint routing | joint precision、micro/DRR 与 policy-level paired $\Delta F_1$ gate |
| C9 | C8 + TRAIN 标签卡、BF/NPMI/confusion challenge | 尾部召回和 macro 是否增加且不泄漏 Dev |

每个 cell 至少报告：1a/1b micro P/R/F1、macro P/R/F1、DRR、TP/FP/FN、labels/actor、distinct classes、target-18、长文章/多 actor 切片、source-union oracle、shortlist TP retention、每个 strata 的 distinct article 数与 cluster interval、logprob option coverage/$Z$/censored rate、API calls、token usage、每新增 TP 成本、失败数。

### Phase 3：clean 轨道冻结后只看一次 Dev，再复制冠军

1. 在 TRAIN-calib 冻结唯一候选配置；
2. dev 上跑一次，不因结果修改 prompt/threshold；
3. 只有冠军做另外两次完整 API replication；
4. 报告三次均值、范围，以及按 article cluster bootstrap 的 95% CI；
5. 若已收到 Liu/WAIPS 逐文章预测，报告相同 article 上的 paired bootstrap $\Delta F_1$；若只有汇总表，明确只能比较数值目标线，不能声称 paired significance；
6. test 仅使用 `test_article_event_base.json` 的四个字段，不读取 Task-2 subevents。

以上“一次 Dev”只适用于所有决策均在 TRAIN 内完成的 clean 轨道；基于 WAIPS Dev oracle 选择过组件的 artifact-assisted 轨道必须标为 exploratory，不得复用这句话包装成未调参结果。

### 9.1 Dev 预注册成功标准

| 指标 | 最低标准 | 理想标准 |
|---|---:|---:|
| Task-1b micro-F1 | 三次均值 **>0.5657** | **≥0.570**，且 paired bootstrap $\Delta F_1$ 下界 >0 |
| Task-1b macro-F1 | **>0.3870** | ≥0.400 |
| Task-1a micro-F1 | **>0.6555** | ≥0.660 |
| Task-1a macro-F1 | **>0.5044** | ≥0.520 |
| DRR（guardrail） | ≤0.0279 | ≤0.0250 |
| unrecovered failures | 0 | 0 |

表中 paired bootstrap 条件仅在取得 WAIPS Dev prediction JSON 时适用。若只把 micro 推高、macro 或 DRR 显著恶化，应报告为不同 Pareto 点，而不是“全面超过”；DRR 等于 0.0279 只表示非劣，严格全面超过需 `<0.0279`。

Test 不参与调参，提交后再分别对照 WAIPS-1：Task-1b micro/macro `0.5543/0.3277`、Task-1a micro/macro `0.6589/0.5366`、DRR `0.0345`。不能用 Dev bootstrap 下界跨集合比较 Test 的 0.5543。

---

## 10. 不需要刘的全部代码：最小结果工件包

真正必要的是“每篇文章预测了什么、由哪个 source 提出”，而不是私有 Prompt 的全部实现。按价值排序，建议提供：

1. **Dev 最终预测：** majority、Targeted balanced、label-aware，最好再含 DeepSeek baseline、compact、compact_strict 的 `pred_task1a.json` 与 `pred_task1b.json`；
2. **ensemble member 预测：** 构成 majority 与 Targeted balanced 的每个独立 member 输出；这是估计错误相关性和 source routing 的关键；
3. **聚合 trace：** 每行至少有 `guid / actor / direction:L1 / source / vote_pattern / kept`；没有 trace 时可由 member 与 final 的集合差反推大部分逻辑；
4. **运行 manifest：** 模型快照与日期、thinking mode、temperature、top_p、max_tokens、response format、Prompt hash、taxonomy/data hash、evaluator 版本；不要包含 API key；
5. **去密后的 raw response/cache：** 包括 parse、retry、empty、truncation 状态，便于区分模型空预测与请求失败；
6. **细粒度指标：** per-label、per-article、按方向与 actor 数切片；若无法给 prediction JSON，这些是次优替代；
7. **WAIPS Test 提交预测与官方回执：** 只用于复现实验身份和未来合法 ensemble，不用于推断 Test gold；任何 Test ensemble 规则都必须在不利用 Test aggregate score/排行榜反馈的情况下预先冻结。

推荐目录结构：

```text
waips_results/
  README_matrix_semantics.md
  manifests/*.json
  predictions/dev/<method>/pred_task1a.json
  predictions/dev/<method>/pred_task1b.json
  predictions/test/waips1/*.json
  members/<ensemble>/<member>/*.json
  ensemble_trace.jsonl
  metrics/overall.json
  metrics/per_label.csv
  metrics/per_article.csv
  hashes.txt
```

如果只能先给一小部分，最有价值的最小集是：**majority、Targeted balanced、label-aware 的 Dev Task-1b prediction JSON，加上组成这两个 ensemble 的 member prediction JSON。** 有了它们就能先做 W0，判断超过 0.5657 的瓶颈到底是候选不足还是 selector 不够好。

---

## 11. 对已有负面实验的直接吸收

### E2 告诉我们：不能在 generator 内全局加严

E2 相对 E1：FP −124，但 TP −103，micro-F1 −0.018，macro-F1 −0.045，DRR没有改善。结论不是“证据无用”，而是**证据 gate 不能同时作用于所有已有候选**。SOL-ACE 将强 evidence gate 只用于低可靠 strata 与 residual additions，保留高可靠 anchor。

### E4 告诉我们：不能先制造高噪 union，再期待 bulk verifier 救场

E4b 达到 8.44 labels/actor、recall 0.6305，但 precision 只有 0.3915；E4c verifier 同时删 TP/FP，最终 F1 更低。SOL-ACE 的候选池必须先通过 value agreement、层级竞争和 sentence evidence 控制，再对新增小集合做候选级验证。

### E3a 告诉我们：局部结构有价值，但机器自造的结构不是免费替代品

E3a 用人工提供的 subevent scaffold 达到 0.5666；E4 自生成 evidence units 反而低于 E1。不能简单推出“先让模型总结/分段就行”。SOL-ACE 不单独生成中间摘要或 evidence ontology，而是让 value discovery 与原文 sentence IDs 同步完成，避免一个错误的抽取阶段成为信息瓶颈。

### V2 告诉我们：把全部完整 definitions 塞进一个 zero-shot prompt 不是答案

Pipeline V2 的 taxonomy-grounded zero-shot 明显低于 few-shot E1。Definitions 的最佳位置不是全局 generation prompt，而是候选级 verifier 和 sibling contrast，只在需要时加载局部定义。

---

## 12. 优先级与止损顺序

### 最高优先级

1. 接收 prediction artifacts，先完成 W0 source-mask 与 oracle audit；
2. 修 cache/failure 语义，重建可信 P1/E1；
3. 固定 thinking mode，做 on/off 对照；
4. 做小规模 tri-temp 与 SC-3 对照，而不是直接全 Dev 扩展；
5. 实现 P2 actor/L2→L1 residual audit；
6. 先实现 U0 unary，再消融 U1 局部 logprob margin，并用 direction-aware joint precision 的 cluster lower bound >$\tau_{add}$ 作为硬验收门槛；
7. 将 direction 独立出来，只处理新增/冲突项。

### 第二优先级

8. 用 TRAIN 错误生成并冻结 label cards；
9. 将 NPMI、Actor BF、pairwise confusion 改造成 challenge routing；
10. 只对冠军做三次完整复制；
11. 在长文章、多 actor、tail label 上做切片，确认增益机制与 E3a 类似。

### 明确不做或暂缓

- 不在 thinking enabled 下跑名义三温度；
- 不用 A3 的 actor role 直接加标签；
- 不用 A4 对二值输出无证据扩散；
- 不用 dev gold 的 A5/SVD 做正式结果；
- 不把 E3a 当 Task-1 test 方案；
- 不再做 E4 式 family-isolated union；
- 不用 generic verifier 批量删除高可靠 P0/P1 候选集；
- 不在 dev 上选择 label add-list、vote threshold 或 temperature；
- 不把各组件的预期增益简单相加成“理论 0.61”。

---

## 13. 对效果的诚实预期

在没有新实验前，最合理的先验排序是：

| 方向 | 成功先验 | 原因 |
|---|---|---|
| 现有 WAIPS/E1 artifacts 的 oracle audit | 最高信息价值、0 API | 先分清瓶颈是 candidate coverage 还是 selector，决定是否值得生成新 view |
| thinking on/off 固定与基线重建 | 必须做，不评价增益 | 当前实验身份不完整，temperature 可能无效 |
| 同 Prompt 三温度多数票 | 低到中 | 错误高度相关，高温≠高召回；但便宜且可快速证伪 |
| actor-isolated + L2→L1 value-only | 中到高 | 对准 E3a 的 actor/局部检索增益，同时保留全局类别竞争 |
| residual audit + label-wise likelihood/verifier | 高 | 在最终 direction-aware 原子上利用 $q>F_1/2$ 的可改善区域，且不破坏高可靠 anchor |
| value/direction 分解 | 高 | 与本项目最稳定的 hybrid 机制一致，纯 Prompt 同样适用 |
| Actor BF / NPMI challenge | 中 | 能扩大候选搜索，但只有文章证据能决定最终标签 |
| A3/A4/A5 直接改集合 | 低 | 当前实现和统计假设都不足以支持自动决策 |

如果 tri-temp 只是高度相关重复，它的合理增益可能接近 0。若 W0 显示 WAIPS precision source 与 E1/E3a recall source 的 oracle 也低于 0.570，再精巧的 ensemble selector 都无法过线，必须增加 P2；若 oracle 明显高于 0.570，先优化 source routing/U，而不是扩大生成池。对 E1 单基座而言，P2 若能产生约 100–200 个、验证后 precision 约 60% 的净新增候选，再配合少量正确方向修复，才有现实机会进入 0.566–0.575 区间。这个区间来自第 3 节的条件推导，不是效果承诺。

---

## 14. 建议的下一步交付

若能先提供第 10 节的 prediction artifacts，第一个交付应是零 API 的：

> **WAIPS-Artifact-Audit = schema 对齐 + source mask + pairwise overlap + unique TP/FP + oracle union/selector/direction + per-label complementarity。**

它会直接决定 artifact-assisted 探索的下一笔 API 预算应该投给 selector 还是新 generator；clean 决策仍要在 TRAIN-calib 复刻同一审计。随后第一个代码实验再做：

> **SOL-Pilot = failure-aware E1 + explicit thinking mode + 40 篇 TRAIN-calib 的 thinking on/off 与 T={0,0.25,0.70} 多样性诊断。**

它会回答最关键、也最便宜的三个问题：

1. 历史 E1 在当前 DeepSeek V4 上应使用 thinking enabled 还是 disabled？
2. 三温度是否真的产生 unique true positives，还是只产生随机噪声？
3. 同 Prompt 温度多样性是否值得继续，还是应直接转向 P0/P1/P2 的功能正交 Prompt？

只有 SOL-Pilot 通过第 5.2 节的 go/no-go 条件，才值得跑 full-calib tri-temp；否则立即把预算转到 actor-isolated residual + candidate verifier。

---

## 参考材料

### 仓库内证据

- 用户于 2026-07-24 提供的 WAIPS “Full Experiment Matrix”截图（本报告第 1.1 节已逐项转录）
- [FEHU_PROJECT_PROGRESS_SUMMARY.md](./FEHU_PROJECT_PROGRESS_SUMMARY.md)
- [FEHU_PROJECT_RESEARCH_SUMMARY.md](./FEHU_PROJECT_RESEARCH_SUMMARY.md)
- [Deepseek_分析.md](./Deepseek_分析.md)
- [FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md](./FEHU_DEEP_OPTIMIZATION_PLAN_20260724.md)
- [FEHU_OPTIMIZATION_EXPERIMENT_PLAN_20260724.md](./FEHU_OPTIMIZATION_EXPERIMENT_PLAN_20260724.md)
- [ds研究progress.md](./ds研究progress.md)
- [liu_method_pipeline3_audit.md](./liu_method_pipeline3_audit.md)
- [E1_REPORT.md](../RH_test/E1_fewshot_repair/reports/E1_REPORT.md)
- [E2_REPORT.md](../RH_test/E2_prompt_bias_control/reports/E2_REPORT.md)
- [E3a_REPORT.md](../RH_test/E3a_task1_only_subevent/reports/E3a_REPORT.md)
- [E4_DEV_EVALUATION_REPORT.md](../RH_test/E4_actor_evidence_decomposition_and_verification/reports/E4_DEV_EVALUATION_REPORT.md)

### DeepSeek 官方接口事实

- [DeepSeek V4 Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)
- [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- [DeepSeek V4 release notes](https://api-docs.deepseek.com/news/news260424/)

### 外部一手研究

- [Large Language Models Do Multi-Label Classification Differently](https://aclanthology.org/2025.emnlp-main.126/)
- [OPINE: A Prior-calibrated Scoring Framework for LLM-based Multi-label Scientific Opinion Classification](https://aclanthology.org/2026.findings-acl.1617/)
- [Structured Confidence–Guided Online Adaptation for LLM-based Multi-Label Classification](https://aclanthology.org/2026.findings-acl.822/)
- [Ensembling Prompting Strategies for Zero-Shot Hierarchical Text Classification with Large Language Models](https://aclanthology.org/2025.emnlp-main.918/)
- [Dipper: Diversity in Prompts for Producing Large Language Model Ensembles in Reasoning Tasks](https://aclanthology.org/2025.emnlp-main.1801/)
- [Atomic Self-Consistency for Better Long Form Generations](https://aclanthology.org/2024.emnlp-main.706/)
- [Beyond Instruction Optimization: Multi-Agent Error-Driven Class Description Refinement for LLM-Based Classification](https://aclanthology.org/2026.acl-industry.137/)
- [Understanding the Dark Side of LLMs’ Intrinsic Self-Correction](https://aclanthology.org/2025.acl-long.1314/)
- [Confidence Improves Self-Consistency in LLMs](https://aclanthology.org/2025.findings-acl.1030/)
- [Multi-Agent Verification: Scaling Test-Time Compute with Multiple Verifiers（预印本）](https://arxiv.org/abs/2502.20379)
- [Two Calls, Two Moments, and the Vote-Accuracy Curve of Repeated LLM Inference（预印本）](https://arxiv.org/abs/2605.03379)

---

**最终判断：** 超过 WAIPS/Liu 的最佳纯 Prompt 路线不是“更多相似输出”，而是先用现有结果证明候选上界，再以 WAIPS 型 precision core、E1 型 recall core 和 actor/L2→L1 structured rescue 构成原子候选池，最后用 TRAIN-calibrated source routing、局部似然、盲式 aspect verifiers 与单独的 direction judge 做选择。三温度可以作为控制组和探索器，但真正的优势应来自功能正交与候选级决策，而不是全局多数票。
