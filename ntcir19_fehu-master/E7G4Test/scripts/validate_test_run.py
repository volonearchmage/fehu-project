#!/usr/bin/env python3
"""E7G4Test — schema validation + statistics for the final test predictions.

Checks (all hard requirements; any failure => exit 1):
  1. pred files are valid JSON lists in the official schema
  2. every test GUID present exactly once, no extra GUIDs
  3. every actor id belongs to the article's official actor list
  4. l1 in 0..53, direction in {0,1}, l2 in 0..19; no duplicate labels
  5. Task-1a == deterministic L2 projection of Task-1b (recomputed here)
  6. per-member cache health: no article cached as an empty list without a
     documented confirmation (list supplied via --confirmed_empty)

Writes validation/validation_report.json and validation/stats.json.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEST_ARTICLES = ROOT / "dataset/test/test_article_event_base.json"
HV_DIR = ROOT / "dataset/hv_categories"

problems = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not ok:
        problems.append({"check": name, "detail": detail})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", type=Path, required=True,
                    help="dir containing final pred_task1a/b.json")
    ap.add_argument("--member_cache", action="append", default=[],
                    help="NAME=path to a member run's article cache json")
    ap.add_argument("--confirmed_empty", action="append", default=[],
                    help="NAME:guid entries confirmed empty by re-fetch")
    ap.add_argument("--out_dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    arts = json.loads(TEST_ARTICLES.read_text())
    test_guids = [str(a["guid"]) for a in arts]
    actors_of = {str(a["guid"]): {str(aid) for d in a.get("actors", [])
                                  for aid in d.values()} for a in arts}
    n_actors_total = sum(len(v) for v in actors_of.values())

    l1_names = json.loads((HV_DIR / "human_value_level1_values.json").read_text())
    l2_names = json.loads((HV_DIR / "human_value_level2_values.json").read_text())
    l1_to_l2_raw = json.loads((HV_DIR / "level_1_to_level_2.json").read_text())[
        "level_1_to_level_2"]
    l1_to_l2 = {str(l1_names[a]): str(l2_names[b])
                for a, b in l1_to_l2_raw.items()}

    p1a = json.loads((args.run_dir / "pred_task1a.json").read_text())
    p1b = json.loads((args.run_dir / "pred_task1b.json").read_text())

    # 1+2: schema + guid coverage
    for name, data in (("task1a", p1a), ("task1b", p1b)):
        check(f"{name}: JSON list", isinstance(data, list))
        got = [str(it.get("guid")) for it in data]
        check(f"{name}: every test GUID exactly once, no extras",
              got == test_guids or sorted(got) == sorted(test_guids),
              f"{len(got)} entries vs {len(test_guids)} test articles")
        for it in data:
            if set(it.keys()) != {"guid", "article_human_values"}:
                check(f"{name}: entry keys official", False,
                      f"{it.get('guid')}: {sorted(it.keys())}")
                break
        else:
            check(f"{name}: entry keys official "
                  f"(guid, article_human_values)", True)

    # 3+4: actor ids, label ranges, duplicates
    bad_actor = bad_label = dup = 0
    seen_b = defaultdict(set)
    for it in p1b:
        g = str(it["guid"])
        for hv in it["article_human_values"]:
            keys_ok = set(hv.keys()) == {"actor", "l1_value", "direction"}
            a, l1, d = str(hv.get("actor")), str(hv.get("l1_value")), str(hv.get("direction"))
            if not keys_ok or a not in actors_of.get(g, set()):
                bad_actor += 1
                continue
            if not (l1.isdigit() and 0 <= int(l1) <= 53 and d in ("0", "1")):
                bad_label += 1
                continue
            if (a, d, l1) in seen_b[g]:
                dup += 1
            seen_b[g].add((a, d, l1))
    check("task1b: all actors official, in-range labels, no duplicates",
          bad_actor == 0 and bad_label == 0 and dup == 0,
          f"bad_actor={bad_actor} bad_label={bad_label} dup={dup}")

    seen_a = defaultdict(set)
    bad_a = dup_a = 0
    for it in p1a:
        g = str(it["guid"])
        for hv in it["article_human_values"]:
            keys_ok = set(hv.keys()) == {"actor", "l2_value"}
            a, l2 = str(hv.get("actor")), str(hv.get("l2_value"))
            if not keys_ok or a not in actors_of.get(g, set()) \
                    or not (l2.isdigit() and 0 <= int(l2) <= 19):
                bad_a += 1
                continue
            if (a, l2) in seen_a[g]:
                dup_a += 1
            seen_a[g].add((a, l2))
    check("task1a: all actors official, in-range l2, no duplicates",
          bad_a == 0 and dup_a == 0, f"bad={bad_a} dup={dup_a}")

    # 5: 1a is the deterministic projection of 1b
    proj = defaultdict(set)
    for it in p1b:
        g = str(it["guid"])
        for hv in it["article_human_values"]:
            proj[g].add((str(hv["actor"]), l1_to_l2[str(hv["l1_value"])]))
    match = all(proj.get(g, set()) == seen_a.get(g, set())
                for g in set(list(proj) + list(seen_a)))
    check("task1a == L2 projection of task1b", match)

    # 6: member cache health
    confirmed = set(args.confirmed_empty)
    for spec in args.member_cache:
        name, _, path = spec.partition("=")
        cache = json.loads(Path(path).read_text())
        check(f"{name}: cache covers all {len(test_guids)} test articles",
              set(cache.keys()) >= set(test_guids),
              f"{len(cache)} cached")
        empty = [g for g in test_guids if not cache.get(g)]
        unconfirmed = [g for g in empty if f"{name}:{g}" not in confirmed]
        check(f"{name}: no unconfirmed empty-response articles",
              not unconfirmed, f"empty={empty[:5]}")

    # ---- statistics -------------------------------------------------------
    n_labels_b = sum(len(v) for v in seen_b.values())
    labels_per_actor = Counter()
    per_actor = defaultdict(set)
    class_counter = Counter()
    dir_counter = Counter()
    for g, cells in seen_b.items():
        for (a, d, l1) in cells:
            per_actor[(g, a)].add((d, l1))
            class_counter[f"{d}:{l1}"] += 1
            dir_counter["aligned(1)" if d == "1" else "contradictory(0)"] += 1
    actors_with_preds = len(per_actor)
    lpa = [len(v) for v in per_actor.values()]
    stats = {
        "articles": len(test_guids),
        "official_actors_total": n_actors_total,
        "actors_with_predictions": actors_with_preds,
        "actors_without_predictions": n_actors_total - actors_with_preds,
        "task1b_labels": n_labels_b,
        "task1a_labels": sum(len(v) for v in seen_a.values()),
        "labels_per_predicted_actor": {
            "mean": round(sum(lpa) / len(lpa), 2),
            "min": min(lpa), "max": max(lpa)},
        "distinct_1b_classes_of_108": len(class_counter),
        "distinct_l1_values_of_54": len({c.split(":")[1]
                                         for c in class_counter}),
        "direction_distribution": dict(dir_counter),
        "top10_classes": class_counter.most_common(10),
    }
    (args.out_dir / "stats.json").write_text(json.dumps(stats, indent=2))
    (args.out_dir / "validation_report.json").write_text(json.dumps({
        "run_dir": str(args.run_dir),
        "n_problems": len(problems), "problems": problems,
        "confirmed_empty": sorted(confirmed)}, indent=2))
    print(json.dumps(stats, indent=2))
    if problems:
        print(f"\n{len(problems)} VALIDATION PROBLEM(S)")
        sys.exit(1)
    print("\nALL VALIDATION CHECKS PASSED")


if __name__ == "__main__":
    main()
