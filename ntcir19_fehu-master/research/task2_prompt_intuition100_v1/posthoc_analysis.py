"""Offline post-hoc diagnostics after complete, frozen Task2 confirmation.

Never changes prompts, primary method, thresholds, predictions, or API state.
Requires all 300 confirmation responses and completed official evaluations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("task2_input_diagnostics", HERE / "diagnostics.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
METHODS = ("A", "B", "C", "VETO", "CONSENSUS", "UNION")


def flatten(labels):
    return {(*key, direction, value) for key, values in labels.items() for direction, value in values}


def counts_for(gold, pred):
    return d.scores((len(gold & pred), len(pred - gold), len(gold - pred)))


def error_overlap(errors):
    union = set().union(*errors.values())
    membership = Counter("".join(name for name in ("A", "B", "C") if label in errors[name]) for label in union)
    pairs = {}
    for a, b in itertools.combinations(("A", "B", "C"), 2):
        inter, either = errors[a] & errors[b], errors[a] | errors[b]
        pairs[a + "_and_" + b] = {"intersection": len(inter), "union": len(either),
            "jaccard": len(inter) / len(either) if either else None,
            "fraction_of_" + a: len(inter) / len(errors[a]) if errors[a] else None,
            "fraction_of_" + b: len(inter) / len(errors[b]) if errors[b] else None}
    return {"definition": "Each item is an exact (guid, subevent, actor, direction, L1 value) tuple.",
            "totals": {name: len(values) for name, values in errors.items()},
            "exact_membership_pattern_counts": {name: membership[name] for name in ("A", "B", "C", "AB", "AC", "BC", "ABC")},
            "all_three_shared": len(errors["A"] & errors["B"] & errors["C"]), "pairs": pairs,
            "interpretation": "Shared errors are observed dependence, not proof of its cause or a formal correlation estimate."}


def additions_and_removals(before, after, gold):
    added, removed = after - before, before - after
    return {"added_tp": len(added & gold), "added_fp": len(added - gold),
            "removed_tp": len(removed & gold), "removed_fp": len(removed - gold),
            "net_tp": len(after & gold) - len(before & gold),
            "net_fp": len(after - gold) - len(before - gold)}


def analyze(cases, gold, predictions):
    candidates = sorted(gold)
    if any(set(p) != set(gold) for p in predictions.values()):
        raise ValueError("Incomplete candidate coverage")
    flat_gold = flatten(gold)
    flat = {name: flatten(p) for name, p in predictions.items()}
    if flat["VETO"] != flat["A"] & (flat["B"] | flat["C"]):
        raise ValueError("VETO does not match its frozen rule")
    if flat["CONSENSUS"] != (flat["A"] & flat["B"]) | (flat["A"] & flat["C"]) | (flat["B"] & flat["C"]):
        raise ValueError("CONSENSUS does not match its frozen rule")
    if flat["UNION"] != flat["A"] | flat["B"] | flat["C"]:
        raise ValueError("UNION does not match its fixed diagnostic rule")
    empty = {key for key in candidates if not gold[key]}
    summaries = {}
    rows = []
    for name, pred in predictions.items():
        empty_fp = sum(len(pred[key]) for key in empty)
        summaries[name] = {
            **counts_for(flat_gold, flat[name]),
            "gold_directed_labels": len(flat_gold), "predicted_directed_labels": len(flat[name]),
            "gold_count_per_actor_event": dict(sorted(Counter(str(len(gold[k])) for k in candidates).items())),
            "predicted_count_per_actor_event": dict(sorted(Counter(str(len(pred[k])) for k in candidates).items())),
            "joint_gold_pred_count": dict(sorted(Counter(f"gold={len(gold[k])},pred={len(pred[k])}" for k in candidates).items())),
            "empty_gold_candidates": len(empty),
            "empty_gold_candidates_predicted_nonempty": sum(bool(pred[k]) for k in empty),
            "empty_gold_false_positive_labels": empty_fp,
            "empty_gold_candidate_false_alarm_rate": sum(bool(pred[k]) for k in empty) / len(empty) if empty else None,
            "nonempty_gold_false_positive_labels": sum(len(pred[k] - gold[k]) for k in candidates if k not in empty),
            "gold_supported_directed_classes": len({(x[3], x[4]) for x in flat_gold}),
            "predicted_directed_classes": len({(x[3], x[4]) for x in flat[name]}),
        }
    for key in candidates:
        rows.append({"guid": key[0], "subevent_id": key[1], "actor": key[2], "gold_count": len(gold[key]),
            "methods": {name: {"predicted_count": len(pred[key]), **counts_for(gold[key], pred[key])}
                        for name, pred in predictions.items()}})
    covered = flat["UNION"] & flat_gold
    recall = len(covered) / len(flat_gold) if flat_gold else 0.0
    return {
        "events": len(cases), "articles": len({c["guid"] for c in cases}), "actor_event_pairs": len(candidates),
        "method_summaries": summaries, "actor_event_records": rows,
        "exact_error_overlap": {"false_positives": error_overlap({n: flat[n] - flat_gold for n in ("A", "B", "C")}),
                                "false_negatives": error_overlap({n: flat_gold - flat[n] for n in ("A", "B", "C")})},
        "veto_relative_to_A": {**additions_and_removals(flat["A"], flat["VETO"], flat_gold),
            "tp_retention_fraction": len(flat["VETO"] & flat_gold) / len(flat["A"] & flat_gold) if flat["A"] & flat_gold else None,
            "fp_removal_fraction": len((flat["A"] - flat["VETO"]) - flat_gold) / len(flat["A"] - flat_gold) if flat["A"] - flat_gold else None},
        "consensus_relative_to_veto": {**additions_and_removals(flat["VETO"], flat["CONSENSUS"], flat_gold),
            "interpretation": "CONSENSUS adds B-and-C agreement omitted by A; it is a superset of VETO."},
        "consensus_relative_to_A": additions_and_removals(flat["A"], flat["CONSENSUS"], flat_gold),
        "union_oracle_candidate_recall": {"gold_labels": len(flat_gold), "gold_covered_by_union": len(covered),
            "gold_absent_from_union": len(flat_gold - flat["UNION"]), "candidate_recall_ceiling": recall,
            "oracle_filtered_f1_upper_bound": 2 * recall / (1 + recall) if recall else 0.0,
            "not_an_executable_method": True,
            "interpretation": "An oracle with gold access deletes every UNION false positive and keeps every UNION true positive. This measures the directed-label candidate ceiling, not achieved verifier performance or an expected future score."},
    }


def check_complete():
    evaluation = HERE / "run/confirm/evaluation"
    comparison_path = evaluation / "comparison.json"
    if not comparison_path.is_file() or not (HERE / "run/confirm/EXECUTION_FINISHED.json").is_file():
        raise RuntimeError("Confirmation has not fully completed and been officially scored")
    cases = d.load_cases(HERE / "frozen/confirm_inputs.json")
    if len(cases) != 100:
        raise RuntimeError("Expected the fixed 100-event confirmation set")
    for case in cases:
        for variant in ("A", "B", "C"):
            result = d.read(HERE / "run/confirm/cases" / f'{case["sample_index"]:03d}' / variant / "result.json")
            if (str(result["guid"]), str(result["subevent_id"])) != d.event_key(case):
                raise RuntimeError("Confirmation identity mismatch")
    comparison = d.read(comparison_path)
    lock_path = HERE / "confirmation_lock.json"
    lock = d.read(lock_path)
    start = d.read(HERE / "run/confirm/RUN_STARTED.json")
    if start["confirmation_lock_sha256"] != d.digest(lock_path):
        raise RuntimeError("Primary lock differs from confirmation-start lock")
    if comparison["stage"] != "confirm" or comparison["events"] != 100 or comparison["primary_method"] != lock["primary_method"]:
        raise RuntimeError("Confirmation report or primary method mismatch")
    for method in METHODS:
        verification = d.read(evaluation / method / "verification.json")
        if not verification["passed"] or verification["prediction_sha256"]["task2b"] != d.digest(evaluation / method / "pred_task2b.json"):
            raise RuntimeError("Prediction export changed since official verification")
    return cases, comparison, lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "run/confirm/evaluation/posthoc/analysis.json")
    args = parser.parse_args()
    cases, comparison, lock = check_complete()
    evaluation = HERE / "run/confirm/evaluation"
    gold_path = evaluation / "gold_subset.json"
    gold = d.parse_predictions(gold_path, cases, gold=True)
    gold_present = {(str(row["guid"]), str(event["subevent_id"]))
                    for row in d.read(gold_path) for event in row.get("subevents_human_values", [])}
    omitted_gold_events = sorted({d.event_key(case) for case in cases} - gold_present)
    paths = {method: evaluation / method / "pred_task2b.json" for method in METHODS}
    predictions = {name: d.parse_predictions(path, cases) for name, path in paths.items()}
    result = analyze(cases, gold, predictions)
    for method in METHODS:
        if abs(result["method_summaries"][method]["micro_f1"] - comparison["metrics"][method]["task2b"]["micro_f1"]) > 1e-12:
            raise RuntimeError("Post-hoc counts differ from official score")
    result.update({"analysis_type": "post-hoc explanation of already frozen results; not a new selection or validation stage",
                   "frozen_primary_method": lock["primary_method"], "primary_unchanged": True,
                   "sparse_official_gold_omitted_events": [{"guid": g, "subevent_id": s} for g, s in omitted_gold_events],
                   "offline_analysis_repair": "Initial analysis parser required complete gold event rows and stopped before writing output. Repaired to match the official sparse-gold convention: omitted gold events/actors have empty sets. Prediction coverage remains strict. No predictions, model requests, official scores or primary method changed.",
                   "limitations": ["Same-model prompts share errors; observed overlap does not establish why errors occurred.",
                                   "100 sampled events are not full DEV or an unseen test set; prior DEV analyses exist.",
                                   "Do not change the frozen primary, prompts, gate, or thresholds based on these findings."]})
    inputs_path = HERE / "input_representativeness.json"
    if inputs_path.exists():
        result["input_representativeness"] = d.read(inputs_path)["representativeness"]
    sources = [Path(__file__), HERE / "diagnostics.py", HERE / "frozen/confirm_inputs.json", HERE / "confirmation_lock.json",
               evaluation / "comparison.json", gold_path, *paths.values()]
    if inputs_path.exists():
        sources.append(inputs_path)
    result["source_sha256"] = {str(path): d.digest(path) for path in sources}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"out": str(args.out), "primary_unchanged": result["frozen_primary_method"],
                      "events": result["events"], "actor_event_pairs": result["actor_event_pairs"],
                      "veto_relative_to_A": result["veto_relative_to_A"],
                      "consensus_relative_to_veto": result["consensus_relative_to_veto"],
                      "union_oracle_candidate_recall": result["union_oracle_candidate_recall"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
