"""Offline fit-frequency baseline on the frozen tune split; no model or API."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, out):
    paths = {
        "inputs": root / "dataset/train/train_event_base.json",
        "gold": root / "dataset/gold_labels/train/train_human_values.json",
        "split": root / "docs/2026-11-03_Task2_组会准备/evidence/grouped_train_split.json",
        "evaluator": root / "research/task2_prompt_baseline_v1/evaluator/official_original.py",
        "provenance": root / "research/task2_prompt_baseline_v1/evaluator/provenance.json",
    }
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    split = read(paths["split"])
    guids = {part: set(split["guids"][part]) for part in ("fit", "tune")}
    assert guids["fit"].isdisjoint(guids["tune"])
    allowed = guids["fit"] | guids["tune"]
    inputs = {r["guid"]: r for r in read(paths["inputs"]) if r["guid"] in allowed}
    assert set(inputs) == allowed
    labels = {f"{d}:{v}" for d in (0, 1) for v in range(54)}
    targets = {part: {} for part in guids}
    part_for = {guid: part for part in guids for guid in guids[part]}
    for guid, row in inputs.items():
        actors = [str(next(iter(a.values()))) for a in row["actors"]]
        events = [str(e["id"]) for e in row["subevents"]]
        assert len(set(actors)) == len(actors) and len(set(events)) == len(events)
        for event, actor in itertools.product(events, actors):
            targets[part_for[guid]][guid, event, actor] = set()
    seen = set()
    empty_rows = Counter()
    # TRAIN is a single source file. Only selected fit/tune records are inspected.
    for row in read(paths["gold"]):
        guid = row["guid"]
        if guid not in allowed:
            continue
        assert guid not in seen
        seen.add(guid)
        part = part_for[guid]
        for event in row["subevents_human_values"]:
            sid = str(event["subevent_id"])
            values = event["subevent_human_values"]
            if sid == "" and not values:
                empty_rows[part] += 1
                continue
            for value in values:
                key = (guid, sid, str(value["actor"]))
                label = f'{value["direction"]}:{value["l1_value"]}'
                assert key in targets[part] and label in labels
                assert label not in targets[part][key], "Duplicate directed label"
                targets[part][key].add(label)
    assert seen == allowed
    counts = {part: Counter(lab for labs in rows.values() for lab in labs)
              for part, rows in targets.items()}
    nfit, ntune = len(targets["fit"]), len(targets["tune"])
    positives = sum(counts["tune"].values())
    assert (nfit, ntune, sum(counts["fit"].values()), positives) == (23783, 3843, 14624, 2312)
    grouped = defaultdict(list)
    for label in labels:
        grouped[counts["fit"][label]].append(label)
    tp = predicted = 0
    ap = 0.0
    best = {"threshold": 2.0, "micro_f1": 0.0, "tp": 0, "fp": 0,
            "fn": positives, "predicted_class_count": 0}
    curve = []
    for count in sorted(grouped, reverse=True):
        group = grouped[count]
        added_tp = sum(counts["tune"][lab] for lab in group)
        tp += added_tp
        predicted += ntune * len(group)
        ap += (added_tp / positives) * (tp / predicted)
        row = {"threshold": count / nfit, "micro_f1": 2 * tp / (predicted + positives),
               "tp": tp, "fp": predicted - tp, "fn": positives - tp,
               "predicted_class_count": predicted // ntune}
        curve.append(row)
        if (row["micro_f1"], row["threshold"]) > (best["micro_f1"], best["threshold"]):
            best = row
    # Independent tie-grouped ranking over all 3843*108 binary positions.
    ranked = sorted((counts["fit"][lab], int(lab in labs))
                    for labs in targets["tune"].values() for lab in labels)
    n = hits = 0
    expanded_ap = 0.0
    for _, block in itertools.groupby(reversed(ranked), key=lambda x: x[0]):
        block = list(block)
        gain = sum(y for _, y in block)
        n += len(block)
        hits += gain
        expanded_ap += (gain / positives) * hits / n
    assert abs(ap - expanded_ap) < 1e-12
    assert sha(paths["evaluator"]) == read(paths["provenance"])["original_sha256"]
    spec = importlib.util.spec_from_file_location("frozen_official_evaluator", paths["evaluator"])
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    predicted_labels = {lab for lab in labels if counts["fit"][lab] / nfit >= best["threshold"]}
    predictions = {key: predicted_labels.copy() for key in targets["tune"]}
    official = evaluator.evaluate(targets["tune"], predictions, evaluator.l1_dir_universe())
    assert evaluator.micro_counts(targets["tune"], predictions, set(predictions)) == (best["tp"], best["fp"], best["fn"])
    assert abs(official["micro_f1"] - best["micro_f1"]) < 1e-12
    result = {
        "description": "Each directed class gets its fit frequency for every tune candidate; one global threshold selected on tune.",
        "source_sha256": {k: sha(p) for k, p in paths.items()},
        "script_sha256": sha(Path(__file__)),
        "fit_candidates": nfit, "fit_positives": sum(counts["fit"].values()),
        "tune_articles": len(guids["tune"]), "tune_candidates": ntune,
        "tune_binary_positions": ntune * 108, "tune_positives": positives,
        "flat_score_micro_ap": positives / (ntune * 108),
        "fit_frequency_micro_ap": ap, "selected_threshold": best,
        "frozen_official_task2b": official,
        "predicted_labels_at_selected_threshold": sorted(predicted_labels),
        "fit_class_counts": {lab: counts["fit"][lab] for lab in sorted(labels)},
        "threshold_curve": curve,
        "ignored_empty_gold_rows": dict(empty_rows),
        "holdout_dev_test_scores_computed": False, "paid_api_calls": 0,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"output": str(out), "fit_frequency_micro_ap": ap,
                      "flat_score_micro_ap": result["flat_score_micro_ap"],
                      "selected_threshold": best, "official": official}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.project_root, args.out)
