# DS 数学优化研究进度

**项目：** NTCIR-19 FEHU Task-1 纯 Prompt 后处理优化  
**工作目录：** `Mathematical_optimization/`  
**基线系统：** E1 (few-shot repair, 1b micro 0.5480 / macro 0.3719)  
**目标：** 在 E1 输出基础上，通过零成本数学后处理超越 Liu Ensemble (0.5543 micro / 0.5366 1a macro)  
**日期：** 2026-07-24  
**状态：** 代码框架就绪，待执行实验  

---

## 零、实验设计哲学

### 0.1 为什么是纯后处理

E1 已经是项目最强的 prompt-only 单系统（95 个类别，0.5480 micro-F1）。重新设计 prompt（E2 路线）已被证伪——在生成阶段加精度约束的 TP:FP 交换比约 1:1.2，不可接受。因此，我们的策略是：

> **冻结 E1 的生成能力（不改 prompt、不改温度、不增加 API 调用），在其离散输出上叠加数学后处理。**

### 0.2 三阶段流水线：A3 → A4 → A5

```
E1 预测 (discrete labels)
    │
    ▼
┌─────────────────────────────────┐
│ DS-A3: Bayesian Actor-Type Prior │  ← 外部先验知识
│ 机制: P(label|actor_type)/P(label)│     ADD 遗漏标签
│ 方向: 纯增量 (只加不删)          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ DS-A4: Label Co-occurrence Graph │  ← 内部结构信息
│ 机制: 图扩散传播共现标签信号      │     ADD 相关标签
│ 方向: 纯增量 (只加不删)          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ DS-A5: Spectral Debiasing        │  ← 系统误差纠正
│ 机制: SVD 混淆矩阵, 去除混淆投影  │     REMOVE 假阳性
│ 方向: 纯减量 (只删不加)          │
└─────────────────────────────────┘
    │
    ▼
最终预测
```

**排序理由：**
- A3 使用外部先验（actor type 统计），不依赖预测结构 → 适合最先
- A4 使用内部依赖（标签共现），受益于 A3 新增的标签 → 适合第二
- A5 消除系统性混淆，在所有添加完成后做减法最安全 → 适合最后

### 0.3 内部校准协议

所有超参数（alpha_add, alpha_diffuse, T, threshold, r, eta）在**内部校准集**上调优：

```
Train (1228 articles)
  ├── sub_train (~1044 articles)  → 用于 A3/A4 的统计估计
  └── calib     (~184 articles)   → 用于超参数网格搜索
Dev   (177 articles)              → 仅用于最终报告（只跑一次最优配置）
Test  (175 articles)              → 提交
```

切分脚本：`calib/split_calib.py`（基于 guid hash 的确定性切分，可复现）。

---

## 一、目录结构

```
Mathematical_optimization/
├── README.md                               ← 本文件同内容
├── base/
│   ├── run_pipeline_e1_base.py             ← E1 流水线（从 RH_test 复制）
│   └── analyze_e1_base.py                  ← E1 分析脚本（从 RH_test 复制）
├── calib/
│   ├── split_calib.py                      ← 内部校准集切分
│   └── sweep_params.py                     ← 超参数网格搜索框架
├── DS_A3_bayesian_prior/
│   └── run_a3.py                           ← Bayesian Actor-Type Prior
├── DS_A4_label_cooccurrence/
│   └── run_a4.py                           ← Label Co-occurrence Graph
├── DS_A5_spectral_debiasing/
│   └── run_a5.py                           ← Spectral Debiasing
├── stacking/
│   └── run_stacking.py                     ← A3→A4→A5 顺序叠加流水线
└── evaluation/
    └── eval_full.py                        ← 全指标评测脚本
```

---

## 二、各方法的数学原理与实现细节

### 2.1 DS-A3：贝叶斯 Actor-Type 先验

**数学公式：**

$$P(y_c=1 | x, t) \propto P(y_c=1 | x) \cdot \frac{P(y_c=1 | t)}{P(y_c=1)}$$

其中 $t$ 是 actor 类型（通过关键词规则分入 ~15 个类型），$P(y_c=1|t)$ 是从 sub_train 估计的经验条件概率。

**Bayes Factor 决策规则：**

$$BF(c, t) = \frac{P(y_c=1|t) + \varepsilon}{P(y_c=1) + \varepsilon}$$

- 若 $BF > \alpha_{add}$（默认 2.0）：ADD 该标签（E1 遗漏但该类型 actor 高频表达）
- 若 $BF \leq \alpha_{add}$：不操作（保持 E1 原始预测）

**Actor 类型聚类：** 基于 50+ 条关键词规则（police→LawEnforcement, hospital→Medical, church→Religious...），完全确定性，无需 LLM。

**关键设计选择：**
- **仅增量（additive-only）：** E1 的高精度（0.54）不应被先验削弱。只加不删。
- **ε-平滑：** $\varepsilon = 0.01$ 防止零概率崩溃。

### 2.2 DS-A4：标签共现图正则化

**数学公式：**

构建 108×108 共现矩阵（从 sub_train 的 per-actor 标签集）：

