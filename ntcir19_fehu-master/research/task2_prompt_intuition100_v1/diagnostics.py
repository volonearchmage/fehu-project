"""Offline input representativeness and paired article-cluster bootstrap.

No credentials, network, model imports, sampling changes, or rule selection.
The bootstrap describes article sampling uncertainty in the observed subset;
it is not a design-exact full-DEV confidence interval or a repeat-run estimate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_hash(text):
    # Exact content, with no semantic or whitespace normalization.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_key(case):
    return str(case["guid"]), str(case["subevent_id"])


def load_cases(path):
    rows = read(path)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty list of input cases or articles")
    if "candidate_actors" in rows[0]:
        cases = rows
    else:
        cases = []
        for article in rows:
            actors = [{"actor": str(actor_id), "name": str(name)}
                      for item in article["actors"] for name, actor_id in item.items()]
            for event in article["subevents"]:
                cases.append({"guid": str(article["guid"]), "subevent_id": str(event["id"]),
                              "subevent": event["subevent"], "candidate_actors": actors,
                              "article_background": {"title": article.get("title", ""),
                                                     "content": article["content"]}})
    keys = [event_key(c) for c in cases]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate event keys")
    for case in cases:
        actors = [str(a["actor"]) for a in case["candidate_actors"]]
        if len(actors) != len(set(actors)):
            raise ValueError("Duplicate candidate actor IDs")
    return cases


def quantile(values, q):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def distribution(values):
    return {"n": len(values), "min": min(values) if values else None,
            "mean": statistics.mean(values) if values else None,
            "p25": quantile(values, .25), "median": quantile(values, .5),
            "p75": quantile(values, .75), "p90": quantile(values, .9),
            "max": max(values) if values else None}


def summarize_inputs(cases, old_keys, train_hashes, train_normalized_hashes):
    by_article = defaultdict(list)
    for case in cases:
        by_article[str(case["guid"])].append(case)
    overlapping = {g for g, group in by_article.items()
                   if body_hash(group[0]["article_background"]["content"]) in train_hashes}
    normalized_overlapping = {g for g, group in by_article.items()
                   if body_hash(" ".join(group[0]["article_background"]["content"].split())) in train_normalized_hashes}
    historical = [c for c in cases if event_key(c) in old_keys]
    return {
        "events": len(cases), "articles": len(by_article),
        "actor_event_pairs": sum(len(c["candidate_actors"]) for c in cases),
        "actor_count_per_event": distribution([len(c["candidate_actors"]) for c in cases]),
        "actor_count_histogram": dict(sorted(Counter(str(len(c["candidate_actors"])) for c in cases).items())),
        "subevent_character_length": distribution([len(c["subevent"]) for c in cases]),
        "article_character_length_event_weighted": distribution([len(c["article_background"]["content"]) for c in cases]),
        "article_character_length_unique_articles": distribution([len(cs[0]["article_background"]["content"]) for cs in by_article.values()]),
        "observed_events_per_article": distribution([len(cs) for cs in by_article.values()]),
        "historical_completed_intersection": {"events": len(historical),
            "articles": len({c["guid"] for c in historical}),
            "actor_event_pairs": sum(len(c["candidate_actors"]) for c in historical)},
        "exact_train_body_overlap": {"articles": len(overlapping),
            "events": sum(len(by_article[g]) for g in overlapping),
            "actor_event_pairs": sum(len(c["candidate_actors"]) for g in overlapping for c in by_article[g])},
        "whitespace_normalized_train_body_overlap": {"normalization": "single spaces between content.split() tokens",
            "articles": len(normalized_overlapping),
            "events": sum(len(by_article[g]) for g in normalized_overlapping),
            "actor_event_pairs": sum(len(c["candidate_actors"]) for g in normalized_overlapping for c in by_article[g])},
    }


def representativeness(sample, population, old_keys, train_articles):
    population_by_key = {event_key(c): c for c in population}
    for case in sample:
        expected = population_by_key.get(event_key(case))
        if expected is None:
            raise ValueError("Sample event is outside the declared population")
        for field in ("subevent", "candidate_actors", "article_background"):
            if case[field] != expected[field]:
                raise ValueError("Sample input content differs from population")
    train_hashes = {body_hash(a["content"]) for a in train_articles}
    train_normalized_hashes = {body_hash(" ".join(a["content"].split())) for a in train_articles}
    sample_stats = summarize_inputs(sample, old_keys, train_hashes, train_normalized_hashes)
    population_stats = summarize_inputs(population, old_keys, train_hashes, train_normalized_hashes)
    sample_by_article = Counter(str(c["guid"]) for c in sample)
    population_by_article = Counter(str(c["guid"]) for c in population)
    sample_stats["fully_observed_articles"] = sum(n == population_by_article[g] for g, n in sample_by_article.items())
    return {
        "input_only": True, "sample": sample_stats, "population": population_stats,
        "event_coverage_fraction": len(sample) / len(population),
        "article_coverage_fraction": sample_stats["articles"] / population_stats["articles"],
        "plan_change": "Before any model calls, replace the earlier proposed 100-of-508-successes sample with a fixed hash-selected 100 from all 1526 supplied DEV events. The old completion pool was nonrandom and favored completed calls. Historical results are compared only on the resulting intersection, never by replacing sampled events.",
        "interpretation": [
            "This describes observed input coverage; similar marginal distributions do not prove representativeness.",
            "A hash ranking with a fixed pre-outcome seed is a reproducible pseudorandom selection; do not reroll after viewing inputs or labels.",
            "Under genuine equal-probability event sampling, expanded TP/FP/FN totals are unbiased; their F1 ratio is not exactly unbiased.",
            "100 events do not cover all 177 articles or guarantee rare-label coverage. This is not a full-DEV result.",
            "Exact TRAIN body overlap is an input diagnostic, not evidence that a particular model memorized those articles.",
        ],
    }


def parse_predictions(path, cases, *, gold=False):
    """Read official Task2b format, preserving legal empty candidate sets."""
    wanted = {event_key(c) for c in cases}
    candidate_keys = {(str(c["guid"]), str(c["subevent_id"]), str(a["actor"]))
                      for c in cases for a in c["candidate_actors"]}
    labels = {key: set() for key in candidate_keys}
    covered = set()
    for row in read(path):
        guid = str(row["guid"])
        for event in row.get("subevents_human_values", []):
            key = guid, str(event["subevent_id"])
            if key not in wanted:
                if gold:
                    continue
                raise ValueError("Predictions contain an event outside the frozen sample")
            if key in covered:
                raise ValueError("Duplicate event in prediction/gold export")
            covered.add(key)
            for value in event.get("subevent_human_values", []):
                candidate = (*key, str(value["actor"]))
                if candidate not in labels:
                    raise ValueError("Unknown candidate actor in prediction/gold")
                label = str(value["direction"]), str(value["l1_value"])
                if label[0] not in ("0", "1") or label[1] not in {str(i) for i in range(54)}:
                    raise ValueError("Invalid directed value")
                if label in labels[candidate]:
                    raise ValueError("Duplicate directed value")
                labels[candidate].add(label)
    # Official gold is sparse: omitted events/actors have empty gold label sets.
    # Predictions must still explicitly cover every supplied event; omission there
    # could represent failed inference and must never be scored as empty.
    if not gold and covered != wanted:
        raise ValueError("Incomplete event export; failures cannot be scored as empty predictions")
    return labels


def scores(counts):
    tp, fp, fn = counts
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "micro_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def paired_cluster_bootstrap(cases, gold, predictions, *, replicates=2000, seed=20261105):
    if replicates < 1:
        raise ValueError("replicates must be positive")
    expected = {(str(c["guid"]), str(c["subevent_id"]), str(a["actor"]))
                for c in cases for a in c["candidate_actors"]}
    if set(gold) != expected or any(set(pred) != expected for pred in predictions.values()):
        raise ValueError("Bootstrap inputs must have identical complete candidate coverage")
    guids = sorted({key[0] for key in expected})
    if len(guids) < 2:
        raise ValueError("At least two article clusters required")
    counts = {name: {g: [0, 0, 0] for g in guids} for name in predictions}
    for name, pred in predictions.items():
        for key in sorted(expected):
            g, p = gold[key], pred[key]
            for i, n in enumerate((len(g & p), len(p - g), len(g - p))):
                counts[name][key[0]][i] += n
    point = {name: scores([sum(c[i] for c in by_guid.values()) for i in range(3)])
             for name, by_guid in counts.items()}
    draws = {name: [] for name in predictions}
    rng = random.Random(seed)
    for _ in range(replicates):
        weights = Counter(rng.choices(guids, k=len(guids)))
        for name in predictions:
            aggregate = [sum(counts[name][g][i] * weight for g, weight in weights.items()) for i in range(3)]
            draws[name].append(scores(aggregate)["micro_f1"])
    pairs = {}
    for a, b in itertools.combinations(sorted(predictions), 2):
        differences = [x - y for x, y in zip(draws[a], draws[b])]
        pairs[f"{a}_minus_{b}"] = {"delta_micro_f1": point[a]["micro_f1"] - point[b]["micro_f1"],
            "percentile_95_interval": [quantile(differences, .025), quantile(differences, .975)]}
    return {"seed": seed, "replicates": replicates, "article_clusters": len(guids),
            "method": "paired nonparametric article-cluster percentile bootstrap, resampling observed articles with all their sampled events",
            "point": point, "micro_f1_intervals": {n: [quantile(v, .025), quantile(v, .975)] for n, v in draws.items()},
            "paired_differences_descriptive": pairs,
            "limitations": ["Partial article clusters from event sampling: this is not a design-exact full-DEV confidence interval.",
                            "Does not measure stochastic model rerun variance, repair prior DEV exposure, or guarantee rare-label coverage.",
                            "All pairwise intervals are descriptive and unadjusted for multiplicity; do not select a new primary using confirmation scores.",
                            "Official prediction format omits empty actor rows; runner actor-coverage validation must pass before exporting."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=HERE / "frozen/confirm_inputs.json")
    parser.add_argument("--population", type=Path, default=HERE / "frozen/population_dev_inputs.json")
    parser.add_argument("--historical-keys", type=Path, default=HERE / "frozen/historical_completed_keys.json")
    parser.add_argument("--train-input", type=Path, default=ROOT / "dataset/train/train_event_base.json")
    parser.add_argument("--prediction", action="append", default=[], metavar="METHOD=PATH")
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sample, population = load_cases(args.sample), load_cases(args.population)
    old_keys = {event_key(c) for c in read(args.historical_keys)}
    report = {"representativeness": representativeness(sample, population, old_keys, read(args.train_input))}
    sources = [args.sample, args.population, args.historical_keys, args.train_input, Path(__file__)]
    if args.prediction:
        if not args.gold:
            raise ValueError("--gold required for bootstrap")
        gold = parse_predictions(args.gold, sample, gold=True)
        predictions = {}
        for item in args.prediction:
            name, path = item.split("=", 1)
            if not name or name in predictions:
                raise ValueError("Prediction names must be nonempty and unique")
            predictions[name] = parse_predictions(path, sample)
            sources.append(Path(path))
        report["bootstrap"] = paired_cluster_bootstrap(sample, gold, predictions, replicates=args.replicates, seed=args.seed)
        sources.append(args.gold)
    elif args.gold:
        raise ValueError("--gold without predictions is unnecessary; input diagnostics never read gold")
    report["source_sha256"] = {str(p): digest(p) for p in sources}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({"written": str(args.out), "sample_events": len(sample), "sample_articles": len({c['guid'] for c in sample}),
                      "bootstrap_included": "bootstrap" in report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
