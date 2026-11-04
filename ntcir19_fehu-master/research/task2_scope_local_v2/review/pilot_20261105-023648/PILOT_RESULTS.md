# FEHU Task 2 v2 — PILOT_RESULTS

**已完成：T/J/S 各3 epochs、seed11；P复用选定J；仅fit训练与tune开发评估。未评估holdout、DEV或TEST。**

## 执行与协议

- 固定协议提交：`d9d070ba1290c30520f8a56c053fb753fe30e956`；完整原文在上级 `protocol_reference/`，通过 `git show SHA:path` 读取。
- 研究分支：`task2-local-4090-20261104-2033`；起始HEAD：`9d162c6dd8e971cd58e1e240891892de129dc62b`。确认origin后只fetch main；未pull/reset/clean、未切换main、未push。
- 本次运行目录：`/home/szf-4090/projects/fehu-project-main-2da2ea5/ntcir19_fehu-master/output/task2_scope_local_v2/pilot_20261105-023648/execution`。启动、PID、逐阶段退出码见 `launcher.json`、`processes.jsonl`、`driver_result.json`。
- 旧8-bag诊断仍是“未通过原Recall门槛”。v2在全量探索前公开撤销这一准入规则；未改写旧结果或复用诊断权重。低分不触发追加预算。
- T=事件BCE；J=事件BCE+独立文章BCE；S=事件BCE+原gold-aware文章项。T/J/S同全文、主体、完整子事件输入、mean pooling和共享108维head。P只改变选定J的评分为文章概率×事件概率。
- 与旧方案的输入调整：去掉插入文本的actor/event ID，保留元数据、主体名称、正文、事件文本与文章内序号；不声称这些ID导致旧诊断低召回。
- 三组均从原始ModernBERT权重与相同新head开始，AdamW encoder2e-5/head1e-4、wd.01、clip1、lambda1（T为0）、BF16、microbatch1、有效batch16、窗口checkpoint。50步warmup后按完整498步线性衰减到0。第一步LR为0，第二步已核对真实参数改变。
- 原bag文章项计一次，事件BCE按每bag有效事件数×108归一化，再按bag平均；每轮尾批10bags按10归一化。每条件7950bags/7950microbatches、7953windows、498optimizer steps；合计23850bags、1494updates。
- 精确全局阈值扫描：同分成组、score>=threshold、全空阈值2.0；不四舍五入。同分取较高阈值再较早epoch。P仅在已选J epoch选阈值。

## 绑定、覆盖与工程证据

- Python：`/home/szf-4090/miniconda3/envs/fehu/bin/python`；软件版本：`{"torch": "2.6.0+cu124", "transformers": "5.8.1", "tokenizers": "0.22.2", "numpy": "2.4.4", "scikit-learn": "1.8.0"}`。
- GPU/驱动/显存（nvidia-smi）：`NVIDIA GeForce RTX 4090, 590.48.01, 24564 MiB`；内核 `6.17.0-40-generic`；PyTorch CUDA build `12.4`。GPU恢复以来boot未变。
- 模型/tokenizer：answerdotai/ModernBERT-base，revision `8949b909ec900327062f0ebf497f51aef5e6f0c8`。真实149,014,272参数encoder与83,052参数共享head；未下载新模型或修改环境。
- 三组初始参数SHA-256：`befdcf0a043d4743bafdc17169123513bac67e81e452673f000b5b2c2c1574c4`。每epoch的顺序哈希跨三组一致，详见各epoch JSON。
- 输入/标签/模型/实现版本与逐条件生效配置见 `frozen.json`、`config_T/J/S.json`、`source_frozen/`；逐bag输入/渲染/分窗哈希见 `input_cache/*.coverage.json`。

| 划分 | 文章 | bags | windows | 候选 | 最大窗口tokens |
|---|---:|---:|---:|---:|---:|
| fit | 973 | 2650 | 2651 | 23783 | 8192 |
| tune | 138 | 398 | 398 | 3843 | 3874 |

