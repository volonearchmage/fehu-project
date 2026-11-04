"""Read-only, key-free verification of the completed prompt experiment.

All re-exports and official scoring take place in TemporaryDirectory. Never call
the frozen runner's score(): it rewrites locked exploration evidence, and newline
conversion on another platform can invalidate the original byte hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("frozen_intuition_runner_for_archive", HERE / "run_experiment.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
METHODS = (*runner.METHODS, "UNION")


def forbidden(*args, **kwargs):
    raise RuntimeError("Archive verification forbids inference, credentials and network")


# Defense against an accidental future call to a stateful helper. The verifier
# only needs frozen checks, validators, pure fusion and temporary exports.
runner.run = runner.prepare = runner.score = runner.load_credentials = forbidden
runner.old.run = runner.old.prepare = runner.old.settings = forbidden
runner.urllib.request.urlopen = runner.urllib.request.build_opener = forbidden


def same(expected, actual, location):
    """Compare every metric, with exact integer counts and 1e-12 float tolerance."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            raise RuntimeError(f"Dictionary keys differ: {location}")
        for key in expected:
            same(expected[key], actual[key], f"{location}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise RuntimeError(f"List length/type differs: {location}")
        for i, (a, b) in enumerate(zip(expected, actual)):
            same(a, b, f"{location}[{i}]")
    elif type(expected) is float:
        if type(actual) not in (int, float) or not math.isfinite(expected) or not math.isfinite(actual):
            raise RuntimeError(f"Non-finite or nonnumeric metric: {location}")
        if not math.isclose(expected, actual, rel_tol=0, abs_tol=1e-12):
            raise RuntimeError(f"Metric differs: {location}")
    elif type(expected) is not type(actual) or expected != actual:
        raise RuntimeError(f"Value differs: {location}")


def member(directory, filename):
    """Archived response filenames must be plain child names, not old OS paths."""
    if not isinstance(filename, str) or "/" in filename or "\\" in filename:
        raise RuntimeError("Invalid response filename in archive")
    result = (directory / filename).resolve()
    if result.parent != directory.resolve():
        raise RuntimeError("Response path escapes archived case")
    return result


def protected_paths():
    paths = set()
    for directory in (runner.FROZEN, runner.RUN):
        paths.update(p for p in directory.rglob("*") if p.is_file())
    paths.update(HERE / name for name in ("AUTHORIZATION.json", "confirmation_lock.json", "RESULTS_zh.md"))
    paths.update(HERE / name for name in ("RUN_STOP.json",) if (HERE / name).exists())
    manifest = runner.read(runner.FROZEN / "manifest.json")
    paths.update(runner.ROOT / relative for relative in manifest["source_hashes"])
    for row in runner.read(runner.FROZEN / "historical_completed_keys.json"):
        if (str(row["guid"]), str(row["subevent_id"])) not in CONFIRM_KEYS:
            continue
        directory = runner.OLD / "runs/full/cases" / f'{row["historical_case_index"]:05d}'
        result_path = directory / "result.json"
        result = runner.read(result_path)
        paths.update((result_path, directory / "request.json", member(directory, result["response_file"])))
    for stage in ("train", "dev"):
        paths.add(runner.ROOT / f"dataset/gold_labels/{stage}/{stage}_human_values.json")
    return paths


def snapshot():
    return {p.relative_to(runner.ROOT).as_posix(): runner.file_sha(p) for p in sorted(protected_paths())}


def check_raw(stage, cases):
    output = {}
    for variant in runner.CONFIG["variants"]:
        prompt = (runner.FROZEN / f"system_prompt_{variant}.txt").read_text(encoding="utf-8")
        records = []
        for case in cases:
            directory = runner.case_directory(stage, case, variant)
            saved = runner.read(directory / "result.json")
            member(directory, saved["response_file"])
            result = runner.validate_result(stage, case, variant, prompt)
            if result.get("stage") != stage or result.get("variant") != variant:
                raise RuntimeError("Result stage/variant identity differs")
            response_path = member(directory, result["response_file"])
            raw_path = response_path.with_name(response_path.name.replace(".response.json", ".response.raw.json"))
            same(runner.read(raw_path), runner.read(response_path), f"{stage}/{case['sample_index']}/{variant}/raw")
            records.append(result)
        output[variant] = records
    return output


def check_export(cases, results, archived, temporary, gold_path, archived_metrics):
    actual = runner.export_and_score(cases, results, temporary, gold_path,
                                     provenance="read-only archive verifier; all writes are temporary")
    same(archived_metrics, actual, f"{archived.name}/comparison_metrics")
    same(runner.read(archived / "metrics_official.json"), actual, f"{archived.name}/metrics_official")
    for name in ("pred_task2a.json", "pred_task2b.json", "coverage.json"):
        same(runner.read(archived / name), runner.read(temporary / name), f"{archived.name}/{name}")
    original = runner.read(archived / "verification.json")
    rebuilt = runner.read(temporary / "verification.json")
    if not original["passed"] or not rebuilt["passed"]:
        raise RuntimeError("Independent-count verification did not pass")
    same(original["independent_scores"], rebuilt["independent_scores"], f"{archived.name}/independent_counts")
    # Hashes describe the archived byte files, not newline-normalized temp exports.
    if original["metrics_sha256"] != runner.file_sha(archived / "metrics_official.json"):
        raise RuntimeError("Archived metric hash changed")
    for task, expected in original["prediction_sha256"].items():
        if expected != runner.file_sha(archived / f"pred_{task}.json"):
            raise RuntimeError("Archived prediction hash changed")
    return {"task2b_micro_f1": actual["task2b"]["micro_f1"],
            "independent_task2b": rebuilt["independent_scores"]["task2b"],
            "independent_drr": rebuilt["independent_scores"]["drr"]}


def historical_results(cases):
    by_key = {(str(r["guid"]), str(r["subevent_id"])): r
              for r in runner.read(runner.FROZEN / "historical_completed_keys.json")}
    indices = [i for i, c in enumerate(cases) if (c["guid"], c["subevent_id"]) in by_key]
    prompt = (runner.FROZEN / "system_prompt_A.txt").read_text(encoding="utf-8")
    results = []
    for i in indices:
        case = cases[i]
        row = by_key[(case["guid"], case["subevent_id"])]
        directory = runner.OLD / "runs/full/cases" / f'{row["historical_case_index"]:05d}'
        result = runner.read(directory / "result.json")
        expected = runner.old.payload_for(case, prompt)
        same(expected, runner.read(directory / "request.json"), "historical/request")
        if result["request_sha256"] != runner.sha(runner.canonical(expected).encode("utf-8")):
            raise RuntimeError("Historical request hash differs")
        if (str(result["guid"]), str(result["subevent_id"])) != (case["guid"], case["subevent_id"]):
            raise RuntimeError("Historical result identity differs")
        raw = runner.read(member(directory, result["response_file"]))
        if raw["choices"][0]["finish_reason"] != "stop":
            raise RuntimeError("Historical response truncated")
        actors, labels = runner.old.validate(raw["choices"][0]["message"]["content"], case)
        same(result["actors"], actors, "historical/actors")
        same(result["labels"], labels, "historical/labels")
        results.append(result)
    return indices, results


def verify():
    started = time.monotonic()
    if (runner.RUN / "ACTIVE_EXECUTION.lock").exists():
        raise RuntimeError("An execution lock exists; refuse to verify a changing archive")
    before = snapshot()
    manifest = runner.check_frozen()
    lock = runner.verify_confirmation_lock()
    start = runner.read(runner.RUN / "confirm/RUN_STARTED.json")
    if start["confirmation_lock_sha256"] != runner.file_sha(HERE / "confirmation_lock.json"):
        raise RuntimeError("Confirmation was not started with the archived selection lock")
    reports = {}
    count = 0
    with tempfile.TemporaryDirectory(prefix="fehu_intuition100_verify_") as temporary:
        workspace = Path(temporary)
        for stage in ("explore", "confirm"):
            cases = runner.read(runner.FROZEN / f"{stage}_inputs.json")
            raw_results = check_raw(stage, cases)
            count += sum(map(len, raw_results.values()))
            archived = runner.RUN / stage / "evaluation"
            comparison = runner.read(archived / "comparison.json")
            if comparison["primary_method"] != lock["primary_method"] or not comparison["confirmation_primary_unchanged"]:
                raise RuntimeError("Primary method changed in archived report")
            gold_stage = "train" if stage == "explore" else "dev"
            gold_source = runner.ROOT / f"dataset/gold_labels/{gold_stage}/{gold_stage}_human_values.json"
            if runner.file_sha(gold_source) != comparison["source_gold_sha256"]:
                raise RuntimeError("Original gold source hash differs")
            gold_path = workspace / stage / "gold_subset.json"
            runner.subset_gold(cases, gold_source, gold_path)
            same(runner.read(archived / "gold_subset.json"), runner.read(gold_path), f"{stage}/gold_subset")
            combined = {method: runner.fuse_results(cases, raw_results, method) for method in METHODS}
            metrics = {method: check_export(cases, combined[method], archived / method,
                                            workspace / stage / method, gold_path, comparison["metrics"][method])
                       for method in METHODS}
            reports[stage] = {"events": len(cases), "validated_responses": len(cases) * 3,
                              "actor_event_pairs": sum(len(c["candidate_actors"]) for c in cases), "methods": metrics}
            if stage == "confirm":
                indices, previous = historical_results(cases)
                if len(indices) != manifest["historical_intersection_events"]:
                    raise RuntimeError("Historical intersection count differs")
                shared = [cases[i] for i in indices]
                old_archive = archived / "historical_intersection"
                historical = runner.read(old_archive / "comparison.json")
                same(comparison["historical_intersection"], historical, "historical/comparison")
                old_gold = workspace / "historical" / "gold_subset.json"
                runner.subset_gold(shared, gold_source, old_gold)
                same(runner.read(old_archive / "gold_subset.json"), runner.read(old_gold), "historical/gold")
                old_methods = {"historical_max": previous} | {
                    method: [combined[method][i] for i in indices] for method in METHODS}
                reports["historical_intersection"] = {
                    "events": len(shared), "validated_historical_responses": len(previous),
                    "methods": {method: check_export(shared, results, old_archive / method,
                                                      workspace / "historical" / method, old_gold,
                                                      historical["metrics"][method])
                                for method, results in old_methods.items()}}
    if count != 336:
        raise RuntimeError("Expected exactly 336 validated new responses")
    after = snapshot()
    same(before, after, "protected_archive_before_after_sha256")
    runner.check_frozen()
    runner.verify_confirmation_lock()
    return {"passed": True, "verified_at": runner.now(), "seconds": time.monotonic() - started,
            "primary_method": lock["primary_method"], "validated_new_responses": count,
            "official_metric_groups_recomputed": 19, "archive_files_unchanged": len(before),
            "archive_sha256_manifest_digest": hashlib.sha256(runner.canonical(before).encode("utf-8")).hexdigest(),
            "verifier_sha256": runner.file_sha(Path(__file__)),
            "frozen_manifest_sha256": runner.file_sha(runner.FROZEN / "manifest.json"),
            "runner_score_called": False, "api_calls": 0, "credentials_read": False,
            "all_scoring_outputs_were_temporary": True, "reports": reports}


def report_destination(path):
    result = path.resolve()
    for root in (HERE, runner.OLD, runner.ROOT / "dataset", runner.ROOT / "docs"):
        if result == root.resolve() or root.resolve() in result.parents:
            raise ValueError("--out must be outside archived experiments, official data and docs")
    if result.suffix.lower() != ".json" or result.exists():
        raise ValueError("--out must name a new JSON file; overwriting is forbidden")
    return result


CONFIRM_KEYS = {(str(c["guid"]), str(c["subevent_id"]))
                for c in runner.read(runner.FROZEN / "confirm_inputs.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Optional new JSON report outside the archived experiment")
    args = parser.parse_args()
    destination = report_destination(args.out) if args.out else None
    report = verify()
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    summary = {key: value for key, value in report.items() if key != "reports"}
    if destination:
        summary["report_written"] = str(destination)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
