# FEHU 优化方案：实验执行路线图

**日期：** 2026-07-24  
**目的：** 将两个分析文档中的所有优化方案组织为可执行、可消融、成本可控的实验序列。  
**核心原则：** 零成本先行验证机制 → 低成本确认增益 → 中成本组合冲刺。所有参数调优使用 train 内部切分，dev 仅用于最终报告。

---

## 一、方案全景图：依赖关系与组合逻辑

### 1.1 方案分类

```
方案集 A：零成本后处理（可堆叠、可并行验证）
├── A1. Per-Class 保形预测阈值          [作用于: DeBERTa 概率输出]
├── A2. OT Logit 调整 (FreqAlign)        [作用于: DeBERTa 概率输出]
├── A3. 贝叶斯 Actor-Type 先验           [作用于: E1 离散输出 或 DeBERTa 概率]
├── A4. 标签共现图正则化                 [作用于: E1 离散输出]
└── A5. 混淆矩阵谱分解纠偏               [作用于: E1 离散输出]

方案集 B：多通道 E1（增加 API 调用，互相独立）
├── B1. 温度退火三通道 (TAME)           [+354 calls]
├── B2. Demo 随机化五通道 (CSS-E)        [+708 calls]
├── B3. Actor-Type 导向 Demo 选择        [+0 calls, 替换现有 demo 逻辑]
└── B4. 摘要-分类两阶段                  [+177 calls]

方案集 C：新推理结构（增加 API 调用，可与 A/B 叠加）
├── C1. 句子级证据聚合 (SLEA)            [+708 calls]
├── C2. 定向方向 QA 修复                 [+150 calls]
└── C3. E1+DeBERTa 混合推理              [+300 calls, 需先完成 A1]

方案集 D：重训练（GPU 成本，独立）
└── D1. 负样本重标定 (E1-softened BCE)   [需重训练 DeBERTa]
```

### 1.2 关键洞察：为什么零成本方案必须先做

1. **A1-A5 全部作用于 E1 或 DeBERTa 的已有输出**——不需要任何新 API 调用。
2. **它们的机制互相正交**（贝叶斯先验 ≠ 图正则化 ≠ 阈值校准），增益大概率可叠加。
3. **它们验证了核心数学假设**：如果 A3（贝叶斯先验）无效 → actor-type 信息对 FEHU 任务无用 → B3 也不必做。如果 A4（标签共现图）无效 → 标签间依存关系弱 → 不必设计更复杂的图模型。
4. **它们为零成本提供了上界估计**：A1-A5 的 max 增益告诉我们纯后处理的天花板，从而判断是否值得投入 API 预算做 B 和 C。

---

## 二、Phase 1：零成本扫描（Day 1，0 API 调用）

### 目标
- 验证 A1-A5 每个方法的独立增益
- 测量叠加增益（判断机制正交性）
- 确定哪些数学原理在 FEHU 数据上成立

### 2.1 Step 1.1 — 准备：建立内部校准协议

**关键：** 所有参数（阈值、温度系数、先验强度）必须在**非 dev 数据**上调优。

```
从 train 的 1228 篇文章中：
  切出 calib_articles (15%, ~184 篇, 约 500 actor 实例)  → 用于参数调优
  剩余 train_articles (~1044 篇)                           → 可用于 DeBERTa 训练
  dev_articles (177 篇)                                     → 仅用于最终报告
```

**实现：** 一个 `split_config.json` + 确定性切分函数（按 guid hash 取模，保证可复现）。

### 2.2 Step 1.2 — 准备：基线快照

需要收集以下已有产物的基线数据（均已在 `output/` 和 `new_check/` 中存在）：

| 数据 | 路径 | 用途 |
|---|---|---|
| E1 的 dev 预测 | `RH_test/E1_fewshot_repair/runs/20260722_152456/` | A3/A4/A5 的输入 |
| DeBERTa v2 的 dev 概率 | `output/research_hybrid_deberta_v2_liu_flash/20260714_184515/02_deberta_actor_probabilities.jsonl` | A1/A2 的输入 |
| DeBERTa F′ 的 dev 概率 | `new_check/phase3/` 对应 checkpoint | A1/A2 的输入 |
| Liu frozen 的 dev 预测 | `output/task1/runs/dev_deepseek_..._targeted_more_shot_balanced.../` | 对比基线 |