- fit cache SHA-256：`575a7b11a23e4a743a0d4b4b8e73b7853ed53c00316c34fbed9ff7d739260c18`。
- tune cache SHA-256：`71bf72a916eb97e667087aa56c96600b70a8b5f155ad4adcf8c16d2cb6f25099`。
- 唯一长bag `33-2677-7-t / 33-2677-7-t-0`：9585tokens=正文9249+事件文本288+列表标记32+主体/正文头14+特殊标记2；两窗8192/1985，正文ownership7856/1393，9事件完整。所有span、窗口覆盖和正文唯一ownership已核验。
- 仅新增4项针对变更的CPU核查：T梯度、ID改变不影响tokens/spans、并列分数/全空/暴力阈值扫描、序列化精度与导出。执行命令与结果在上级 `focused_cpu_checks.json`；未重复47项旧测试。
- 第一轮v2 GPU receipt因连续/恢复下一步哈希不同而失败。诊断证明重载前状态完全一致，默认GPU更新有非确定性；仅在进程中统一启用确定性算法和cuBLAS workspace后，下一步模型、AdamW、scheduler、RNG逐位一致。所有失败日志及checkpoint保留在上级目录。详见 `ENGINEERING_CHANGE.md` 和上级 `resume_*_diagnosis.json`。
- 新receipt重新执行T/J/S短/中/最长真实bag前反向、真实AdamW更新、更新后最长输入及下一步恢复一致检查，全部通过。最长输入更新后峰值 9.011 GiB allocated / 10.646 GiB reserved；见 `preflight/receipt.json`。
- 恢复检查用少量完整optimizer groups模拟序列化边界，未声称预检完成一个训练epoch。实际训练每166步保存完整epoch状态；支持显式epoch边界恢复，不支持自动或microbatch中途恢复。

## Tune开发成绩

**下表经过同一tune上的checkpoint与阈值选择，不是未触碰测试集的泛化成绩。百分数表示P/R/F1/AP，阈值保持原精度。**

| 方法 | epoch | 阈值 | 2b P | 2b R | 2b micro-F1 | 2b macro-F1 | micro-AP | TP/FP/FN |
|---|---:|---|---:|---:|---:|---:|---:|---|
| T | 3 | `0.048136770725250244` | 8.37 | 14.40 | 10.58 | 0.51 | 4.20 | 333/3647/1979 |
| J | 3 | `0.060086652636528015` | 7.58 | 19.51 | 10.92 | 2.41 | 4.82 | 451/5497/1861 |
| S | 3 | `0.07807816565036774` | 8.60 | 16.39 | 11.28 | 2.21 | 4.99 | 379/4027/1933 |
| P | 3 | `0.023790206760168076` | 7.91 | 20.24 | 11.37 | 1.82 | 5.06 | 468/5452/1844 |

| 方法 | 2a P | 2a R | 2a micro-F1 | 2a macro-F1 | 2a TP/FP/FN | 2b DRR | 0.5下2b P/R/F1 | 0.5下TP/FP/FN |
|---|---:|---:|---:|---:|---|---:|---|---|
| T | 9.58 | 17.15 | 12.29 | 1.39 | 380/3587/1836 | 1.65 | 0.00/0.00/0.00 | 0/0/2312 |
| J | 11.13 | 26.71 | 15.71 | 6.26 | 592/4729/1624 | 4.33 | 0.00/0.00/0.00 | 0/0/2312 |
| S | 12.83 | 23.38 | 16.57 | 5.48 | 518/3519/1698 | 3.25 | 0.00/0.00/0.00 | 0/0/2312 |
| P | 11.75 | 29.60 | 16.82 | 5.15 | 656/4928/1560 | 4.68 | 0.00/0.00/0.00 | 0/0/2312 |

- Task2a按官方54→20映射、去方向并去重，DRR不适用；Task2b保留54×2，1=aligned、0=contradictory。没有强制非空或两标签上限。
- 各方法selected/fixed_05目录保存严格官方格式、全部候选覆盖清单、评价器命令/版本/stdout/metrics。官方TP/FP/FN与扫描计数全部相符。tune gold来自固定TRAIN派生的tune监督缓存，按冻结manifest和候选核对；未读取holdout/DEV/TEST gold。
- 官方评价器的 `support_instances` 仅统计gold/pred非空键的并集，各方法可不同；这不代表漏推理。独立覆盖清单均核对了完整138文章、1288事件、3843候选。
- 原始初始化tune AP=0.47%，选阈值F1=1.13%；仅作epoch0基线，不参与checkpoint选择。
- fit候选频率基线（分母23783，不按bag平均）：tune AP=3.50%，选阈值F1=10.37%。频率只来自fit；AP也受跨类频率影响。

## 真实学习曲线

![Learning curves](learning_curves.png)

![Tune PR](tune_pr_curves.png)

图表的CSV/PDF和全部精确P/R边界NPZ均已保存。fit损失是在训练模式、不断变化的参数下累计，不能当作固定checkpoint的eval loss。正负BCE按有效label cells平均，事件/文章loss按bag平均；T的文章BCE仅记录，训练权重为0。

