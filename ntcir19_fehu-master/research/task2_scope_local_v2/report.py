"""Write source-backed pilot tables/figures after all three fixed runs finish."""
import argparse
import csv
import json
from pathlib import Path
import statistics

import numpy as np


def read(p): return json.loads(p.read_text())
def pct(x): return f"{100*x:.2f}"
def gib(x): return x / 1024**3


def build(run):
    completed=read(run/'driver_result.json')
    if not completed['completed']: raise RuntimeError('Pilot is not complete')
    summary=read(run/'tune_evaluation/summary.json')
    selections={m:read(run/m/'selection.json') for m in ('T','J','S')}
    epochs={m:[read(run/m/f'epoch_{e}.json') for e in (1,2,3)] for m in selections}
    initial=read(run/'preflight/initial_tune_metrics.json')['metrics']
    manifest=read(run/'input_cache/manifest.json')
    receipt=read(run/'preflight/receipt.json')
    runtime=read(run/'runtime_environment.json')
    frozen=read(run/'frozen.json')
    before=read(run.parent/'provenance_before.json')
    if len({v['initial_weights_sha256'] for v in selections.values()}) != 1:
        raise AssertionError('Initial weights not shared')
    for e in range(3):
        if len({epochs[m][e]['ordered_bag_keys_sha256'] for m in epochs}) != 1:
            raise AssertionError('Sample orders not shared')
    if any(v['optimizer_steps'] != 498 or v['processed_bags'] != 7950 for v in selections.values()):
        raise AssertionError('Incomplete fixed budget')
    cost={}
    for m in selections:
        rows=[json.loads(x) for x in (run/m/'training.jsonl').read_text().splitlines()]
        steady=[r for r in rows if r['optimizer_step']>50]
        n=sum(r['bags'] for r in steady); seconds=sum(r['group_seconds'] for r in steady)
        cost[m]=dict(post_warmup_bags=n,post_warmup_seconds=seconds,bags_per_second=n/seconds,
            train_seconds=sum(r['train_seconds'] for r in epochs[m]),
            validation_and_metrics_seconds=sum(r['tune_and_metrics_seconds'] for r in epochs[m]),
            checkpoint_seconds=sum(r['checkpoint_seconds'] for r in epochs[m]),
            forward_seconds=sum(r['forward_seconds'] for r in epochs[m]),
            backward_seconds=sum(r['backward_seconds'] for r in epochs[m]),
            optimizer_seconds=sum(r['optimizer_seconds'] for r in epochs[m]),
            run_seconds=selections[m]['elapsed_seconds'],
            peak_allocated_gib=max(gib(r['peak_allocated_bytes']) for r in epochs[m]),
            peak_reserved_gib=max(gib(r['peak_reserved_bytes']) for r in epochs[m]))
    (run/'training_cost.json').write_text(json.dumps(cost,indent=2)+'\n')
    with (run/'learning_curves.csv').open('x') as f:
        writer=csv.DictWriter(f,fieldnames=['method','epoch','fit_event_bce','fit_article_loss','fit_positive_bce','fit_negative_bce','tune_ap','tune_selected_f1','tune_fixed05_f1','threshold','optimizer_steps'])
        writer.writeheader()
        for m, es in epochs.items():
            for r in es:
                writer.writerow(dict(method=m,epoch=r['epoch'],fit_event_bce=r['fit_event_loss'],fit_article_loss=r['fit_article_loss'],fit_positive_bce=r['fit_positive_bce'],fit_negative_bce=r['fit_negative_bce'],tune_ap=r['tune']['micro_ap'],tune_selected_f1=r['tune']['selected']['micro_f1'],tune_fixed05_f1=r['tune']['fixed_05']['micro_f1'],threshold=r['tune']['selected']['threshold'],optimizer_steps=r['optimizer_steps']))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for m,es in epochs.items():
        axes[0,0].plot([1,2,3],[r['fit_event_loss'] for r in es],marker='o',label=m)
        axes[0,1].plot([0,1,2,3],[initial['micro_ap']]+[r['tune']['micro_ap'] for r in es],marker='o',label=m)
        axes[1,0].plot([0,1,2,3],[initial['selected']['micro_f1']]+[r['tune']['selected']['micro_f1'] for r in es],marker='o',label=m)
        axes[1,1].plot([0,1,2,3],[initial['fixed_05']['micro_f1']]+[r['tune']['fixed_05']['micro_f1'] for r in es],marker='o',label=m)
    for ax,title in zip(axes.flat,['Fit event BCE (training-mode aggregate)','Tune micro-AP','Tune globally selected micro-F1','Tune micro-F1 at threshold 0.5']):
        ax.set_title(title);ax.set_xlabel('Epoch');ax.set_xticks([0,1,2,3]);ax.grid(alpha=.25);ax.legend()
    fig.suptitle('FEHU Task 2 v2 pilot | seed11 | tune development results')
    fig.savefig(run/'learning_curves.png',dpi=180);fig.savefig(run/'learning_curves.pdf');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    for m in ('T','J','S','P'):
        c=np.load(run/f'tune_evaluation/{m}/pr_curve.npz')
        for ax in axs: ax.plot(c['recall'],c['precision'],label=f'{m} (AP={summary["methods"][m]["metrics"]["micro_ap"]:.4f})')
    for ax, limit in zip(axs,(1.,.25)):
        ax.set(xlim=(0,1),ylim=(0,limit),xlabel='Recall',ylabel='Precision',title='Full scale' if limit==1. else 'Precision zoom: 0 to 0.25')
        ax.grid(alpha=.25);ax.legend()
    fig.suptitle('Selected checkpoints: tune development PR curves')
    fig.savefig(run/'tune_pr_curves.png',dpi=180);fig.savefig(run/'tune_pr_curves.pdf');plt.close(fig)
    lines=['# FEHU Task 2 v2 — PILOT_RESULTS', '',
        '**已完成：T/J/S 各3 epochs、seed11；P复用选定J；仅fit训练与tune开发评估。未评估holdout、DEV或TEST。**', '',
        '## 执行与协议', '',
        f'- 固定协议提交：`{frozen["binding"]["protocol_commit"]}`；完整原文在上级 `protocol_reference/`，通过 `git show SHA:path` 读取。',
        f'- 研究分支：`{before["branch"]}`；起始HEAD：`{before["head"]}`。确认origin后只fetch main；未pull/reset/clean、未切换main、未push。',
        f'- 本次运行目录：`{run}`。启动、PID、逐阶段退出码见 `launcher.json`、`processes.jsonl`、`driver_result.json`。',
        '- 旧8-bag诊断仍是“未通过原Recall门槛”。v2在全量探索前公开撤销这一准入规则；未改写旧结果或复用诊断权重。低分不触发追加预算。',
        '- T=事件BCE；J=事件BCE+独立文章BCE；S=事件BCE+原gold-aware文章项。T/J/S同全文、主体、完整子事件输入、mean pooling和共享108维head。P只改变选定J的评分为文章概率×事件概率。',
        '- 与旧方案的输入调整：去掉插入文本的actor/event ID，保留元数据、主体名称、正文、事件文本与文章内序号；不声称这些ID导致旧诊断低召回。',
        '- 三组均从原始ModernBERT权重与相同新head开始，AdamW encoder2e-5/head1e-4、wd.01、clip1、lambda1（T为0）、BF16、microbatch1、有效batch16、窗口checkpoint。50步warmup后按完整498步线性衰减到0。第一步LR为0，第二步已核对真实参数改变。',
        '- 原bag文章项计一次，事件BCE按每bag有效事件数×108归一化，再按bag平均；每轮尾批10bags按10归一化。每条件7950bags/7950microbatches、7953windows、498optimizer steps；合计23850bags、1494updates。',
        '- 精确全局阈值扫描：同分成组、score>=threshold、全空阈值2.0；不四舍五入。同分取较高阈值再较早epoch。P仅在已选J epoch选阈值。', '',
        '## 绑定、覆盖与工程证据', '',
        f'- Python：`{frozen["binding"]["python"]}`；软件版本：`{json.dumps(frozen["binding"]["versions"],ensure_ascii=False)}`。',
        f'- GPU/驱动/显存（nvidia-smi）：`{runtime["gpu"]}`；内核 `{runtime["kernel"]}`；PyTorch CUDA build `{frozen["binding"]["cuda_build"]}`。GPU恢复以来boot未变。',
        '- 模型/tokenizer：answerdotai/ModernBERT-base，revision `8949b909ec900327062f0ebf497f51aef5e6f0c8`。真实149,014,272参数encoder与83,052参数共享head；未下载新模型或修改环境。',
        f'- 三组初始参数SHA-256：`{receipt["initial_weights_sha256"]}`。每epoch的顺序哈希跨三组一致，详见各epoch JSON。',
        '- 输入/标签/模型/实现版本与逐条件生效配置见 `frozen.json`、`config_T/J/S.json`、`source_frozen/`；逐bag输入/渲染/分窗哈希见 `input_cache/*.coverage.json`。', '',
        '| 划分 | 文章 | bags | windows | 候选 | 最大窗口tokens |', '|---|---:|---:|---:|---:|---:|']
    for name,r in manifest['partitions'].items():lines.append(f'| {name} | {r["articles"]} | {r["bags"]} | {r["windows"]} | {r["candidates"]} | {r["max_window_tokens"]} |')
    lines += ['', '- fit cache SHA-256：`'+manifest['partitions']['fit']['sha256']+'`。',
        '- tune cache SHA-256：`'+manifest['partitions']['tune']['sha256']+'`。',
        '- 唯一长bag `33-2677-7-t / 33-2677-7-t-0`：9585tokens=正文9249+事件文本288+列表标记32+主体/正文头14+特殊标记2；两窗8192/1985，正文ownership7856/1393，9事件完整。所有span、窗口覆盖和正文唯一ownership已核验。',
        '- 仅新增4项针对变更的CPU核查：T梯度、ID改变不影响tokens/spans、并列分数/全空/暴力阈值扫描、序列化精度与导出。执行命令与结果在上级 `focused_cpu_checks.json`；未重复47项旧测试。',
        '- 第一轮v2 GPU receipt因连续/恢复下一步哈希不同而失败。诊断证明重载前状态完全一致，默认GPU更新有非确定性；仅在进程中统一启用确定性算法和cuBLAS workspace后，下一步模型、AdamW、scheduler、RNG逐位一致。所有失败日志及checkpoint保留在上级目录。详见 `ENGINEERING_CHANGE.md` 和上级 `resume_*_diagnosis.json`。',
        f'- 新receipt重新执行T/J/S短/中/最长真实bag前反向、真实AdamW更新、更新后最长输入及下一步恢复一致检查，全部通过。最长输入更新后峰值 {gib(receipt["updated_longest"]["peak_allocated_bytes"]):.3f} GiB allocated / {gib(receipt["updated_longest"]["peak_reserved_bytes"]):.3f} GiB reserved；见 `preflight/receipt.json`。',
        '- 恢复检查用少量完整optimizer groups模拟序列化边界，未声称预检完成一个训练epoch。实际训练每166步保存完整epoch状态；支持显式epoch边界恢复，不支持自动或microbatch中途恢复。', '',
        '## Tune开发成绩', '',
        '**下表经过同一tune上的checkpoint与阈值选择，不是未触碰测试集的泛化成绩。百分数表示P/R/F1/AP，阈值保持原精度。**', '',
        '| 方法 | epoch | 阈值 | 2b P | 2b R | 2b micro-F1 | 2b macro-F1 | micro-AP | TP/FP/FN |',
        '|---|---:|---|---:|---:|---:|---:|---:|---|']
    for m,v in summary['methods'].items():
        x=v['official']['selected']['task2b'];met=v['metrics']
        lines.append(f'| {m} | {v["epoch"]} | `{met["selected"]["threshold"]!r}` | {pct(x["micro_precision"])} | {pct(x["micro_recall"])} | {pct(x["micro_f1"])} | {pct(x["macro_f1"])} | {pct(met["micro_ap"])} | {x["tp"]}/{x["fp"]}/{x["fn"]} |')
    lines += ['', '| 方法 | 2a P | 2a R | 2a micro-F1 | 2a macro-F1 | 2a TP/FP/FN | 2b DRR | 0.5下2b P/R/F1 | 0.5下TP/FP/FN |', '|---|---:|---:|---:|---:|---|---:|---|---|']
    for m,v in summary['methods'].items():
        a=v['official']['selected']['task2a'];b=v['official']['selected']['task2b'];fixed=v['metrics']['fixed_05']
        lines.append(f'| {m} | {pct(a["micro_precision"])} | {pct(a["micro_recall"])} | {pct(a["micro_f1"])} | {pct(a["macro_f1"])} | {a["tp"]}/{a["fp"]}/{a["fn"]} | {pct(b["direction_reverse_rate"])} | {pct(fixed["precision"])}/{pct(fixed["recall"])}/{pct(fixed["micro_f1"])} | {fixed["tp"]}/{fixed["fp"]}/{fixed["fn"]} |')
    lines += ['', '- Task2a按官方54→20映射、去方向并去重，DRR不适用；Task2b保留54×2，1=aligned、0=contradictory。没有强制非空或两标签上限。',
        '- 各方法selected/fixed_05目录保存严格官方格式、全部候选覆盖清单、评价器命令/版本/stdout/metrics。官方TP/FP/FN与扫描计数全部相符。tune gold来自固定TRAIN派生的tune监督缓存，按冻结manifest和候选核对；未读取holdout/DEV/TEST gold。',
        f'- 原始初始化tune AP={pct(initial["micro_ap"])}%，选阈值F1={pct(initial["selected"]["micro_f1"])}%；仅作epoch0基线，不参与checkpoint选择。',
        f'- fit候选频率基线（分母23783，不按bag平均）：tune AP={pct(summary["fit_frequency_baseline"]["micro_ap"])}%，选阈值F1={pct(summary["fit_frequency_baseline"]["selected"]["micro_f1"])}%。频率只来自fit；AP也受跨类频率影响。', '',
        '## 真实学习曲线', '',
        '![Learning curves](learning_curves.png)', '',
        '![Tune PR](tune_pr_curves.png)', '',
        '图表的CSV/PDF和全部精确P/R边界NPZ均已保存。fit损失是在训练模式、不断变化的参数下累计，不能当作固定checkpoint的eval loss。正负BCE按有效label cells平均，事件/文章loss按bag平均；T的文章BCE仅记录，训练权重为0。', '',
        '| 方法 | epoch | fit事件BCE | fit文章项 | fit正例BCE | fit负例BCE | tune AP | tune选阈值F1 | tune 0.5 F1 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m,es in epochs.items():
        for r in es:
            lines.append(f'| {m} | {r["epoch"]} | {r["fit_event_loss"]:.5f} | {r["fit_article_loss"]:.5f} | {r["fit_positive_bce"]:.5f} | {r["fit_negative_bce"]:.5f} | {pct(r["tune"]["micro_ap"])} | {pct(r["tune"]["selected"]["micro_f1"])} | {pct(r["tune"]["fixed_05"]["micro_f1"])} |')
    lines += ['', '## 方法差值与机制', '', '| 比较 | 2b F1差（百分点） | AP差（百分点） | 新TP / 丢TP / 减FP / 增FP |', '|---|---:|---:|---|']
    for pair,c in summary['comparisons'].items():
        ch=c['changes']; lines.append(f'| {pair} | {100*c["delta_f1"]:+.2f} | {100*c["delta_ap"]:+.2f} | {ch["new_tp"]["count"]}/{ch["lost_tp"]["count"]}/{ch["removed_fp"]["count"]}/{ch["new_fp"]["count"]} |')
    lines += ['', '| 方法 | 原始event>article（分子/分母） | 空候选误报（候选/分母；标签数） | 文章独有标签下传（bag-label对/分母） |', '|---|---|---|---|']
    diagnostics_by_method={}
    for m in summary['methods']:
        d=read(run/f'tune_evaluation/{m}/diagnostics.json');diagnostics_by_method[m]=d
        v=d['raw_event_gt_article']; e=d['empty_candidates']; a=d['article_only']
        lines.append(f'| {m} | {v["numerator"]}/{v["denominator"]} ({pct(v["rate"])}%) | {e["candidates_with_fp"]}/{e["denominator"]}; {e["fp_labels"]} | {a["pairs_with_event_fp"]}/{a["article_label_pairs"]} |')
    lines += ['', 'S的max承接计数（正项仅允许gold-positive child；负项允许全部child，概率并列单列）：', '', '| 文章项 | article独占 | child独占 | article/child并列 |', '|---|---:|---:|---:|']
    for sign,v in diagnostics_by_method['S']['max_responsibility'].items():
        total=sum(v.values())
        lines.append(f'| {sign} | {v["article_only"]} ({pct(v["article_only"]/total)}%) | {v["child_only"]} ({pct(v["child_only"]/total)}%) | {v["tie_article_child"]} ({pct(v["tie_article_child"]/total)}%) |')
    lines += ['', '- 文章独有标签无须分给任何事件；上述下传是诊断中的误报计数。原始违反率只是机制描述，不把上行max后的零违反率作为成功。T无文章训练目标，其原始文章概率仅供机制参考。',
        '- 各方法 `diagnostics.json` 保存108类fit/tune支持数、零fit正例类、方向分层、bag事件数和同文多主体预测差异；`comparisons.json` 给出可按GUID/actor/event/label核对的新增/丢失TP、增减FP例子。', '',
        '| 零fit正例有向类 index/value/direction | tune正例 | T TP/FP/FN | J TP/FP/FN | S TP/FP/FN | P TP/FP/FN |', '|---|---:|---|---|---|---|']
    for r in diagnostics_by_method['T']['zero_fit_positive_classes']:
        index=r['index']; values=[diagnostics_by_method[m]['per_class'][index] for m in ('T','J','S','P')]
        lines.append(f'| {index}/{r["value"]}/{r["direction"]} | {r["tune_support"]} | '+' | '.join(f'{v["tp"]}/{v["fp"]}/{v["fn"]}' for v in values)+' |')
    lines += ['', '## 实测成本与边界恢复', '', '| 方法 | 训练秒 | 验证/指标秒 | checkpoint秒 | 总运行秒 | 预热后bags/s | allocated/reserved峰值GiB |', '|---|---:|---:|---:|---:|---:|---|']
    for m,c in cost.items():lines.append(f'| {m} | {c["train_seconds"]:.1f} | {c["validation_and_metrics_seconds"]:.1f} | {c["checkpoint_seconds"]:.1f} | {c["run_seconds"]:.1f} | {c["bags_per_second"]:.2f} | {c["peak_allocated_gib"]:.2f}/{c["peak_reserved_gib"]:.2f} |')
    lines += ['', f'有限driver总墙钟时间（包括三组加载、训练、验证、保存和最后官方评分）{completed["elapsed_seconds"]:.1f}秒；前期实现和GPU验收不计入该值。',
        '- 每组吞吐排除前50个warmup updates，实际统计7150bags，包含前向/反向/优化器更新。逐阶段耗时和每次ETA见 `training.jsonl`、`training_cost.json`；首次epoch完成后将实测验证与保存成本计入估算。',
        '- 启动入口与环境见 `launcher.json`；复跑须新输出目录。显式恢复完整epoch示例（先设置同launcher环境）：', '', '```bash',
        f'FEHU_PY={frozen["binding"]["python"]}', f'FEHU_RUN={run}',
        '"$FEHU_PY" -m research.task2_scope_local_v2.train --run "$FEHU_RUN" --method J \\',
        '  --resume "$FEHU_RUN/J/epoch_1.pt" --out "$FEHU_RUN/J_recovered_new"',
        '"$FEHU_PY" -m research.task2_scope_local_v2.score --run "$FEHU_RUN" \\',
        '  --j-dir "$FEHU_RUN/J_recovered_new" --out "$FEHU_RUN/tune_evaluation_recovered_new"', '```', '',
        '## 可以支持的结论与下一步', '']
    sj=summary['comparisons']['S-J']; pj=summary['comparisons']['P-J'];jt=summary['comparisons']['J-T']
    lines.append(f'- 当前单种子、三轮、tune选择条件下，S−J的2b F1为{100*sj["delta_f1"]:+.2f}个百分点，AP为{100*sj["delta_ap"]:+.2f}个百分点；J−T F1为{100*jt["delta_f1"]:+.2f}个百分点；P−J F1为{100*pj["delta_f1"]:+.2f}个百分点。这些是开发集效应量，不是显著性或独特机制的证明。')
    jm=summary['methods']['J']['metrics']['selected'];sm=summary['methods']['S']['metrics']['selected'];pm=summary['methods']['P']['metrics']['selected']
    lines.append(f'- S相对J减少{jm["fp"]-sm["fp"]}个FP（{100*(jm["fp"]-sm["fp"])/jm["fp"]:.2f}%），同时少找到{jm["tp"]-sm["tp"]}个TP、Recall变化{100*(sm["recall"]-jm["recall"]):+.2f}个百分点。这是在各自选定操作点上的取舍，不能称为“同召回下减少FP”。')
    lines.append(f'- P没有额外训练，复用J第{summary["methods"]["P"]["epoch"]}轮；相对J净增加{pm["tp"]-jm["tp"]}个TP、FP变化{pm["fp"]-jm["fp"]:+d}，F1略高于S（{100*(pm["micro_f1"]-sm["micro_f1"]):+.2f}点）。本轮没有显示S优于简单P后处理的证据。')
    lines.append('- 整体效果仍弱：四种方法选阈值F1约10–11%，macro-F1很低，固定0.5均为空；最佳AP约5%，fit频率基线约3.5%。存在有限的排序改善，但不能据此声称模型已能可靠区分候选，更不能称为完成了确认性验证。')
    lines.append('- 三组tune AP与选阈值F1随epoch上升，没有观察到明确的tune下降型过拟合曲线；这也不证明已充分训练。T/J正例BCE在后期没有改善，S略有改善，说明总体BCE降低不足以证明正例学习充分。不能据此保证延长到6轮就能解决。')
    for m,es in epochs.items():
        apdelta=es[-1]['tune']['micro_ap']-es[-2]['tune']['micro_ap']
        fdelta=es[-1]['tune']['selected']['micro_f1']-es[-2]['tune']['selected']['micro_f1']
        lines.append(f'- {m}从epoch2到3：tune AP {100*apdelta:+.2f}点，选阈值F1 {100*fdelta:+.2f}点；fit事件BCE {es[-2]["fit_event_loss"]:.5f}→{es[-1]["fit_event_loss"]:.5f}；正例BCE {es[-2]["fit_positive_bce"]:.4f}→{es[-1]["fit_positive_bce"]:.4f}。仅据三点曲线不能断言收敛或把所有差异归因于校准。')
    lines += ['- 不能用总体BCE下降代替正例学习证据：负标签位置远多于正例，应结合正例BCE、频率基线、AP及候选级TP/FP/FN判断。J/S文章项定义不同，其绝对loss不用于方法排名。',
        '- 若各方法的正例学习仍弱，下一阶段可先在fit/tune预先限定一次针对稀疏监督/优化的共同对照，而不是仅延长S或调整阈值追分；本轮不据此归因于单一缺陷。',
        '- 若后续研究更长预算，应在运行前冻结所有对照一致的完整6-epoch调度，从原始初始化重跑；本轮未延长、未加种子、骨干、采样或新损失。',
        '- 如进一步检验S的独特机制，可先冻结H难负例对照或正/负文章项消融；本次仅记录max承接比例，不能排除难例加权解释。',
        '- 确认阶段再冻结方法/预算/种子和选择规则后使用holdout；当前tune经过开发选择，不能代替确认集。不做Task1或旧508事件DeepSeek分数的跨任务/跨范围直接比较。',
        '- 本轮未执行holdout、DEV、TEST模型评分，未调用付费API；USER_STOP、旧8-bag记录、系统内核/驱动/显示服务和Python环境保留。最终字节核对见 `preservation_final.json`（交付时生成）。', '']
    (run/'PILOT_RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(report=str(run/'PILOT_RESULTS.md'),cost=cost),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    build(p.parse_args().run.resolve())
