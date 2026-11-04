"""Offline official evaluation of exactly the successfully completed subevents.

No credentials are read and no network/API request is made.
"""
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

import audit_results as audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/"subset_evaluation_completed"


def load(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def check(condition,message):
    if not condition:raise RuntimeError(message)


def table(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    source=load(ROOT/"dataset/dev/dev_event_base.json")
    all_cases=[(article,event) for article in source for event in article["subevents"]]
    frozen=load(HERE/"frozen/manifest.json")
    check(sha(ROOT/"dataset/dev/dev_event_base.json")==frozen["source_hashes"]["dataset\\dev\\dev_event_base.json"],"DEV input changed")
    prompt=(HERE/"frozen/system_prompt.txt").read_text(encoding="utf-8")
    hv=ROOT/"dataset/hv_categories"
    l1=load(hv/"human_value_level1_values.json");l2=load(hv/"human_value_level2_values.json")
    parents=load(hv/"level_1_to_level_2.json")["level_1_to_level_2"]
    mapping={l1[name]:l2[parent] for name,parent in parents.items()}
    l1_names={value:name for name,value in l1.items()};l2_names={value:name for name,value in l2.items()}
    run=HERE/"runs/full"
    selected=[];coverage=[];gold_b={};expected_b={};exports={task:{} for task in ("task2a","task2b")}
    latency=[];valid_usage=Counter();attempt_usage=Counter();finish_reasons=Counter();selected_models=Counter()
    observed_files=set()
    for index,(article,event) in enumerate(all_cases):
        case_dir=run/"cases"/f"{index:05d}"
        for path in case_dir.glob("attempt_*.response.json"):
            response=load(path);finish_reasons[response.get("choices",[{}])[0].get("finish_reason","missing")]+=1
            for name,value in response.get("usage",{}).items():
                if isinstance(value,int):attempt_usage[name]+=value
        result_path=case_dir/"result.json"
        if not result_path.exists():continue
        observed_files.add(result_path.resolve())
        result=load(result_path);request=load(case_dir/"request.json")
        check(request["model"]=="deepseek-flash" and request["thinking"]=={"type":"enabled"} and request["reasoning_effort"]=="max","Model settings differ")
        check(request["messages"][0]=={"role":"system","content":prompt},"Prompt differs")
        user=json.loads(request["messages"][1]["content"])
        actors={str(aid):name for record in article["actors"] for name,aid in record.items()}
        check(set(user)=={"TARGET_SUBEVENT","candidate_actors","article_background"},"Unexpected prompt input fields")
        check(user["TARGET_SUBEVENT"]=={"id":str(event["id"]),"text":event["subevent"]},"Wrong event input")
        check(user["article_background"]=={"title":article["title"],"content":article["content"]},"Wrong article input")
        check(user["candidate_actors"]==[{"actor":str(aid),"name":name} for record in article["actors"] for name,aid in record.items()],"Wrong actor candidates")
        canonical=json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        check(hashlib.sha256(canonical.encode()).hexdigest()==result["request_sha256"],"Request hash mismatch")
        response=load(case_dir/result["response_file"])
        check(response["choices"][0]["finish_reason"]=="stop","Selected response did not finish")
        parsed=json.loads(response["choices"][0]["message"]["content"])
        check(set(parsed)=={"actors"} and parsed["actors"]==result["actors"],"Raw/cache response mismatch")
        seen=set();labels=[]
        for actor in parsed["actors"]:
            aid=actor["actor"]
            check(isinstance(aid,str) and aid in actors and aid not in seen,"Invalid output actor")
            seen.add(aid);pairs=set()
            check(isinstance(actor["values"],list),"Invalid actor values")
            for value in actor["values"]:
                vid,direction=value["l1_value"],value["direction"]
                check(isinstance(vid,str) and vid in l1_names and isinstance(direction,str) and direction in {"0","1"},"Invalid value or direction")
                check((direction,vid) not in pairs,"Duplicate output label")
                pairs.add((direction,vid));labels.append({"actor":aid,"l1_value":vid,"direction":direction})
            key=(article["guid"],str(event["id"]),aid)
            expected_b[key]={f"{direction}:{value}" for direction,value in pairs}
            coverage.append({"guid":key[0],"subevent_id":key[1],"actor":aid,"actor_name":actors[aid],"predicted_label_count":len(pairs)})
        check(seen==set(actors),"Missing candidate actor output")
        labels.sort(key=lambda x:(x["actor"],int(x["l1_value"]),x["direction"]))
        check(labels==result["labels"],"Saved labels differ from response")
        coarse=[{"actor":aid,"l2_value":value} for aid,value in sorted({(v["actor"],mapping[v["l1_value"]]) for v in labels})]
        for task,values in (("task2a",coarse),("task2b",labels)):
            row=exports[task].setdefault(article["guid"],{"guid":article["guid"],"subevents_human_values":[]})
            row["subevents_human_values"].append({"subevent_id":str(event["id"]),"subevent_human_values":values})
        selected.append({"case_index":index,"guid":article["guid"],"subevent_id":str(event["id"]),"actor_ids":list(actors)})
        latency.append(result["seconds"]);selected_models[response.get("model","unknown")]+=1
        for name,value in response.get("usage",{}).items():
            if isinstance(value,int):valid_usage[name]+=value
    check(observed_files=={p.resolve() for p in (run/"cases").glob("*/result.json")},"Unmatched successful cache files")
    check(bool(selected),"No completed events")
    selected_keys={(r["guid"],r["subevent_id"]) for r in selected}
    save(OUT/"selected_cases.json",selected)
    save(OUT/"candidate_coverage.json",coverage)
    for task in exports:save(OUT/f"pred_{task}.json",list(exports[task].values()))
    check(audit.read_labels(list(exports["task2b"].values()))=={k:v for k,v in expected_b.items() if v},"Prediction export mismatch")
    # Gold is consulted only after the completion-based selection is fixed.
    gold_source=ROOT/"dataset/gold_labels/dev/dev_human_values.json"
    all_gold=load(gold_source);gold_subset=[];addressed=set();article_gold={}
    for article in all_gold:
        for value in article["article_human_values"]:
            article_gold.setdefault((article["guid"],str(value["actor"])),set()).add(f'{value["direction"]}:{value["l1_value"]}')
        events=[event for event in article["subevents_human_values"] if (article["guid"],str(event["subevent_id"])) in selected_keys]
        addressed.update((article["guid"],str(event["subevent_id"])) for event in events)
        if events:gold_subset.append({"guid":article["guid"],"subevents_human_values":events})
    save(OUT/"gold_subset.json",gold_subset)
    original=HERE/"evaluator/official_original.py";cli=HERE/"evaluator/official_cli.py"
    check(sha(original)=="4d325a5d38277c9dfc7a141088b6724c7c0d6c03dcc8f85b90531c6e69157b31","Pinned official evaluator mismatch")
    check(original.read_text(encoding="utf-8").replace("    DEBUG = True\n","    DEBUG = False\n",1)==cli.read_text(encoding="utf-8"),"Official metric code modified")
    command=[sys.executable,"-X","utf8",str(cli),"--gold_task2",str(OUT/"gold_subset.json"),
             "--pred_task2a",str(OUT/"pred_task2a.json"),"--pred_task2b",str(OUT/"pred_task2b.json"),"--out",str(OUT/"metrics_official.json")]
    result=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",check=True)
    (OUT/"official_stdout.json").write_text(result.stdout,encoding="utf-8")
    official=load(OUT/"metrics_official.json");check(json.loads(result.stdout)==official,"Official output disagreement")
    independent={};per_label=[];per_article=[]
    for task,coarse,universe in (("task2a",True,[str(v) for v in range(20)]),("task2b",False,[f"{d}:{v}" for d in ("0","1") for v in range(54)])):
        gold=audit.read_labels(gold_subset,coarse);pred=audit.read_labels(list(exports[task].values()),coarse)
        check(set(gold).issubset(expected_b),"Gold actor outside input candidate set")
        metrics,counts=audit.counts_and_metrics(gold,pred)
        for field in ("micro_precision","micro_recall","micro_f1","macro_f1"):
            check(abs(metrics[field]-official[task][field])<1e-12,"Independent scores disagree")
        independent[task]=metrics
        for label in universe:
            tp,fp,fn=counts.get(label,[0,0,0]);vid=label if coarse else label.split(":")[1]
            per_label.append({"task":task,"label":label,"value_name":l2_names[vid] if coarse else l1_names[vid],
                              "gold_support":tp+fn,"predicted":tp+fp,"tp":tp,"fp":fp,"fn":fn,
                              "precision":tp/(tp+fp) if tp+fp else 0,"recall":tp/(tp+fn) if tp+fn else 0,
                              "f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,"included_in_macro":tp+fn>0})
        for guid in exports[task]:
            m,_=audit.counts_and_metrics({k:v for k,v in gold.items() if k[0]==guid},{k:v for k,v in pred.items() if k[0]==guid})
            per_article.append({"task":task,"guid":guid,**m})
    gold_b=audit.read_labels(gold_subset);pred_b=audit.read_labels(list(exports["task2b"].values()))
    reversals=denominator=ambiguous=0
    for key,values in gold_b.items():
        for vid in {v.split(":")[1] for v in values}:
            directions={v.split(":")[0] for v in values if v.split(":")[1]==vid}
            if len(directions)==2:ambiguous+=1
            else:
                denominator+=1;opposite="0" if "1" in directions else "1"
                reversals+=f"{opposite}:{vid}" in pred_b.get(key,set())
    check(reversals==official["task2b"]["direction_reverse_count"] and denominator==official["task2b"]["direction_reverse_denom_gold_excl"],"DRR counts mismatch")
    independent["drr"]={"reversals":reversals,"denominator":denominator,"ambiguous":ambiguous}
    errors=[];fp_types=Counter();actor_rows=[]
    for article,event in all_cases:
        if (article["guid"],str(event["id"])) not in selected_keys:continue
        for record in article["actors"]:
            for name,aid in record.items():
                key=(article["guid"],str(event["id"]),str(aid));g=gold_b.get(key,set());p=pred_b.get(key,set())
                fp=p-g;fn=g-p;ap=article_gold.get((key[0],key[2]),set())
                fp_types["article_gold_absent_fp"]+=len(fp-ap);fp_types["article_gold_present_event_gold_absent_fp"]+=len(fp&ap)
                actor_rows.append({"guid":key[0],"subevent_id":key[1],"actor":key[2],"gold":";".join(sorted(g)),"predicted":";".join(sorted(p)),"tp":len(g&p),"fp":len(fp),"fn":len(fn)})
                if fp or fn:errors.append({"guid":key[0],"subevent_id":key[1],"actor":key[2],"actor_name":name,
                                          "subevent":event["subevent"],"gold":sorted(g),"predicted":sorted(p),
                                          "false_positives":sorted(fp),"false_negatives":sorted(fn)})
    check(sum(r["fp"] for r in actor_rows)==independent["task2b"]["fp"] and sum(r["fn"] for r in actor_rows)==independent["task2b"]["fn"],"Actor error totals mismatch")
    table(OUT/"per_label_metrics.csv",per_label);table(OUT/"per_article_metrics.csv",per_article);table(OUT/"per_actor_event_metrics.csv",actor_rows)
    with (OUT/"errors.jsonl").open("w",encoding="utf-8") as stream:
        for row in errors:stream.write(json.dumps(row,ensure_ascii=False)+"\n")
    selected_count=Counter(r["guid"] for r in selected)
    fully_completed=sum(selected_count[a["guid"]]==len(a["subevents"]) and selected_count[a["guid"]]>0 for a in source)
    gold_empty=[r for r in actor_rows if not r["gold"]]
    top_fp=sorted([r for r in per_label if r["task"]=="task2b"],key=lambda r:r["fp"],reverse=True)[:8]
    manifest={"scored_at":datetime.now(timezone(timedelta(hours=9))).isoformat(),"offline_only":True,"new_model_calls":0,
              "subset_events":len(selected),"total_dev_events":len(all_cases),"fraction_of_dev_events":len(selected)/len(all_cases),
              "articles_with_completed_events":len(selected_count),"fully_completed_articles":fully_completed,"candidate_actor_event_pairs":len(coverage),
              "explicit_empty_actor_event_predictions":sum(r["predicted_label_count"]==0 for r in coverage),
              "gold_rows_missing_for_selected_events":sorted(selected_keys-addressed),"selected_min_index":min(r["case_index"] for r in selected),
              "selected_max_index":max(r["case_index"] for r in selected),"missing_within_reached_prefix":max(r["case_index"] for r in selected)+1-len(selected),
              "selection":"All valid cached full-run results before user stopped the experiment; not a random sample",
              "selection_caveat":"Concurrent completion, output truncation and rate limits leave holes; slow/failed events may be underrepresented",
              "not_full_dev_score":True,"not_official_test_score":True,"model_alias_counts":dict(selected_models),
              "valid_response_usage":dict(valid_usage),"all_full_run_returned_attempt_usage":dict(attempt_usage),"returned_attempt_finish_reasons":dict(finish_reasons),
              "median_valid_response_seconds":statistics.median(latency),"official_cli_returncode":result.returncode,
              "official_command":command,"official_provenance":load(HERE/"evaluator/provenance.json"),
              "source_gold_sha256":sha(gold_source),"selected_cases_sha256":sha(OUT/"selected_cases.json"),
              "prediction_sha256":{task:sha(OUT/f"pred_{task}.json") for task in exports},
              "independent_verification_passed":True,"independent_counts_and_scores":independent,"gold_based_fp_decomposition":dict(fp_types),
              "gold_empty_actor_event_pairs":len(gold_empty),"gold_empty_pairs_predicted_nonempty":sum(bool(r["predicted"]) for r in gold_empty),
              "false_positives_on_gold_empty_pairs":sum(r["fp"] for r in gold_empty),"top_false_positive_directed_labels":top_fp}
    save(OUT/"evaluation_manifest.json",manifest)
    rows=[]
    for task in ("task2a","task2b"):
        m=official[task]
        rows.append(f"| {task} | {m['micro_precision']*100:.2f} | {m['micro_recall']*100:.2f} | {m['micro_f1']*100:.2f} | {m['macro_f1']*100:.2f} |")
    text="\n".join(["# 已完成子集的官方评分（全量运行已由用户中止）","",f"评分时间：{manifest['scored_at']}。本次完全离线，新增模型调用为 0。","",
        f"范围：{len(selected)}/{len(all_cases)} 个子事件（{len(selected)/len(all_cases)*100:.2f}%），涉及 {len(selected_count)} 篇文章、{len(coverage)} 个主体—子事件组合。其中 {fully_completed} 篇文章的全部子事件已完成。","",
        "模型请求为 deepseek-flash，thinking enabled，reasoning_effort=max。冻结的零样本 prompt 使用当前子事件、全文背景及官方价值定义。","",
        "| 任务 | Micro精确率 % | Micro召回率 % | Micro-F1 % | Macro-F1 % |","| --- | ---: | ---: | ---: | ---: |",*rows,"",
        f"Task-2b DRR：{official['task2b']['direction_reverse_rate']*100:.4f}%；方向反转 {reversals}/{denominator}。",
        f"Task-2b TP / FP / FN：{independent['task2b']['tp']} / {independent['task2b']['fp']} / {independent['task2b']['fn']}。","",
        f"本次结果的主要问题是过度预测：输出了 {official['task2b']['support_pred_labels']:,} 个有向标签，而金标为 {official['task2b']['support_gold_labels']:,} 个；精确率为 {official['task2b']['micro_precision']*100:.2f}%，召回率为 {official['task2b']['micro_recall']*100:.2f}%。",
        f"{len(gold_empty)} 个主体—事件组合的金标为空，其中 {sum(bool(r['predicted']) for r in gold_empty)} 个仍被预测为非空，贡献 {sum(r['fp'] for r in gold_empty)} 个误报。",
        "误报最多的前三个有向类别为："+"；".join(f"{r['label']} {r['value_name']}（TP={r['tp']}, FP={r['fp']}, FN={r['fn']}）" for r in top_fp[:3])+"。",
        "这些统计支持优先检查标签纳入标准和事件归属；没有同子集、同 prompt 的非思考对照，因此不能据此把问题单独归因于 max 模式。","",
        "仅保留成功完成的 guid/subevent_id 对应金标，并用官方评分器命令行运行。未运行的子事件不作为空预测或漏报计入本次评分。",
        "评分器来自固定官方 commit，仅关闭硬编码 DEBUG 路径覆盖；指标和 parser 未改动。独立集合计数复核 Micro/Macro-F1 与 DRR 计数通过。","",
        "这批样本由并发完成状态决定，并非随机三分之一；输出截断、限流和耗时可能造成选择偏差。Macro-F1 只平均本子集中有金标支持的标签。",
        "因此这是约三分之一 DEV 的探索性结果，不能直接与完整 DEV 的其他系统分数相减，也不能当作全量或官方 TEST 成绩。","",
        f"按金标分解 FP：同主体文章金标也没有该有向标签 {fp_types['article_gold_absent_fp']}；文章有该标签、当前事件无该标签 {fp_types['article_gold_present_event_gold_absent_fp']}。",
        "上述为标签集合对照，不等价于逐例人工确认的语义错误原因。","",
        f"全部已返回 full-run 尝试的 API 用量：{json.dumps(dict(attempt_usage),ensure_ascii=False)}。包含失败的截断响应，不代表本次离线评分新增费用。","",
        "结果文件：metrics_official.json、gold_subset.json、pred_task2a.json、pred_task2b.json、evaluation_manifest.json、逐标签/文章/主体事件 CSV 及 errors.jsonl。",""
    ])
    (OUT/"RESULTS_zh.md").write_text(text,encoding="utf-8",newline="\n")
    archive=HERE/"exports/completed_subset_official_scores.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in OUT.iterdir():
            if path.is_file():zipped.write(path,arcname=str(Path(OUT.name)/path.name))
        for path in (Path(__file__),original,cli,HERE/"evaluator/provenance.json",HERE/"frozen/system_prompt.txt"):
            zipped.write(path,arcname=str(Path("reproducibility")/path.relative_to(HERE)))
    with zipfile.ZipFile(archive) as zipped:check(zipped.testzip() is None,"Archive integrity failure")
    print(json.dumps({"subset_events":len(selected),"articles":len(selected_count),"actor_event_pairs":len(coverage),"official_metrics":official,
                      "independent_counts":independent,"gold_based_fp_decomposition":dict(fp_types),"report":str(OUT/"RESULTS_zh.md"),"archive":str(archive)},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
