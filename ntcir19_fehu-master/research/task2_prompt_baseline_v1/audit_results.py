"""Independent full-scope result audit, summary and credential-free export."""
from __future__ import annotations

import ast
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def counts_and_metrics(gold, pred):
    labels = {label for values in gold.values() for label in values}
    per_label = {label:[0,0,0] for label in labels | {v for values in pred.values() for v in values}}
    tp = fp = fn = 0
    for key in gold.keys() | pred.keys():
        g, p = gold.get(key,set()), pred.get(key,set())
        tp += len(g&p); fp += len(p-g); fn += len(g-p)
        for label in g|p:
            per_label[label][0] += label in g&p
            per_label[label][1] += label in p-g
            per_label[label][2] += label in g-p
    macro = statistics.mean(2*per_label[v][0]/(2*per_label[v][0]+per_label[v][1]+per_label[v][2]) for v in labels) if labels else 0
    return {"tp":tp,"fp":fp,"fn":fn,"micro_f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
            "micro_precision":tp/(tp+fp) if tp+fp else 0,"micro_recall":tp/(tp+fn) if tp+fn else 0,
            "macro_f1":macro}, per_label


def read_labels(rows, coarse=False):
    result = {}
    for article in rows:
        for event in article["subevents_human_values"]:
            for value in event["subevent_human_values"]:
                key=(str(article["guid"]),str(event["subevent_id"]),str(value["actor"]))
                label=str(value["l2_value"]) if coarse else f'{value["direction"]}:{value["l1_value"]}'
                result.setdefault(key,set()).add(label)
    return result


