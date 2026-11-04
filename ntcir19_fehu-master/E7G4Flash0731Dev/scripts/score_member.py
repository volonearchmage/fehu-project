#!/usr/bin/env python3
"""Score E7G4 member runs with the official evaluator only (no E5 extras,
no frozen-baseline dependency). Writes a compact per-member JSON report.

Usage:
  python score_member.py --name E1 --run_dir RH_test/E1_fewshot_repair/runs/<ts> \
      --out E7G4Flash0731Dev/report/members.json  [--append]

The --append flag adds to an existing report file instead of creating a new one.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from evaluation import (  # noqa: E402  (official scorer, never modified)
    parse_task1a, parse_task1b, evaluate, l1_dir_universe, l2_universe,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr,
)

GOLD_1B = ROOT / "dataset/gold_labels/dev/dev_human_values.json"


def score_one(pred_dir: Path) -> dict:
    p1b = pred_dir / "pred_task1b.json"
    p1a = pred_dir / "pred_task1a.json"
    if not p1b.is_file() or not p1a.is_file():
        raise SystemExit(f"ABORT: missing predictions in {pred_dir}")
    gold = json.loads(GOLD_1B.read_text())
    g1b = parse_task1b(str(GOLD_1B))
    g1a = parse_task1a(str(GOLD_1B))
    r1b = evaluate(g1b, parse_task1b(str(p1b)), l1_dir_universe())
    r1a = evaluate(g1a, parse_task1a(str(p1a)), l2_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(g1b,
                                                          parse_task1b(str(p1b)))
    # distinct predicted classes
    preds = parse_task1b(str(p1b))
    classes = sorted({lab for labs in preds.values() for lab in labs})
    n_labels = sum(len(v) for v in preds.values())
    return {
        "task1b_micro_f1": round(r1b["micro_f1"], 4),
        "task1b_micro_p": round(r1b["micro_precision"], 4),
        "task1b_micro_r": round(r1b["micro_recall"], 4),
        "task1b_macro_f1": round(r1b["macro_f1"], 4),
        "task1a_micro_f1": round(r1a["micro_f1"], 4),
        "task1a_macro_f1": round(r1a["macro_f1"], 4),
        "drr": round(drr, 4),
        "drr_reversals": rev,
        "distinct_classes_1b": len(classes),
        "labels_1b": n_labels,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--run_dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    entry = {"name": args.name, "run_dir": str(args.run_dir),
             **score_one(args.run_dir)}
    report = {}
    if args.append and args.out.is_file():
        report = json.loads(args.out.read_text())
    report.setdefault("members", []).append(entry)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    e = entry
    print(f"{args.name}: 1b micro {e['task1b_micro_f1']} "
          f"(P {e['task1b_micro_p']} R {e['task1b_micro_r']}) "
          f"macro {e['task1b_macro_f1']} | 1a micro {e['task1a_micro_f1']} "
          f"macro {e['task1a_macro_f1']} | DRR {e['drr']} "
          f"| classes {e['distinct_classes_1b']}")


if __name__ == "__main__":
    main()