### 2.3 Step 1.3 — 单方法验证矩阵

对每个方法，在 `calib_articles` 上调优参数，在 `dev_articles` 上报告。每个方法预计 1-2 小时（纯计算，无 API）。

| 编号 | 方法 | 输入 | 调优参数 | 预期 dev 增益 (1b) |
|---|---|---|---|---|
| A1 | Per-Class 阈值 | DeBERTa 概率 | 108 个 $\tau_c$ | macro +0.03-0.06 |
| A2 | OT Logit 调整 | DeBERTa 概率 | $\lambda \in [0.3, 1.5]$ | macro +0.02-0.04 |
| A3 | 贝叶斯 Actor 先验 | E1 输出 | $\alpha \in [0.2, 0.8]$ | micro +0.003-0.008 |
| A4 | 标签共现图 | E1 输出 | 扩散步数 $T \in [1, 5]$ | micro +0.002-0.005 |
| A5 | 混淆矩阵纠偏 | E1 输出 | $r \in [2, 10], \eta \in [0.1, 0.5]$ | micro +0.001-0.004 |

### 2.4 Step 1.4 — 叠加实验

选取 Step 1.3 中**增益 > 0.002 且不互相抵消**的方法，做叠加（按 A3 → A4 → A5 的顺序，因为先验 → 结构 → 纠偏是自然的处理流水线）。

```
叠加序列：
  E1_raw → +A3 (先验) → +A4 (共现图) → +A5 (纠偏) → 测量每步边际增益
  DeBERTa_raw → +A1 (阈值) → +A2 (OT) → 测量每步边际增益
```

### 2.5 Phase 1 交付物

- `phase1_optimization/calibration/` — 内部校准集定义和参数搜索结果
- `phase1_optimization/results/A1_metrics.json` 到 `A5_metrics.json` — 单方法结果
- `phase1_optimization/results/stacking_metrics.json` — 叠加结果
- `phase1_optimization/reports/PHASE1_OPTIMIZATION_REPORT.md` — 结论：哪些方法有效、增益量级、是否正交

---

## 三、Phase 2：低成本多通道验证（Day 2-3，~500-1000 API 调用）

### 前提条件
Phase 1 完成，已知零成本后处理的天花板。如果 A3+A4+A5 已接近 Liu Ensemble 的 0.5543，则 Phase 2 可精简。

### 3.1 Step 2.1 — 最小可行温度退火（mini-TAME）

**为什么先做 TAME 而不是 CSS-E：** TAME 验证的是"信息瓶颈"假设（不同温度访问不同操作点），CSS-E 验证的是"demo 多样性"假设。TAME 的数学基础更坚实，且仅需 3 通道（vs CSS-E 的 5 通道）。

**实验设计：**
```
对 calib_articles (~184 篇):
  运行 T=0.05, T=0.10, T=0.30 三通道
  在 calib 上调优: majority 阈值 m ∈ {2, 3}, 是否启用 1-vote QA
  选取最佳配置

对 dev_articles (177 篇):
  用最佳配置运行一次 → 得到 TAME 的 dev 增益
```

**成本：** calib ~552 + dev ~531 = ~1083 Flash 调用（calib 可在后续方案中复用）。

**关键消融：**
- TAME vs E1+T=0.10 alone（验证多温度的价值）
- majority_only vs majority+QA（验证 QA 恢复的价值）
- 温度组合 {0.05, 0.10} vs {0.05, 0.10, 0.30}（验证 T=0.30 的边际价值）

### 3.2 Step 2.2 — 定向方向 QA（如果 Phase 1 后 DRR 仍 > 0.030）

**前提：** 从 E1 的 dev 翻转统计中提取翻转率最高的 10 个 direction:L1 类。

**实验：** 对 TAME 输出中涉及这 10 个类的预测，调用方向 QA（binary prompt："给定文章和 actor，这个价值是 aligned 还是 contradictory？证据是？"）。

