#!/usr/bin/env python3
"""E2 analysis — three-way comparison of the frozen Liu baseline, the
completed E1 run, and this E2 run, using the unchanged official evaluator
plus the Phase-0 group/target machinery (imported, not re-implemented).

Usage: python analyze_e2.py <e2_run_ts>
Reads:  RH_test/E2_prompt_bias_control/runs/<e2_run_ts>/pred_task1{a,b}.json
        RH_test/E1_fewshot_repair/runs/20260722_152456/pred_task1{a,b}.json
        output/task1/runs/dev_deepseek_..._targeted_more_shot_balanced.../  (frozen Liu)
Writes: comparison CSV/JSON into the E2 run dir. Stdlib only.
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
        sys.exit("usage: analyze_e2.py <e2_run_ts>")
    e2 = HERE.parent / "runs" / sys.argv[1]
    for f in ("pred_task1a.json", "pred_task1b.json"):
        if not (e2 / f).is_file():
            sys.exit(f"ABORT: missing {e2 / f}")
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
    e2_row, e2_counts = system_row(
        "E2_prompt_bias_control", e2 / "pred_task1a.json",
        e2 / "pred_task1b.json", gold_1a, gold_1b, gsup)

    def delta(name, hi, lo):
        d = {"system": name}
        for k in hi:
            if k == "system":
                continue
            if isinstance(hi[k], (int, float)):
                d[k] = round(hi[k] - lo[k], 4)
        return d

    rows = [base_row, e1_row, e2_row,
            delta("delta_E2_minus_E1", e2_row, e1_row),
            delta("delta_E2_minus_baseline", e2_row, base_row)]
    write_csv(e2 / "comparison_liu_e1_e2.csv", rows, list(base_row.keys()))

    per_target = []
    for cls in TARGETS:
        b, e1c, e2c = base_counts[cls], e1_counts[cls], e2_counts[cls]
        per_target.append({
            "class_key": cls, "support": gsup.get(cls, 0),
            "liu_tp": b["tp"], "liu_fp": b["fp"],
            "e1_tp": e1c["tp"], "e1_fp": e1c["fp"],
            "e2_tp": e2c["tp"], "e2_fp": e2c["fp"],
            "delta_tp_e2_vs_e1": e2c["tp"] - e1c["tp"],
            "delta_fp_e2_vs_e1": e2c["fp"] - e1c["fp"],
        })
    write_csv(e2 / "per_target_18_comparison.csv", per_target,
              list(per_target[0].keys()))

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
