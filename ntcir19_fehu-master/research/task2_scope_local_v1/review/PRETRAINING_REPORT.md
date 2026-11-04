# Task 2 训练前准备与真实模型验证

本报告用于研究分支代码审阅。软件准备与完整预训练 ModernBERT 的两 bag CPU 集成验证已完成。
GPU 仍不可用，未进行正式训练，也没有新增模型效果指标。
研究分支为 `task2-local-4090-20261104-2033`；第一阶段审阅提交
`5794d76c1d08e37cacbba7173ff16d119b6c48af` 已先行推送，随后才开展下述真实模型验证。

## 已交付与验证边界

源码包含 input-only article–actor bags、固定划分核验、真实 tokenizer/span、确定分块、
原始 bag 聚合、共享 108 维 head、J/S 损失、P 后处理、严格预测导出和未来训练入口。
冻结规则为 [chunking_v1.json](../chunking_v1.json)，训练配置为 [training_v1.json](../training_v1.json)。

固定模型/tokenizer：**answerdotai/ModernBERT-base**；实际分词实现为 Hugging Face
`tokenizers.Tokenizer.from_file(tokenizer.json)`，版本 **0.22.2**。
模型与 tokenizer revision 均固定为 **8949b909ec900327062f0ebf497f51aef5e6f0c8**。
精确文件 URL、字节数与 SHA-256 见 [tokenizer_lock.json](../tokenizer_lock.json)、
[model_lock.json](../model_lock.json)。不会改用浮动的 main revision。

## 全量输入覆盖

| 划分 | 文章 | bags | windows | actor/event 候选 | 最大窗口 tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| fit | 973 | 2650 | 2651 | 23783 | 8192 |
| tune | 138 | 398 | 398 | 3843 | 3970 |
| holdout | 117 | 333 | 333 | 2917 | 3735 |
| DEV | 177 | 459 | 459 | 3998 | 7914 |
| TEST2 | 175 | 444 | 444 | 4126 | 4927 |
| 合计 | 1580 | 4284 | 4285 | 38667 | — |

固定 TRAIN 连通组划分为 678/85/85 组；完整 GUID 覆盖且规范化正文/标题不跨组。
DEV 与 TRAIN 正文重叠 86 篇，另 91 篇不重叠；没有用 DEV/holdout 成绩选方案。
源文件、固定划分、缓存文件哈希见 [input_cache_manifest.json](input_cache_manifest.json)，
逐 bag 输入/分块计划哈希见 `*.coverage.json`。token 缓存本体不提交，可用源码重建。
构建时拦截 gold 文件读取，未读取标签，见 [label_read_guard.json](label_read_guard.json)。

## 超长 bag 与分块调整

唯一超长输入位于 fit：article `33-2677-7-t`，actor `33-2677-7-t-0`。
其 9641 tokens 包含正文 9249、子事件文本 288、列表标记 77、actor/文章提示 25、
`[CLS]/[SEP]` 2。九个子事件文本长度依次为 `56,31,25,24,37,28,22,28,37`。

先编码完整原文一次，重复 actor 前缀和完整子事件后缀，仅将正文按容量分窗，重叠 256 tokens。
每个正文 token 归最早窗口，后续重叠仅作上下文；按拥有正文数加权聚合各 scope 向量，
最后应用一次共享 head。文章损失每原始 bag 一次，事件监督按原事件数×108 归一化。
J/S/P 共用输入处理；P 仅将 J 聚合后的文章和事件 sigmoid 相乘。

该 bag 分为 8192/2097 tokens 两窗，正文 ownership 为 7800/1449，
权重为 7800/9249 和 1449/9249。九个事件均完整保留，最终仍只输出九组事件分数。
短 bag 保持原序列不变；长 bag 的不同正文窗口不再直接互相 attention，位置也在每窗重置。
这是相对原完整上下文方案的明确调整，不声称神经计算等价。重叠宽度未按评估标签或效果选择。