| 方法 | epoch | fit事件BCE | fit文章项 | fit正例BCE | fit负例BCE | tune AP | tune选阈值F1 | tune 0.5 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T | 1 | 0.13981 | 0.26260 | 3.08396 | 0.12033 | 3.90 | 10.38 | 0.00 |
| T | 2 | 0.03273 | 0.19841 | 3.99866 | 0.00775 | 4.06 | 10.38 | 0.00 |
| T | 3 | 0.03208 | 0.19954 | 4.02088 | 0.00700 | 4.20 | 10.58 | 0.00 |
| J | 1 | 0.14386 | 0.23423 | 2.44340 | 0.12860 | 3.12 | 7.64 | 0.00 |
| J | 2 | 0.03328 | 0.14579 | 3.56387 | 0.01110 | 4.33 | 10.28 | 0.26 |
| J | 3 | 0.03138 | 0.13710 | 3.60068 | 0.00902 | 4.82 | 10.92 | 0.00 |
| S | 1 | 0.14366 | 0.24980 | 2.53328 | 0.12780 | 3.56 | 9.94 | 0.00 |
| S | 2 | 0.03309 | 0.14720 | 3.57378 | 0.01086 | 4.23 | 10.37 | 0.00 |
| S | 3 | 0.03159 | 0.13940 | 3.51906 | 0.00974 | 4.99 | 11.28 | 0.00 |

## 方法差值与机制

| 比较 | 2b F1差（百分点） | AP差（百分点） | 新TP / 丢TP / 减FP / 增FP |
|---|---:|---:|---|
| J-T | +0.34 | +0.62 | 167/49/744/2594 |
| S-J | +0.36 | +0.17 | 32/104/1981/511 |
| P-J | +0.45 | +0.24 | 67/50/967/922 |

| 方法 | 原始event>article（分子/分母） | 空候选误报（候选/分母；标签数） | 文章独有标签下传（bag-label对/分母） |
|---|---|---|---|
| T | 17456/415044 (4.21%) | 2310/2310; 2367 | 26/451 |
| J | 5513/415044 (1.33%) | 2057/2310; 3410 | 71/451 |
| S | 452/415044 (0.11%) | 1605/2310; 2532 | 53/451 |
| P | 5513/415044 (1.33%) | 2147/2310; 3474 | 58/451 |

选中S第3轮checkpoint在tune上的max承接计数（正项仅允许gold-positive child；负项允许全部child，概率并列单列；不是训练期间累计梯度统计）：

| 文章项 | article独占 | child独占 | article/child并列 |
|---|---:|---:|---:|
| positive | 2025 (100.00%) | 0 (0.00%) | 0 (0.00%) |
| negative | 40737 (99.46%) | 174 (0.42%) | 48 (0.12%) |

- 这一最终checkpoint上，2025个正文章项均由article承接；负项仅174个由child独占。它提示此时S的文章项多接近独立文章项，但不能据此认定整个训练过程没有child参与，也不能证明已学到独特结构机制。
- 文章独有标签无须分给任何事件；上述下传是诊断中的误报计数。原始违反率只是机制描述，不把上行max后的零违反率作为成功。T无文章训练目标，其原始文章概率仅供机制参考。
- 各方法 `diagnostics.json` 保存108类fit/tune支持数、零fit正例类、方向分层、bag事件数和同文多主体预测差异；`comparisons.json` 给出可按GUID/actor/event/label核对的新增/丢失TP、增减FP例子。

| 零fit正例有向类 index/value/direction | tune正例 | T TP/FP/FN | J TP/FP/FN | S TP/FP/FN | P TP/FP/FN |
|---|---:|---|---|---|---|
| 2/1/contradictory | 0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 47/23/aligned | 0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 48/24/contradictory | 0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| 68/34/contradictory | 1 | 0/0/1 | 0/0/1 | 0/0/1 | 0/0/1 |

### 方向分层（各自选择阈值，tune）

| 方法 | 方向 | gold支持数 | TP/FP/FN | P/R/F1（%） |
|---|---|---:|---|---|
| T | contradictory | 774 | 2/35/772 | 5.41/0.26/0.49 |
| T | aligned | 1538 | 331/3612/1207 | 8.39/21.52/12.08 |
| J | contradictory | 774 | 50/834/724 | 5.66/6.46/6.03 |
| J | aligned | 1538 | 401/4663/1137 | 7.92/26.07/12.15 |
| S | contradictory | 774 | 62/692/712 | 8.22/8.01/8.12 |
| S | aligned | 1538 | 317/3335/1221 | 8.68/20.61/12.22 |
| P | contradictory | 774 | 79/939/695 | 7.76/10.21/8.82 |
| P | aligned | 1538 | 389/4513/1149 | 7.94/25.29/12.08 |

## 实测成本与边界恢复

| 方法 | 训练秒 | 验证/指标秒 | checkpoint秒 | 总运行秒 | 预热后bags/s | allocated/reserved峰值GiB |
|---|---:|---:|---:|---:|---:|---|
| T | 765.4 | 13.5 | 12.8 | 791.7 | 10.42 | 9.57/11.23 |
| J | 764.4 | 13.4 | 14.2 | 791.9 | 10.48 | 9.57/11.23 |
| S | 768.0 | 13.4 | 12.7 | 794.1 | 10.39 | 9.57/11.23 |

