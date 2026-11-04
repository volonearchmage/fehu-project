#!/usr/bin/env python3
"""E7 statistical validation — paired article-level bootstrap (10k resamples).

For each system pair (A, B): resample the 177 dev articles with replacement,
recompute Task-1b micro-F1 for both systems on the resample, record the
delta. Reports the 95% CI of the delta and P(delta <= 0). Also reports each
system's absolute micro-F1 CI and, against the externally reported Liu-best
constant (0.5657), the fraction of resamples clearing it.

Usage:
  python bootstrap_e7.py --system NAME=pred_task1b.json [...] \
      --pairs A:B [...] --n 10000 --out <json path>
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "RH_test/E5_deberta_auxiliary_fusion/scripts"))
from fusion_lib import load_task1b  # noqa: E402

GOLD = ROOT / "dataset/gold_labels/dev/dev_human_values.json"
LIU_REPORTED = 0.5657


def per_article_counts(gold, pred):
    """{guid: [tp, fp, fn]} aggregated over the article's actors."""
    out = defaultdict(lambda: [0, 0, 0])
    for key in set(gold) | set(pred):
        g = gold.get(key, set())
        p = pred.get(key, set())
        c = out[key[0]]
        c[0] += len(g & p)
        c[1] += len(p - g)
        c[2] += len(g - p)
    return dict(out)


def f1_of(counts, guids):
    tp = fp = fn = 0
    for g in guids:
        c = counts.get(g)
        if c:
            tp += c[0]; fp += c[1]; fn += c[2]
    if tp == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    return 2 * prec * rec / (prec + rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", action="append", required=True,
                    help="NAME=path/to/pred_task1b.json")
    ap.add_argument("--pairs", nargs="*", default=[],
                    help="A:B pairs for paired deltas (A minus B)")
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    gold = load_task1b(GOLD)
    systems = {}
    for spec in args.system:
        name, _, path = spec.partition("=")
        systems[name] = per_article_counts(gold, load_task1b(Path(path)))
    all_guids = sorted({k[0] for k in gold})
    print(f"{len(all_guids)} articles, {len(systems)} systems, "
          f"{args.n} resamples")

    rng = random.Random(args.seed)
    resamples = [[rng.choice(all_guids) for _ in all_guids]
                 for _ in range(args.n)]

    report = {"n_resamples": args.n, "seed": args.seed,
              "liu_reported_constant": LIU_REPORTED, "systems": {}, "pairs": {}}
    dists = {}
    for name, counts in systems.items():
        vals = sorted(f1_of(counts, r) for r in resamples)
        dists[name] = vals
        report["systems"][name] = {
            "point": round(f1_of(counts, all_guids), 4),
            "ci95": [round(vals[int(0.025 * args.n)], 4),
                     round(vals[int(0.975 * args.n)], 4)],
            "frac_above_liu_reported": round(
                sum(v > LIU_REPORTED for v in vals) / args.n, 4),
        }
        print(f"{name}: point {report['systems'][name]['point']} "
              f"CI95 {report['systems'][name]['ci95']} "
              f"P(>{LIU_REPORTED}) = "
              f"{report['systems'][name]['frac_above_liu_reported']}")

    for pair in args.pairs:
        a, _, b = pair.partition(":")
        deltas = sorted(f1_of(systems[a], r) - f1_of(systems[b], r)
                        for r in resamples)
        report["pairs"][pair] = {
            "point_delta": round(f1_of(systems[a], all_guids)
                                 - f1_of(systems[b], all_guids), 4),
            "ci95": [round(deltas[int(0.025 * args.n)], 4),
                     round(deltas[int(0.975 * args.n)], 4)],
            "p_delta_le_0": round(sum(d <= 0 for d in deltas) / args.n, 4),
        }
        print(f"{pair}: delta {report['pairs'][pair]['point_delta']} "
              f"CI95 {report['pairs'][pair]['ci95']} "
              f"P(<=0) = {report['pairs'][pair]['p_delta_le_0']}")

    args.out.write_text(json.dumps(report, indent=2))
    print(f"[done] -> {args.out}")


if __name__ == "__main__":
    main()
