"""Balance-checked low-concurrency continuation of the same frozen full run."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, build_opener

import run_experiment as experiment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers",type=int,default=8)
    args=parser.parse_args()
    if not 1<=args.workers<=32:parser.error("workers must be between 1 and 32")
    if (experiment.HERE/"USER_STOP.json").exists():
        print("Full inference was stopped by the user. No balance query or inference submitted.",flush=True)
        return 2
    experiment.check_frozen()
    key,base=experiment.settings()
    request=Request(base+"/user/balance",headers={"Authorization":"Bearer "+key})
    with build_opener(experiment.NoRedirect()).open(request,timeout=30) as response:
        balance=json.loads(response.read().decode("utf-8"))
    safe={"checked_at":experiment.now(),"is_available":balance.get("is_available"),
          "balances":[{"currency":r.get("currency"),"total_balance":r.get("total_balance")} for r in balance.get("balance_infos",[])]}
    experiment.write(experiment.HERE/"account_status.json",safe)
    print(json.dumps(safe,ensure_ascii=False),flush=True)
    if not balance.get("is_available"):
        print("No inference submitted: provider reports insufficient balance.",flush=True)
        return 2
    directory=experiment.HERE/"runs/full"
    history_path=directory/"invocation_history.json"
    if history_path.exists():history=experiment.read(history_path)
    else:
        config=experiment.read(directory/"run_config.json")
        history=[{"started_at":config["started_at"],"workers":config["workers"],"type":"initial"}]
    history.append({"started_at":experiment.now(),"workers":args.workers,"type":"resume",
                    "balance_preflight":safe,"prediction_protocol_unchanged":True})
    experiment.write(history_path,history)
    experiment.run("full",args.workers)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
