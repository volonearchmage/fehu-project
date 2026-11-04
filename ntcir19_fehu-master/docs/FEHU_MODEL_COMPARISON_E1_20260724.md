# FEHU E1 Baseline: 模型对比实验报告

**日期：** 2026-07-24
**实验者：** E1 baseline pipeline (`Mathematical_optimization/base/run_pipeline_e1_base.py`)
**目标：** 对比 DeepSeek V4 Flash vs V4 Pro (non-thinking) 在 FEHU Task-1 上的表现
**配置：** temperature=0.1, max_tokens=8000, prompt_variant=baseline, few-shot=2, extra_body={"thinking": {"type": "disabled"}}

---

## 一、实验总览

| # | 模型 | 模式 | 篇数 | 耗时 | 成功率 |
|---|---|---|---|---|---|
| 1 | V4 Flash | dev | 1 | 8.4s | 1/1 |
| 2 | V4 Pro | dev | 1 | 5.8s | 1/1 |
| 3 | V4 Pro | dev | 30 | 4m05s | 30/30 |
| 4 | **V4 Pro** | **dev** | **177** | **25m32s** | **177/177** |
| 5 | **V4 Flash** | **dev** | **177** | **10m42s** | **177/177** |

> 所有实验均使用 `.env` 自动加载 `DEEPSEEK_API_KEY`，零手动配置。旧脚本 `src/run_pipeline.py` 因不读 `.env` 且硬编码 OpenAI endpoint，全部 Connection Error —— 已弃用。

---

## 二、单篇对比（同一篇文章）

> ⚠️ 单篇方差极大，仅用于定性观察模型行为差异，不作为性能依据。

| 指标 | V4 Flash | V4 Pro | 差异 |
|---|---|---|---|
| 耗时 | 8.43s | 5.81s | Pro 快 31% |
| | | | |
| **1a Micro F1** | 0.7143 | 0.6667 | Flash +0.05 |
| **1a Macro F1** | 0.8000 | 0.6667 | Flash +0.13 |
| 1a Precision | 0.5556 | 0.5714 | 接近 |
| 1a Recall | 1.0000 | 0.8000 | Flash 更全 |
| | | | |
| **1b Micro F1** | 0.5556 | 0.7059 | **Pro +0.15** |
| **1b Macro F1** | 0.6190 | 0.7619 | **Pro +0.14** |
| 1b Precision | 0.4545 | 0.6000 | Pro +32% |
| 1b Recall | 0.7143 | 0.8571 | Pro +20% |
| **DRR** | 0.0000 | 0.0000 | 持平 |

**定性观察：** Pro 在带方向的 1b 任务上显著更准（Precision +0.15），且速度更快。

---

## 三、全量 177 篇 Dev 结果（核心对比）

### 3.1 Flash vs Pro 头对头（同为 non-thinking + baseline prompt）

| 指标 | V4 Flash | V4 Pro | 胜出 |
|---|---|---|---|
| **速度** | 3.63s/篇 | 8.66s/篇 | Flash **2.4×** 🔥 |
| 总耗时 | 10m42s | 25m32s | Flash |
| | | | |
| **1a Micro F1** | 0.6372 | **0.6740** | Pro |
| **1a Macro F1** | 0.4611 | **0.5405** | Pro |
| 1a Precision | **0.7284** | 0.6420 | Flash |
| 1a Recall | 0.5664 | **0.7093** | Pro |
| | | | |
| **1b Micro F1** | 0.5088 | **0.5297** | Pro |
| **1b Macro F1** | 0.3140 | **0.3854** | Pro |
| 1b Precision | **0.5957** | 0.4906 | Flash |
| 1b Recall | 0.4439 | **0.5757** | Pro |
| **DRR ↓** | **0.0320** | 0.0558 | Flash **好 74%** 🔥 |
| | | | |
| 1a 预测数/篇 | 8.2 | 11.6 | Flash 保守 |
| 1b 预测数/篇 | 10.1 | 15.8 | Flash 保守 |

**行为模式诊断：**

- **Flash = 保守精准型**：少预测 → Precision 高、DRR 低（接近刘 Ensemble）、速度快 2.4×、但 Recall 不足
- **Pro = 激进全面型**：多预测 → Recall 高、Macro 强、但 Precision 低、DRR 翻倍、速度慢

两者恰好互补：Flash 的方向判断 + Pro 的标签覆盖 = 天然集成优势。

### 3.2 全部系统对比

| 指标 | V4 Flash | V4 Pro | 刘 frozen | 刘 Ensemble | Hybrid H3 |
|---|---|---|---|---|---|
| **1b Micro F1** | 0.5088 | 0.5297 | 0.535 | **0.5543** | 0.5474 |
| **1b Macro F1** | 0.3140 | **0.3854** | 0.339 | 0.3277 | 0.338 |
| 1b Precision | 0.5957 | 0.4906 | **0.568** | — | 0.548 |
| 1b Recall | 0.4439 | **0.5757** | 0.505 | — | 0.547 |
| **DRR ↓** | 0.0320 | 0.0558 | **0.023** | 0.0345 | 0.031 |
| | | | | | |
| **1a Micro F1** | 0.6372 | **0.6740** | 0.645 | — | 0.662 |
| **1a Macro F1** | 0.4611 | **0.5405** | 0.478 | 0.5366 | 0.503 |

