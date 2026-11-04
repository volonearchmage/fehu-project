"""Frozen zero-shot FEHU Task-2 baseline: DeepSeek 4.1 Flash, max thinking."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "dataset"
OFFICIAL_COMMIT = "c27e19d97c24bd764c2ea520217dba9873fab455"
OFFICIAL_URL = f"https://raw.githubusercontent.com/ii-research/NTCIR-19-FEHU-resource/{OFFICIAL_COMMIT}/evaluation.py"
PROTOCOL = {
    "name": "task2_prompt_baseline_v1", "model": "deepseek-flash",
    "documented_model_version": "DeepSeek-V4.1-Flash-1017",
    "thinking": {"type": "enabled"}, "reasoning_effort": "max",
    "max_tokens": 32768, "response_format": {"type": "json_object"}, "stream": False,
    "few_shot_examples": 0, "input": "target subevent + full article + all candidate actors",
    "label_cap": None, "postprocessing": "exact ID validation, deduplication forbidden, fixed L1-to-L2 projection",
    "smoke_cases": 5, "max_attempts": 3, "timeout_seconds": 240,
    "selection": "published DEV input order; no gold-based selection",
    "official_evaluator_commit": OFFICIAL_COMMIT,
}
STOP = threading.Event()


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def settings():
    names = ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL")
    result = {name: os.environ.get(name, "") for name in names}
    for raw in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.removeprefix("export ").split("=", 1)
            if name.strip() in names:
                result[name.strip()] = value.strip().strip('"').strip("'")
    key = result["DEEPSEEK_API_KEY"]
    if not key or key in {"sk-...", "YOUR_KEY_HERE"}:
        raise RuntimeError("Missing DeepSeek key in the project .env")
    base = (result["DEEPSEEK_BASE_URL"] or "https://api.deepseek.com").rstrip("/")
    url = urlsplit(base)
    if url.scheme != "https" or url.netloc != "api.deepseek.com" or url.path not in {"", "/v1"} or url.query or url.fragment:
        raise RuntimeError("Expected the official DeepSeek HTTPS base URL")
    return key, base


def cases_from_input(articles):
    cases, seen = [], set()
    for article in articles:
        guid = str(article["guid"])
        actors = [{"actor": str(aid), "name": name}
                  for record in article["actors"] for name, aid in record.items()]
        if len(actors) != len({a["actor"] for a in actors}):
            raise ValueError("Duplicate source actor ID")
        for event in article["subevents"]:
            key = (guid, str(event["id"]))
            if key in seen:
                raise ValueError("Duplicate source event ID")
            seen.add(key)
            cases.append({"case_index": len(cases), "guid": guid, "subevent_id": key[1],
                          "subevent": event["subevent"], "candidate_actors": actors,
                          "article_background": {"title": article["title"], "content": article["content"]}})
    return cases


def payload_for(case, prompt):
    user = {key: case[key] for key in ("subevent_id", "subevent", "candidate_actors", "article_background")}
    user = {"TARGET_SUBEVENT": {"id": user["subevent_id"], "text": user["subevent"]},
            "candidate_actors": user["candidate_actors"], "article_background": user["article_background"]}
    return {key: PROTOCOL[key] for key in ("model", "thinking", "reasoning_effort", "max_tokens", "response_format", "stream")} | {
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": canonical(user)}]}


def validate(content, case):
    data = json.loads(content)
    if not isinstance(data, dict) or set(data) != {"actors"} or not isinstance(data["actors"], list):
        raise ValueError("Response must contain only an actors list")
    expected = {a["actor"] for a in case["candidate_actors"]}
    seen, labels = set(), []
    for actor in data["actors"]:
        if not isinstance(actor, dict) or set(actor) != {"actor", "values"}:
            raise ValueError("Invalid actor schema")
        aid = actor["actor"]
        if not isinstance(aid, str) or aid not in expected or aid in seen:
            raise ValueError("Unknown, duplicate or non-string actor ID")
        seen.add(aid)
        if not isinstance(actor["values"], list):
            raise ValueError("values must be a list")
        pairs = set()
        for item in actor["values"]:
            if not isinstance(item, dict) or set(item) != {"l1_value", "direction"}:
                raise ValueError("Invalid value schema")
            value, direction = item["l1_value"], item["direction"]
            if not isinstance(value, str) or value not in {str(i) for i in range(54)}:
                raise ValueError("Invalid Level-1 ID")
            if not isinstance(direction, str) or direction not in {"0", "1"}:
                raise ValueError("Invalid direction")
            if (value, direction) in pairs:
                raise ValueError("Duplicate directed value")
            pairs.add((value, direction))
            labels.append({"actor": aid, "l1_value": value, "direction": direction})
    if seen != expected:
        raise ValueError("Missing candidate actor; not a valid empty output")
    return data["actors"], sorted(labels, key=lambda x: (x["actor"], int(x["l1_value"]), x["direction"]))


def prepare():
    frozen = HERE / "frozen"
    if (frozen / "manifest.json").exists():
        check_frozen()
        print("Existing frozen protocol verified; no prompt changes")
        return
    frozen.mkdir(parents=True, exist_ok=True)
    taxonomy_path = DATA / "hv_categories/human_value_taxonomy.json"
    ids = read(DATA / "hv_categories/human_value_level1_values.json")
    definitions = {value["level-1"]: value for value in read(taxonomy_path)["values"]}
    lines = []
    for name, vid in sorted(ids.items(), key=lambda item: int(item[1])):
        details = definitions[name]
        lines.append(f'{vid}: {name} [Level-2: {details["level-2"]}]. ' + "; ".join(details["descriptions"]))
    prompt = (HERE / "prompt_template.txt").read_text(encoding="utf-8").replace("{{TAXONOMY}}", "\n".join(lines))
    (frozen / "system_prompt.txt").write_text(prompt, encoding="utf-8", newline="\n")
    shutil.copyfile(__file__, frozen / "code_snapshot.py")
    sources = [DATA / "dev/dev_event_base.json", taxonomy_path,
               DATA / "hv_categories/human_value_level1_values.json",
               DATA / "hv_categories/human_value_level2_values.json",
               DATA / "hv_categories/level_1_to_level_2.json", DATA / "hv_categories/direction_mapping.json"]
    source_hashes = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sources}
    cases = cases_from_input(read(sources[0]))
    write(frozen / "case_manifest.json", [{"case_index": c["case_index"], "guid": c["guid"],
          "subevent_id": c["subevent_id"], "actor_ids": [a["actor"] for a in c["candidate_actors"]],
          "request_sha256": digest(canonical(payload_for(c, prompt)).encode())} for c in cases])
    evaluator = HERE / "evaluator"
    evaluator.mkdir(exist_ok=True)
    raw = build_opener(NoRedirect()).open(OFFICIAL_URL, timeout=30).read()
    expected_hash = "4d325a5d38277c9dfc7a141088b6724c7c0d6c03dcc8f85b90531c6e69157b31"
    if digest(raw) != expected_hash:
        raise RuntimeError("Pinned official evaluator hash mismatch")
    (evaluator / "official_original.py").write_bytes(raw)
    text = raw.decode("utf-8")
    if text.count("    DEBUG = True\n") != 1:
        raise RuntimeError("Unexpected official CLI debug switch")
    patched = text.replace("    DEBUG = True\n", "    DEBUG = False\n", 1)
    (evaluator / "official_cli.py").write_text(patched, encoding="utf-8", newline="\n")
    # This is the only change to the runnable official evaluator.
    write(evaluator / "provenance.json", {"source_url": OFFICIAL_URL, "commit": OFFICIAL_COMMIT,
          "original_sha256": digest(raw), "cli_sha256": digest((evaluator / "official_cli.py").read_bytes()),
          "only_change": "DEBUG = True -> DEBUG = False; all metric/parser code unchanged"})
    write(frozen / "manifest.json", {"created_at": now(), "protocol": PROTOCOL,
          "system_prompt_sha256": digest(prompt.encode()), "source_hashes": source_hashes,
          "code_sha256": digest(Path(__file__).read_bytes()),
          "case_manifest_sha256": digest((frozen / "case_manifest.json").read_bytes()),
          "articles": len({c["guid"] for c in cases}), "subevents": len(cases),
          "actor_event_pairs": sum(len(c["candidate_actors"]) for c in cases),
          "python": platform.python_version(), "platform": platform.platform()})
    print(f"Frozen {len(cases)} DEV subevents; zero-shot, full context, max thinking")


def check_frozen():
    frozen = HERE / "frozen"
    manifest = read(frozen / "manifest.json")
    if manifest["protocol"] != PROTOCOL or manifest["code_sha256"] != digest(Path(__file__).read_bytes()):
        raise RuntimeError("Frozen code or protocol changed; do not mix experiments")
    if manifest["system_prompt_sha256"] != digest((frozen / "system_prompt.txt").read_bytes()):
        raise RuntimeError("Frozen prompt changed")
    if manifest["case_manifest_sha256"] != digest((frozen / "case_manifest.json").read_bytes()):
        raise RuntimeError("Frozen case manifest changed")
    for path, expected in manifest["source_hashes"].items():
        if digest((ROOT / path).read_bytes()) != expected:
            raise RuntimeError("Frozen source data changed")
    provenance = read(HERE / "evaluator/provenance.json")
    for name, field in (("official_original.py", "original_sha256"), ("official_cli.py", "cli_sha256")):
        if digest((HERE / "evaluator" / name).read_bytes()) != provenance[field]:
            raise RuntimeError("Official evaluator changed")
    return manifest


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Unexpected API redirect")


class FatalAPIError(RuntimeError):
    pass


def run_case(case, prompt, run_dir, key, base):
    directory = run_dir / "cases" / f'{case["case_index"]:05d}'
    directory.mkdir(parents=True, exist_ok=True)
    payload = payload_for(case, prompt)
    request_hash = digest(canonical(payload).encode())
    result_path = directory / "result.json"
    if result_path.exists():
        result = read(result_path)
        if result["request_sha256"] != request_hash:
            raise RuntimeError("Cached request hash mismatch")
        actors, labels = validate(read(directory / result["response_file"])["choices"][0]["message"]["content"], case)
        if labels != result["labels"] or actors != result["actors"]:
            raise RuntimeError("Cached labels differ from raw response")
        return "cached"
    write(directory / "request.json", payload)
    existing = [int(p.name.split("_")[1].split(".")[0]) for p in directory.glob("attempt_*.response.json")]
    existing += [int(p.name.split("_")[1].split(".")[0]) for p in directory.glob("attempt_*.error.json")]
    first = max(existing, default=0) + 1
    last_error = "No attempt made"
    for attempt in range(first, first + PROTOCOL["max_attempts"]):
        if STOP.is_set():
            return "cancelled"
        start = time.monotonic()
        response_file = f"attempt_{attempt:02d}.response.json"
        try:
            request = Request(base + "/chat/completions", data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
            with build_opener(NoRedirect()).open(request, timeout=PROTOCOL["timeout_seconds"]) as stream:
                response = json.loads(stream.read().decode("utf-8").replace(key, "[REDACTED]"))
            write(directory / response_file, response)
            choices = response.get("choices", [])
            if not choices or choices[0].get("finish_reason") != "stop":
                raise ValueError("Response missing or truncated")
            content = choices[0].get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty model content")
            actors, labels = validate(content, case)
            write(result_path, {"case_index": case["case_index"], "guid": case["guid"],
                  "subevent_id": case["subevent_id"], "request_sha256": request_hash,
                  "response_file": response_file, "actors": actors, "labels": labels,
                  "returned_model": response.get("model"), "usage": response.get("usage", {}),
                  "seconds": time.monotonic() - start, "completed_at": now()})
            return "valid"
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            write(directory / f"attempt_{attempt:02d}.error.json", {"type": "HTTPError", "status": exc.code, "at": now()})
            if exc.code in {400, 401, 402, 403, 404, 422}:
                STOP.set()
                raise FatalAPIError(last_error) from None
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
            last_error = f"{type(exc).__name__}: {str(exc)}".replace(key, "[REDACTED]")
            write(directory / f"attempt_{attempt:02d}.error.json", {"error": last_error, "at": now()})
        if attempt < first + PROTOCOL["max_attempts"] - 1:
            STOP.wait(min(2 ** (attempt - first + 1), 30))
    write(directory / "failed.json", {"last_error": last_error, "at": now()})
    return "failed"


def run(phase, workers):
    frozen = check_frozen()
    key, base = settings()
    cases = cases_from_input(read(DATA / "dev/dev_event_base.json"))
    if phase == "smoke":
        cases = cases[:PROTOCOL["smoke_cases"]]
    directory = HERE / "runs" / phase
    directory.mkdir(parents=True, exist_ok=True)
    prompt = (HERE / "frozen/system_prompt.txt").read_text(encoding="utf-8")
    config_path = directory / "run_config.json"
    if not config_path.exists():
        write(config_path, {"started_at": now(), "phase": phase, "status": "running",
              "protocol": PROTOCOL, "workers": workers, "events": len(cases),
              "actor_event_pairs": sum(len(c["candidate_actors"]) for c in cases),
              "frozen_manifest_sha256": digest((HERE / "frozen/manifest.json").read_bytes()),
              "base_url": base, "smoke_reused_in_full": False})
    else:
        config = read(config_path)
        if config["frozen_manifest_sha256"] != digest((HERE / "frozen/manifest.json").read_bytes()):
            raise RuntimeError("Run manifest does not match frozen experiment")
    start, counts = time.monotonic(), Counter()
    print(f"START {phase}: {len(cases)} events; workers={workers}; thinking=max", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_case, case, prompt, directory, key, base): case["case_index"] for case in cases}
        while futures:
            done, _ = wait(futures, timeout=20, return_when=FIRST_COMPLETED)
            for future in done:
                futures.pop(future)
                try:
                    counts[future.result()] += 1
                except Exception as exc:
                    STOP.set()
                    counts["fatal"] += 1
                    print(f"STOP {type(exc).__name__}: {str(exc).replace(key, '[REDACTED]')}", flush=True)
            write(directory / "progress.json", {"at": now(), "completed": sum(counts.values()),
                  "total": len(cases), "counts": dict(counts), "elapsed_seconds": time.monotonic()-start})
            if not done or sum(counts.values()) % 25 == 0 or not futures:
                print(f"PROGRESS {sum(counts.values())}/{len(cases)} {dict(counts)} elapsed={time.monotonic()-start:.1f}s", flush=True)
            if STOP.is_set():
                for future in futures:
                    future.cancel()
    config = read(config_path)
    valid = sum((directory / "cases" / f'{c["case_index"]:05d}' / "result.json").exists() for c in cases)
    config.update(status="inference_complete" if valid == len(cases) else "incomplete", finished_at=now(), valid_events=valid)
    write(config_path, config)
    if valid != len(cases):
        raise RuntimeError(f"Only {valid}/{len(cases)} valid events; refusing partial scoring")
    finalize(phase)


def label_sets(rows, task):
    result = {}
    for article in rows:
        for event in article["subevents_human_values"]:
            for value in event["subevent_human_values"]:
                key = (str(article["guid"]), str(event["subevent_id"]), str(value["actor"]))
                label = str(value["l2_value"]) if task == "task2a" else str(value["direction"]) + ":" + str(value["l1_value"])
                result.setdefault(key, set()).add(label)
    return result


def independent_metrics(gold, pred):
    tp = fp = fn = 0
    classes = Counter()
    for key in set(gold) | set(pred):
        g, p = gold.get(key, set()), pred.get(key, set())
        tp += len(g & p); fp += len(p - g); fn += len(g - p)
        for label in g | p:
            classes[(label, "tp")] += label in g and label in p
            classes[(label, "fp")] += label in p and label not in g
            classes[(label, "fn")] += label in g and label not in p
    supported = {label for labels in gold.values() for label in labels}
    macro = sum(2*classes[(label,"tp")]/(2*classes[(label,"tp")]+classes[(label,"fp")]+classes[(label,"fn")])
                for label in supported) / len(supported) if supported else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "micro_f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0,
            "micro_precision": tp/(tp+fp) if tp+fp else 0.0,
            "micro_recall": tp/(tp+fn) if tp+fn else 0.0, "macro_f1": macro}, classes


def finalize(phase):
    check_frozen()
    directory = HERE / "runs" / phase
    cases = cases_from_input(read(DATA / "dev/dev_event_base.json"))
    if phase == "smoke":
        cases = cases[:PROTOCOL["smoke_cases"]]
    ids = read(DATA / "hv_categories/human_value_level1_values.json")
    l2 = read(DATA / "hv_categories/human_value_level2_values.json")
    parents = read(DATA / "hv_categories/level_1_to_level_2.json")["level_1_to_level_2"]
    mapping = {ids[name]: l2[parent] for name, parent in parents.items()}
    prompt = (HERE / "frozen/system_prompt.txt").read_text(encoding="utf-8")
    exports, explicit_coverage = {"task2a": {}, "task2b": {}}, []
    selected_responses, attempt_usage, model_counts, total_seconds = [], Counter(), Counter(), 0
    for case in cases:
        case_dir = directory / "cases" / f'{case["case_index"]:05d}'
        result = read(case_dir / "result.json")
        payload = payload_for(case, prompt)
        if read(case_dir / "request.json") != payload or result["request_sha256"] != digest(canonical(payload).encode()):
            raise RuntimeError("Request mismatch during finalization")
        response = read(case_dir / result["response_file"])
        if response["choices"][0]["finish_reason"] != "stop":
            raise RuntimeError("Selected response is truncated")
        actors, labels = validate(response["choices"][0]["message"]["content"], case)
        if labels != result["labels"] or actors != result["actors"]:
            raise RuntimeError("Saved prediction not supported by response")
        explicit_coverage.extend({"guid": case["guid"], "subevent_id": case["subevent_id"],
                                 "actor": actor["actor"], "label_count": len(actor["values"])} for actor in actors)
        coarse = sorted({(v["actor"], mapping[v["l1_value"]]) for v in labels})
        for task, values in (("task2b", labels), ("task2a", [{"actor": a, "l2_value": value} for a, value in coarse])):
            row = exports[task].setdefault(case["guid"], {"guid": case["guid"], "subevents_human_values": []})
            row["subevents_human_values"].append({"subevent_id": case["subevent_id"], "subevent_human_values": values})
        selected_responses.append({"guid": case["guid"], "subevent_id": case["subevent_id"],
                                  "response_file": str((case_dir / result["response_file"]).relative_to(directory)),
                                  "model": response.get("model"), "usage": response.get("usage", {})})
        for path in case_dir.glob("attempt_*.response.json"):
            attempt = read(path)
            for name, value in attempt.get("usage", {}).items():
                if isinstance(value, int):
                    attempt_usage[name] += value
            model_counts[attempt.get("model", "unknown")] += 1
        total_seconds += result["seconds"]
    for task in exports:
        write(directory / f"pred_{task}.json", list(exports[task].values()))
    write(directory / "coverage.json", {"complete": True, "articles": len(exports["task2b"]),
          "subevents": len(cases), "actor_event_pairs": len(explicit_coverage),
          "empty_actor_event_pairs": sum(v["label_count"] == 0 for v in explicit_coverage), "records": explicit_coverage})
    write(directory / "response_index.json", selected_responses)
    write(directory / "usage.json", {"all_response_attempts": dict(attempt_usage), "returned_model_counts": dict(model_counts),
          "response_attempts": sum(model_counts.values()), "successful_case_latency_sum_seconds": total_seconds})
    # Evaluation data is first read after all selected predictions have been validated.
    gold_source = DATA / "gold_labels/dev/dev_human_values.json"
    all_gold = read(gold_source)
    selected = {(c["guid"], c["subevent_id"]) for c in cases}
    if phase == "full":
        gold_path = gold_source
    else:
        gold_subset = [{"guid": row["guid"], "subevents_human_values": [event for event in row["subevents_human_values"]
                       if (str(row["guid"]), str(event["subevent_id"])) in selected]} for row in all_gold]
        gold_subset = [row for row in gold_subset if row["subevents_human_values"]]
        gold_path = directory / "gold_subset.json"
        write(gold_path, gold_subset)
    command = [sys.executable, "-X", "utf8", str(HERE / "evaluator/official_cli.py"),
               "--gold_task2", str(gold_path), "--pred_task2a", str(directory / "pred_task2a.json"),
               "--pred_task2b", str(directory / "pred_task2b.json"), "--out", str(directory / "metrics_official.json")]
    scored = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True)
    (directory / "official_stdout.json").write_text(scored.stdout, encoding="utf-8")
    write(directory / "scoring_command.json", {"command": command, "returncode": scored.returncode,
          "gold_sha256": digest(gold_source.read_bytes()), "official_evaluator": read(HERE / "evaluator/provenance.json")})
    verify_and_export(directory, cases, gold_path)
    config = read(directory / "run_config.json")
    config.update(status="complete", scored_at=now())
    write(directory / "run_config.json", config)
    print(json.dumps(read(directory / "metrics_official.json"), ensure_ascii=False, indent=2), flush=True)
    print(f"COMPLETE {phase}: official evaluator passed; all {len(cases)} events covered", flush=True)


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def verify_and_export(directory, cases, gold_path):
    official = read(directory / "metrics_official.json")
    gold_rows = read(gold_path)
    check, per_label = {}, []
    for task, universe in (("task2a", [str(i) for i in range(20)]),
                            ("task2b", [f"{d}:{i}" for d in ("0", "1") for i in range(54)])):
        gold = label_sets(gold_rows, task)
        pred = label_sets(read(directory / f"pred_{task}.json"), task)
        metric, counts = independent_metrics(gold, pred)
        for name in ("micro_f1", "micro_precision", "micro_recall", "macro_f1"):
            if abs(metric[name]-official[task][name]) > 1e-12:
                raise RuntimeError(f"Independent {task} {name} differs from official score")
        check[task] = metric
        for label in universe:
            tp, fp, fn = (counts[(label, name)] for name in ("tp", "fp", "fn"))
            per_label.append({"task": task, "label": label, "gold_support": tp+fn, "predicted": tp+fp,
                              "tp": tp, "fp": fp, "fn": fn, "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
                              "included_in_official_macro": tp+fn > 0})
    gold, pred = label_sets(gold_rows, "task2b"), label_sets(read(directory / "pred_task2b.json"), "task2b")
    reversals = denominator = ambiguous = 0
    for key, labels in gold.items():
        by_value = {}
        for label in labels:
            direction, value = label.split(":")
            by_value.setdefault(value, set()).add(direction)
        for value, directions in by_value.items():
            if len(directions) == 2:
                ambiguous += 1
            else:
                denominator += 1
                opposite = "0" if next(iter(directions)) == "1" else "1"
                reversals += f"{opposite}:{value}" in pred.get(key, set())
    drr = reversals/denominator if denominator else 0
    if abs(drr-official["task2b"]["direction_reverse_rate"]) > 1e-12:
        raise RuntimeError("Independent DRR differs from official score")
    check["drr"] = {"rate": drr, "reversals": reversals, "denominator": denominator, "ambiguous": ambiguous}
    per_article = []
    for guid in dict.fromkeys(c["guid"] for c in cases):
        metric, _ = independent_metrics({k:v for k,v in gold.items() if k[0]==guid}, {k:v for k,v in pred.items() if k[0]==guid})
        per_article.append({"guid": guid, **metric})
    errors = []
    for case in cases:
        for actor in case["candidate_actors"]:
            key = (case["guid"], case["subevent_id"], actor["actor"])
            g, p = gold.get(key,set()), pred.get(key,set())
            if g != p:
                errors.append({"guid": key[0], "subevent_id": key[1], "actor": key[2], "actor_name": actor["name"],
                               "subevent": case["subevent"], "gold": sorted(g), "predicted": sorted(p),
                               "false_positives": sorted(p-g), "false_negatives": sorted(g-p)})
    write_csv(directory / "per_label_metrics.csv", per_label, list(per_label[0]))
    write_csv(directory / "per_article_metrics.csv", per_article, list(per_article[0]))
    with (directory / "errors.jsonl").open("w", encoding="utf-8") as stream:
        for error in errors:
            stream.write(json.dumps(error,ensure_ascii=False)+"\n")
    write(directory / "verification.json", {"passed": True, "independent_scores": check,
          "official_cli_returncode": 0, "all_cases_validated_from_responses": True,
          "prediction_sha256": {task:digest((directory/f"pred_{task}.json").read_bytes()) for task in ("task2a","task2b")},
          "metrics_sha256": digest((directory/"metrics_official.json").read_bytes())})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "finalize"))
    parser.add_argument("--phase", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.workers <= 32:
        parser.error("workers must be between 1 and 32")
    try:
        if args.action == "prepare":
            prepare()
        elif args.action == "run":
            run(args.phase, args.workers)
        else:
            finalize(args.phase)
        return 0
    except Exception as exc:
        # No raw request headers or provider error bodies are printed.
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
