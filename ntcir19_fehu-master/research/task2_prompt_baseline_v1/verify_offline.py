"""Verify the stopped Task 2 archive and rerun official scoring, fully offline.

Uses only the standard library. No credentials, environment settings, GPU, or
network are accessed. Historical inputs are read-only; results go under --out.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OFFICIAL_COMMIT = "c27e19d97c24bd764c2ea520217dba9873fab455"
OFFICIAL_SHA = "4d325a5d38277c9dfc7a141088b6724c7c0d6c03dcc8f85b90531c6e69157b31"
CLI_SHA = "3dddbdc10a3177332f96d3362bc7688d475bf398da3959511f50ff0bc21b0d5f"


def check(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")


def contained_path(root, relative):
    """Resolve a historic Windows/POSIX relative path without directory escape."""
    check(isinstance(relative, str) and bool(relative), "Empty or invalid relative path")
    windows = PureWindowsPath(relative)
    parts = relative.replace("\\", "/").split("/")
    check(not windows.drive and not windows.root and not relative.startswith("/"),
          "Absolute paths are not accepted in archive references")
    check(all(part not in {"", ".", ".."} and ":" not in part for part in parts),
          "Unsafe component in archive path")
    root = Path(root).resolve()
    result = root.joinpath(*parts).resolve()
    check(result.is_relative_to(root), "Archive path escapes its directory")
    return result


def compare_json(expected, actual, location="root"):
    """Compare complete JSON structures, tolerating only numeric roundoff."""
    if isinstance(expected, dict):
        check(isinstance(actual, dict) and expected.keys() == actual.keys(),
              f"Object keys differ at {location}")
        for key in expected:
            compare_json(expected[key], actual[key], f"{location}.{key}")
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(expected) == len(actual),
              f"Array length differs at {location}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare_json(left, right, f"{location}[{index}]")
    elif isinstance(expected, bool) or expected is None:
        check(type(expected) is type(actual) and expected == actual, f"Value differs at {location}")
    elif isinstance(expected, (int, float)):
        check(isinstance(actual, (int, float)) and not isinstance(actual, bool),
              f"Expected number at {location}")
        check(math.isfinite(expected) and math.isfinite(actual)
              and math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-12),
              f"Numeric value differs at {location}")
    else:
        check(type(expected) is type(actual) and expected == actual, f"Value differs at {location}")


def verify_archive(out):
    frozen_dir = HERE / "frozen"
    subset = HERE / "subset_evaluation_completed"
    frozen = load(frozen_dir / "manifest.json")
    evaluation = load(subset / "evaluation_manifest.json")
    config = load(HERE / "runs/full/run_config.json")
    stop = load(HERE / "USER_STOP.json")
    check(stop["inference_authorized"] is False and config["status"] == "stopped_by_user"
          and config["continuation_allowed"] is False, "Archive is not marked stopped by user")
    check(sha(frozen_dir / "manifest.json") == config["frozen_manifest_sha256"],
          "Frozen manifest bytes changed (check Git line-ending conversion)")
    check(frozen["protocol"] == config["protocol"], "Run protocol changed")
    for filename, field in (("system_prompt.txt", "system_prompt_sha256"),
                            ("case_manifest.json", "case_manifest_sha256"),
                            ("code_snapshot.py", "code_sha256")):
        check(sha(frozen_dir / filename) == frozen[field], f"Frozen {filename} hash mismatch")
    check(sha(HERE / "run_experiment.py") == frozen["code_sha256"], "Historical runner hash mismatch")
    for relative, expected in frozen["source_hashes"].items():
        check(sha(contained_path(ROOT, relative)) == expected, f"Source hash mismatch: {relative}")
    gold_source = ROOT / "dataset/gold_labels/dev/dev_human_values.json"
    check(sha(gold_source) == evaluation["source_gold_sha256"], "Source gold hash mismatch")
    check(sha(subset / "selected_cases.json") == evaluation["selected_cases_sha256"],
          "Selected-case hash mismatch")
    for task in ("task2a", "task2b"):
        check(sha(subset / f"pred_{task}.json") == evaluation["prediction_sha256"][task],
              f"Archived prediction hash mismatch: {task}")

    provenance = load(HERE / "evaluator/provenance.json")
    check(provenance == evaluation["official_provenance"], "Evaluator provenance differs")
    check(provenance["commit"] == OFFICIAL_COMMIT
          and provenance["source_url"] == f"https://raw.githubusercontent.com/ii-research/NTCIR-19-FEHU-resource/{OFFICIAL_COMMIT}/evaluation.py",
          "Unexpected official evaluator source")
    original = HERE / "evaluator/official_original.py"
    cli = HERE / "evaluator/official_cli.py"
    check(sha(original) == provenance["original_sha256"] == OFFICIAL_SHA, "Original evaluator hash mismatch")
    check(sha(cli) == provenance["cli_sha256"] == CLI_SHA, "CLI evaluator hash mismatch")
    original_bytes = original.read_bytes()
    check(original_bytes.count(b"    DEBUG = True\n") == 1, "Unexpected original DEBUG marker")
    check(original_bytes.replace(b"    DEBUG = True\n", b"    DEBUG = False\n", 1) == cli.read_bytes(),
          "Evaluator differs beyond the permitted DEBUG change")

    source = load(ROOT / "dataset/dev/dev_event_base.json")
    cases = [(article, event) for article in source for event in article["subevents"]]
    frozen_cases = load(frozen_dir / "case_manifest.json")
    selected = load(subset / "selected_cases.json")
    check(len(source) == frozen["articles"] == 177, "Unexpected DEV article count")
    check(len(cases) == len(frozen_cases) == frozen["subevents"] == 1526, "Unexpected DEV event count")
    check(len(selected) == evaluation["subset_events"] == config["valid_events"] == 508,
          "Expected the stopped 508-event subset")
    check(len({row["case_index"] for row in selected}) == 508, "Duplicate selected case index")
    check([row["case_index"] for row in selected] == sorted(row["case_index"] for row in selected),
          "Selected cases are not in source order")
    actual_results = {path.resolve() for path in (HERE / "runs/full/cases").glob("*/result.json")}
    expected_results = {HERE / "runs/full/cases" / f"{row['case_index']:05d}" / "result.json" for row in selected}
    check(actual_results == {path.resolve() for path in expected_results}, "Selected/cache result coverage differs")

    taxonomy = ROOT / "dataset/hv_categories"
    l1 = load(taxonomy / "human_value_level1_values.json")
    l2 = load(taxonomy / "human_value_level2_values.json")
    parents = load(taxonomy / "level_1_to_level_2.json")["level_1_to_level_2"]
    projection = {l1[name]: l2[parent] for name, parent in parents.items()}
    prompt = (frozen_dir / "system_prompt.txt").read_text(encoding="utf-8")
    coverage = []
    exports = {"task2a": {}, "task2b": {}}
    selected_keys = set()
    for selected_row in selected:
        index = selected_row["case_index"]
        check(isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(cases),
              "Selected index outside DEV")
        article, event = cases[index]
        actors = [{"actor": str(aid), "name": name} for record in article["actors"] for name, aid in record.items()]
        actor_ids = [actor["actor"] for actor in actors]
        check(len(set(actor_ids)) == len(actor_ids), "Duplicate source actor")
        identity = {"case_index": index, "guid": article["guid"], "subevent_id": str(event["id"]), "actor_ids": actor_ids}
        check(selected_row == identity, f"Selection/source disagreement for {index}")
        frozen_row = frozen_cases[index]
        check({key: frozen_row[key] for key in identity} == identity, f"Frozen selection disagreement for {index}")
        case_dir = HERE / "runs/full/cases" / f"{index:05d}"
        result = load(case_dir / "result.json")
        check(all(result[key] == identity[key] for key in ("case_index", "guid", "subevent_id")),
              f"Cached result identity differs for {index}")
        request = load(case_dir / "request.json")
        user = {"TARGET_SUBEVENT": {"id": str(event["id"]), "text": event["subevent"]},
                "candidate_actors": actors, "article_background": {"title": article["title"], "content": article["content"]}}
        expected_request = {key: frozen["protocol"][key] for key in
                            ("model", "thinking", "reasoning_effort", "max_tokens", "response_format", "stream")}
        expected_request["messages"] = [{"role": "system", "content": prompt}, {"role": "user", "content": canonical(user)}]
        check(request == expected_request, f"Request input/protocol differs for {index}")
        request_sha = hashlib.sha256(canonical(request).encode("utf-8")).hexdigest()
        check(request_sha == result["request_sha256"] == frozen_row["request_sha256"],
              f"Request hash mismatch for {index}")
        response = load(contained_path(case_dir, result["response_file"]))
        check(response["choices"][0]["finish_reason"] == "stop", f"Incomplete response for {index}")
        parsed = json.loads(response["choices"][0]["message"]["content"])
        check(isinstance(parsed, dict) and set(parsed) == {"actors"}
              and isinstance(parsed["actors"], list) and parsed["actors"] == result["actors"],
              f"Response/cache actor output differs for {index}")
        seen, labels = set(), []
        actor_names = {actor["actor"]: actor["name"] for actor in actors}
        for actor in parsed["actors"]:
            check(isinstance(actor, dict) and set(actor) == {"actor", "values"}, "Invalid actor schema")
            aid = actor["actor"]
            check(isinstance(aid, str) and aid in actor_ids and aid not in seen, "Unexpected/duplicate actor")
            check(isinstance(actor["values"], list), "Actor values must be a list")
            seen.add(aid)
            pairs = set()
            for value in actor["values"]:
                check(isinstance(value, dict) and set(value) == {"l1_value", "direction"}, "Invalid value schema")
                vid, direction = value["l1_value"], value["direction"]
                check(isinstance(vid, str) and vid in projection and isinstance(direction, str)
                      and direction in {"0", "1"} and (vid, direction) not in pairs,
                      "Invalid or duplicate directed value")
                pairs.add((vid, direction))
                labels.append({"actor": aid, "l1_value": vid, "direction": direction})
            coverage.append({"guid": article["guid"], "subevent_id": str(event["id"]), "actor": aid,
                             "actor_name": actor_names[aid], "predicted_label_count": len(pairs)})
        check(seen == set(actor_ids), f"Missing actor output for {index}")
        labels.sort(key=lambda row: (row["actor"], int(row["l1_value"]), row["direction"]))
        check(labels == result["labels"], f"Cached labels differ from raw response for {index}")
        coarse = [{"actor": aid, "l2_value": vid} for aid, vid in
                  sorted({(row["actor"], projection[row["l1_value"]]) for row in labels})]
        for task, values in (("task2a", coarse), ("task2b", labels)):
            target = exports[task].setdefault(article["guid"], {"guid": article["guid"], "subevents_human_values": []})
            target["subevents_human_values"].append({"subevent_id": str(event["id"]), "subevent_human_values": values})
        selected_keys.add((article["guid"], str(event["id"])))
    check(len(selected_keys) == 508, "Duplicate selected event key")
    check(len(coverage) == evaluation["candidate_actor_event_pairs"] == 1328, "Actor-event coverage differs")
    check(len(exports["task2b"]) == evaluation["articles_with_completed_events"] == 66, "Subset article count differs")
    check(coverage == load(subset / "candidate_coverage.json"), "Archived actor coverage differs")
    for task, rows in exports.items():
        check(list(rows.values()) == load(subset / f"pred_{task}.json"), f"Raw responses do not reproduce {task} predictions")
    gold_subset = []
    for article in load(gold_source):
        events = [event for event in article["subevents_human_values"]
                  if (article["guid"], str(event["subevent_id"])) in selected_keys]
        if events:
            gold_subset.append({"guid": article["guid"], "subevents_human_values": events})
    check(gold_subset == load(subset / "gold_subset.json"), "Archived gold is not the exact selected-event subset")

    command = [sys.executable, "-X", "utf8", str(cli), "--gold_task2", str(subset / "gold_subset.json"),
               "--pred_task2a", str(subset / "pred_task2a.json"), "--pred_task2b", str(subset / "pred_task2b.json"),
               "--out", str(out / "metrics_official.json")]
    process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=60, check=True)
    actual = load(out / "metrics_official.json")
    compare_json(load(subset / "metrics_official.json"), actual)
    compare_json(actual, json.loads(process.stdout))
    compare_json(actual, load(subset / "official_stdout.json"))
    return {"passed": True, "checked_at": datetime.now(timezone.utc).isoformat(), "offline_only": True,
            "new_model_calls": 0, "credentials_read": False, "user_stop_preserved": True,
            "source_hashes_verified": len(frozen["source_hashes"]), "frozen_hashes_verified": True,
            "subset_events": len(selected), "articles": len(exports["task2b"]), "candidate_actor_event_pairs": len(coverage),
            "raw_responses_verified": len(selected), "raw_predictions_match_archive": True,
            "gold_subset_reconstructed": True, "official_provenance": provenance,
            "official_command": command, "official_returncode": process.returncode, "official_metrics": actual,
            "metrics_match_archive": True, "comparison_tolerance": {"relative": 1e-12, "absolute": 1e-12},
            "historical_files_modified": False, "not_full_dev_score": True, "output_directory": str(out)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/task2_offline_verification",
                        help="Output directory (must be outside the historical experiment directory)")
    args = parser.parse_args(argv)
    out = args.out.resolve()
    try:
        check(not out.is_relative_to(HERE) and out != ROOT and out != HERE.parent,
              "Choose a separate output directory outside the historical experiment")
        out.mkdir(parents=True, exist_ok=True)
        report = verify_archive(out)
    except Exception as exc:
        report = {"passed": False, "checked_at": datetime.now(timezone.utc).isoformat(),
                  "offline_only": True, "new_model_calls": 0, "credentials_read": False,
                  "error_type": type(exc).__name__, "error": str(exc)}
        # Never write into the historical archive, even on a failed --out check.
        if out.is_dir() and not out.is_relative_to(HERE) and out != ROOT and out != HERE.parent:
            save(out / "verification.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    save(out / "verification.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
