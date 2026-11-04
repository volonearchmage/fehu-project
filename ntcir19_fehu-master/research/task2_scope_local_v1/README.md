# Task 2 本地 J/S/P：训练前软件准备

2026-11-04 更新：已实现并冻结正文分窗、原始 bag 聚合和 J/S/P 共用输入缓存；
原有 26 项测试逐项复核，补充后的 47 项 CPU 测试通过。**未训练预训练 ModernBERT，未完成 GPU 实验。**
4,284 bags 全部可编码为预算内的 4,285 窗口，长输入软件阻塞解除。GPU 仍阻塞，权重尚未下载。
完整证据、测试覆盖边界和准确的未来启动命令见
[训练前报告](review/PRETRAINING_REPORT.md)。审阅证据和数据/缓存哈希清单位于 `review/`；
token 缓存本体、权重和私人系统诊断日志不提交。

最新安全边界见根 AGENTS.md。保持 AnyDesk、6.17、所有现有内核与 Python 环境；
没有安装依赖、下载模型权重、调用付费 API 或改 USER_STOP。旧 GPU 执行提示不授权本轮训练。

## 组件与输入边界

- `data.py`：输入白名单构建 article–actor bag，候选为输入 actors × subevents。
  使用固定 manifest，独立重算同正文/同标题连通分量和种子排序，并检查完整覆盖与组不交叉。
  标签/解释不进入 `Bag`。TRAIN gold 单独解析；只导出 fit/tune 监督；holdout/DEV/TEST 只有输入。
- `tokenization.py`：目标 actor + 完整正文 + 完整编号子事件，正文/子事件依据 tokenizer offsets
  构造独立 token mask，排除 CLS/SEP、提示前缀和 padding。不加新 embedding，不裁切。
  `audit_overlength=True` 只用于审计；常规 encode 对超长报错。
- `chunking.py` / `chunking_v1.json`：新入口对完整编码分正文窗口，重复全部 actor/子事件上下文，
  相邻窗口重叠 256；每个正文 token 仅归最早窗口。短输入原样保留，不重新分词或丢事件。
- `chunk_model.py`：按各窗口拥有的正文 token 数聚合 scope 向量，最后一次共享 head，
  监督仍按原始 bag/事件计数；P 只对 J 的最终文章/事件概率相乘。
- `build_chunk_cache.py`：全量输入缓存及 hash/coverage 审计，不读取 gold；使用完成的 manifest，
  拒绝覆盖现有目录。最新缓存是报告目录的 `input_cache_v1/`。
- `model.py`：接受 encoder 的 `last_hidden_state`，每个范围有效 token 均值池化，接同一个 108 维线性头。
  CPU 测试使用小型合成 encoder；未下载/实例化 ModernBERT 权重，也未验证其 GPU forward。
- `losses.py`：J/S 使用同一 child BCE 和文章权重 1。每 bag 的事件 BCE 除有效事件数×108，
  再对 bag 平均；文章每 bag 计一次。S 正项只在文章及 gold-positive 子事件间取 max，
  负项在文章及所有有效子事件间取 max，使用 softplus 的稳定 logit 等价形式。
  padded logits/targets 先 mask，半精度归约升至 fp32；没有把文章标签向下复制。
- `predictions.py`：Task 2b 输出子事件自身 108 概率；索引 `2*l1+direction`，0 矛盾、1 一致。
  Task 2a 用官方映射去重。缺失/额外候选、NaN、非 108 维概率均报错，不能把推理失败填成空集。
  这里不选择阈值，未来阈值/checkpoint 只能使用 tune。
- `train.py` / `training_v1.json`：未来 CUDA-only 训练入口，默认只做静态检查；
  `--execute` 需已完成并绑定代码/输入/模型的 GPU 验收文件，无 CPU fallback 或自动下载。
  J/S 各 3 epochs、同种子/顺序；只读取 fit/tune 监督。实现 epoch 保存，尚无自动 resume。
- `gpu_preflight.py`：未来 GPU 小张量与代表性 bags 的 forward/backward/同步检查；本轮未执行。

`protocol.json` 原样保留初版数据/分类表/划分哈希与当时的超长阻塞记录；
新的分块策略由 `chunking_v1.json` 冻结，训练参数由 `training_v1.json` 冻结。
`tokenizer_lock.json` 固定公开模型 `answerdotai/ModernBERT-base` revision
`8949b909ec900327062f0ebf497f51aef5e6f0c8`，含四个 tokenizer/config 文件的 URL 和 SHA-256。
本机缓存位于项目 `.cache/task2_scope_local_v1/tokenizer/<revision>/`，不提交缓存。
这些公开文件通过无认证 HTTPS 获取，没有读取 HF token 或任何项目 API 密钥。
在其他机器复现时，应按 lock 中精确 URL 下载并核验 SHA-256；不要改用漂移的 `main`。

## 复验命令（Git 根）

沿用现有 fehu 解释器：Python 3.11.15、PyTorch 2.6.0+cu124、tokenizers 0.22.2、
transformers 5.8.1、numpy 2.4.4。这是已完成 47 项测试的历史环境；
新的真实模型 CPU 验证将使用项目隔离 `.venv`，依赖配置见 `requirements-cpu.txt`，原环境保持不变。

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
PYTHONPATH=ntcir19_fehu-master \
/home/szf-4090/miniconda3/envs/fehu/bin/python -m unittest discover \
  -s ntcir19_fehu-master/research/task2_scope_local_v1/tests -p 'test_*.py' -v

PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 \
PYTHONPATH=ntcir19_fehu-master \
/home/szf-4090/miniconda3/envs/fehu/bin/python -m research.task2_scope_local_v1.build_chunk_cache \
  --tokenizer-dir ntcir19_fehu-master/.cache/task2_scope_local_v1/tokenizer/8949b909ec900327062f0ebf497f51aef5e6f0c8 \
  --out ntcir19_fehu-master/output/task2_scope_local_v1/NEW_UNIQUE_AUDIT
```

`--out` 必须不存在；程序拒绝覆盖。缓存命令返回成功表示输入审计完成，**不表示 GPU 已可训练**；
需检查 `manifest.json`、GPU 环境报告及用户授权。旧 `prepare.py` 仍保留作原始未分块审计。
数据读取/导出与全量 tokenizer 审计不运行模型，不做 CPU 全量训练。
原有 `verify_offline.py` 也已对新目录执行，508 事件历史指标和冻结哈希保持一致。

本轮结果见上方训练前报告；本机 output 中的旧 RESULTS 与诊断文件作为历史证据保留。
剩余工作：固定权重下载/核验、GPU 恢复及验收、真实 ModernBERT 资源/学习验证、
正式运行与 tune 选型、自动断点恢复及授权后的最终评分。
当前没有 checkpoint、J/S/P F1、显存/训练时长或新模型预测，不能据此比较 S−J。
