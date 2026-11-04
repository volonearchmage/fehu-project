"""Preserve an interrupted full run without mislabeling it as a full score."""
from collections import Counter
import json
from pathlib import Path
import zipfile

import run_experiment as experiment


def main():
    experiment.check_frozen()
    root=experiment.HERE
    directory=root/"runs/full"
    cases=experiment.cases_from_input(experiment.read(experiment.DATA/"dev/dev_event_base.json"))
    prompt=(root/"frozen/system_prompt.txt").read_text(encoding="utf-8")
    hv=experiment.DATA/"hv_categories"
    ids=experiment.read(hv/"human_value_level1_values.json")
    l2=experiment.read(hv/"human_value_level2_values.json")
    parents=experiment.read(hv/"level_1_to_level_2.json")["level_1_to_level_2"]
    mapping={ids[name]:l2[parent] for name,parent in parents.items()}
    completed=[];pending=[];usage=Counter();errors=Counter();reasons=Counter()
    exports={task:{} for task in ("task2a","task2b")}
    actor_pairs=0
    for case in cases:
        case_dir=directory/"cases"/f'{case["case_index"]:05d}'
        for response_path in case_dir.glob("attempt_*.response.json"):
            response=experiment.read(response_path)
            reasons[response.get("choices",[{}])[0].get("finish_reason","missing")]+=1
            for name,value in response.get("usage",{}).items():
                if isinstance(value,int):usage[name]+=value
        for error_path in case_dir.glob("attempt_*.error.json"):
            error=experiment.read(error_path)
            errors[error.get("error",f'HTTP {error.get("status","unknown")}')]+=1
        result_path=case_dir/"result.json"
        if not result_path.exists():
            pending.append({"case_index":case["case_index"],"guid":case["guid"],"subevent_id":case["subevent_id"],
                            "actor_ids":[a["actor"] for a in case["candidate_actors"]],
                            "has_prior_attempts":bool(list(case_dir.glob("attempt_*")))})
            continue
        result=experiment.read(result_path)
        response=experiment.read(case_dir/result["response_file"])
        if response["choices"][0]["finish_reason"]!="stop":raise RuntimeError("Invalid successful response")
        actors,labels=experiment.validate(response["choices"][0]["message"]["content"],case)
        payload=experiment.payload_for(case,prompt)
        if experiment.read(case_dir/"request.json")!=payload or result["request_sha256"]!=experiment.digest(experiment.canonical(payload).encode()):
            raise RuntimeError("Cached request mismatch")
        if labels!=result["labels"] or actors!=result["actors"]:raise RuntimeError("Cached response mismatch")
        completed.append({"case_index":case["case_index"],"guid":case["guid"],"subevent_id":case["subevent_id"]})
        actor_pairs+=len(actors)
        coarse=[{"actor":actor,"l2_value":value} for actor,value in sorted({(v["actor"],mapping[v["l1_value"]]) for v in labels})]
        for task,values in (("task2a",coarse),("task2b",labels)):
            article=exports[task].setdefault(case["guid"],{"guid":case["guid"],"subevents_human_values":[]})
            article["subevents_human_values"].append({"subevent_id":case["subevent_id"],"subevent_human_values":values})
    snapshot=root/"interrupted_checkpoint"
    snapshot.mkdir(exist_ok=True)
    for task in exports:experiment.write(snapshot/f"pred_{task}_PARTIAL.json",list(exports[task].values()))
    experiment.write(snapshot/"completed_cases.json",completed)
    experiment.write(snapshot/"pending_cases.json",pending)
    status={"at":experiment.now(),"objective_complete":False,"status":"waiting_for_provider_balance",
            "full_target_events":len(cases),"validated_events":len(completed),"pending_events":len(pending),
            "validated_actor_event_pairs":actor_pairs,"successful_cache_revalidated":True,
            "smoke_official_scoring_complete":experiment.read(root/"runs/smoke/run_config.json")["status"]=="complete",
            "full_scoring_complete":False,"partial_predictions_are_not_a_full_dev_result":True,
            "provider_balance":experiment.read(root/"account_status.json"),"all_returned_attempt_usage":dict(usage),
            "response_finish_reasons":dict(reasons),"technical_error_attempts":dict(errors),
            "resume_command":"python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/resume_full.py --workers 8",
            "after_full_run":"python -X utf8 ntcir19_fehu-master/research/task2_prompt_baseline_v1/audit_results.py"}
    experiment.write(snapshot/"status.json",status)
    experiment.write(directory/"progress_reconciled.json",status)
    text=f"""# Experiment interrupted: full objective is not complete

Last checked: {status['at']}.

- Smoke: 5 subevents completed, official CLI scoring and independent audit passed.
- Full DEV target: 1,526 subevents / 177 articles / 3,998 candidate actor-event pairs.
- Valid cached subevents: {len(completed)}; pending: {len(pending)}.
- Current blocking condition: DeepSeek HTTP 402; balance endpoint reports unavailable.
- Account balance at last check: {json.dumps(status['provider_balance']['balances'],ensure_ascii=False)}.
- There is no complete DEV baseline score yet. Partial predictions are explicitly named PARTIAL.
- The queue's old fatal counter includes cancelled futures; progress_reconciled.json derives true coverage from validated response caches.

Successful results remain reusable. No model, prompt or reasoning-effort substitution was made.
The same frozen prompt and max-thinking configuration will be used on continuation.
The continuation entry checks the account balance before submitting inference and uses 8 workers.

From the outer fehu-project folder:

```powershell
{status['resume_command']}
{status['after_full_run']}
```

The final audit/export command intentionally requires a fully completed run.
The interrupted checkpoint archive is only a progress snapshot, not the requested final all-results archive.
"""
    (root/"STATUS.md").write_text(text,encoding="utf-8",newline="\n")
    key,_=experiment.settings()
    exports_dir=root/"exports";exports_dir.mkdir(exist_ok=True)
    paths=[p for p in root.rglob("*") if p.is_file() and not any(part in {"exports","__pycache__","preflight_frozen_before_line_ending_fix"} for part in p.relative_to(root).parts)
           and not p.name.endswith((".pyc",".tmp"))]
    for path in paths:
        if key.encode() in path.read_bytes():raise RuntimeError("Credential found in artifact; export refused")
    archive=exports_dir/"INTERRUPTED_checkpoint_NOT_FULL_RESULTS.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for path in paths:zipped.write(path,arcname=str(Path(root.name)/path.relative_to(root)))
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:raise RuntimeError("Checkpoint archive corrupt")
    experiment.write(exports_dir/"interrupted_archive_manifest.json",{"file":archive.name,"bytes":archive.stat().st_size,
                     "sha256":experiment.digest(archive.read_bytes()),"files":len(paths),"credentials_excluded":True,
                     "full_experiment_complete":False})
    print(json.dumps({"validated":len(completed),"pending":len(pending),"export":str(archive),"complete":False},ensure_ascii=False))


if __name__=="__main__":main()
