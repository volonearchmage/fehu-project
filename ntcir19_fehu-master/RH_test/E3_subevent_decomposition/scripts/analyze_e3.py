#!/usr/bin/env python3
"""E3 analysis — three-way comparison of the frozen Liu baseline, the
completed E1 run, and this E3 run, using the unchanged official evaluator
plus the Phase-0 group/target machinery (imported, not re-implemented).
Also summarizes E3's unit_support metadata (how many subevents back each
predicted 1b label) for the E4 verifier design.

Usage: python analyze_e3.py <e3_run_ts>
Reads:  RH_test/E3_subevent_decomposition/runs/<e3_run_ts>/pred_task1{a,b}.json
        RH_test/E3_subevent_decomposition/runs/<e3_run_ts>/unit_support.json
        RH_test/E1_fewshot_repair/runs/20260722_152456/pred_task1{a,b}.json
        output/task1/runs/dev_deepseek_..._targeted_more_shot_balanced.../  (frozen Liu)
Writes: comparison CSV/JSON into the E3 run dir. Stdlib only.
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
        sys.exit("usage: analyze_e3.py <e3_run_ts>")
    e3 = HERE.parent / "runs" / sys.argv[1]
    for f in ("pred_task1a.json", "pred_task1b.json"):
        if not (e3 / f).is_file():
            sys.exit(f"ABORT: missing {e3 / f}")
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
    e3_row, e3_counts = system_row(
        "E3_subevent_decomposition", e3 / "pred_task1a.json",
        e3 / "pred_task1b.json", gold_1a, gold_1b, gsup)

    def delta(name, hi, lo):
        d = {"system": name}
        for k in hi:
            if k == "system":
                continue
            if isinstance(hi[k], (int, float)):
                d[k] = round(hi[k] - lo[k], 4)
        return d

    rows = [base_row, e1_row, e3_row,
            delta("delta_E3_minus_E1", e3_row, e1_row),
            delta("delta_E3_minus_baseline", e3_row, base_row)]
    write_csv(e3 / "comparison_liu_e1_e3.csv", rows, list(base_row.keys()))

    per_target = []
    for cls in TARGETS:
        b, e1c, e3c = base_counts[cls], e1_counts[cls], e3_counts[cls]
        per_target.append({
            "class_key": cls, "support": gsup.get(cls, 0),
            "liu_tp": b["tp"], "liu_fp": b["fp"],
            "e1_tp": e1c["tp"], "e1_fp": e1c["fp"],
            "e3_tp": e3c["tp"], "e3_fp": e3c["fp"],
            "delta_tp_e3_vs_e1": e3c["tp"] - e1c["tp"],
            "delta_fp_e3_vs_e1": e3c["fp"] - e1c["fp"],
        })
    write_csv(e3 / "per_target_18_comparison.csv", per_target,
              list(per_target[0].keys()))

    # ---- unit-support histogram: TP vs FP by number of supporting subevents
    support_file = e3 / "unit_support.json"
    if support_file.is_file():
        with open(support_file, encoding="utf-8") as f:
            all_support = json.load(f)
        pred_1b = parse_task1b(str(e3 / "pred_task1b.json"))
        hist = {}
        for (guid, actor), labels in pred_1b.items():
            for lab in labels:  # evaluator label form "direction:l1"
                n = len(all_support.get(guid, {}).get(f"{lab}@{actor}", []))
                gold_labels = gold_1b.get((guid, actor), set())
                kind = "tp" if lab in gold_labels else "fp"
                bucket = hist.setdefault(n, {"support_units": n, "tp": 0, "fp": 0})
                bucket[kind] += 1
        hrows = [hist[k] for k in sorted(hist)]
        for r in hrows:
            tot = r["tp"] + r["fp"]
            r["precision"] = round(r["tp"] / tot, 4) if tot else 0.0
        write_csv(e3 / "unit_support_histogram.csv", hrows,
                  ["support_units", "tp", "fp", "precision"])
        print("unit-support histogram (1b): "
              + json.dumps(hrows))

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