**成本：** ~80-150 Flash 调用（取决于触发频率）。

### 3.3 Step 2.3 — 组合：TAME + Phase 1 最佳后处理

将 Phase 1 选出的最佳后处理流水线（如 A3+A4）应用于 TAME 的输出（而非 E1 原始输出）。

**注意：** A3（贝叶斯先验）和 A4（共现图）的数学输入是离散的标签集合——它们可以无缝应用于任何预测源（E1, TAME, CSS-E）。

### 3.4 Phase 2 交付物

- TAME dev 结果 vs E1 vs Liu Ensemble 的三方对比表（含 micro/macro/DRR/每类详情）
- 消融结果（温度数、majority 阈值、QA 启用）
- TAME + 后处理 vs 纯 TAME 对比

---

## 四、Phase 3：探索性方案（Day 4-7，视 Phase 1-2 结论决定是否执行）

### 4.1 决策门控

| Phase 1-2 结论 | Phase 3 动作 |
|---|---|
| TAME + 后处理 已达 0.560+ | 做 ×3 复制确认，准备 test 提交 |
| 1a macro 仍显著低于 Liu Ensemble | 执行 CSS-E（B2）以增加 L2 覆盖 |
| 18 个目标类仍有多类零召回 | 执行句子级聚合（C1）或混合推理（C3） |
| DeBERTa 仍未超过 prompt-only | 执行负样本重标定（D1）重训练 |

### 4.2 B2：Demo 随机化集成（CSS-E）

仅在 TAME 的 1a macro 不理想时执行。CSS-E 通过不同 demo 注入不同的 L2 组先验——这是 TAME（同 demo、不同温度）覆盖不到的维度。

**实验：** 从训练集中随机选 5 组 demo 对（每组 2 篇，满足 E1 的 demo 选择标准），运行 5 通道 → majority 3/5 集成。

**成本：** ~885 Flash 调用。

### 4.3 C1：句子级证据聚合（SLEA）

仅在 18 目标类问题持续存在时执行。这是 E3 的替代方案。

**简版先试：** 对 TAME 的每个预测标签，调用一次证据搜索（"这个句子是否支持 actor X 表达了价值 Y？给出是/否"），每篇文章批处理 10 个候选 → 每篇额外 ~2-3 次调用。

**成本：** ~350-530 Flash 调用。

### 4.4 D1：负样本重标定

仅在 DeBERTa 路线仍被需要时执行。使用 E1 的输出对训练集做 soft negative labeling，重训练 DeBERTa。

**成本：** ~177 Flash 调用（E1 标注训练集）+ GPU 训练时间。

---

## 五、组合路线图总览

```
                     Phase 1 (Day 1, 0 API)
                     ═══════════════════════
                     A1→A5 单方法验证
                          │
                     A3+A4+A5 叠加
                          │
                     ┌─────┴─────┐
                     │  增益判读   │
                     └─────┬─────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
          macro已达    micro已达    都未达
          期望         期望         期望
              │            │            │
              ▼            ▼            ▼
        跳过A1/A2    跳过A1/A2    执行全部A
              │            │            │
              └────────────┼────────────┘
                           │
                     Phase 2 (Day 2-3, ~1000 calls)
                     ═══════════════════════════════
                     B1: mini-TAME (3 temps)
                           │
                     B1 + Phase1最佳后处理
                           │
                     ┌─────┴─────┐
                     │ DRR>0.030? │
                     └─────┬─────┘
                       Yes │
                           ▼
                     C2: 定向方向QA
                           │
                     ┌─────┴──────┐
                     │ 结果判读    │
                     └─────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     micro>0.560      0.555-0.560      <0.555
     且1a macro       但1a macro       或目标类
     接近Liu          低于Liu          仍零召回
          │                │                │
          ▼                ▼                ▼
     Phase 3:          Phase 3:         Phase 3:
     ×3 复制           B2 CSS-E         C1 SLEA
     准备提交          +5 demo通道      +证据搜索
          │                │                │
          └────────────────┼────────────────┘
                           │
                    最终组合验证
                    (最佳B + 最佳A + 可选C)
                           │
                     ×3 复制 + CI
                           │
                     Test 提交准备
```