## 47 项 CPU 测试：实际执行与覆盖

原有 26 项包括 14 项损失、8 项数据/映射、4 项 tokenizer/model 测试。
逐项复核后补足分块梯度、归一化与全部官方映射，最终执行 **47 项，通过 47、失败 0、跳过 0**。
耗时 **4.097 秒**。执行时使用原 fehu Python 3.11.15、torch 2.6.0+cu124、
transformers 5.8.1、tokenizers 0.22.2；计算在 CPU 上完成。

从 Git 根实际使用的等价命令（`FEHU_PY` 指向当时的 fehu Python）：

```bash
FEHU_PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
PYTHONPATH=ntcir19_fehu-master "$FEHU_PY" -m unittest discover \
  -s ntcir19_fehu-master/research/task2_scope_local_v1/tests -p 'test_*.py' -v
```

测试名称、完整成功输出和当时源码哈希见 [cpu_tests_47.json](cpu_tests_47.json)。本轮交付没有增加或重跑该套测试。

| 行为 | 直接验证证据及限制 |
| --- | --- |
| J/S 梯度 | 与概率空间公式比较、gradcheck；正 article 仅允许 gold-positive child 支持，负 article 纠正最高错误 child |
| article-only | 文章正项对所有负 child logits 的直接梯度为 0；共享参数更新仍可能间接改变 child 分数 |
| 空标签/padding | J/S 全空标签梯度、padding NaN 屏蔽、可变事件数分母和尾批次归一化 |
| 全部标签映射 | 独立反向分类表和冻结官方 parser 核对全部 54 价值×2 方向及 coarse 去重；1=aligned、0=contradictory |
| 分块/聚合 | token ownership 唯一、事件完整、Unicode/span、缓存往返、无上下文 encoder 下分块前后 loss/梯度一致 |
| 实际输入 | 三个 fit bags 含 9/24/2 个事件，CPU 小型随机 encoder 通过一次 forward/backward；参数未更新 |
| 模型接口 | 两层、hidden=16 的随机 ModernBERT CPU 接口检查；不是完整预训练模型验证 |

三例原始结果见 [cpu_real_input_validation.json](cpu_real_input_validation.json)。这些测试证明特定实现行为，
不证明收敛、泛化或 GPU 可用。旧 508 事件离线复评未变，但不作为本地 J/S 的模型效果。

## 依赖与复现

CPU 隔离环境配置见 [requirements-cpu.txt](../requirements-cpu.txt)，实际全部依赖版本见
[requirements-cpu.lock.txt](../requirements-cpu.lock.txt)，`pip check` 通过。
真实模型检查在项目 `.venv/` 执行，`include-system-site-packages=false`。
环境基于原 FEHU 的 Python 3.11.15 创建，依赖单独安装；原环境包清单和三个关键文件的哈希未变。
以下是环境不存在时的重建命令；本机环境已存在，无需重复创建：

```bash
/home/szf-4090/miniconda3/envs/fehu/bin/python -m venv ntcir19_fehu-master/.venv
PIP_CONFIG_FILE=/dev/null ntcir19_fehu-master/.venv/bin/python -m pip --isolated install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0+cpu
PIP_CONFIG_FILE=/dev/null ntcir19_fehu-master/.venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple -r ntcir19_fehu-master/research/task2_scope_local_v1/requirements-cpu.lock.txt
```

tokenizer 文件按 lock 中精确 URL 获取到项目 `.cache/` 并核验哈希。新机器需要用 `prepare.py`
重建输入/监督审计目录，用 `build_chunk_cache.py` 重建窗口缓存；两者要求输出目录不存在。
仓库只保存哈希清单与小型验证记录，不包含环境、token 缓存或权重。

## 完整预训练模型：真实 CPU 验证

