# Task 2 训练前准备与真实模型验证

本报告用于研究分支代码审阅。第一阶段的软件准备已完成；真实预训练模型验证将在本报告追加，
当前尚未完成。GPU 仍不可用，未进行正式训练，也没有新增模型效果指标。

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

CPU 隔离环境配置见 [requirements-cpu.txt](../requirements-cpu.txt)。后续真实模型检查在项目 `.venv/`
执行，不修改原 FEHU 环境。创建/安装命令仅涉及该项目环境，不涉及系统 apt/dpkg：

```bash
python3.11 -m venv ntcir19_fehu-master/.venv
ntcir19_fehu-master/.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0+cpu
ntcir19_fehu-master/.venv/bin/python -m pip install -r ntcir19_fehu-master/research/task2_scope_local_v1/requirements-cpu.txt
```

tokenizer 文件按 lock 中精确 URL 获取到项目 `.cache/` 并核验哈希。新机器需要用 `prepare.py`
重建输入/监督审计目录，用 `build_chunk_cache.py` 重建窗口缓存；两者要求输出目录不存在。
仓库只保存哈希清单与小型验证记录，不包含环境、token 缓存或权重。

## 尚未验证

第一阶段尚未验证完整预训练 ModernBERT-base 的加载及参数更新；这将由第二阶段真实 CPU 检查补充。
GPU/4090、CUDA/BF16、8K SDPA 的显存和速度、GPU optimizer 更新、fit 非平凡学习、完整训练与
tune 推理均未验证；自动 resume 也未实现。`train.py` 默认静态校验，正式入口需要匹配的 GPU 验收记录。
当前不执行正式训练命令，不以 CPU 小样本检查代替 GPU 冒烟或模型效果。

系统修复保持暂停；USER_STOP.json、官方数据与历史证据保留。不调用付费 API。