---

## 六、最小可行实验（如果时间极度有限）

如果只有 **1 天 + 1000 次 Flash 调用** 的预算，执行以下最小子集：

### 半天：零成本验证
```
1. A3（贝叶斯先验）应用于 E1 输出           [2 小时, 0 calls]
2. A4（共现图）叠加于 A3                    [1 小时, 0 calls]
→ 预期: micro +0.005-0.010, macro +0.01-0.03
```

### 半天：TAME + 组合
```
3. B1（TAME, 3 温度）在 dev 上运行          [~531 calls]
4. A3+A4 后处理应用于 TAME 输出             [1 小时, 0 calls]
→ 预期: micro 0.555-0.565
```

### 总成本
- API：~531 Flash 调用（约 $1-2）
- 计算：~4 小时（Python 后处理，无 GPU）
- 覆盖：8 个方案中最高 ROI 的 3 个

---

## 七、成功标准与决策规则

### 7.1 各阶段的 go/no-go 标准

| 检查点 | 标准 | Go | No-Go |
|---|---|---|---|
| Phase 1 后 | A3 增量 | ≥ +0.003 micro | < +0.001 → 跳过 A3，B3 也不必做 |
| Phase 1 后 | A4 增量 | ≥ +0.002 micro | < 0 → 标签独立性假设成立，跳过图方法 |
| Phase 1 后 | A1 增量 | macro ≥ +0.02 | < +0.005 → DeBERTa 概率空间已无潜力 |
| Phase 2 TAME 后 | vs E1 | micro > E1 + 0.005 | ≤ E1 → 信息瓶颈假设不成立 |
| Phase 2 组合后 | micro | ≥ 0.558 | < 0.552 → 考虑 CSS-E 或 SLEA |
| 最终 | ×3 复制 CI | 下限 > 0.550 | 下限 ≤ 0.545 → 方法优势不稳健 |

### 7.2 不做什么

- **不在 dev 上调参：** 所有参数在 `calib_articles` 上确定，dev 只跑一次最终配置。
- **不做全量网格搜索：** 每个方法只扫 3-5 个参数值，选取 calib 上最佳。
- **不盲目叠加：** 如果 A3+A4 的叠加增益 < 0.001，说明机制重叠，只保留更强的那个。
- **不复制非冠军方案：** 只对最终选定的最佳组合做 ×3 复制。

---

## 八、实现提示

### 8.1 代码组织

```
phase1_optimization/
├── scripts/
│   ├── split_calib.py          # 确定性切分 calib_articles
│   ├── method_a1_threshold.py   # Per-class 保形预测阈值
│   ├── method_a2_ot_logit.py    # OT Logit 调整
│   ├── method_a3_bayes_prior.py # 贝叶斯 Actor-Type 先验
│   ├── method_a4_graph.py       # 标签共现图正则化
│   ├── method_a5_spectral.py    # 混淆矩阵谱分解
│   └── stacking.py              # 叠加实验
├── outputs/                     # 单方法结果
├── calib/                       # 校准集定义和参数搜索
└── reports/                     # Phase 1 报告
```

### 8.2 避免的坑

1. **A3 需要 actor 类型标签：** 训练集的 actor 名是自然语言（如 "Emergency Services and Medical Staff"），可以用简单的关键词规则做类型聚类（10-15 个类型），不需要 LLM。
2. **A4 的共现矩阵必须从训练集构建：** 从 dev 构建会泄露 gold 信息。
3. **TAME 的 $T=0.30$ 可能触发 JSON 解析失败：** 需要复用 E1 的 retry 逻辑，但 $T=0.30$ 时最多重试 5 次（vs 当前的 3 次）。
4. **所有方法需要在 E1 的 actor-gold-only 约定下工作：** E1 只预测 gold 中存在的 actor——后处理方法不要破坏这个约定。

---

*本路线图将 14 个方案组织为 3 个 Phase、可独立验证的消融序列。核心策略：零成本验证机制 → 低成本确认增益 → 中成本组合冲刺。预计 3-7 天可完成全部关键实验。*