原缓存缺少完整权重。本轮从官方模型的上述固定 revision 下载 `model.safetensors` 和 `config.json`，
采用无认证 HTTPS，未读取账号或 token。权重 **598,635,032 bytes**，SHA-256：
`340ac08b74eef0d7bdec2d7981a6a3d4249bf0e6aab60634b72ad02c2b8023a9`。
校验通过后仅从本地加载，`local_files_only=True, token=False, trust_remote_code=False`。
原 `model_lock.json` 中 `weights_downloaded=false` 是冻结时的历史状态；下载事实由本次
[real_cpu_provenance.json](real_cpu_provenance.json) 补充，不改历史锁文件。

模型为完整 **ModernBertModel，22 层，hidden=768，149,014,272 个 encoder 参数**；
所有编码器权重均来自预训练文件，missing/mismatched/error 均为空。
加载时仅丢弃预训练 MLM 的 `decoder.bias`、`head.dense.weight`、`head.norm.weight`，
另初始化 Task 2 的共享 108 维分类头（83,052 参数）。没有使用随机小型编码器替代真实模型。

从冻结 fit 输入覆盖清单按 `(token数, guid, actor_id)` 排序，取两个不同文章的最短完整 bags，
选定之后才读取它们的 fit 监督。未按标签/分数挑选，也未读取评估标签。

| article | actor | tokens | 完整子事件 | windows |
| --- | --- | ---: | ---: | ---: |
| `9-21340-1-t` | `9-21340-1-t-0` | 111 | 2 | 1 |
| `2-34666-1-1` | `2-34666-1-1-1` | 122 | 1 | 1 |

调用现有真实 tokenizer、冻结分块、`ChunkedScopeModel` 的正文/子事件均值池化、共享 head 和 S 损失，
在 CPU float32/SDPA 下完成一次 forward、backward、AdamW update。
encoder/head LR 为 `2e-5/1e-4`，weight decay `.01`，seed 11，CPU 线程 2、interop 1。

| 记录 | 实测结果 |
| --- | --- |
| encoder hidden shapes | `[1,111,768]`、`[1,122,768]` |
| article logits | `[2,108]` |
| subevent logits / mask | `[2,2,108]` / `[2,2]`，有效事件数 `[2,1]`；第二个 bag 的尾项为 padding |
| 输出与损失 | 全部有限；S 总损失 1.520659（事件 0.726522 + 文章 0.794138） |
| 梯度 | 136 个可训练参数张量都有有限梯度；encoder/head 范数 1.595865 / 2.685803 |
| 一次更新后的参数 | 全部有限；134 个 encoder 张量、2 个 head 张量的 SHA-256 改变 |
| forward + loss | 0.278371 秒 |
| backward | 0.619241 秒 |
| optimizer update | 0.645019 秒 |
| 上述三阶段合计 | 1.542631 秒 |
| 验证函数 / 完整进程 | 2.953200 / 4.478140 秒（进程包含 Python 导入与退出） |
| 进程峰值 RSS | 3,355,724 KiB，约 3.20 GiB |

实际环境：Python 3.11.15、torch **2.6.0+cpu**（`torch.version.cuda=None`）、transformers 5.8.1、
tokenizers 0.22.2、numpy 2.4.4、safetensors 0.7.0、huggingface-hub 1.15.0。
损失值仅用于检查数值和链路，不能用来评价模型效果。
完整结果及逐参数前后哈希见 [real_cpu_result.json](real_cpu_result.json)。

首次执行在更新后写 JSON 时失败：Transformers 的加载信息含 `set`。
修正记录格式并在更新前检查可序列化性后，重新加载原始权重运行成功。
**共两个独立、各一步的临时 CPU 更新**，没有连续训练、保存更新后权重或覆盖首次日志；
上表是第二次成功执行的数据，首次进程耗时 4.500315 秒。

