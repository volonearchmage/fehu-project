#!/usr/bin/env python3
"""Score one fusion cell dir (pred_task1a/1b.json) with the official evaluator.

No E5 frozen-baseline dependencies (the frozen E1 run and TARGETS_JSON are not
present on this machine). Writes <cell>/metrics.json in the E7 layout.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from evaluation import (  # noqa: E402
    parse_task1a, parse_task1b, evaluate, l1_dir_universe, l2_universe,
    direction_reverse_rate_gold_excl,
)

GOLD_1B = ROOT / "dataset/gold_labels/dev/dev_human_values.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    ap.add_argument("--run_dir", type=Path, required=True)
    args = ap.parse_args()

    p1b = args.run_dir / "pred_task1b.json"
    p1a = args.run_dir / "pred_task1a.json"
    if not p1b.is_file() or not p1a.is_file():
        sys.exit(f"ABORT: missing predictions in {args.run_dir}")

    g1b = parse_task1b(str(GOLD_1B))
    g1a = parse_task1a(str(GOLD_1B))
    r1b = evaluate(g1b, parse_task1b(str(p1b)), l1_dir_universe())
    r1a = evaluate(g1a, parse_task1a(str(p1a)), l2_universe())
    drr, rev, den, amb = direction_reverse_rate_gold_excl(
        g1b, parse_task1b(str(p1b)))

    report = {
        "cell": args.cell,
        "task1b": r1b,
        "task1a": r1a,
        "drr": {"drr": drr, "reversals": rev, "denominator": den,
                "ambiguous_gold": amb},
    }
    (args.run_dir / "metrics.json").write_text(json.dumps(report, indent=2))
    t = r1b
    print(f"{args.cell}: 1b micro {t['micro_f1']:.4f} "
          f"(P {t['micro_precision']:.4f} R {t['micro_recall']:.4f}) "
          f"macro {t['macro_f1']:.4f} | 1a micro {r1a['micro_f1']:.4f} "
          f"macro {r1a['macro_f1']:.4f} | DRR {drr:.4f}")


if __name__ == "__main__":
    main()