def audit_phase(phase):
    directory=HERE/"runs"/phase
    config=load(directory/"run_config.json")
    check(config["status"]=="complete",f"{phase} not complete")
    source=load(ROOT/"dataset/dev/dev_event_base.json")
    cases=[(article,event) for article in source for event in article["subevents"]]
    if phase=="smoke":cases=cases[:5]
    expected_events={(a["guid"],str(e["id"])) for a,e in cases}
    expected_actors={(a["guid"],str(e["id"]),str(aid)) for a,e in cases for record in a["actors"] for aid in record.values()}
    expected_b={}; latencies=[]; selected_usage=Counter()
    prompt=(HERE/"frozen/system_prompt.txt").read_text(encoding="utf-8")
    manifest=load(HERE/"frozen/manifest.json")
    check(manifest["system_prompt_sha256"]==sha(HERE/"frozen/system_prompt.txt"),"Prompt hash mismatch")
    check(manifest["code_sha256"]==sha(HERE/"run_experiment.py"),"Code hash mismatch")
    for path,value in manifest["source_hashes"].items():check(sha(ROOT/path)==value,"Source hash mismatch")
    for index,(article,event) in enumerate(cases):
        case_dir=directory/"cases"/f"{index:05d}"
        request=load(case_dir/"request.json"); result=load(case_dir/"result.json")
        check(request["model"]=="deepseek-flash" and request["reasoning_effort"]=="max", "Wrong model/effort")
        check(request["thinking"]=={"type":"enabled"},"Thinking not enabled")
        check(request["max_tokens"]==32768 and "temperature" not in request,"Unexpected generation settings")
        check(request["messages"][0]=={"role":"system","content":prompt},"Prompt changed between requests")
        user=json.loads(request["messages"][1]["content"])
        check(set(user)=={"TARGET_SUBEVENT","candidate_actors","article_background"},"Unexpected model-visible fields")
        check(user["TARGET_SUBEVENT"]=={"id":str(event["id"]),"text":event["subevent"]},"Target event mismatch")
        check(user["article_background"]=={"title":article["title"],"content":article["content"]},"Background mismatch/truncation")
        actors={str(aid):name for record in article["actors"] for name,aid in record.items()}
        check(user["candidate_actors"]==[{"actor":str(aid),"name":name} for record in article["actors"] for name,aid in record.items()],"Candidate input mismatch")
        response=load(case_dir/result["response_file"])
        check(response["choices"][0]["finish_reason"]=="stop","Truncated selected response")
        output=json.loads(response["choices"][0]["message"]["content"])
        check(set(output)=={"actors"},"Invalid output root")
        observed={}
        for actor in output["actors"]:
            aid=actor["actor"]
            check(aid in actors and aid not in observed,"Unknown/duplicate output actor")
            values=set()
            for value in actor["values"]:
                check(isinstance(value["l1_value"],str) and value["l1_value"] in {str(i) for i in range(54)},"Invalid L1")
                check(isinstance(value["direction"],str) and value["direction"] in {"0","1"},"Invalid direction")
                pair=(value["direction"],value["l1_value"])
                check(pair not in values,"Duplicate output label")
                values.add(pair)
            observed[aid]=values
            expected_b[(article["guid"],str(event["id"]),aid)]={f"{d}:{v}" for d,v in values}
        check(set(observed)==set(actors),"Missing actor output")
        check(result["actors"]==output["actors"],"Cache not supported by response")
        latencies.append(result["seconds"])
        for key,value in response.get("usage",{}).items():
            if isinstance(value,int):selected_usage[key]+=value
    check(set(expected_b)==expected_actors,"Candidate coverage mismatch")
    predictions={task:load(directory/f"pred_{task}.json") for task in ("task2a","task2b")}
    for task,rows in predictions.items():
        event_keys=[(a["guid"],str(e["subevent_id"])) for a in rows for e in a["subevents_human_values"]]
        check(len(event_keys)==len(set(event_keys)) and set(event_keys)==expected_events,f"{task} event coverage mismatch")
        for article in rows:
            for event in article["subevents_human_values"]:
                values=event["subevent_human_values"]
                identities=[(v["actor"],v["l2_value"]) if task=="task2a" else (v["actor"],v["l1_value"],v["direction"]) for v in values]
                check(len(identities)==len(set(identities)),"Duplicate exported labels")
    actual_b=read_labels(predictions["task2b"])
    check(actual_b=={k:v for k,v in expected_b.items() if v},"Exported Task2b differs from raw responses")
    hv=ROOT/"dataset/hv_categories"
    ids=load(hv/"human_value_level1_values.json"); parents=load(hv/"level_1_to_level_2.json")["level_1_to_level_2"]
    l2=load(hv/"human_value_level2_values.json"); mapping={ids[n]:l2[p] for n,p in parents.items()}
    expected_a={key:{mapping[label.split(":")[1]] for label in values} for key,values in actual_b.items()}
    check(read_labels(predictions["task2a"],True)==expected_a,"Task2a mapping mismatch")
    gold_path=ROOT/"dataset/gold_labels/dev/dev_human_values.json" if phase=="full" else directory/"gold_subset.json"
    gold_rows=load(gold_path); metrics=load(directory/"metrics_official.json")
    check(load(directory/"official_stdout.json")==metrics,"Official stdout/output disagree")
    independent={}; label_counts={}
    for task,coarse in (("task2a",True),("task2b",False)):
        metric,counts=counts_and_metrics(read_labels(gold_rows,coarse),read_labels(predictions[task],coarse))
        for field in ("micro_f1","micro_precision","micro_recall","macro_f1"):
            check(abs(metric[field]-metrics[task][field])<1e-12,f"Official {task} {field} mismatch")
        independent[task]=metric;label_counts[task]=counts
    gold_b=read_labels(gold_rows); pred_b=read_labels(predictions["task2b"])
    reversed_count=exclusive_count=ambiguous_count=0
    for key,values in gold_b.items():
        identities={label.split(":")[1] for label in values}
        for identity in identities:
            directions={label.split(":")[0] for label in values if label.split(":")[1]==identity}
            if len(directions)==2:
                ambiguous_count+=1
            else:
                exclusive_count+=1
                opposite="0" if "1" in directions else "1"
                reversed_count+=f"{opposite}:{identity}" in pred_b.get(key,set())
    drr=reversed_count/exclusive_count if exclusive_count else 0
    check(abs(drr-metrics["task2b"]["direction_reverse_rate"])<1e-12,"Official DRR mismatch")
    check(reversed_count==metrics["task2b"]["direction_reverse_count"],"DRR numerator mismatch")
    check(exclusive_count==metrics["task2b"]["direction_reverse_denom_gold_excl"],"DRR denominator mismatch")
    check(ambiguous_count==metrics["task2b"]["ambiguous_gold_values_filtered"],"DRR ambiguity count mismatch")
    independent["drr"]={"rate":drr,"reversed":reversed_count,"exclusive":exclusive_count,"ambiguous":ambiguous_count}
    with (directory/"per_label_metrics.csv").open(encoding="utf-8-sig",newline="") as stream:
        label_rows=list(csv.DictReader(stream))
        expected_label_rows={("task2a",str(v)) for v in range(20)}|{("task2b",f"{d}:{v}") for d in ("0","1") for v in range(54)}
        check(len(label_rows)==128 and {(r["task"],r["label"]) for r in label_rows}==expected_label_rows,"Per-label table is incomplete")
        for row in label_rows:
            count=label_counts[row["task"]].get(row["label"],[0,0,0])
            check([int(row[n]) for n in ("tp","fp","fn")]==count,"Per-label counts mismatch")
    with (directory/"per_article_metrics.csv").open(encoding="utf-8-sig",newline="") as stream:
        rows=list(csv.DictReader(stream))
    check(len(rows)==len({a["guid"] for a,e in cases}) and {r["guid"] for r in rows}=={a["guid"] for a,e in cases},"Per-article table is incomplete")
    for field in ("tp","fp","fn"):
        check(sum(int(r[field]) for r in rows)==independent["task2b"][field],"Per-article total mismatch")
    errors=[json.loads(line) for line in (directory/"errors.jsonl").read_text(encoding="utf-8").splitlines()]
    check(sum(len(r["false_positives"]) for r in errors)==independent["task2b"]["fp"],"FP error export mismatch")
    check(sum(len(r["false_negatives"]) for r in errors)==independent["task2b"]["fn"],"FN error export mismatch")
    original=(HERE/"evaluator/official_original.py").read_text(encoding="utf-8")
    runnable=(HERE/"evaluator/official_cli.py").read_text(encoding="utf-8")
    check(original.replace("    DEBUG = True\n","    DEBUG = False\n",1)==runnable,"Unexpected evaluator modification")
    actual_cov=load(directory/"coverage.json")
    check(actual_cov["actor_event_pairs"]==len(expected_actors) and actual_cov["subevents"]==len(cases),"Coverage totals mismatch")
    check(len(actual_cov["records"])==len(expected_actors),"Coverage record count mismatch")
    check({(r["guid"],r["subevent_id"],r["actor"]) for r in actual_cov["records"]}==expected_actors,"Coverage records mismatch")
    summary={"passed":True,"phase":phase,"articles":len({a["guid"] for a,e in cases}),"subevents":len(cases),
             "actor_event_pairs":len(expected_actors),"empty_actor_event_pairs":sum(not v for v in expected_b.values()),
             "independent_metrics":independent,"official_metrics":metrics,"selected_response_usage":dict(selected_usage),
             "all_attempt_usage":load(directory/"usage.json"),"median_case_seconds":statistics.median(latencies),
             "max_case_seconds":max(latencies),"checked_requests":len(cases),"checked_raw_responses":len(cases),
             "all_exported_events_and_candidates_match_inputs":True,"prompt_and_generation_parameters_identical":True,
             "task2a_projection_verified":True,"all_error_and_metric_exports_reconciled":True}
    save(directory/"independent_audit.json",summary)
    return summary