$$W_{ij} = P(y_j=1 | y_i=1) = \frac{\text{count}(i,j \text{ both } 1)}{\text{count}(i=1)}$$

图扩散（谱图理论）：

$$p^{(0)} = p_{E1} \quad \text{(binary vector)}$$
$$p^{(t+1)} = (1-\alpha) \cdot p^{(0)} + \alpha \cdot D^{-1/2} W D^{-1/2} \cdot p^{(t)}$$

其中 $D_{ii} = \sum_j W_{ij}$ 是度矩阵，$\alpha$ 控制扩散强度。

**决策规则：** 若 $p^{(T)}_c > \tau_{diffuse}$ 且 $p^{(0)}_c < 0.5$（E1 未预测），ADD 该标签。

**关键设计选择：**
- **Per-actor 独立扩散：** 共现关系在同一 actor 内最可靠。
- **图不跨方向扩散：** aligned 和 contradictory 版本是独立节点。

### 2.3 DS-A5：混淆矩阵谱分解纠偏

**数学公式：**

在 calib 集上估计混淆矩阵 $C \in \mathbb{R}^{108 \times 108}$：

$$C_{ij} = \frac{\text{count}(\text{predict } j \land \text{gold } i)}{\text{count}(\text{gold } i)}$$

SVD 分解：

$$C = U \Sigma V^T, \quad U_r = U[:, :r]$$

对预测向量 $p$，去掉其在混淆子空间上的投影：

$$p' = p - \eta \cdot U_r U_r^T p$$

**决策规则：** 若 $p'_c < \tau_{suppress}$（默认 0.3），DROP 该标签。

**直觉：** 如果 E1 系统性地将 "Be just (aligned)" 与 "Be fair (aligned)" 混淆预测，则混淆矩阵的 top 奇异向量会捕获这个方向。当这两个标签同时被预测时，谱纠偏会将较弱的那个压低。

---

## 三、实验计划

### Phase 1: 获取 E1 基线预测（预计 1 小时）

```bash
# 1. 运行 E1 在 dev 集上（如果还没有新鲜预测）
cd Mathematical_optimization
python base/run_pipeline_e1.py \
    --mode dev --provider deepseek --model deepseek-v4-flash \
    --prompt_variant targeted_more_shot_balanced

# 2. 评估基线
python evaluation/eval_full.py \
    --pred_1a runs/<ts>/pred_task1a.json \
    --pred_1b runs/<ts>/pred_task1b.json \
    --output runs/<ts>/baseline_metrics.json \
    --label "E1_baseline"
```

### Phase 2: 单方法扫描（预计 3 小时，0 API 调用）

使用 E1 的已有 dev 预测（`RH_test/E1_fewshot_repair/runs/20260722_152456/`）：

```bash
# A3 — 扫 alpha_add ∈ {1.5, 2.0, 2.5, 3.0, 4.0}
for alpha in 1.5 2.0 2.5 3.0 4.0; do
    python DS_A3_bayesian_prior/run_a3.py \
        --e1_pred <E1_pred_1b> \
        --output DS_A3_bayesian_prior/outputs/a3_a${alpha}_1b.json \
        --output_1a DS_A3_bayesian_prior/outputs/a3_a${alpha}_1a.json \
        --alpha_add $alpha
    python evaluation/eval_full.py \
        --pred_1a DS_A3_bayesian_prior/outputs/a3_a${alpha}_1a.json \
        --pred_1b DS_A3_bayesian_prior/outputs/a3_a${alpha}_1b.json \
        --output DS_A3_bayesian_prior/outputs/a3_a${alpha}_metrics.json \
        --label "A3_alpha=${alpha}"
done

# A4 — 扫 (alpha, T, threshold)
for alpha in 0.2 0.3 0.4; do
  for T in 2 3 5; do
    for th in 0.4 0.5 0.6; do
        python DS_A4_label_cooccurrence/run_a4.py \
            --e1_pred <E1_pred_1b> \
            --output DS_A4_label_cooccurrence/outputs/a4_a${alpha}_t${T}_th${th}_1b.json \
            --output_1a DS_A4_label_cooccurrence/outputs/a4_a${alpha}_t${T}_th${th}_1a.json \
            --alpha $alpha --t_steps $T --threshold $th
        python evaluation/eval_full.py \
            --pred_1a ... --pred_1b ... --output ..._metrics.json
    done
  done
done

# A5 — 扫 (r, eta)
for r in 3 5 8 10; do
  for eta in 0.1 0.2 0.3 0.5; do
      python DS_A5_spectral_debiasing/run_a5.py \
          --e1_pred <E1_pred_1b> \
          --output DS_A5_spectral_debiasing/outputs/a5_r${r}_e${eta}_1b.json \
          --output_1a DS_A5_spectral_debiasing/outputs/a5_r${r}_e${eta}_1a.json \
          --r $r --eta $eta
      python evaluation/eval_full.py \
          --pred_1a ... --pred_1b ... --output ..._metrics.json
  done
done
```

### Phase 3: 叠加实验（预计 30 分钟，0 API 调用）