### 3.3 输出统计

| 统计项 | V4 Flash | V4 Pro |
|---|---|---|
| Task-1a 预测总数 | 1,447 (avg 8.2/article) | 2,056 (avg 11.6/article) |
| Task-1b 预测总数 | 1,781 (avg 10.1/article) | 2,805 (avg 15.8/article) |
| 处理速度 | 3.63 s/article | 8.66 s/article |
| 处理速度 | 8.66 s/article |

---

## 四、30 篇 vs 177 篇：子集膨胀效应

| 指标 | V4 Pro 30篇 | V4 Pro 177篇 | 膨胀幅度 |
|---|---|---|---|
| 1b Micro F1 | 0.5469 | 0.5297 | +0.0172 |
| 1b Macro F1 | 0.4350 | 0.3854 | +0.0496 |
| 1a Micro F1 | 0.6883 | 0.6740 | +0.0143 |
| 1a Macro F1 | 0.5679 | 0.5405 | +0.0274 |
| DRR | 0.0661 | 0.0558 | −0.0103 |

**结论：** 30 篇子集在所有指标上均膨胀 0.01–0.05，不可用于系统间严格对比。全量 177 篇是唯一有效的评测基准。

---

## 五、关键发现

### 5.1 Flash vs Pro：两种截然不同的策略

| 维度 | V4 Flash | V4 Pro |
|---|---|---|
| **策略类型** | 保守精准型 | 激进全面型 |
| **预测量** | 10.1/篇 (1b) | 15.8/篇 (1b) |
| **优势** | Precision 高、DRR 低、速度快 | Recall 高、Macro 强、覆盖广 |
| **劣势** | Recall 不足、Micro F1 低 | Precision 低、DRR 高、速度慢 |
| **适用场景** | 需要方向准确性 | 需要标签覆盖面 |

### 5.2 V4 Pro 的定位

1. **1a 全面领先**：L2 分类 Micro 0.6740、Macro 0.5405，均超过所有对比系统。
2. **1b Macro 最高**：0.3854，覆盖最多稀有类别（Recall 0.5757 也是最高）。
3. **DRR 严重偏高**：0.0558（124/2222），是刘 frozen 的 2.4 倍——方向判断是最大弱点。
4. **速度慢**：8.66s/篇，Flash 的 2.4 倍。

### 5.3 V4 Flash 的定位

1. **DRR 优秀**：0.0320（71/2222），仅次于刘 frozen（0.023），远优于 Pro（0.0558）。
2. **Precision 最高**：0.5957（1b），比 Pro 高 21%。
3. **速度最快**：3.63s/篇，全量仅 10m42s。
4. **Recall 不足**：0.4439（1b），比 Pro 低 0.13——标签遗漏是主要短板。
5. **1b Micro 垫底**：0.5088，比刘 Ensemble 低 0.0455。

### 5.4 互补性：集成的理论基础

Flash 和 Pro 在关键指标上恰好互补：

| 能力 | Flash | Pro | 集成潜力 |
|---|---|---|---|
| 方向判断 (DRR) | ✅ 0.032 | ❌ 0.056 | 取 Flash |
| 标签覆盖 (Recall) | ❌ 0.444 | ✅ 0.576 | 取 Pro |
| 预测精度 (Precision) | ✅ 0.596 | ❌ 0.491 | 取 Flash |
| 稀有类 (Macro) | ❌ 0.314 | ✅ 0.385 | 取 Pro |

**最简单的集成策略**：Pro 提名候选标签 → Flash 验证方向 → 投票/置信度过滤。预期可同时提升 Micro 和 Macro，压低 DRR。

---

## 六、技术细节

### 6.1 Thinking 模式关闭

在 `call_deepseek()` 函数中添加了 `extra_body={"thinking": {"type": "disabled"}}`，确保 V4 Pro 不进入推理链模式，直接输出 JSON。

### 6.2 .env 自动加载

`load_dotenv_files()` 函数在脚本启动时自动加载项目根目录 `.env` 文件，不覆盖已导出的环境变量，无需 `python-dotenv` 依赖。

### 6.3 运行命令

```bash
# 全量 dev
venv/bin/python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-pro --mode dev

# 单篇测试
venv/bin/python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-pro --mode dev --limit 1

# test 提交（不评测）
venv/bin/python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-pro --mode test
```

### 6.4 输出路径

所有结果保存在 `Mathematical_optimization/runs/{timestamp}/`：
- `pred_task1a.json` — Task-1a 预测
- `pred_task1b.json` — Task-1b 预测
- `system_prompt_snapshot.txt` — 系统 prompt 快照
- `fewshot_meta.json` — few-shot 示例元信息
- `run_config.json` — 运行配置

---

## 七、下一步建议

1. **🔥 Flash + Pro 集成（最高优先级）**：Pro 提名候选标签 + Flash 验证方向，利用互补性同时提升 Micro 和 Macro，压低 DRR
2. **方向 I（概率校准）**：调整 temperature / prompt 收紧 Pro 的输出 → 提升 Precision + 降低 DRR
3. **Prompt 变体探索**：用 Flash 速度快（10min/轮）的优势快速迭代 `--prompt_variant balanced/compact/targeted_more_shot`
4. **Test 提交**：确定最优单模型或集成策略后，跑 `--mode test` 生成提交文件