def main():
    smoke=audit_phase("smoke"); full=audit_phase("full")
    check(full["articles"]==177 and full["subevents"]==1526 and full["actor_event_pairs"]==3998,"Incomplete full DEV")
    # Inspect credentials only in memory; output is a boolean, never the secret.
    key=""
    for line in (ROOT/".env").read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("DEEPSEEK_API_KEY="):
            key=line.split("=",1)[1].strip().strip('"').strip("'")
    check(bool(key),"Unable to verify secret exclusion")
    paths=[p for p in HERE.rglob("*") if p.is_file() and "exports" not in p.relative_to(HERE).parts
           and "__pycache__" not in p.relative_to(HERE).parts and not p.name.endswith(".pyc")]
    for path in paths:
        check(key.encode() not in path.read_bytes(),"Secret detected in an experiment artifact")
    ignored=subprocess.run(["git","check-ignore","--",str(ROOT/".env")],cwd=ROOT,capture_output=True,text=True)
    check(ignored.returncode==0,"Credential file not Git-ignored")
    timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat()
    rows=[]
    for task in ("task2a","task2b"):
        m=full["official_metrics"][task]
        rows.append(f"| {task} | {m['micro_precision']*100:.2f} | {m['micro_recall']*100:.2f} | {m['micro_f1']*100:.2f} | {m['macro_f1']*100:.2f} |")
    usage=full["all_attempt_usage"]["all_response_attempts"]
    report="\n".join([
        "# Task 2 prompt baseline v1 — completed", "", f"Completed audit: {timestamp} (Asia/Tokyo).", "",
        "Frozen zero-shot prompt; target subevent plus full article background and official value definitions.",
        "Model request: deepseek-flash (documented as DeepSeek-V4.1-Flash-1017); thinking enabled; reasoning_effort=max.",
        "The response alias is recorded; remote weight identity is not independently verifiable.", "",
        "Full official DEV: 177 articles, 1,526 subevents, 3,998 candidate actor-event pairs. All completed and validated.",
        "Smoke: 5 subevents, separate calls, completed before the full pass. Prompt was not tuned using smoke scores.", "",
        "| Task | Micro precision % | Micro recall % | Micro-F1 % | Macro-F1 % |",
        "| --- | ---: | ---: | ---: | ---: |", *rows, "",
        f"Task-2b DRR: {full['official_metrics']['task2b']['direction_reverse_rate']*100:.4f}%.",
        f"Task-2b independent TP/FP/FN: {full['independent_metrics']['task2b']['tp']} / {full['independent_metrics']['task2b']['fp']} / {full['independent_metrics']['task2b']['fn']}.",
        f"Explicit empty actor-event outputs: {full['empty_actor_event_pairs']}.", "",
        f"API-reported full-run usage across returned attempts: {json.dumps(usage,ensure_ascii=False)}.",
        "Usage does not estimate unreturned requests or account billing; failed/timeout request charges cannot be inferred.", "",
        "Official evaluator is pinned to resource commit c27e19d97c24bd764c2ea520217dba9873fab455.",
        "Only its hardcoded DEBUG path override is disabled; metric and parser functions are unchanged.",
        "The official CLI exited successfully; independent counts reconcile scores and every exported FP/FN.", "",
        "This is one DEV baseline run. It is not official TEST, a replicated estimate, or evidence of superiority over Liu's different model/prompt settings.",
        "No DEV gold or explanations enter prompts; gold is read only after each phase's predictions are completed.", "",
        "Files: runs/full/pred_task2a.json, pred_task2b.json, metrics_official.json, independent_audit.json, coverage.json,",
        "per_label_metrics.csv, per_article_metrics.csv, errors.jsonl, usage.json, and original request/response caches.",
        "The export archive includes smoke/full results, prompt, code, frozen manifests and evaluator; it excludes credentials.", ""
    ])
    (HERE/"RESULTS.md").write_text(report,encoding="utf-8",newline="\n")
    (HERE/"STATUS.md").write_text("# Full experiment complete\n\n"+f"Audited at {timestamp}.\n\n"+
        "All 1,526 DEV subevents and 3,998 actor-event pairs are completed. Official CLI scoring and the independent audit passed.\n\n"+
        "See RESULTS.md and exports/task2_prompt_baseline_v1_all_results.zip. The interrupted_checkpoint directory is a historical progress snapshot.\n",encoding="utf-8",newline="\n")
    save(HERE/"runs/full/progress_reconciled.json",{"at":timestamp,"status":"complete","validated_events":1526,
         "pending_events":0,"actor_event_pairs":3998,"official_scoring_complete":True})
    save(HERE/"completion_audit.json",{"passed":True,"at":timestamp,"smoke_passed":True,"full_passed":True,
         "requirements":{"independent_folder":True,"prompt_and_code":True,"first_live_test":True,
         "full_dev_experiment":True,"deepseek_4_1_flash_max":True,"all_predictions_exported":True,
         "official_cli_scoring_passed":True,"all_cases_and_scores_independently_verified":True},
         "secrets_excluded":True,"env_git_ignored":True})
    exports=HERE/"exports";exports.mkdir(exist_ok=True)
    archive=exports/"task2_prompt_baseline_v1_all_results.zip"
    files=[p for p in HERE.rglob("*") if p.is_file() and not any(part in {"exports","__pycache__","preflight_frozen_before_line_ending_fix"} for part in p.relative_to(HERE).parts)
           and not p.name.endswith((".pyc",".tmp"))]
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for path in files:zipped.write(path,arcname=str(Path(HERE.name)/path.relative_to(HERE)))
    with zipfile.ZipFile(archive) as zipped:
        check(zipped.testzip() is None,"Archive integrity failure")
        check(not any(Path(name).name==".env" for name in zipped.namelist()),"Credential file in archive")
    save(exports/"archive_manifest.json",{"file":archive.name,"sha256":sha(archive),"bytes":archive.stat().st_size,
         "files":len(files),"archive_integrity_passed":True,"credentials_excluded":True})
    print(json.dumps({"passed":True,"full_metrics":full["official_metrics"],"export":str(archive),"files":len(files)},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
