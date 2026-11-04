"""Two-stage, bounded non-thinking prompt experiment. prepare/score/status are offline.

The 12-fit-event exploration selects a fixed fusion method; only then may the
100-event DEV confirmation run. Interrupted stages are not automatically replayed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.parent / "task2_prompt_baseline_v1"
FROZEN = HERE / "frozen"
RUN = HERE / "run"
METHODS = ("A", "B", "C", "VETO", "CONSENSUS")
CONFIG = {
    "experiment": "task2_prompt_intuition100_v1", "explore_events": 12, "confirm_events": 100,
    "variants": ["A", "B", "C"], "model": "deepseek-flash", "thinking": {"type": "disabled"},
    "temperature": 0, "response_format": {"type": "json_object"}, "max_tokens": 4096,
    "stream": False, "workers": 4, "timeout_seconds": 90,
    "max_initial_attempts": 336, "max_http_attempts": 360, "max_technical_retries": 24,
    "budget_usd": "1.50", "input_usd_per_million": "0.30", "output_usd_per_million": "1.20",
    "input_upper_bound": "UTF8 request bytes + 1024", "budget_settlement": "reliable usage at peak uncached rates; otherwise keep full reservation",
    "primary_selection": "explore Task2b micro-F1 descending; exact ties A,B,C,VETO,CONSENSUS",
    "fusion": {"VETO": "A intersect (B union C)", "CONSENSUS": "(A intersect B) union (A intersect C) union (B intersect C)", "UNION": "A union B union C; diagnostic only"},
    "confirmation_selection": "first 100 SHA256(intuition100-v1|guid|subevent_id) among all 1526 DEV events; input only",
}
SUFFIXES = {
    "A": "",
    "B": "\n\nADDITIONAL VIEW: ACTOR AND EVENT ATTRIBUTION\nFor each supplied actor, base the decision on that actor's own actions, choices,\ncommitments or attributed positions in this target subevent. Background can resolve\nreferences and motives, but labels belonging only to another actor or another event\nare not evidence for this actor here. Distinguish acting, being affected, observing,\nand being mentioned. An affected person may express values through their own conduct;\nbeing harmed alone does not establish the person's alignment or contradiction.\nReturn every value clearly supported for this actor and event, including implicit\nones, without adding generic values solely because the topic sounds related. Keep\nthe original JSON schema, all actors, and empty lists where unsupported. No explanations.\n",
    "C": "\n\nADDITIONAL VIEW: ACTION, VALUE DEFINITION AND DIRECTION\nInterpret the concrete behavior or position attributed to each actor in the target\nsubevent using the exact official value definitions. Distinguish a value's specific\nmotivational meaning from a loosely related theme. Use context-supported implicit\nvalues as well as explicit ones. For each supported value, decide whether this actor's\nbehavior advances it (1) or undermines it (0); harm, sentiment and the journalist's\nevaluation are not themselves direction labels. An actor may support some values\nwhile contradicting others. Preserve genuinely supported multiple values and both\ndirections; do not add a label merely to describe the article's topic. Keep the original\nJSON schema, all actors, and empty lists where unsupported. No explanations.\n",
}
spec = importlib.util.spec_from_file_location("historical_task2_helpers", OLD / "run_experiment.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
read, write, canonical, now = old.read, old.write, old.canonical, old.now


def sha(value):
    return hashlib.sha256(value).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def normalize(text):
    return " ".join(str(text).split()).casefold()


def selection_key(key):
    return sha(("intuition100-v1|" + key[0] + "|" + key[1]).encode("utf-8"))


def select_keys(keys, n=100):
    if len(keys) != len(set(keys)) or len(keys) < n:
        raise ValueError("Duplicate or insufficient event keys")
    return sorted(keys, key=lambda key: (selection_key(key), key))[:n]


def payload(case, prompt):
    user = {"TARGET_SUBEVENT": {"id": case["subevent_id"], "text": case["subevent"]},
            "candidate_actors": case["candidate_actors"], "article_background": case["article_background"]}
    return {key: CONFIG[key] for key in ("model", "thinking", "temperature", "response_format", "max_tokens", "stream")} | {
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": canonical(user)}]}


def reserved_cost(body):
    tokens = len(body) + 1024
    cost = (Decimal(tokens) * Decimal(CONFIG["input_usd_per_million"]) +
            Decimal(CONFIG["max_tokens"]) * Decimal(CONFIG["output_usd_per_million"])) / Decimal(1000000)
    return tokens, cost


def usage_cost(usage):
    # No cache or off-peak discount is assumed. Unknown usage retains the reservation.
    p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if type(p) is not int or type(c) is not int or p <= 0 or c < 0:
        return None
    if "total_tokens" in usage and usage["total_tokens"] != p + c:
        return None
    return (Decimal(p) * Decimal("0.30") + Decimal(c) * Decimal("1.20")) / Decimal(1000000)


def split_path():
    matches = list((ROOT / "docs").glob("*/evidence/grouped_train_split.json"))
    if len(matches) != 1:
        raise RuntimeError("Expected one existing grouped TRAIN split manifest")
    return matches[0]


def source_paths():
    return [Path(__file__).resolve(), OLD / "run_experiment.py", OLD / "frozen/system_prompt.txt",
            OLD / "prompt_template.txt", OLD / "evaluator/official_cli.py", OLD / "evaluator/official_original.py",
            OLD / "evaluator/provenance.json", OLD / "USER_STOP.json", split_path(),
            ROOT / "dataset/dev/dev_event_base.json", ROOT / "dataset/train/train_event_base.json",
            *sorted((ROOT / "dataset/hv_categories").glob("*.json"))]


def prepare():
    if FROZEN.exists():
        check_frozen()
        print("Already prepared and verified; no API calls.")
        return
    dev = old.cases_from_input(read(ROOT / "dataset/dev/dev_event_base.json"))
    train = old.cases_from_input(read(ROOT / "dataset/train/train_event_base.json"))
    if len(dev) != 1526:
        raise RuntimeError("DEV population differs from 1526 frozen-input events")
    by_key = {(c["guid"], c["subevent_id"]): c for c in dev}
    confirm = [by_key[key] | {"sample_index": i} for i, key in enumerate(select_keys(list(by_key)))]
    fit = set(map(str, read(split_path())["guids"]["fit"]))
    dev_bodies = {normalize(c["article_background"]["content"]) for c in dev}
    dev_titles = {normalize(c["article_background"]["title"]) for c in dev}
    eligible = [c for c in train if c["guid"] in fit and
                normalize(c["article_background"]["content"]) not in dev_bodies and
                normalize(c["article_background"]["title"]) not in dev_titles]
    explore, used_guids, used_bodies = [], set(), set()
    for case in sorted(eligible, key=lambda c: (sha(("intuition100-v1-explore|" + c["guid"] + "|" + c["subevent_id"]).encode()), c["guid"], c["subevent_id"])):
        body = normalize(case["article_background"]["content"])
        if case["guid"] in used_guids or body in used_bodies:
            continue
        explore.append(case | {"sample_index": len(explore)})
        used_guids.add(case["guid"])
        used_bodies.add(body)
        if len(explore) == 12:
            break
    if len(explore) != 12:
        raise RuntimeError("Not enough eligible fit-only exploration articles")
    history, historical_sources = [], []
    selected = set((c["guid"], c["subevent_id"]) for c in confirm)
    for path in sorted((OLD / "runs/full/cases").glob("*/result.json")):
        metadata = read(path)
        row = {"guid": str(metadata["guid"]), "subevent_id": str(metadata["subevent_id"]), "historical_case_index": metadata["case_index"]}
        history.append(row)
        if (row["guid"], row["subevent_id"]) in selected:
            historical_sources.append(path)
    if len(history) != 508 or len({(c["guid"], c["subevent_id"]) for c in history}) != 508:
        raise RuntimeError("Historical completed population changed")
    original = (OLD / "frozen/system_prompt.txt").read_text(encoding="utf-8")
    prompts = {variant: original + suffix for variant, suffix in SUFFIXES.items()}
    reservations = [reserved_cost(canonical(payload(c, p)).encode())[1] for c in explore + confirm for p in prompts.values()]
    max_cost = sum(reservations, Decimal(0)) + max(reservations) * CONFIG["max_technical_retries"]
    FROZEN.mkdir(parents=True)
    for name, value in (("config", CONFIG), ("explore_inputs", explore), ("confirm_inputs", confirm),
                        ("population_dev_inputs", dev), ("historical_completed_keys", history)):
        write(FROZEN / (name + ".json"), value)
    shutil.copyfile(OLD / "frozen/system_prompt.txt", FROZEN / "system_prompt_A.txt")
    for variant in ("B", "C"):
        (FROZEN / f"system_prompt_{variant}.txt").write_text(prompts[variant], encoding="utf-8")
    shutil.copyfile(OLD / "prompt_template.txt", HERE / "prompt_template.txt")
    manifest = {"prepared_at": now(), "explore_events": 12, "confirm_events": 100,
                "explore_articles": len(used_guids), "confirm_articles": len({c["guid"] for c in confirm}),
                "confirm_actor_event_pairs": sum(len(c["candidate_actors"]) for c in confirm),
                "historical_intersection_events": len(historical_sources),
                "maximum_all_attempts_unsettled_usd": str(max_cost), "hard_exposure_limit_usd": "1.50",
                "completion_not_guaranteed_under_budget": True,
                "frozen_hashes": {p.name: file_sha(p) for p in FROZEN.iterdir() if p.is_file()},
                "source_hashes": {p.relative_to(ROOT).as_posix(): file_sha(p) for p in source_paths() + historical_sources},
                "selection_uses_gold_or_predictions": False,
                "normalization": "collapse whitespace + casefold", "explore_excludes_dev_same_body_or_title": True}
    write(FROZEN / "manifest.json", manifest)
    write(HERE / "AUTHORIZATION.json", {"scope": CONFIG["experiment"], "authorized": True, "created_at": now(),
          "manifest_sha256": file_sha(FROZEN / "manifest.json"), "max_events": 112, "max_http_attempts": 360,
          "max_reserved_usd": "1.50", "does_not_authorize_historical_resume": True,
          "user_instruction": "2026-11-05 user requests a small non-thinking low-temperature multi-direction prompt and fusion experiment followed by 100-event Task 2 testing.",
          "historical_stop_preserved": True})
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("source_hashes", "frozen_hashes")}, ensure_ascii=False, indent=2))


def check_scope(authorization, manifest_hash, stopped=False):
    if stopped:
        raise RuntimeError("This experiment is stopped by RUN_STOP.json")
    expected = {"scope": CONFIG["experiment"], "authorized": True, "manifest_sha256": manifest_hash,
                "max_events": 112, "max_http_attempts": 360, "max_reserved_usd": "1.50", "does_not_authorize_historical_resume": True}
    if any(authorization.get(k) != v for k, v in expected.items()):
        raise RuntimeError("Scope authorization mismatch")


def check_frozen(check_stop=False):
    manifest = read(FROZEN / "manifest.json")
    if read(FROZEN / "config.json") != CONFIG:
        raise RuntimeError("Frozen configuration mismatch")
    for name, expected in manifest["frozen_hashes"].items():
        if file_sha(FROZEN / name) != expected:
            raise RuntimeError(f"Frozen file changed: {name}")
    for relative, expected in manifest["source_hashes"].items():
        if file_sha(ROOT / relative) != expected:
            raise RuntimeError(f"Historical/source file changed: {relative}")
    check_scope(read(HERE / "AUTHORIZATION.json"), file_sha(FROZEN / "manifest.json"), check_stop and (HERE / "RUN_STOP.json").exists())
    for stage, n in (("explore", 12), ("confirm", 100)):
        cases = read(FROZEN / f"{stage}_inputs.json")
        if len(cases) != n or len({(c["guid"], c["subevent_id"]) for c in cases}) != n:
            raise RuntimeError("Frozen coverage mismatch")
    return manifest


def load_credentials():
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"):
            values[key.strip()] = value.strip().strip("\"'")
    key = values.get("DEEPSEEK_API_KEY", "")
    base = values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    url = urllib.parse.urlsplit(base)
    if not key or key.startswith("YOUR_"):
        raise RuntimeError("Project .env has no usable key; key value omitted")
    if url.scheme != "https" or url.netloc != "api.deepseek.com" or url.path not in ("", "/v1") or url.query or url.fragment:
        raise RuntimeError("Only official HTTPS DeepSeek endpoint allowed")
    return key, base + "/chat/completions"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("API redirect refused")


class Budget:
    def __init__(self, path):
        self.path, self.lock = Path(path), threading.Lock()
        self.rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()] if self.path.exists() else []
        self.reservations = {r["attempt"]: r for r in self.rows if r["event"] == "reserved"}
        self.settlements = {r["attempt"]: r for r in self.rows if r["event"] == "settled"}
        self.attempts = len(self.reservations)
        self.retries = sum(r["retry"] for r in self.reservations.values())
        self.total = sum((Decimal(self.settlements[n]["charge_usd"] if n in self.settlements else r["reserved_usd"])
                          for n, r in self.reservations.items()), Decimal(0))

    def record(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical(data) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.rows.append(data)

    def reserve(self, case, body, retry=False, stage="explore", variant="A"):
        with self.lock:
            if (HERE / "RUN_STOP.json").exists():
                raise RuntimeError("Scoped stop switch present")
            upper, cost = reserved_cost(body)
            if self.attempts >= CONFIG["max_http_attempts"] or (retry and self.retries >= CONFIG["max_technical_retries"]):
                raise RuntimeError("HTTP attempt budget exhausted")
            if not retry and self.attempts - self.retries >= CONFIG["max_initial_attempts"]:
                raise RuntimeError("Initial attempt budget exhausted")
            if self.total + cost > Decimal(CONFIG["budget_usd"]):
                raise RuntimeError("USD exposure/reservation budget exhausted")
            number = self.attempts + 1
            row = {"event": "reserved", "time": now(), "attempt": number, "stage": stage, "variant": variant,
                   "sample_index": case["sample_index"], "retry": retry, "request_sha256": sha(body),
                   "input_token_upper_bound": upper, "reserved_usd": str(cost), "cumulative_exposure_usd": str(self.total + cost)}
            self.record(row)
            self.reservations[number] = row
            self.attempts = number
            self.retries += int(retry)
            self.total += cost
            return number

    def finish(self, number, state, usage=None, **fields):
        with self.lock:
            if number in self.settlements:
                return  # A later exception path must never release this reservation twice.
            if number not in self.reservations:
                raise RuntimeError("Cannot settle an unreserved attempt")
            self.record({"event": "finished", "time": now(), "attempt": number, "state": state, **fields})
            charge = usage_cost(usage or {})
            if charge is not None:
                reserved = Decimal(self.reservations[number]["reserved_usd"])
                # A violated accounting assumption cannot be hidden by clamping reported cost.
                row = {"event": "settled", "time": now(), "attempt": number, "charge_usd": str(charge),
                       "released_reservation_usd": str(reserved - charge), "usage": usage}
                self.record(row)
                self.settlements[number] = row
                self.total += charge - reserved
                if charge > reserved:
                    write(HERE / "RUN_STOP.json", {"reason": "usage exceeds conservative reservation", "time": now()})


def case_directory(stage, case, variant):
    return RUN / stage / "cases" / f'{case["sample_index"]:03d}' / variant


def one_request(stage, case, variant, prompt, key, endpoint, budget, retry=False):
    directory = case_directory(stage, case, variant)
    directory.mkdir(parents=True, exist_ok=True)
    request_data = payload(case, prompt)
    body = canonical(request_data).encode("utf-8")
    write(directory / "request.json", request_data)
    number = budget.reserve(case, body, retry=retry, stage=stage, variant=variant)
    name, started, response_data = f"attempt_{number:03d}", time.monotonic(), {}
    received = False
    try:
        req = urllib.request.Request(endpoint, body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=CONFIG["timeout_seconds"]) as response:
            raw = response.read()
        received = True
        (directory / (name + ".response.raw.json")).write_bytes(raw)
        response_data = json.loads(raw)
        write(directory / (name + ".response.json"), response_data)
        choice = response_data["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Non-stop finish reason")
        actors, labels = old.validate(choice["message"]["content"], case)
        if response_data.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0) or choice["message"].get("reasoning_content"):
            raise ValueError("Unexpected reasoning in disabled-thinking condition")
        write(directory / "result.json", {"sample_index": case["sample_index"], "guid": case["guid"], "subevent_id": case["subevent_id"],
              "variant": variant, "stage": stage, "request_sha256": sha(body), "response_file": name + ".response.json",
              "actors": actors, "labels": labels, "returned_model": response_data.get("model"), "usage": response_data.get("usage", {}),
              "seconds": time.monotonic() - started, "completed_at": now()})
        budget.finish(number, "valid", usage=response_data.get("usage"))
        return case, variant, False
    except urllib.error.HTTPError as error:
        technical = error.code in (408, 429, 500, 502, 503, 504)
        write(directory / (name + ".error.json"), {"type": "HTTPError", "status_code": error.code, "technical_retry_eligible": technical})
        budget.finish(number, "http_error", status_code=error.code)
        if error.code in (401, 402, 403):
            # Write through the budget lock to avoid concurrent stop-file temp collisions.
            with budget.lock:
                write(HERE / "RUN_STOP.json", {"reason": "authentication/account API error; no account query", "status": error.code, "time": now()})
        return case, variant, technical
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
        write(directory / (name + ".error.json"), {"type": type(error).__name__, "technical_retry_eligible": not received, "server_processing_may_have_occurred": True})
        budget.finish(number, "transport_or_io_error", usage=response_data.get("usage"), received=received)
        return case, variant, not received
    except Exception as error:
        write(directory / (name + ".error.json"), {"type": type(error).__name__, "technical_retry_eligible": False})
        budget.finish(number, "invalid_response", usage=response_data.get("usage"))
        return case, variant, False


def validate_result(stage, case, variant, prompt):
    directory = case_directory(stage, case, variant)
    result = read(directory / "result.json")
    expected = payload(case, prompt)
    if (str(result["guid"]), str(result["subevent_id"])) != (case["guid"], case["subevent_id"]):
        raise RuntimeError("Result event identity mismatch")
    if read(directory / "request.json") != expected or result["request_sha256"] != sha(canonical(expected).encode()):
        raise RuntimeError("Request differs from frozen inputs")
    response = read(directory / result["response_file"])
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise RuntimeError("Truncated response")
    actors, labels = old.validate(choice["message"]["content"], case)
    if actors != result["actors"] or labels != result["labels"]:
        raise RuntimeError("Saved result differs from raw response")
    if response.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0) or choice["message"].get("reasoning_content"):
        raise RuntimeError("Unexpected reasoning output")
    return result


def fused_labels(a, b, c, method):
    a, b, c = set(a), set(b), set(c)
    return {"A": a, "B": b, "C": c, "VETO": a & (b | c),
            "CONSENSUS": (a & b) | (a & c) | (b & c), "UNION": a | b | c}[method]


def fuse_results(cases, results, method):
    combined = []
    for i, case in enumerate(cases):
        sets = [{(v["actor"], v["l1_value"], v["direction"]) for v in results[variant][i]["labels"]} for variant in CONFIG["variants"]]
        labels = [{"actor": a, "l1_value": v, "direction": d} for a, v, d in sorted(fused_labels(*sets, method))]
        actors = [{"actor": a["actor"], "values": [{"l1_value": v["l1_value"], "direction": v["direction"]} for v in labels if v["actor"] == a["actor"]]} for a in case["candidate_actors"]]
        validated_actors, validated_labels = old.validate(canonical({"actors": actors}), case)
        combined.append({"actors": validated_actors, "labels": validated_labels})
    return combined


def export_and_score(cases, results, directory, gold_path, provenance="validated raw A/B/C and fixed set fusion"):
    directory.mkdir(parents=True, exist_ok=True)
    ids = read(ROOT / "dataset/hv_categories/human_value_level1_values.json")
    l2 = read(ROOT / "dataset/hv_categories/human_value_level2_values.json")
    parents = read(ROOT / "dataset/hv_categories/level_1_to_level_2.json")["level_1_to_level_2"]
    mapping = {str(ids[name]): str(l2[parent]) for name, parent in parents.items()}
    exports, coverage = {"task2a": {}, "task2b": {}}, []
    for case, result in zip(cases, results):
        labels = result["labels"]
        coarse = sorted({(v["actor"], mapping[v["l1_value"]]) for v in labels})
        for task, values in (("task2b", labels), ("task2a", [{"actor": a, "l2_value": v} for a, v in coarse])):
            row = exports[task].setdefault(case["guid"], {"guid": case["guid"], "subevents_human_values": []})
            row["subevents_human_values"].append({"subevent_id": case["subevent_id"], "subevent_human_values": values})
        coverage.extend({"guid": case["guid"], "subevent_id": case["subevent_id"], "actor": a["actor"], "label_count": len(a["values"])} for a in result["actors"])
    for task, rows in exports.items():
        write(directory / f"pred_{task}.json", list(rows.values()))
    write(directory / "coverage.json", {"complete": True, "events": len(cases), "actor_event_pairs": len(coverage),
          "empty_actor_event_pairs": sum(c["label_count"] == 0 for c in coverage), "records": coverage})
    command = [sys.executable, "-X", "utf8", str(OLD / "evaluator/official_cli.py"), "--gold_task2", str(gold_path),
               "--pred_task2a", str(directory / "pred_task2a.json"), "--pred_task2b", str(directory / "pred_task2b.json"), "--out", str(directory / "metrics_official.json")]
    output = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True)
    (directory / "official_stdout.json").write_text(output.stdout, encoding="utf-8")
    write(directory / "scoring_command.json", {"command": command, "returncode": output.returncode, "gold_sha256": file_sha(gold_path),
          "evaluator_sha256": file_sha(OLD / "evaluator/official_cli.py"), "provenance": provenance})
    old.verify_and_export(directory, cases, gold_path)
    return read(directory / "metrics_official.json")


def subset_gold(cases, source, destination):
    selected = {(case["guid"], case["subevent_id"]) for case in cases}
    gold = [{"guid": row["guid"], "subevents_human_values": [e for e in row["subevents_human_values"]
            if (str(row["guid"]), str(e["subevent_id"])) in selected]} for row in read(source)]
    write(destination, [row for row in gold if row["subevents_human_values"]])


def choose_primary(metrics):
    return max(METHODS, key=lambda method: (metrics[method]["task2b"]["micro_f1"], -METHODS.index(method)))


def verify_confirmation_lock():
    lock = read(HERE / "confirmation_lock.json")
    if lock["manifest_sha256"] != file_sha(FROZEN / "manifest.json") or lock["primary_method"] not in METHODS:
        raise RuntimeError("Invalid confirmation lock")
    metrics = {method: read(RUN / "explore/evaluation" / method / "metrics_official.json") for method in METHODS}
    if lock["primary_method"] != choose_primary(metrics):
        raise RuntimeError("Primary selection mismatch")
    for relative, expected in lock["evidence_hashes"].items():
        if file_sha(HERE / relative) != expected:
            raise RuntimeError("Exploration evidence changed after confirmation lock")
    return lock


def stop_pending(futures, reason):
    # Create the stop marker BEFORE the executor context waits for running threads.
    # O_EXCL avoids overwriting an existing user stop and requires no budget lock.
    try:
        fd = os.open(HERE / "RUN_STOP.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"reason": reason, "time": now()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        pass
    for future in futures:
        future.cancel()


def run(stage):
    check_frozen(check_stop=True)
    if stage == "confirm":
        verify_confirmation_lock()
    cases = read(FROZEN / f"{stage}_inputs.json")
    prompts = {v: (FROZEN / f"system_prompt_{v}.txt").read_text(encoding="utf-8") for v in CONFIG["variants"]}
    RUN.mkdir(parents=True, exist_ok=True)
    guard = RUN / "ACTIVE_EXECUTION.lock"
    guard_fd = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    os.close(guard_fd)
    try:
        directory = RUN / stage
        directory.mkdir(parents=True, exist_ok=True)
        # Stage start is never deleted, so crashes and restarts cannot replay it.
        fd = os.open(directory / "RUN_STARTED.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"started_at": now(), "pid": os.getpid(), "stage": stage, "manifest_sha256": file_sha(FROZEN / "manifest.json"),
                       "confirmation_lock_sha256": file_sha(HERE / "confirmation_lock.json") if stage == "confirm" else None}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        key, endpoint = load_credentials()
        started, budget, retries, errors = time.monotonic(), Budget(RUN / "attempt_ledger.jsonl"), [], []
        with ThreadPoolExecutor(max_workers=CONFIG["workers"]) as executor:
            futures = []
            try:
                for case in cases:
                    for variant in CONFIG["variants"]:
                        futures.append(executor.submit(one_request, stage, case, variant, prompts[variant], key, endpoint, budget))
                for future in as_completed(futures):
                    try:
                        case, variant, technical = future.result()
                        if technical:
                            retries.append((case, variant))
                    except RuntimeError as error:
                        errors.append(str(error))
                    count = len(list((directory / "cases").glob("*/*/result.json")))
                    print(f"{stage}: valid {count}/{len(cases)*3}; attempts {budget.attempts}/360; exposure USD {budget.total}", flush=True)
            except BaseException as error:
                stop_pending(futures, "Execution interrupted: " + type(error).__name__)
                raise
        for case, variant in sorted(retries, key=lambda item: (item[0]["sample_index"], item[1])):
            if budget.retries >= CONFIG["max_technical_retries"]:
                break
            try:
                one_request(stage, case, variant, prompts[variant], key, endpoint, budget, retry=True)
            except RuntimeError as error:
                errors.append(str(error))
                break
        del key
        write(directory / "EXECUTION_FINISHED.json", {"finished_at": now(), "seconds": time.monotonic() - started,
              "global_http_attempts": budget.attempts, "global_technical_retries": budget.retries, "global_exposure_usd": str(budget.total), "errors": sorted(set(errors))})
    except KeyboardInterrupt:
        stop_pending([], "KeyboardInterrupt during stage execution")
        raise
    finally:
        guard.unlink(missing_ok=True)
    status()
    if len(list((RUN / stage / "cases").glob("*/*/result.json"))) != len(cases) * 3:
        raise RuntimeError("Incomplete stage: no main scoring, empty substitution or automatic replay")
    score(stage)


def historical_comparison(cases, method_results, evaluation):
    history = {(c["guid"], c["subevent_id"]): c for c in read(FROZEN / "historical_completed_keys.json")}
    indices = [i for i, c in enumerate(cases) if (c["guid"], c["subevent_id"]) in history]
    if not indices:
        return {"events": 0, "note": "No overlap with historical completed set"}
    shared = [cases[i] for i in indices]
    previous = []
    original = (FROZEN / "system_prompt_A.txt").read_text(encoding="utf-8")
    for case in shared:
        item = history[(case["guid"], case["subevent_id"])]
        directory = OLD / "runs/full/cases" / f'{item["historical_case_index"]:05d}'
        result = read(directory / "result.json")
        expected = old.payload_for(case, original)
        if read(directory / "request.json") != expected or result["request_sha256"] != sha(canonical(expected).encode()):
            raise RuntimeError("Historical request mismatch")
        response = read(directory / result["response_file"])
        if response["choices"][0]["finish_reason"] != "stop":
            raise RuntimeError("Historical response truncated")
        actors, labels = old.validate(response["choices"][0]["message"]["content"], case)
        if actors != result["actors"] or labels != result["labels"]:
            raise RuntimeError("Historical raw response mismatch")
        previous.append(result)
    directory = evaluation / "historical_intersection"
    gold_path = directory / "gold_subset.json"
    subset_gold(shared, evaluation / "gold_subset.json", gold_path)
    metrics = {"historical_max": export_and_score(shared, previous, directory / "historical_max", gold_path, "historical raw responses revalidated")}
    for method, results in method_results.items():
        metrics[method] = export_and_score(shared, [results[i] for i in indices], directory / method, gold_path)
    output = {"events": len(shared), "not_full_100": True, "metrics": metrics,
              "caveat": "Historical successful-set intersection only; old reasoning/max_tokens, time and model-version confounds remain"}
    write(directory / "comparison.json", output)
    return output


def usage_summary():
    totals, models, fingerprints, known_cost = Counter(), Counter(), Counter(), Decimal(0)
    count = 0
    for path in sorted(RUN.glob("*/cases/*/*/attempt_*.response.json")):
        response = read(path)
        usage = response.get("usage", {})
        count += 1
        models[str(response.get("model"))] += 1
        fingerprints[str(response.get("system_fingerprint"))] += 1
        for k, value in usage.items():
            if type(value) is int:
                totals[k] += value
        details = usage.get("completion_tokens_details", {})
        if "reasoning_tokens" in details:
            totals["reasoning_tokens_field_present_responses"] += 1
            totals["reasoning_tokens"] += details["reasoning_tokens"]
        else:
            totals["reasoning_tokens_field_missing_responses"] += 1
        message = response.get("choices", [{}])[0].get("message", {})
        totals["reasoning_content_nonempty_responses"] += int(bool(message.get("reasoning_content")))
        known_cost += usage_cost(usage) or Decimal(0)
    budget = Budget(RUN / "attempt_ledger.jsonl")
    result = {"returned_attempts": count, "usage": dict(totals), "models": dict(models), "fingerprints": dict(fingerprints),
              "known_usage_peak_uncached_estimate_usd": str(known_cost), "global_charge_plus_unsettled_reservations_usd": str(budget.total),
              "attempts": budget.attempts, "technical_retries": budget.retries, "not_account_bill": True,
              "all_returned_attempts_have_explicit_zero_reasoning": bool(count) and
                  totals["reasoning_tokens_field_present_responses"] == count and totals["reasoning_tokens"] == 0 and
                  totals["reasoning_content_nonempty_responses"] == 0,
              "missing_reasoning_usage_is_not_verified_zero": True}
    write(RUN / "usage.json", result)
    return result


def score(stage):
    manifest = check_frozen()
    lock = verify_confirmation_lock() if stage == "confirm" else None
    cases = read(FROZEN / f"{stage}_inputs.json")
    results = {variant: [validate_result(stage, c, variant, (FROZEN / f"system_prompt_{variant}.txt").read_text(encoding="utf-8")) for c in cases]
               for variant in CONFIG["variants"]}
    # Gold is first opened only after ALL stage responses are complete and validated.
    evaluation = RUN / stage / "evaluation"
    gold_path = evaluation / "gold_subset.json"
    gold_source = ROOT / f"dataset/gold_labels/{'train' if stage == 'explore' else 'dev'}/{'train' if stage == 'explore' else 'dev'}_human_values.json"
    subset_gold(cases, gold_source, gold_path)
    method_results = {method: fuse_results(cases, results, method) for method in (*METHODS, "UNION")}
    metrics = {method: export_and_score(cases, output, evaluation / method, gold_path) for method, output in method_results.items()}
    if stage == "explore":
        evidence = sorted(evaluation.rglob("metrics_official.json")) + sorted((RUN / stage / "cases").glob("*/*/result.json"))
        evidence += [gold_path]
        proposed = {"manifest_sha256": file_sha(FROZEN / "manifest.json"), "primary_method": choose_primary(metrics),
                    "selection_rule": CONFIG["primary_selection"], "explore_events": 12, "not_independent_test": True,
                    "evidence_hashes": {p.relative_to(HERE).as_posix(): file_sha(p) for p in evidence}}
        path = HERE / "confirmation_lock.json"
        if path.exists():
            lock = read(path)
            if any(lock.get(k) != v for k, v in proposed.items()):
                raise RuntimeError("Refusing to alter an existing confirmation lock")
        else:
            lock = proposed | {"locked_at": now()}
            write(path, lock)
        history = None
    else:
        start_path = RUN / "confirm/RUN_STARTED.json"
        if start_path.exists() and read(start_path)["confirmation_lock_sha256"] != file_sha(HERE / "confirmation_lock.json"):
            raise RuntimeError("Confirmation lock changed since inference began")
        history = historical_comparison(cases, method_results, evaluation)
    usage = usage_summary()
    write(evaluation / "comparison.json", {"stage": stage, "events": len(cases), "primary_method": lock["primary_method"], "metrics": metrics,
          "source_gold_sha256": file_sha(gold_source), "historical_intersection": history, "confirmation_primary_unchanged": True})
    lines = ["# Task 2 多方向无思考 prompt 实验", "", f"阶段：{stage}；{len(cases)} 个子事件 × 3 个 prompt 全部完整；每个事件包含全部候选 actor。", "",
             f"探索锁定的主要方法：**{lock['primary_method']}**。A 原始 prompt，B 主体/事件归属，C 行为/价值/方向。VETO=A∩(B∪C)；CONSENSUS=至少两个 prompt 同意同一 actor/value/direction。UNION 仅诊断，不参与选优。", "",
             "| 方法 | 任务 | Precision | Recall | micro-F1 | TP/FP/FN |", "|---|---|---:|---:|---:|---|"]
    for method in (*METHODS, "UNION"):
        checks = read(evaluation / method / "verification.json")["independent_scores"]
        for task in ("task2a", "task2b"):
            m, c = metrics[method][task], checks[task]
            lines.append(f"| {method} | {task} | {m['micro_precision']:.2%} | {m['micro_recall']:.2%} | {m['micro_f1']:.2%} | {c['tp']}/{c['fp']}/{c['fn']} |")
    lines += ["", "所有分数通过官方 CLI 和独立计数/DRR 核对；失败响应未当作空预测。探索 12 条来自 TRAIN fit、每文一条，正文和标题均不与 DEV 重合，是开发探索数据，不能称独立测试。", "",
              f"确认 100 条由全部 1526 个 DEV 事件按冻结 hash 选出，覆盖 {manifest['confirm_articles']} 篇文章、{manifest['confirm_actor_event_pairs']} 个 actor/event。不是完整 DEV/TEST；应检查长度、actor数、文章聚类与 TRAIN 重合等差异。确认成绩不会改变已锁定 primary。", "",
              "三个 prompt 是同一模型的不同指令视角，错误不独立，投票不保证提升；交集策略可能提高精度但降低召回。与历史 max 的比较只针对确认样本和旧 508 成功事件的交集，同时存在时间、模型版本、温度和输出上限差异，不能当作‘思考开关’因果实验。", "",
              f"全部阶段已知 usage：{json.dumps(usage, ensure_ascii=False)}。成本为峰值无缓存折扣估算，不是账户账单；未知 usage 请求保留完整最坏预留。共享硬上限 US$1.50 / 360 attempts，可能导致实验无法完成。", "",
              "原 USER_STOP.json 保留。本目录 RUN_STOP.json 可停止后续请求；stage RUN_STARTED.json 阻止自动重跑；没有查询账户余额。"]
    (evaluation / "RESULTS_zh.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if stage == "confirm":
        shutil.copyfile(evaluation / "RESULTS_zh.md", HERE / "RESULTS_zh.md")
    print(json.dumps({"stage": stage, "complete": True, "primary_method": lock["primary_method"], "metrics": metrics, "usage": usage}, ensure_ascii=False, indent=2))


def status():
    budget = Budget(RUN / "attempt_ledger.jsonl")
    finished = {r["attempt"] for r in budget.rows if r["event"] == "finished"}
    print(json.dumps({"prepared": FROZEN.exists(), "stopped": (HERE / "RUN_STOP.json").exists(),
          "valid_responses": {s: len(list((RUN / s / "cases").glob("*/*/result.json"))) for s in ("explore", "confirm")},
          "http_attempts": budget.attempts, "technical_retries": budget.retries, "charge_plus_reservations_usd": str(budget.total),
          "uncertain_inflight_attempts": [n for n in budget.reservations if n not in finished],
          "confirmation_locked": (HERE / "confirmation_lock.json").exists(), "automatic_stage_replay_allowed": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "score", "status"))
    parser.add_argument("--stage", choices=("explore", "confirm"))
    args = parser.parse_args()
    if args.action in ("run", "score"):
        if not args.stage:
            parser.error("--stage is required for run/score")
        globals()[args.action](args.stage)
    else:
        globals()[args.action]()
