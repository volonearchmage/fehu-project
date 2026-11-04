# Prompt: rerun frozen E7-G4 with the current DeepSeek V4 Flash backend

Copy everything below the divider into the local coding agent. The task is a
development-set experiment. It must not modify the paper or replace the
official test submission.

---

你现在位于这台 Mac 上的 FEHU 仓库：

`/Users/lloydhuang/Documents/GitHub/fehu-project/ntcir19_fehu-master`

请完整执行一次 **frozen E7-G4 在当前 `deepseek-v4-flash` API 后端上的 DEV 重跑**，并与 2026-07-25 的旧版 Flash 冻结结果作严格比较。不要只给计划；请检查、修正输出隔离问题、运行、评分、验证并写出报告，直到实验完整结束。不要运行 TEST，不要改论文，不要把本实验自动写入 paper draft。

## 1. 实验问题与唯一允许变化的变量

我们要回答：在 prompt、temperature、few-shot、DeBERTa 概率、融合规则、阈值和 DEV 数据全部冻结时，DeepSeek 后端在相同 API model id `deepseek-v4-flash` 下的更新，是否改变 E7-G4 的 DEV 表现？

唯一预期变化是当前 API 返回的 Flash 行为。保持以下配置不变：

- 数据：`dataset/dev/dev_event_base.json` 与官方 DEV gold。
- Flash model id：`deepseek-v4-flash`。
- temperature：0.1。
- prompt variant：`targeted_more_shot_balanced`。
- E6/E6b segmentation prompts 与所有成员 prompts：不得重写或调参。
- E6c：仍用 `deepseek-v4-pro` non-thinking；但由于它使用新的 E6b segments，必须重新运行。
- DeBERTa：不重新训练，固定使用
  `RH_test/E5_deberta_auxiliary_fusion/inputs/dev_fp_seed44_probs.jsonl`。
- E7 calibration、frequency gate、addition cap、threshold family、G4 flag rule：保持当前冻结实现，不得根据新结果调参。

这次必须重跑完整 DEV 流程，而不是只重跑 G4 direction QA。当前 Flash 会影响：E1、Liu juror、E6 segmentation、E6 predictions、E6b segmentation、E6b predictions，以及 G4 direction QA。E6c 虽然使用 Pro，也必须在新的 E6b segments 上重跑。随后重新 cross-fit fusion。

## 2. 先阅读和审计，不要立即调用 API

完整阅读：

- `RH_test/E7_calibrated_jury_fusion/reports/E7_REPORT.md`
- `RH_test/E7_calibrated_jury_fusion/scripts/run_fusion_e7.py`
- `RH_test/E7_calibrated_jury_fusion/scripts/run_direction_qa_e7.py`
- `E7G4Test/E7G4_TEST_RUN_REPORT.md`
- `E7G4Test/scripts/cache_health.py`
- `E7G4Flash0731Dev/scripts/run_dev_flow.sh`
- `E7G4Flash0731Dev/scripts/run_fusion_flow.sh`
- E1、Liu、E6、E6b、E6c 和两个 segmentation 入口脚本。

`E7G4Flash0731Dev` 只是参考草稿，不能原样执行。已知问题包括：固定 run tag、可能残留的两条 smoke cache、Liu 的固定 cache/output 名称、已有目录被跳过，以及旧输出可能被移动或覆盖。

执行只读 preflight，并在日志中列出：

1. `git status --short`；保留所有用户修改，不还原无关文件。
2. `.env` 是否声明 `DEEPSEEK_API_KEY`，但绝对不要打印 key。
3. `venv/bin/python`、`openai` 包、官方 evaluator、DEV 数据、DEV gold、冻结 DeBERTa 概率是否可用。
4. 所有准备写入的目标目录是否已存在。
5. 旧冻结 baseline 文件是否存在：
   `RH_test/E7_calibrated_jury_fusion/runs/20260725_004522_G4_dirqa/`。

官方 DeepSeek 文档仍把公开 model id 写作 `deepseek-v4-flash`；不要凭 model id 猜测内部 snapshot。API health probe 或首个真实响应若返回 `model`、`system_fingerprint`、response id、时间戳，请记录到 manifest；如果没有 fingerprint，要明确写 `not exposed by API`，不要编造版本号。

## 3. 输出隔离是硬性要求

生成一次且仅一次的唯一 run id，例如：

`e7g4_flash_refresh_20260813_161530`

必须使用实际开始时间，不能复用上例。统一实验根目录：

`E7G4FlashRefreshDev/runs/<RUN_ID>/`

在这里保存：`logs/`、`segmentation/`、`fusion/`、`report/`、`manifest.json` 和最终比较报告。成员 pipeline 如果按现有设计必须写到各自的 `runs/<RUN_ID>/`，可以这样做，但 manifest 必须记录所有绝对/相对路径和 SHA-256。

严格遵守：

- 不删除、不移动、不改名、不覆盖任何旧 run、旧 cache、`E7G4Test`、`E7G4Flash0731Dev` 或 20260725 baseline。
- 不使用任何现有 Flash cache，包括只有 2 条记录的 smoke cache。
- 不把 smoke cache 复制到 full run。
- 任何 full-run 输出目录一旦存在，立即换一个新的 RUN_ID；不能“目录存在则跳过”。
- 新 full run 中某阶段已经产生部分 cache 时，允许仅在同一 RUN_ID 内断点续跑。
- 不使用 `rm -f` 清理报告。报告文件已存在时应 fail fast 或使用新 RUN_ID。

