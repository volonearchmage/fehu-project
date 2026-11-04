# DS_final: 3-Way Majority Vote + Flash Direction Verification

**Task-1 提交方案 | Dev Micro 0.5560, DRR 0.0338 | 超越刘 Ensemble (0.5543)**

---

## 一、方法速览

```
3 个 Pro T=0.0 Prompt 变体 (各 175 test calls)
    ↓
3-Way Majority Vote (≥2/3 票)
    ↓
Flash T=0.0 Direction Verification (175 test calls)
    ↓
pred_task1a.json + pred_task1b.json
```

## 二、Dev 验证结果

| 指标 | DS_final | 刘 Ensemble |
|---|---|---|
| 1b Micro F1 | **0.5560** | 0.5543 |
| 1b Macro F1 | **0.3816** | 0.3277 |
| DRR | **0.0338** | 0.0345 |
| 1a Micro F1 | **0.6840** | ~0.645 |

## 三、依赖

- Python 3.9+ with `openai`, `numpy`, `tqdm`
- `DEEPSEEK_API_KEY` in `.env` or environment
- E1 pipeline: `Mathematical_optimization/base/run_pipeline_e1_base.py`

## 四、快速执行

### 全自动（推荐）

```bash
cd ntcir19_fehu-master
source venv/bin/activate

# Run everything (~125 min)
python DS_final/scripts/run_all.py

# Or resume from cache
python DS_final/scripts/run_all.py --skip_completed

# Or ensemble only (if all 4 runs exist)
python DS_final/scripts/run_all.py --ensemble_only
```

### 手动分步

```bash
# Step 1: Flash test (~11 min)
python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-flash --mode test --temperature 0.0

# Step 2: Pro compact_strict test (~14 min)
python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-pro --mode test --temperature 0.0 \
  --prompt_variant compact_strict

# Step 3: Pro baseline test (~24 min)
python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-pro --mode test --temperature 0.0

# Step 4: Pro targeted_more_shot_balanced test (~76 min)
python Mathematical_optimization/base/run_pipeline_e1_base.py \
  --provider deepseek --model deepseek-v4-pro --mode test --temperature 0.0 \
  --prompt_variant targeted_more_shot_balanced

# Step 5: Ensemble
python DS_final/scripts/ensemble.py \
  --baseline DS_final/runs/pro_baseline/pred_task1b.json \
  --targeted DS_final/runs/pro_targeted/pred_task1b.json \
  --compact  DS_final/runs/pro_compact/pred_task1b.json \
  --flash    DS_final/runs/flash/pred_task1b.json \
  --event_base dataset/test/test_article_event_base.json \
  --output_1b DS_final/outputs/pred_task1b.json \
  --output_1a DS_final/outputs/pred_task1a.json
```

## 五、输出

```
DS_final/outputs/
├── pred_task1a.json      ← Task-1a 提交文件
├── pred_task1b.json      ← Task-1b 提交文件
├── ensemble_summary.json ← 集成统计
└── dev_metrics.json      ← Dev 指标（不是 Test 分数）

DS_final/submission/
├── pred_task1a.json      ← 已验证的提交副本
└── pred_task1b.json      ← 已验证的提交副本

DS_final/runs/
├── flash/                ← Flash T=0.0 预测
├── pro_baseline/         ← Pro baseline 预测
├── pro_compact/          ← Pro compact_strict 预测
└── pro_targeted/         ← Pro targeted_more_shot_balanced 预测
```

## 六、Test 合规性

| 检查项 | 状态 |
|---|---|
| 仅用 test_article_event_base.json | ✅ |
| 不依赖 subevents | ✅ |
| 不依赖 test gold labels | ✅ |
| Few-shot 仅用 train | ✅ |
| Prompt/temp 固定，无 dev 调参 | ✅ |

## 七、2026-07-26 Test 实跑结果

- 覆盖 175/175 篇 test 文章、479/479 个 actor。
- Task-1a：1,834 条预测；Task-1b：2,260 条预测。
- 严格格式守卫通过；Task-1a 与 Task-1b 的 L1→L2 映射完全一致。
- 提交压缩包：`FEHU_Task1_DS_final_20260726.zip`（仅含两份官方 JSON）。
- 详细哈希与验证信息见 `SUBMISSION_MANIFEST.md`。

## 八、成本

| 调用 | 次数 | 预估时间 |
|---|---|---|
| Pro baseline | 175 | 24 min |
| Pro compact_strict | 175 | 14 min |
| Pro targeted | 175 | 76 min |
| Flash | 175 | 11 min |
| Ensemble | 0 | <1s |
| **总计** | **700** | **~125 min** |
