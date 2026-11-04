#!/usr/bin/env python3
"""Phase 3 — analysis over all completed phase-3 runs (auto-discovered from
new_check/phase3/runs/<cell>_seed<seed>/), same metric conventions and
readouts as Phase 2. Emits per-run metrics, per-target-per-run detail,
per-cell aggregates, and paired per-seed contrasts for every cell pair that
shares the full seed set. Stdlib only.
"""

from __future__ import annotations

import itertools
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "phase0" / "scripts"))
sys.path.insert(0, str(HERE.parents[1] / "phase1" / "scripts"))

from phase0_lib import (  # noqa: E402
    ALL_108, Phase0InputError, fmt, gold_support, group_metrics,
    per_label_counts, rp, reversals_by_gold_class, write_csv,
)
from analyze_baseline_probabilities import per_target_stats  # noqa: E402
from evaluation import (  # noqa: E402
    parse_task1b, direction_reverse_rate_gold_excl, safe_div, f1_from_pr,
)

PHASE3 = HERE.parent
RUNS = PHASE3 / "runs"
LOGS = PHASE3 / "logs"
OUT = PHASE3 / "outputs"
CFG = json.loads((HERE.parents[1] / "phase0" / "configs"
                  / "phase0_config.json").read_text())
TARGETS = json.loads((HERE.parents[1] / "phase0" / "outputs"
                      / "run_manifest.json").read_text())["targets_18"]

KEY_METRICS = ["all108_micro_f1", "all108_macro_f1_gold",
               "target18_micro_f1", "target18_macro_f1_gold",
               "target18_tp", "nontarget90_macro_f1_gold",
               "drr", "mean_target_auc", "mean_target_oracle_f1",
               "distinct_pred_classes"]


def best_epoch_from_log(cell, seed):
    log_path = LOGS / f"train_{cell}_seed{seed}.log"
    if not log_path.is_file():
        raise Phase0InputError(f"missing training log {log_path}")
    saved = [int(m.group(1)) for m in re.finditer(
        r"=== Epoch (\d+)/\d+ ===(?:(?!=== Epoch).)*?checkpoint saved",
        log_path.read_text(), re.S)]
    if not saved:
        raise Phase0InputError(f"no saved checkpoint in log {log_path}")
    return saved[-1]


def analyze_run(cell, seed, gold, gsup):
    run = RUNS / f"{cell}_seed{seed}"
    pred = parse_task1b(str(run / "output" / "pred_task1b.json"))
    counts = per_label_counts(gold, pred)
    nontargets = [l for l in ALL_108 if l not in set(TARGETS)]
    g_t = group_metrics(counts, TARGETS, gsup)
    g_n = group_metrics(counts, nontargets, gsup)
    g_a = group_metrics(counts, ALL_108, gsup)
    drr, rev, _, _ = direction_reverse_rate_gold_excl(gold, pred)
    rev_cls, _ = reversals_by_gold_class(gold, pred)

    prob_file = run / "probabilities.jsonl"
    if not prob_file.is_file():
        raise Phase0InputError(f"missing probabilities for {cell}_seed{seed}; "
                               f"run export_probs_phase3.py first")
    kept = []
    for line in open(prob_file):
        r = json.loads(line)
        kept.append(((str(r["guid"]), str(r["actor_id"])),
                     r["probabilities_108"]))
    tstats = {cls: per_target_stats(kept, gold, cls) for cls in TARGETS}

    row = {"cell": cell, "seed": seed,
           "best_epoch": best_epoch_from_log(cell, seed)}
    for prefix, gm in (("all108", g_a), ("target18", g_t),
                       ("nontarget90", g_n)):
        row[f"{prefix}_micro_precision"] = fmt(gm["micro_precision"])
        row[f"{prefix}_micro_recall"] = fmt(gm["micro_recall"])
        row[f"{prefix}_micro_f1"] = fmt(gm["micro_f1"])
        row[f"{prefix}_macro_p_gold"] = fmt(gm["macro_precision_gold_supported"])
        row[f"{prefix}_macro_r_gold"] = fmt(gm["macro_recall_gold_supported"])
        row[f"{prefix}_macro_f1_gold"] = fmt(gm["macro_f1_gold_supported"])
    row.update({
        "target18_tp": g_t["sum_tp"], "target18_fp": g_t["sum_fp"],
        "target18_fn": g_t["sum_fn"],
        "target18_reversals": sum(rev_cls.get(c, 0) for c in TARGETS),
        "drr": fmt(drr), "reversals": rev,
        "distinct_pred_classes": sum(
            1 for l in ALL_108 if counts[l]["tp"] + counts[l]["fp"] > 0),
        "mean_target_auc": fmt(sum(t["auc"] for t in tstats.values()) / 18),
        "mean_target_oracle_f1": fmt(
            sum(t["oracle_f1"] for t in tstats.values()) / 18),
        "targets_with_tp": sum(1 for c in TARGETS if counts[c]["tp"] > 0),
        "targets_auc_above_0.6": sum(
            1 for t in tstats.values() if t["auc"] > 0.6),
    })
    per_target = []
    for cls in TARGETS:
        c = counts[cls]
        p = safe_div(c["tp"], c["tp"] + c["fp"])
        r = safe_div(c["tp"], c["tp"] + c["fn"])
        t = tstats[cls]
        per_target.append({
            "cell": cell, "seed": seed, "class_key": cls,
            "dev_gold_support": gsup.get(cls, 0),
            "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
            "precision": fmt(p), "recall": fmt(r),
            "f1": fmt(f1_from_pr(p, r)),
            "auc": t["auc"], "oracle_f1": t["oracle_f1"],
            "median_prob_gold": t["median_prob_gold"],
            "reversals_on_gold": rev_cls.get(cls, 0),
        })
    return row, per_target