E1/E6/E6b/E6c 已支持各自的 `*_RUN_TS` 环境变量，请全部设为唯一 RUN_ID。

重点修复 Liu 隔离问题：`liu_method/run_pipeline.py` 当前把 DEV cache 固定写在 `logs/cache_dev_...json`，把预测固定写在 `output/task1/runs/dev_.../`。在调用 API 前做最小、可审查的修改，使调用者可以显式指定新 cache path 与新 output directory；默认旧行为可保持兼容，但本实验必须传入唯一的新路径。不要通过移动旧目录来腾位置，也不要使用 `--refresh_cache` 覆写旧 cache。为这个路径隔离改动做一次无 API 的 smoke check。

同样审计两个 segmentation 脚本的 cache/raw 输出位置，确保全部位于新实验根目录，不会读取 `E7G4Flash0731Dev/smoke/`。

## 4. 执行顺序

先用独立的 `<RUN_ID>_smoke` 和独立目录做 2 篇文章的 API smoke test，验证：

- API 可用；
- JSON 能解析；
- 输出路径完全隔离；
- response metadata 能记录；
- 没有读取旧 cache。

smoke 成功后，full run 必须使用新的 `<RUN_ID>`，从空 cache 开始处理全部 177 篇 DEV 文章：

1. E6 segmentation，current Flash。
2. E6b 6--9 segmentation，current Flash。
3. E1，current Flash。
4. Liu juror，current Flash，使用隔离后的 cache/output。
5. E6，current Flash + 新 E6 segments。
6. E6b，current Flash + 新 E6b segments。
7. E6c，V4 Pro non-thinking + 新 E6b segments。
8. 对每个成员运行 cache health：177/177；空响应按现有“purge once, refetch once, then explicit fail/confirmed-empty”协议处理。不得静默接受 API 失败。
9. 用官方 evaluator 评分全部成员。
10. 在新目录重新运行 G0、G1、G2、G3、G5 DEV cross-fit fusion。
11. 从新 G3 运行 G4 direction QA，必须使用全新 G4 cache。
12. 用官方 evaluator 评分全部 fusion cells。
13. 运行 10,000 次 paired article bootstrap，至少包含：
    - new G4 vs old frozen G4；
    - new G4 vs new E6b；
    - new G4 vs new G3；
    - new E6b vs old frozen E6b。

若 API 出现暂时性 429/5xx/empty response，使用现有重试与外层退避机制；如果重复失败，保留 cache 和日志并明确停止，不得切换模型、降低样本数、复用旧响应或使用 fallback。

## 5. 验证和对照

旧冻结 DEV 基线使用仓库中的实际 artifacts 重新读取，不要手抄后当作唯一依据。已知参考值用于 sanity check：

- old E6b：1b Micro-F1 0.5496，Macro-F1 0.4124，1a Micro-F1 0.6621，DRR 0.0459。
- old G3：1b Micro-F1 0.5790，Macro-F1 0.4266，1a Micro-F1 0.6874，DRR 0.0450。
- old G4：1b Micro-F1 0.5817，Macro-F1 0.4308，1a Micro-F1 0.6874，DRR 0.0419；176 flagged、46 flipped、7 failed。

验证以下内容：

- 每个 full member cache 恰好覆盖 177 个 DEV guid。
- prediction JSON schema、guid、actor membership、label ranges、duplicates 均合法。
- Task-1a 必须等于最终 Task-1b 的确定性 L1-to-L2 projection。
- fusion manifest 中成员、概率文件、calibration 与输入 SHA-256 完整。
- 新旧 G4 逐 actor/value/direction 比较：新增、删除、同 value 反向、完全相同的 cell 数量。
- 新旧 segmentation 的 mean/median、6--9 约束、异常文章。
- 新旧 G1 removals、G3 additions、G4 flagged/flipped/kept/failed 数量。
- 新 G3→G4 的独立增量，避免把整个 pipeline 变化误说成 QA 变化。

## 6. 最终报告

写入：

`E7G4FlashRefreshDev/runs/<RUN_ID>/report/E7G4_FLASH_REFRESH_COMPARISON.md`

报告需简洁但完整，至少包括：

1. 实验时间、请求 model id、API 实际返回的 model/fingerprint（若有）、唯一 RUN_ID。
2. 代码/数据/旧 baseline/new outputs 的 SHA-256 与 git 状态。
3. 新旧成员指标表：1b Micro/P/R/Macro、1a Micro/Macro、DRR、预测标签数、108 类覆盖数。
4. 新旧 G0/G1/G3/G4/G5 指标表及绝对差值。
5. bootstrap 差值、95% CI 和单次重跑的局限。
6. segmentation 与 fusion action 对照。
7. G4 direction QA 对照和失败记录。
8. API 调用数、重试数、失败数；若响应 usage 可得，再报告 input/output/cache-hit tokens 与估算费用。不要猜测缺失的 token/cost。
9. 明确回答：当前 Flash 的一次完整重跑是改善、退化还是混合变化；主要变化来自 E6b/成员预测、fusion，还是 G4 QA。
10. 建议是否值得再跑 2 个独立 replicate。一次 temperature 0.1 重跑不能单独证明变化必然来自后端升级。

完成后在终端给出：RUN_ID、报告路径、新 G4 的核心指标、新旧 G4 差值、是否全部验证通过。不要更新论文、outline、官方 test prediction 或 submission 文件。

---
