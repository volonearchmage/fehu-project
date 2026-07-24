#!/usr/bin/env python3
"""E3a analysis — three-way comparison of the frozen Liu baseline, the
completed E1 run, and this E3a run, using the unchanged official evaluator
plus the Phase-0 group/target machinery (imported, not re-implemented).

E3a outputs article-level predictions directly (like E1), so this is the
same structure as analyze_e2.py — no unit_support histogram (that belongs to
the Task-2-based E3 only).

Usage: python analyze_e3a.py <e3a_run_ts>
Reads:  RH_test/E3a_task1_only_subevent/runs/<e3a_run_ts>/pred_task1{a,b}.json
        RH_test/E1_fewshot_repair/runs/20260722_152456/pred_task1{a,b}.json
        output/task1/runs/dev_deepseek_..._targeted_more_shot_balanced.../  (frozen Liu)
Writes: comparison CSV/JSON into the E3a run dir. Stdlib only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
# Reuse the verified E1 analysis helpers verbatim.
sys.path.insert(0, str(BASE / "RH_test" / "E1_fewshot_repair" / "scripts"))
sys.path.insert(0, str(BASE / "new_check" / "phase0" / "scripts"))

from analyze_e1 import (  # noqa: E402  (system_row, macro_prf, constants)
    system_row, BASELINE_DIR, GOLD, TARGETS, EXPECTED_BASELINE_1B_MICRO,
)
from phase0_lib import fmt, gold_support, write_csv  # noqa: E402
from evaluation import parse_task1a, parse_task1b  # noqa: E402

E1_RUN = (BASE / "RH_test" / "E1_fewshot_repair" / "runs" / "20260722_152456")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: analyze_e3a.py <e3a_run_ts>")
    e3a = HERE.parent / "runs" / sys.argv[1]
    for f in ("pred_task1a.json", "pred_task1b.json"):
        if not (e3a / f).is_file():
            sys.exit(f"ABORT: missing {e3a / f}")
        if not (E1_RUN / f).is_file():
            sys.exit(f"ABORT: missing frozen E1 artifact {E1_RUN / f}")

    gold_1a = parse_task1a(str(GOLD))
    gold_1b = parse_task1b(str(GOLD))
    gsup = gold_support(gold_1b)

    base_row, base_counts = system_row(
        "liu_baseline_frozen", BASELINE_DIR / "pred_task1a.json",
        BASELINE_DIR / "pred_task1b.json", gold_1a, gold_1b, gsup)
    if abs(base_row["1b_micro_f1"] - EXPECTED_BASELINE_1B_MICRO) > 0.001:
        sys.exit(f"ABORT: frozen baseline re-eval {base_row['1b_micro_f1']} "
                 f"!= documented {EXPECTED_BASELINE_1B_MICRO}")
    e1_row, e1_counts = system_row(
        "E1_fewshot_repair", E1_RUN / "pred_task1a.json",
        E1_RUN / "pred_task1b.json", gold_1a, gold_1b, gsup)
    e3a_row, e3a_counts = system_row(
        "E3a_task1_only_subevent", e3a / "pred_task1a.json",
        e3a / "pred_task1b.json", gold_1a, gold_1b, gsup)

    def delta(name, hi, lo):
        d = {"system": name}
        for k in hi:
            if k == "system":
                continue
            if isinstance(hi[k], (int, float)):
                d[k] = round(hi[k] - lo[k], 4)
        return d

    rows = [base_row, e1_row, e3a_row,
            delta("delta_E3a_minus_E1", e3a_row, e1_row),
            delta("delta_E3a_minus_baseline", e3a_row, base_row)]
    write_csv(e3a / "comparison_liu_e1_e3a.csv", rows, list(base_row.keys()))

    per_target = []
    for cls in TARGETS:
        b, e1c, e3ac = base_counts[cls], e1_counts[cls], e3a_counts[cls]
        per_target.append({
            "class_key": cls, "support": gsup.get(cls, 0),
            "liu_tp": b["tp"], "liu_fp": b["fp"],
            "e1_tp": e1c["tp"], "e1_fp": e1c["fp"],
            "e3a_tp": e3ac["tp"], "e3a_fp": e3ac["fp"],
            "delta_tp_e3a_vs_e1": e3ac["tp"] - e1c["tp"],
            "delta_fp_e3a_vs_e1": e3ac["fp"] - e1c["fp"],
        })
    write_csv(e3a / "per_target_18_comparison.csv", per_target,
              list(per_target[0].keys()))

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