def main():
    gold = parse_task1b(str(rp(CFG["gold_dev_labels"])))
    gsup = gold_support(gold)
    OUT.mkdir(parents=True, exist_ok=True)

    discovered = sorted(
        (m.group(1), int(m.group(2)))
        for d in RUNS.iterdir() if d.is_dir()
        for m in [re.fullmatch(r"([A-Za-z0-9]+)_seed(\d+)", d.name)] if m)
    if not discovered:
        raise Phase0InputError("no runs found under phase3/runs/")

    run_rows, target_rows = [], []
    for cell, seed in discovered:
        row, trs = analyze_run(cell, seed, gold, gsup)
        run_rows.append(row)
        target_rows.extend(trs)
    write_csv(OUT / "per_run_metrics.csv", run_rows, list(run_rows[0].keys()))
    write_csv(OUT / "per_target_per_run.csv", target_rows,
              list(target_rows[0].keys()))

    cells = sorted({r["cell"] for r in run_rows})
    seeds_by_cell = {c: sorted(r["seed"] for r in run_rows if r["cell"] == c)
                     for c in cells}
    metrics = [k for k in run_rows[0]
               if isinstance(run_rows[0][k], (int, float)) and k != "seed"]
    agg_rows = []
    for c in cells:
        rows = [r for r in run_rows if r["cell"] == c]
        agg = {"cell": c, "n_seeds": len(rows),
               "seeds": " ".join(map(str, seeds_by_cell[c]))}
        for m in metrics:
            vals = [r[m] for r in rows]
            agg[f"{m}_mean"] = round(statistics.mean(vals), 4)
            agg[f"{m}_sd"] = (round(statistics.stdev(vals), 4)
                              if len(vals) > 1 else 0.0)
        agg_rows.append(agg)
    write_csv(OUT / "cell_aggregates.csv", agg_rows, list(agg_rows[0].keys()))

    by = {(r["cell"], r["seed"]): r for r in run_rows}
    delta_rows = []
    for hi, lo in itertools.permutations(cells, 2):
        shared = sorted(set(seeds_by_cell[hi]) & set(seeds_by_cell[lo]))
        if len(shared) < 2 or hi < lo:
            continue
        for m in KEY_METRICS:
            ds = [by[(hi, s)][m] - by[(lo, s)][m] for s in shared]
            delta_rows.append({
                "contrast": f"{hi}-{lo}", "metric": m,
                "seeds": " ".join(map(str, shared)),
                **{f"delta_seed{s}": round(d, 4)
                   for s, d in zip(shared, ds)},
                "mean_delta": round(statistics.mean(ds), 4),
                "sd_delta": round(statistics.stdev(ds), 4),
                "sign_consistent": len({d > 0 for d in ds if d != 0}) <= 1,
            })
    if delta_rows:
        fields = sorted({k for r in delta_rows for k in r},
                        key=lambda k: (k not in ("contrast", "metric", "seeds"), k))
        for r in delta_rows:
            for f in fields:
                r.setdefault(f, "")
        write_csv(OUT / "paired_contrasts.csv", delta_rows, fields)

    summary = {a["cell"]: {m + "_mean": a[m + "_mean"] for m in
                           ["all108_micro_f1", "all108_macro_f1_gold",
                            "target18_micro_f1", "target18_macro_f1_gold",
                            "target18_tp", "mean_target_auc",
                            "mean_target_oracle_f1", "drr", "best_epoch"]}
               for a in agg_rows}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
