"""Read-only training status; append timestamped ETA evidence, never control GPU."""
import argparse
import datetime
import json
from pathlib import Path


def monitor(run, brief=False):
    info={};reference=None;finished=[]
    for method in ('T','J','S'):
        d=run/method
        ep=[json.loads(p.read_text()) for p in sorted(d.glob('epoch_*.json'))]
        log=d/'training.jsonl'
        if not log.exists():info[method]=dict(started=False);continue
        lines=log.read_text().splitlines()
        if not lines:info[method]=dict(started=True);continue
        rows=[json.loads(x) for x in lines]
        last=rows[-1];steady=[r for r in rows if r['optimizer_step']>50]
        n=sum(r['bags'] for r in steady)
        if n>=100:
            seconds=sum(r['group_seconds'] for r in steady)
            overhead=sum(e['tune_and_metrics_seconds']+e['checkpoint_seconds'] for e in ep)/len(ep) if ep else (reference['overhead'] if reference else None)
            reference=dict(method=method,seconds_per_bag=seconds/n,overhead=overhead)
        completed=(d/'selection.json').exists()
        if completed:finished.append(method)
        info[method]=dict(started=True,completed=completed,epoch=last['epoch'],steps=last['optimizer_step'],bags=last['total_bags'],
            gradients_finite=all(r['gradients_finite'] for r in rows),post_warmup_bags=n,
            bags_per_second=n/sum(r['group_seconds'] for r in steady) if n else None,
            epochs=[dict(epoch=e['epoch'],ap=e['tune']['micro_ap'],f1=e['tune']['selected']['micro_f1'],fixed05_f1=e['tune']['fixed_05']['micro_f1'],
                train_seconds=e['train_seconds'],validation_seconds=e['tune_and_metrics_seconds'],checkpoint_seconds=e['checkpoint_seconds']) for e in ep])
    now=datetime.datetime.now().astimezone(); remaining=None
    if reference and reference['overhead'] is not None:
        remaining=0.
        for method,r in info.items():
            if r.get('completed'):continue
            bags=7950-r.get('bags',0);epochs_remaining=3-len(r.get('epochs',[]))
            rate=1/r['bags_per_second'] if r.get('bags_per_second') and r.get('post_warmup_bags',0)>=100 else reference['seconds_per_bag']
            remaining+=bags*rate+epochs_remaining*reference['overhead']
    result=dict(time=now.isoformat(),methods=info,estimated_remaining_training_validation_checkpoint_seconds=remaining,
        estimated_finish=(now+datetime.timedelta(seconds=remaining)).isoformat() if remaining is not None else None,
        future_method_reference=reference,final_official_scoring_and_report_cost_not_yet_estimated=True)
    with (run/'eta_snapshots.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
    if brief:
        for r in result['methods'].values():
            if 'epochs' in r:r['epochs']=r['epochs'][-1:]
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--brief',action='store_true')
    a=p.parse_args();monitor(a.run.resolve(),a.brief)