有限driver总墙钟时间（包括三组加载、训练、验证、保存和最后官方评分）2397.1秒；前期实现和GPU验收不计入该值。

- 每组吞吐排除前50个warmup updates，实际统计7150bags，包含前向/反向/优化器更新。逐阶段耗时和每次ETA见 `training.jsonl`、`training_cost.json`；首次epoch完成后将实测验证与保存成本计入估算。
- 启动入口与环境见 `launcher.json`；复跑须新输出目录。显式恢复完整epoch示例（先设置同launcher环境）：

```bash
FEHU_PY=/home/szf-4090/miniconda3/envs/fehu/bin/python
FEHU_RUN=/home/szf-4090/projects/fehu-project-main-2da2ea5/ntcir19_fehu-master/output/task2_scope_local_v2/pilot_20261105-023648/execution
"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method J \
  --resume "$FEHU_RUN/J/epoch_1.pt" --out "$FEHU_RUN/J_recovered_new"
"$FEHU_PY" -m research.task2_scope_local_v2.score --run "$FEHU_RUN" \
  --j-dir "$FEHU_RUN/J_recovered_new" --out "$FEHU_RUN/tune_evaluation_recovered_new"
```

## 可以支持的结论与下一步

- 当前单种子、三轮、tune选择条件下，S−J的2b F1为+0.36个百分点，AP为+0.17个百分点；J−T F1为+0.34个百分点；P−J F1为+0.45个百分点。这些是开发集效应量，不是显著性或独特机制的证明。
- S相对J减少1470个FP（26.74%），同时少找到72个TP、Recall变化-3.11个百分点。这是在各自选定操作点上的取舍，不能称为“同召回下减少FP”。
- P没有额外训练，复用J第3轮；相对J净增加17个TP、FP变化-45，F1略高于S（+0.09点）。本轮没有显示S优于简单P后处理的证据。
- 整体效果仍弱：四种方法选阈值F1约10–11%，macro-F1很低，固定0.5均为空；最佳AP约5%，fit频率基线约3.5%。存在有限的排序改善，但不能据此声称模型已能可靠区分候选，更不能称为完成了确认性验证。
- 三组tune AP与选阈值F1随epoch上升，没有观察到明确的tune下降型过拟合曲线；这也不证明已充分训练。T/J正例BCE在后期没有改善，S略有改善，说明总体BCE降低不足以证明正例学习充分。不能据此保证延长到6轮就能解决。
- T从epoch2到3：tune AP +0.15点，选阈值F1 +0.20点；fit事件BCE 0.03273→0.03208；正例BCE 3.9987→4.0209。仅据三点曲线不能断言收敛或把所有差异归因于校准。
- J从epoch2到3：tune AP +0.49点，选阈值F1 +0.64点；fit事件BCE 0.03328→0.03138；正例BCE 3.5639→3.6007。仅据三点曲线不能断言收敛或把所有差异归因于校准。
- S从epoch2到3：tune AP +0.76点，选阈值F1 +0.92点；fit事件BCE 0.03309→0.03159；正例BCE 3.5738→3.5191。仅据三点曲线不能断言收敛或把所有差异归因于校准。
- 不能用总体BCE下降代替正例学习证据：负标签位置远多于正例，应结合正例BCE、频率基线、AP及候选级TP/FP/FN判断。J/S文章项定义不同，其绝对loss不用于方法排名。
- 若各方法的正例学习仍弱，下一阶段可先在fit/tune预先限定一次针对稀疏监督/优化的共同对照，而不是仅延长S或调整阈值追分；本轮不据此归因于单一缺陷。
- 若后续研究更长预算，应在运行前冻结所有对照一致的完整6-epoch调度，从原始初始化重跑；本轮未延长、未加种子、骨干、采样或新损失。
- 如进一步检验S的独特机制，可先冻结H难负例对照或正/负文章项消融；本次仅记录max承接比例，不能排除难例加权解释。
- 确认阶段再冻结方法/预算/种子和选择规则后使用holdout；当前tune经过开发选择，不能代替确认集。不做Task1或旧508事件DeepSeek分数的跨任务/跨范围直接比较。
- 本轮未执行holdout、DEV、TEST模型评分，未调用付费API；USER_STOP、旧8-bag记录、系统内核/驱动/显示服务和Python环境保留。最终字节核对见 `preservation_final.json`：150个本轮开始时保留文件、1997个历史文件、3个环境关键文件及5个旧输入缓存均一致；当前boot、HEAD和研究分支未变。