成功执行命令（Git 根；该输出目录现已存在，再复现须换新目录）：

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_PROGRESS_BARS=1 \
PYTHONPATH=ntcir19_fehu-master \
ntcir19_fehu-master/.venv/bin/python -m research.task2_scope_local_v1.verify_real_cpu \
  --model-dir ntcir19_fehu-master/.cache/task2_scope_local_v1/model/8949b909ec900327062f0ebf497f51aef5e6f0c8 \
  --tokenizer-dir ntcir19_fehu-master/.cache/task2_scope_local_v1/tokenizer/8949b909ec900327062f0ebf497f51aef5e6f0c8 \
  --supervision-dir ntcir19_fehu-master/output/task2_scope_local_v1/20261104-2135 \
  --out ntcir19_fehu-master/output/task2_scope_local_v1/real_model_20261104-220202/validation_retry
```

## 未来正式启动命令（本轮未执行）

这些命令须等 GPU 恢复、独立验收及正式训练授权后使用。`.venv` 是 CPU 专用环境；
未来 GPU 入口使用保留的 FEHU CUDA 环境。验收文件必须匹配当前 boot、代码、输入与模型，不能用本次 CPU 记录替代。

```bash
FEHU_PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
FEHU_CACHE=ntcir19_fehu-master/output/task2_scope_local_v1/pretraining_20261104-214022/input_cache_v1
FEHU_SUPERVISION=ntcir19_fehu-master/output/task2_scope_local_v1/20261104-2135
FEHU_MODEL=ntcir19_fehu-master/.cache/task2_scope_local_v1/model/8949b909ec900327062f0ebf497f51aef5e6f0c8
FEHU_GPU_REPORT=ntcir19_fehu-master/output/task2_scope_local_v1/future_gpu_ready.json
export PYTHONPATH=ntcir19_fehu-master PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

"$FEHU_PY" -m research.task2_scope_local_v1.gpu_preflight \
  --cache-dir "$FEHU_CACHE" --supervision-dir "$FEHU_SUPERVISION" \
  --model-dir "$FEHU_MODEL" --out "$FEHU_GPU_REPORT" --execute

"$FEHU_PY" -m research.task2_scope_local_v1.train --method J \
  --cache-dir "$FEHU_CACHE" --supervision-dir "$FEHU_SUPERVISION" --model-dir "$FEHU_MODEL" \
  --gpu-ready-report "$FEHU_GPU_REPORT" \
  --out ntcir19_fehu-master/output/task2_scope_local_v1/future_J_seed11 --execute

"$FEHU_PY" -m research.task2_scope_local_v1.train --method S \
  --cache-dir "$FEHU_CACHE" --supervision-dir "$FEHU_SUPERVISION" --model-dir "$FEHU_MODEL" \
  --gpu-ready-report "$FEHU_GPU_REPORT" \
  --out ntcir19_fehu-master/output/task2_scope_local_v1/future_S_seed11 --execute
```

所有输出路径必须不存在。J/S 按冻结配置从相同初始权重独立训练；P 是 J 的后处理，不另训模型。
当前代码不自动恢复断点，阈值和 checkpoint 只能使用 tune 选择。

## 尚未验证

真实预训练 CPU 证据限于两个短 bag、S 损失及一次更新；没有在完整模型上运行超长两窗 bag、J/P 路径或全部划分。
GPU/4090、CUDA/BF16、8K SDPA 的显存和速度、GPU optimizer 更新、fit 非平凡学习、完整训练与
tune 推理均未验证；自动 resume 也未实现。`train.py` 默认静态校验，正式入口需要匹配的 GPU 验收记录。
当前不执行正式训练命令，不以 CPU 小样本检查代替 GPU 冒烟或模型效果。

系统修复保持暂停；内核、驱动、启动配置和显示服务未改动，未重启。
USER_STOP.json 的 SHA-256 保持不变，1,997 个冻结/历史文件检查无变化，main 未修改；
核验摘要见 [preservation_check.json](preservation_check.json)。不调用付费 API。