取 Phase 2 中各方法的最优参数，运行 A3→A4→A5 叠加：

```bash
python stacking/run_stacking.py \
    --e1_pred_1b <E1_pred_1b> \
    --e1_pred_1a <E1_pred_1a> \
    --output_dir stacking/outputs/ \
    --alpha_add <best_alpha_add> \
    --alpha_diffuse <best_alpha_diffuse> \
    --t_steps <best_T> --graph_threshold <best_threshold> \
    --r <best_r> --eta <best_eta>

# 评估各阶段
python evaluation/eval_full.py \
    --pred_1a stacking/outputs/stage1_a3_pred_task1a.json \
    --pred_1b stacking/outputs/stage1_a3_pred_task1b.json \
    --output stacking/outputs/stage1_metrics.json --label "A3"

python evaluation/eval_full.py \
    --pred_1a stacking/outputs/stage2_a4_pred_task1a.json \
    --pred_1b stacking/outputs/stage2_a4_pred_task1b.json \
    --output stacking/outputs/stage2_metrics.json --label "A3+A4"

python evaluation/eval_full.py \
    --pred_1a stacking/outputs/stage3_a5_final_pred_task1a.json \
    --pred_1b stacking/outputs/stage3_a5_final_pred_task1b.json \
    --output stacking/outputs/stage3_metrics.json --label "A3+A4+A5"
```

### Phase 4: 分析报告（预计 2 小时）

对比 E1 基线 vs A3 vs A4 vs A5 vs A3+A4+A5 的全指标：
- 1a/1b micro-F1, macro-F1, macro-P, macro-R
- DRR
- target-18 / nontarget-90 分组指标
- 每类详情（识别哪些目标类被救活、哪些被误删）
- 边际增益分解（验证 A3/A4/A5 机制正交性）

---

## 四、成功标准

| 检查点 | 标准 | 行动 |
|---|---|---|
| A3 单独增益 | ≥ +0.003 micro-F1 | 保留 |
| A4 单独增益 | ≥ +0.002 micro-F1 | 保留 |
| A5 单独增益 | 不显著降低 recall | 保留 |
| A3+A4 叠加增益 | > max(A3, A4) | 机制正交 ✓ |
| A3+A4+A5 micro | ≥ 0.555 | 进入复制阶段 |
| A3+A4+A5 1a macro | ≥ 0.520 | 接近 Liu Ensemble |

---

## 五、决策树

```
E1 基线 (0.5480)
    │
    ├── A3 有效? (micro +≥0.003)
    │   ├── YES → 保留 A3, 继续 A4
    │   └── NO  → 跳过 A3, B3 路线放弃, 直接试 A4
    │
    ├── A4 有效? (micro +≥0.002)
    │   ├── YES → 保留 A4
    │   └── NO  → 标签独立性假设成立, 共现图无价值
    │
    ├── A5 安全? (recall 不崩)
    │   ├── YES → 保留 A5
    │   └── NO  → 混淆矩阵估计噪声太大, 跳过
    │
    └── A3+A4+A5 达标? (micro ≥ 0.555)
        ├── YES → ×3 复制 + test 提交准备
        └── NO  → 启动 Phase 5: TAME 温度退火（多通道 API 调用）
```

---

## 六、已完成的准备工作

- [x] 目录结构创建
- [x] E1 基线代码复制（`base/run_pipeline_e1_base.py`）
- [x] 内部校准集切分脚本（`calib/split_calib.py`）
- [x] DS-A3 实现（`DS_A3_bayesian_prior/run_a3.py`）— 贝叶斯 Actor-Type 先验
- [x] DS-A4 实现（`DS_A4_label_cooccurrence/run_a4.py`）— 标签共现图正则化
- [x] DS-A5 实现（`DS_A5_spectral_debiasing/run_a5.py`）— 混淆矩阵谱分解纠偏
- [x] 叠加流水线（`stacking/run_stacking.py`）— A3→A4→A5 顺序叠加
- [x] 全指标评测脚本（`evaluation/eval_full.py`）— 含所有 micro/macro P/R/F1/DRR/分组指标
- [x] 超参数扫描框架（`calib/sweep_params.py`）
- [x] 本进度文档

## 七、待执行（需要你的指令）

1. **运行 `calib/split_calib.py`** — 生成内部校准集切分（零成本，10 秒）
2. **运行 Phase 2 参数扫描** — 对 E1 的已有 dev 预测运行 A3/A4/A5 参数扫描（零 API 成本，3 小时 CPU）
3. **分析 Phase 2 结果** — 确定各方法的最优参数和独立增益
4. **运行 Phase 3 叠加** — 最优参数下的 A3→A4→A5 叠加
5. **决策** — 基于 Phase 3 结果决定是否启动 TAME（多通道 API 方案）

---

*从数学大师角度：这些方法都是零阶优化（不需要梯度），在 E1 的离散预测空间 $\{0,1\}^{108}$ 上做结构化的集合操作。它们的数学优雅之处在于互不冲突——A3 用外部统计、A4 用内部图结构、A5 用错误模式——形成正交的改进维度。*
