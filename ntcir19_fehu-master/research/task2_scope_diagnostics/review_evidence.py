"""Offline summaries of existing prompt caches and published v2 review tables.

No model imports, network, raw gold, credentials, or inference. Outputs are new.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import statistics

PROJECT = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prompt = PROJECT / "research/task2_prompt_baseline_v1"
    snapshot = PROJECT / "output/task2_scope_diagnostics/review_20261105/source_snapshot"
    files = sorted((prompt / "runs/full/cases").glob("*/result.json"))
    results = [read_json(p) for p in files]
    assert len(results) == 508, "This review is bound to the stopped 508-event run"
    assert len({(r["guid"], str(r["subevent_id"])) for r in results}) == len(results)
    assert all("reasoning_tokens" in r["usage"].get("completion_tokens_details", {}) for r in results)
    completion = sum(r["usage"]["completion_tokens"] for r in results)
    reasoning = [r["usage"]["completion_tokens_details"]["reasoning_tokens"] for r in results]
    rows = csv_rows(prompt / "subset_evaluation_completed/per_actor_event_metrics.csv")
    assert len(rows) == 1328
    cardinality = lambda value: len([v for v in value.split(";") if v])
    tp, fp, fn = (sum(int(r[k]) for r in rows) for k in ("tp", "fp", "fn"))
    assert (tp, fp, fn) == (597, 2701, 384)
    prompt_summary = dict(
        events=len(results), candidates=len(rows), completion_tokens=completion,
        reasoning_tokens=sum(reasoning), visible_answer_tokens=completion-sum(reasoning),
        reasoning_fraction=sum(reasoning)/completion,
        mean_reasoning_tokens=statistics.mean(reasoning), median_reasoning_tokens=statistics.median(reasoning),
        median_seconds=statistics.median(r["seconds"] for r in results),
        tp=tp, fp=fp, fn=fn,
        gold_cardinality=dict(sorted(Counter(cardinality(r["gold"]) for r in rows).items())),
        prediction_cardinality=dict(sorted(Counter(cardinality(r["predicted"]) for r in rows).items())),
        empty_gold_false_positives=sum(int(r["fp"]) for r in rows if not r["gold"]),
        perfect_filter_oracle_f1=2*tp/(2*tp+fn),
        caveat="Existing nonrandom DEV subset; oracle is diagnostic, not achievable or expected performance; token summary covers successful responses only.",
        result_file_sha256={p.parent.name: digest(p) for p in files},
    )
    model_summary = {}
    for method in ("T", "J", "S"):
        path = snapshot / f"{method}_per_label_predictions.csv"
        labels = csv_rows(path)
        assert len(labels) == 108
        active = sorted((r for r in labels if int(r["predicted_positives"]) > 0),
                        key=lambda r: int(r["predicted_positives"]), reverse=True)
        supported = [r for r in labels if int(r["tune_support"]) > 0]
        assert len(supported) == 86
        model_summary[method] = dict(
            predicted_classes=len(active), correct_classes=sum(int(r["tp"]) > 0 for r in labels),
            supported_tune_classes=len(supported),
            macro_ap_supported=sum(float(r["ap"]) for r in supported)/len(supported),
            constant_score_perclass_ap_mean=sum(int(r["tune_support"])/3843 for r in supported)/len(supported),
            top_predicted_labels=active[:5], source_sha256=digest(path),
        )
    report = dict(
        date_jst="2026-11-05", offline_only=True, new_inference_calls=0,
        v2_source=read_json(snapshot / "SOURCE.json"), prompt=prompt_summary, v2=model_summary,
        source_sha256={str(p.relative_to(PROJECT)): digest(p) for p in (
            prompt / "subset_evaluation_completed/per_actor_event_metrics.csv",
            prompt / "subset_evaluation_completed/metrics_official.json",
            prompt / "runs/full/run_config.json", Path(__file__),
        )},
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps(dict(events=len(results), reasoning_fraction=report["prompt"]["reasoning_fraction"],
                         predicted_classes={k: v["predicted_classes"] for k, v in model_summary.items()})))


if __name__ == "__main__":
    main()
