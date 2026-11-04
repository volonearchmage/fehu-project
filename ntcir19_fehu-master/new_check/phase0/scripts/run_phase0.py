#!/usr/bin/env python3
"""Phase-0 validation runner.

Usage (from anywhere):
    python ntcir19_fehu-master/new_check/phase0/scripts/run_phase0.py

Reads only existing repository artifacts (paths in configs/phase0_config.json),
writes all results to new_check/phase0/outputs/ and a log to
new_check/phase0/logs/. Never modifies anything outside new_check/.

No training, no model inference, no network access.
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from phase0_lib import (  # noqa: E402
    ROOT, ALL_108, Phase0InputError, class_index, index_class, fmt,
    group_metrics, gold_support, load_json, per_label_counts, rp,
    reversals_by_gold_class, sha256_file, write_csv,
)
from evaluation import (  # noqa: E402
    parse_task1b, evaluate, l1_dir_universe, direction_reverse_rate_gold_excl,
    safe_div, f1_from_pr,
)

PHASE0 = HERE.parent
OUT = PHASE0 / "outputs"
LOGS = PHASE0 / "logs"
CONFIG_PATH = PHASE0 / "configs" / "phase0_config.json"

LOG_LINES: list[str] = []
HUMAN_CHECKS: list[dict] = []


def log(msg: str):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    LOG_LINES.append(line)


def human_check(path: str, uncertainty: str, why_unresolvable: str,
                what_to_inspect: str, blocks: str):
    HUMAN_CHECKS.append(dict(path=path, uncertainty=uncertainty,
                             why=why_unresolvable, inspect=what_to_inspect,
                             blocks=blocks))
    log(f"HUMAN_CHECK_REQUIRED registered: {uncertainty[:100]}")


# ======================================================================
# Step 1 — targets
# ======================================================================
def verify_targets(cfg) -> list[str]:
    alloc = load_json(cfg["targets_source"])
    if not alloc.get("frozen"):
        raise Phase0InputError("targets_source is not marked frozen")
    targets = [t["class_key"] for t in alloc["targets"]]
    if len(targets) != 18 or len(set(targets)) != 18:
        raise Phase0InputError(f"expected 18 unique targets, got {targets}")

    # cross-check 1: hybrid run's historical CSV
    import csv as _csv
    with open(rp(cfg["targets_crosscheck_csv"])) as f:
        csv_targets = [r["class_key"] for r in _csv.DictReader(f)]
    if sorted(csv_targets) != sorted(targets):
        raise Phase0InputError(
            f"target mismatch between allocation JSON and hybrid CSV:"
            f" {sorted(set(targets) ^ set(csv_targets))}")

    # cross-check 2: v2 run's own target metrics file
    with open(rp(cfg["v2_target_metrics_crosscheck"])) as f:
        v2_targets = [r["class_key"] for r in _csv.DictReader(f)]
    if sorted(v2_targets) != sorted(targets):
        raise Phase0InputError("target mismatch vs v2 target_label_metrics.csv")

    # verify every target is a valid 108-space label and index round-trips
    for t in targets:
        if t not in l1_dir_universe():
            raise Phase0InputError(f"target {t} not in the 108-label universe")
        assert index_class(class_index(t)) == t
    log(f"targets verified against 3 independent artifacts: {targets}")
    return targets


# ======================================================================
# Step 2 — baseline training-data provenance check
# ======================================================================
def verify_baseline_inputs(cfg):
    """The smoke-run baseline trained on copies under research_ablation_inputs.
    Confirm they are byte-identical in content to the official train files."""
    off_art = load_json(cfg["official_train_articles"])
    off_lab = load_json(cfg["gold_train_labels"])
    cp_art = load_json(cfg["baseline_train_articles_copy"])
    cp_lab = load_json(cfg["baseline_train_labels_copy"])
    same_art = off_art == cp_art
    same_lab = off_lab == cp_lab
    log(f"baseline train copies identical to official? articles={same_art} labels={same_lab}")
    if not (same_art and same_lab):
        human_check(
            cfg["baseline_train_articles_copy"],
            "smoke-run baseline train inputs differ from official train files",
            "content comparison failed; the difference cannot be judged benign automatically",
            "diff the two JSON pairs and decide whether the baseline is a valid official-only anchor",
            "blocks the interpretation of every baseline comparison")
    return same_art and same_lab


# ======================================================================
# Step 3 — per-system parsing, comparability, and metrics
# ======================================================================
def analyze_system(name: str, sc: dict, gold: dict, gsup: dict,
                   targets: list, tol: float):
    pred = parse_task1b(str(rp(sc["pred_task1b"])))

    # ---- comparability audit ------------------------------------------
    gold_guids = {iid[0] for iid in gold}
    pred_guids = {iid[0] for iid in pred}
    unknown_labels = sorted({lab for labs in pred.values() for lab in labs}
                            - l1_dir_universe())
    extra_instances = sorted(set(pred) - set(gold))
    comp = {
        "system": name,
        "pred_path": sc["pred_task1b"],
        "sha256_pred": sha256_file(sc["pred_task1b"])[:16],
        "threshold": sc.get("threshold"),
        "supervision_policy": sc.get("supervision_policy"),
        "training_data": sc.get("training_data"),
        "seed": sc.get("seed"),
        "family": sc.get("family"),
        "probabilities_available": bool(sc.get("probabilities")),
        "n_pred_guids": len(pred_guids),
        "n_gold_guids": len(gold_guids),
        "guids_missing_from_pred": len(gold_guids - pred_guids),
        "n_pred_instances": len(pred),
        "n_pred_instances_not_in_gold": len(extra_instances),
        "n_unknown_labels": len(unknown_labels),
        "n_pred_labels_total": sum(len(v) for v in pred.values()),
    }
    if unknown_labels:
        raise Phase0InputError(
            f"{name}: predictions contain labels outside the 108 universe: "
            f"{unknown_labels[:10]}")

    # ---- official-scorer cross-check ----------------------------------
    official = evaluate(gold, pred, l1_dir_universe())
    drr, rev, denom, ambig = direction_reverse_rate_gold_excl(gold, pred)
    exp = sc.get("expected_1b_micro_f1")
    if exp is not None and abs(official["micro_f1"] - exp) > tol:
        raise Phase0InputError(
            f"{name}: recomputed 1b micro-F1 {official['micro_f1']:.4f} does not "
            f"match the documented value {exp} (tol {tol}); refusing to continue "
            f"with a possibly wrong artifact")
    comp["recomputed_1b_micro_f1"] = round(official["micro_f1"], 6)
    comp["documented_1b_micro_f1"] = exp
    comp["crosscheck_passed"] = True
    log(f"{name}: micro-F1 {official['micro_f1']:.4f} matches documented "
        f"{exp} | DRR {drr:.4f} ({rev}/{denom}, ambiguous {ambig})")

    # ---- per-label counts + groups ------------------------------------
    counts = per_label_counts(gold, pred)
    # internal consistency: micro over ALL_108 must equal official micro
    g_all = group_metrics(counts, ALL_108, gsup)
    assert abs(g_all["micro_f1"] - official["micro_f1"]) < 1e-9
    assert abs(g_all["macro_f1_gold_supported"] - official["macro_f1"]) < 1e-9

    nontargets = [l for l in ALL_108 if l not in set(targets)]
    groups = {
        "target_18": group_metrics(counts, targets, gsup),
        "nontarget_90": group_metrics(counts, nontargets, gsup),
        "all_108": g_all,
    }
    rev_by_class, denom_by_class = reversals_by_gold_class(gold, pred)
    assert sum(rev_by_class.values()) == rev, "reversal attribution mismatch"
    assert sum(denom_by_class.values()) == denom

    return comp, counts, groups, {
        "drr": drr, "reversals": rev, "denominator": denom,
        "ambiguous_excluded": ambig, "rev_by_class": rev_by_class,
        "denom_by_class": denom_by_class,
    }, pred


# ======================================================================
# Step 4 — positive / known-negative / unknown ratios
# ======================================================================
def ratio_analysis(cfg, targets):
    """Reproduce the exact label/mask construction of the trainers (set
    semantics per (guid, actor); official = assume-negative; v2 = masked)."""

    def actor_examples(label_items, sup_map=None):
        """[(guid, actor, positive_class_set, mode, known_neg_set)]"""
        out = []
        for item in label_items:
            guid = str(item["guid"])
            per_actor = defaultdict(set)
            for hv in item.get("article_human_values", []):
                per_actor[str(hv["actor"])].add(f"{hv['direction']}:{hv['l1_value']}")
            sup = (sup_map or {}).get(guid)
            mode = sup["supervision_mode"] if sup else "official"
            kneg = set(sup.get("known_negative", [])) if sup else set()
            for actor, pos in per_actor.items():
                out.append((guid, actor, pos, mode, kneg))
        return out

    official = actor_examples(load_json(cfg["gold_train_labels"]))
    sup_map = load_json(cfg["v2_supervision_map"])
    v2 = actor_examples(load_json(cfg["v2_train_labels"]), sup_map)

    n_official = len(official)
    n_v2 = len(v2)
    n_v2_full = sum(1 for *_, mode, _k in v2 if mode in ("official", "full_multilabel"))
    n_v2_masked = n_v2 - n_v2_full
    log(f"ratio analysis: official examples={n_official}, v2 examples={n_v2} "
        f"(full={n_v2_full}, target_only={n_v2_masked})")

    rows = []
    universe = list(targets) + ["__GLOBAL__"]
    for cls in universe:
        if cls == "__GLOBAL__":
            pos_o = sum(len(p) for _, _, p, _, _ in official)
            slots_o = n_official * 108
            row = {
                "class_key": "GLOBAL_all_108", "l1_name": "(all labels pooled)",
                "official_examples": n_official,
                "pos_official": pos_o,
                "known_neg_official": slots_o - pos_o,
                "ratio_official": f"1:{(slots_o - pos_o) / pos_o:.1f}",
            }
            pos_v = kneg_v = unk_v = 0
            for _, _, p, mode, kn in v2:
                if mode in ("official", "full_multilabel"):
                    pos_v += len(p); kneg_v += 108 - len(p)
                else:
                    pos_v += len(p); kneg_v += len(kn)
                    unk_v += 108 - len(p) - len(kn)
            row.update({
                "v2_pos_total": pos_v, "v2_known_neg": kneg_v,
                "v2_unknown_masked": unk_v,
                "ratio_v2_known": f"1:{kneg_v / pos_v:.1f}",
                "pos_added_full": "", "pos_added_target_only": "",
                "excluded": 0,
            })
        else:
            pos_o = sum(1 for _, _, p, _, _ in official if cls in p)
            row = {
                "class_key": cls, "l1_name": "",
                "official_examples": n_official,
                "pos_official": pos_o,
                "known_neg_official": n_official - pos_o,
                "ratio_official": f"1:{(n_official - pos_o) / max(pos_o, 1):.0f}",
            }
            pos_v = kneg_v = unk_v = 0
            add_full = add_masked = 0
            for guid, _, p, mode, kn in v2:
                is_pos = cls in p
                if mode in ("official", "full_multilabel"):
                    if is_pos:
                        pos_v += 1
                        if mode == "full_multilabel":
                            add_full += 1
                    else:
                        kneg_v += 1
                else:  # target_only
                    if is_pos:
                        pos_v += 1; add_masked += 1
                    elif cls in kn:
                        kneg_v += 1
                    else:
                        unk_v += 1
            row.update({
                "v2_pos_total": pos_v, "v2_known_neg": kneg_v,
                "v2_unknown_masked": unk_v,
                "ratio_v2_known": f"1:{kneg_v / max(pos_v, 1):.0f}",
                "pos_added_full": add_full, "pos_added_target_only": add_masked,
                "excluded": 0,
            })
        rows.append(row)

    l1_names = {v: k for k, v in load_json(cfg["l1_names"]).items()}
    for r in rows:
        if r["class_key"] != "GLOBAL_all_108":
            r["l1_name"] = l1_names.get(r["class_key"].split(":")[1], "?")
    return rows, dict(n_official=n_official, n_v2=n_v2,
                      n_v2_full=n_v2_full, n_v2_target_only=n_v2_masked)


# ======================================================================
# Step 5 — threshold sensitivity (v2 probabilities only)
# ======================================================================
def threshold_analysis(cfg, gold, gsup, targets, v2_pred):
    prob_path = rp(cfg["v2_probabilities_jsonl"])
    rows_raw = [json.loads(l) for l in open(prob_path)]
    gold_iids = set(gold)
    kept, extra = [], []
    for r in rows_raw:
        iid = (str(r["guid"]), str(r["actor_id"]))
        (kept if iid in gold_iids else extra).append((iid, r["probabilities_108"]))
    log(f"probabilities: {len(rows_raw)} rows; {len(kept)} gold instances, "
        f"{len(extra)} non-gold actor rows EXCLUDED from the sweep "
        f"(the frozen v2 prediction file contains gold actors only)")
    if extra:
        human_check(
            cfg["v2_probabilities_jsonl"],
            f"{len(extra)} probability rows belong to dev actors absent from gold "
            f"({[i for i, _ in extra]})",
            "whether a submission-time system would also predict for these actors "
            "is a protocol choice, not derivable from the artifact",
            "confirm that excluding non-gold actors matches the frozen v2 "
            "prediction protocol (it does per src/train_deberta.py build_examples "
            "with DEV_LABELS), and note micro-precision would change if they "
            "were included with non-empty predictions",
            "interpretation only — does not block any Phase-0 metric")

    # validation: threshold 0.30 must reproduce the frozen v2 predictions
    mism = 0
    for iid, probs in kept:
        got = {index_class(i) for i, p in enumerate(probs) if p >= 0.30}
        want = v2_pred.get(iid, set())
        if got != want:
            mism += 1
    if mism:
        raise Phase0InputError(
            f"thresholding exported probabilities at 0.30 fails to reproduce the "
            f"frozen v2 predictions on {mism} instances — index convention or "
            f"artifact mismatch; aborting threshold analysis")
    log("validated: probabilities @0.30 reproduce frozen v2 pred_task1b exactly")

    sweep = []
    for th in cfg["global_thresholds"]:
        pred = {}
        for iid, probs in kept:
            labs = {index_class(i) for i, p in enumerate(probs) if p >= th}
            if labs:
                pred[iid] = labs
        counts = per_label_counts(gold, pred)
        g_t = group_metrics(counts, targets, gsup)
        g_all = group_metrics(counts, ALL_108, gsup)
        drr, rev, denom, _ = direction_reverse_rate_gold_excl(gold, pred)
        distinct = sum(1 for l in ALL_108
                       if counts[l]["tp"] + counts[l]["fp"] > 0)
        sweep.append({
            "threshold": th,
            "all108_micro_p": fmt(g_all["micro_precision"]),
            "all108_micro_r": fmt(g_all["micro_recall"]),
            "all108_micro_f1": fmt(g_all["micro_f1"]),
            "all108_macro_f1_gold": fmt(g_all["macro_f1_gold_supported"]),
            "target18_micro_p": fmt(g_t["micro_precision"]),
            "target18_micro_r": fmt(g_t["micro_recall"]),
            "target18_micro_f1": fmt(g_t["micro_f1"]),
            "target18_macro_p_gold": fmt(g_t["macro_precision_gold_supported"]),
            "target18_macro_r_gold": fmt(g_t["macro_recall_gold_supported"]),
            "target18_macro_f1_gold": fmt(g_t["macro_f1_gold_supported"]),
            "distinct_pred_classes": distinct,
            "drr": fmt(drr), "reversals": rev,
        })

    # per-target oracle thresholds (DEV-TUNED — diagnostic upper bound only)
    og = cfg["oracle_threshold_grid"]
    grid = [round(og["start"] + i * og["step"], 4)
            for i in range(int(round((og["stop"] - og["start"]) / og["step"])) + 1)]
    oracle = []
    for cls in targets:
        ci = class_index(cls)
        best = None
        for th in grid:
            tp = fp = fn = 0
            for iid, probs in kept:
                pos = probs[ci] >= th
                is_gold = cls in gold.get(iid, set())
                if pos and is_gold:
                    tp += 1
                elif pos:
                    fp += 1
                elif is_gold:
                    fn += 1
            p = safe_div(tp, tp + fp)
            r = safe_div(tp, tp + fn)
            f1 = f1_from_pr(p, r)
            if best is None or f1 > best["oracle_f1"]:
                best = dict(class_key=cls, oracle_threshold=th,
                            oracle_precision=fmt(p), oracle_recall=fmt(r),
                            oracle_f1=fmt(f1), tp=tp, fp=fp, fn=fn)
        best["flag"] = "DEV_TUNED_ORACLE_NOT_A_PERFORMANCE_CLAIM"
        # score separability: max prob among gold instances vs frozen 0.3
        gold_probs = sorted((probs[ci] for iid, probs in kept
                             if cls in gold.get(iid, set())), reverse=True)
        best["max_prob_on_gold_instances"] = fmt(gold_probs[0]) if gold_probs else ""
        best["median_prob_on_gold_instances"] = (
            fmt(gold_probs[len(gold_probs) // 2]) if gold_probs else "")
        oracle.append(best)
    return sweep, oracle


# ======================================================================
# main
# ======================================================================
def main():
    started = datetime.datetime.now().isoformat(timespec="seconds")
    cfg = json.loads(CONFIG_PATH.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    targets = verify_targets(cfg)
    baseline_inputs_ok = verify_baseline_inputs(cfg)

    gold = parse_task1b(str(rp(cfg["gold_dev_labels"])))
    gsup = gold_support(gold)
    log(f"gold: {len(gold)} instances, {sum(len(v) for v in gold.values())} labels, "
        f"{sum(1 for l in ALL_108 if gsup.get(l, 0) > 0)} gold-supported classes")

    tol = cfg["micro_f1_crosscheck_tolerance"]
    comp_rows, group_rows, target_rows, err_rows, overall_rows = [], [], [], [], []
    preds = {}

    for name, sc in cfg["systems"].items():
        comp, counts, groups, drr_info, pred = analyze_system(
            name, sc, gold, gsup, targets, tol)
        comp_rows.append(comp)
        preds[name] = (counts, drr_info, pred)

        for gname, gm in groups.items():
            group_rows.append({"system": name, "group": gname,
                               **{k: fmt(v) for k, v in gm.items()}})
        ga = groups["all_108"]
        overall_rows.append({
            "system": name,
            "micro_precision": fmt(ga["micro_precision"]),
            "micro_recall": fmt(ga["micro_recall"]),
            "micro_f1": fmt(ga["micro_f1"]),
            "macro_precision_gold_supported": fmt(ga["macro_precision_gold_supported"]),
            "macro_recall_gold_supported": fmt(ga["macro_recall_gold_supported"]),
            "macro_f1_gold_supported": fmt(ga["macro_f1_gold_supported"]),
            "drr": fmt(drr_info["drr"]),
            "reversals": drr_info["reversals"],
            "drr_denominator": drr_info["denominator"],
            "drr_ambiguous_excluded": drr_info["ambiguous_excluded"],
            "distinct_pred_classes": sum(
                1 for l in ALL_108 if counts[l]["tp"] + counts[l]["fp"] > 0),
        })

        for cls in targets:
            c = counts[cls]
            p = safe_div(c["tp"], c["tp"] + c["fp"])
            r = safe_div(c["tp"], c["tp"] + c["fn"])
            target_rows.append({
                "system": name, "class_key": cls,
                "dev_gold_support": gsup.get(cls, 0),
                "predicted_positives": c["tp"] + c["fp"],
                "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
                "precision": fmt(p), "recall": fmt(r),
                "f1": fmt(f1_from_pr(p, r)),
                "gold_excl_direction_denom": drr_info["denom_by_class"].get(cls, 0),
                "direction_reversals_on_this_gold_class":
                    drr_info["rev_by_class"].get(cls, 0),
            })

        tset = set(targets)
        zero_gold = [l for l in ALL_108 if gsup.get(l, 0) == 0]
        err_rows.append({
            "system": name,
            "fn_target18": sum(counts[l]["fn"] for l in targets),
            "fn_nontarget90": sum(counts[l]["fn"] for l in ALL_108 if l not in tset),
            "fp_target18": sum(counts[l]["fp"] for l in targets),
            "fp_nontarget90_gold_supported": sum(
                counts[l]["fp"] for l in ALL_108
                if l not in tset and gsup.get(l, 0) > 0),
            "fp_on_zero_gold_classes": sum(counts[l]["fp"] for l in zero_gold),
            "reversals_on_target18_gold": sum(
                drr_info["rev_by_class"].get(l, 0) for l in targets),
            "reversals_on_nontarget_gold": drr_info["reversals"] - sum(
                drr_info["rev_by_class"].get(l, 0) for l in targets),
            "reversals_total": drr_info["reversals"],
        })

    # deltas vs baseline for the per-target table
    base = {(r["class_key"]): r for r in target_rows
            if r["system"] == "deberta_baseline"}
    for r in target_rows:
        b = base[r["class_key"]]
        r["delta_tp_vs_baseline"] = r["tp"] - b["tp"]
        r["delta_f1_vs_baseline"] = fmt(r["f1"] - b["f1"])

    ratio_rows, ratio_meta = ratio_analysis(cfg, targets)
    sweep_rows, oracle_rows = threshold_analysis(
        cfg, gold, gsup, targets, preds["augmented_v2"][2])

    # ------------------------------------------------------------- outputs
    write_csv(OUT / "experiment_comparability.csv", comp_rows,
              list(comp_rows[0].keys()))
    write_csv(OUT / "overall_metrics_all_systems.csv", overall_rows,
              list(overall_rows[0].keys()))
    write_csv(OUT / "group_metrics_long.csv", group_rows,
              list(group_rows[0].keys()))
    for gname, fname in [("target_18", "target18_group_metrics.csv"),
                         ("nontarget_90", "nontarget90_group_metrics.csv")]:
        rows = [r for r in group_rows if r["group"] == gname]
        write_csv(OUT / fname, rows, list(rows[0].keys()))
    write_csv(OUT / "per_target_18_metrics.csv", target_rows,
              list(target_rows[0].keys()))
    write_csv(OUT / "pos_neg_ratio_table.csv", ratio_rows,
              list(ratio_rows[0].keys()))
    write_csv(OUT / "threshold_sensitivity_v2.csv", sweep_rows,
              list(sweep_rows[0].keys()))
    write_csv(OUT / "per_target_oracle_thresholds_v2.csv", oracle_rows,
              list(oracle_rows[0].keys()))
    write_csv(OUT / "error_categories.csv", err_rows, list(err_rows[0].keys()))

    # human-check markdown
    hc = ["# HUMAN_CHECK_REQUIRED — Phase 0", "",
          "Items that could not be resolved safely from repository evidence.",
          ""]
    static_items = [
        dict(path="evaluation.py (lines 33–39, 65–81)",
             uncertainty="DRR docstring/variable names call direction '0' aligned, "
                         "while dataset/hv_categories/direction_mapping.json defines "
                         "'1' = aligned. The DRR arithmetic is symmetric, so official "
                         "numbers are unaffected; Phase-0 reversal attribution follows "
                         "direction_mapping.json.",
             why="the naming conflict is in official scorer code, which this project "
                 "never modifies; only the task organizers can say which comment is "
                 "authoritative",
             inspect="confirm with the task documentation that '1'=aligned is the "
                     "intended semantic (all repo experiment reports assume it)",
             blocks="interpretation only — no metric is affected"),
        dict(path="output/research_ablation_smoke_runs/20260704_201355/baseline/",
             uncertainty="no exported dev probabilities exist for the baseline model, "
                         "so threshold sensitivity could only be computed for "
                         "augmented v2",
             why="producing them requires loading the checkpoint and running local "
                 "inference, which Phase 0 is forbidden to do",
             inspect="approve the Phase-1 step: one local inference pass from the "
                     "stored baseline checkpoint to export probabilities",
             blocks="blocks the baseline column of the threshold-sensitivity table "
                    "(the 'was the baseline learning but thresholded away?' question)"),
        dict(path="output/task1/runs/dev_deepseek_.../pred_task1b.json (liu_frozen), "
                  "hybrid H2/H3 prediction files",
             uncertainty="LLM/hybrid systems differ from the DeBERTa runs in far more "
                         "than augmentation (model family, prompt, inference protocol); "
                         "they are included as descriptive context only",
             why="no artifact can make these causally comparable to the "
                 "augmentation question",
             inspect="when discussing with the professor, present LLM/hybrid rows as "
                     "context, never as augmentation evidence",
             blocks="interpretation only"),
    ]
    for it in static_items + HUMAN_CHECKS:
        hc += [f"## {it['uncertainty'][:80]}", "",
               f"- **Path:** `{it['path']}`",
               f"- **Uncertainty:** {it['uncertainty']}",
               f"- **Why not automatically resolvable:** {it['why']}",
               f"- **What to inspect/confirm:** {it['inspect']}",
               f"- **Blocks:** {it['blocks']}", ""]
    (OUT / "HUMAN_CHECK_REQUIRED.md").write_text("\n".join(hc))

    # manifest
    manifest = {
        "phase": 0,
        "started": started,
        "finished": datetime.datetime.now().isoformat(timespec="seconds"),
        "config": str(CONFIG_PATH.relative_to(ROOT)),
        "project_root": str(ROOT),
        "inputs_sha256": {
            k: sha256_file(v) for k, v in {
                "gold_dev_labels": cfg["gold_dev_labels"],
                "gold_train_labels": cfg["gold_train_labels"],
                "targets_source": cfg["targets_source"],
                "v2_supervision_map": cfg["v2_supervision_map"],
                "v2_train_labels": cfg["v2_train_labels"],
                "v2_probabilities_jsonl": cfg["v2_probabilities_jsonl"],
                **{f"pred__{n}": s["pred_task1b"]
                   for n, s in cfg["systems"].items()},
            }.items()},
        "targets_18": targets,
        "baseline_train_inputs_equal_official": baseline_inputs_ok,
        "ratio_meta": ratio_meta,
        "settings": {
            "global_thresholds": cfg["global_thresholds"],
            "oracle_threshold_grid": cfg["oracle_threshold_grid"],
            "instance_rule": "instances = gold keys | pred keys (official)",
            "undefined_pr_convention": "safe_div -> 0.0 (official)",
            "macro_variants": ["gold_supported (official)", "full_universe"],
        },
        "outputs": sorted(p.name for p in OUT.iterdir()),
        "constraints_respected": {
            "no_training": True, "no_inference": True, "no_api_calls": True,
            "no_existing_artifact_modified": True,
        },
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    (LOGS / "run_phase0.log").write_text("\n".join(LOG_LINES) + "\n")
    log(f"Phase 0 complete. Outputs: {len(manifest['outputs'])} files in {OUT}")


if __name__ == "__main__":
    main()
