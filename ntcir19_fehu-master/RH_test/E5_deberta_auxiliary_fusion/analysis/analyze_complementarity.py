#!/usr/bin/env python3
"""E5 — complementarity analysis between E1 (primary) and the augmented
DeBERTa-v3 LoRA v2 model (auxiliary), on the official Task-1 dev set.

Read-only over frozen artifacts:
  * E1 predictions   RH_test/E1_fewshot_repair/runs/20260722_152456/
  * v2 probabilities output/research_hybrid_deberta_v2_liu_flash/20260714_184515/
                       02_deberta_actor_probabilities.jsonl
  * v2 frozen preds  output/research_augmented_deberta_v2_unfiltered/20260714_032758/
  * Fp seed probs    new_check/phase3/runs/Fp_seed{42,43,44}/probabilities.jsonl
  * gold             dataset/gold_labels/dev/dev_human_values.json

Hard validation: thresholding the v2 probabilities at 0.30 must reproduce the
frozen v2 pred_task1b.json exactly, else the analysis aborts (no fallbacks).

Outputs (all under analysis/outputs/):
  per_class_metrics.csv        108-class P/R/F1 for E1 and v2@0.30
  overlap_summary.json         gold-cell hit overlap, group metrics
  recovery_sweep.csv           add-if-p>=tau candidate precision sweep
  filter_analysis.json         v2 prob separation of E1 TP vs FP
  direction_analysis.json      v2 direction-repair fix/break estimates
  ANALYSIS_SUMMARY.md          human-readable summary
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from evaluation import (  # noqa: E402
    parse_task1a, parse_task1b, evaluate, l1_dir_universe, l2_universe,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr, split_dir_l1,
)

GOLD_1B = ROOT / "dataset/gold_labels/dev/dev_human_values.json"
E1_RUN = ROOT / "RH_test/E1_fewshot_repair/runs/20260722_152456"
V2_PROBS = (ROOT / "output/research_hybrid_deberta_v2_liu_flash/20260714_184515/"
            "02_deberta_actor_probabilities.jsonl")
V2_PRED_1B = (ROOT / "output/research_augmented_deberta_v2_unfiltered/20260714_032758/"
              "predictions/pred_task1b.json")
FP_RUNS = {s: ROOT / f"new_check/phase3/runs/Fp_seed{s}/probabilities.jsonl"
           for s in (42, 43, 44)}
TARGETS_JSON = (ROOT / "output/research_label_aware_low_frequency_augmentation_v2/"
                "20260713_163751/02_selected_targets_and_allocation.json")
OUT = HERE / "outputs"

ALL_108 = sorted(l1_dir_universe(), key=lambda s: (int(s.split(":")[1]), s))


class AnalysisError(RuntimeError):
    pass


def label_index(label: str) -> int:
    d, l1 = split_dir_l1(label)
    return int(l1) * 2 + int(d)


def load_probs(path: Path, sources: dict | None = None) -> dict:
    """Load probabilities keyed by (guid, actor_id). If `sources` is a dict it
    is filled with each row's actor_source tag (v2 export only)."""
    rows = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            key = (str(r["guid"]), str(r["actor_id"]))
            p = r["probabilities_108"]
            if len(p) != 108:
                raise AnalysisError(f"bad prob vector length {len(p)} in {path}")
            rows[key] = p
            if sources is not None:
                sources[key] = r.get("actor_source", "")
    if not rows:
        raise AnalysisError(f"no rows in {path}")
    return rows


def preds_from_probs(probs: dict, tau: float) -> dict:
    out = {}
    for key, p in probs.items():
        labs = {lab for lab in ALL_108 if p[label_index(lab)] >= tau}
        if labs:
            out[key] = labs
    return out


def per_label_counts(gold, pred):
    counts = {lab: {"tp": 0, "fp": 0, "fn": 0} for lab in ALL_108}
    for iid in set(gold) | set(pred):
        g = gold.get(iid, set())
        p = pred.get(iid, set())
        for lab in g & p:
            counts[lab]["tp"] += 1
        for lab in p - g:
            counts[lab]["fp"] += 1
        for lab in g - p:
            counts[lab]["fn"] += 1
    return counts


def prf(c):
    p = safe_div(c["tp"], c["tp"] + c["fp"])
    r = safe_div(c["tp"], c["tp"] + c["fn"])
    return p, r, f1_from_pr(p, r)


def group_micro(counts, labels):
    tp = sum(counts[l]["tp"] for l in labels)
    fp = sum(counts[l]["fp"] for l in labels)
    fn = sum(counts[l]["fn"] for l in labels)
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "micro_p": p, "micro_r": r,
            "micro_f1": f1_from_pr(p, r)}


def auc(pos, neg):
    """Rank-based AUC of score separating pos (higher) from neg."""
    if not pos or not neg:
        return None
    scores = [(s, 1) for s in pos] + [(s, 0) for s in neg]
    scores.sort(key=lambda x: x[0])
    rank_sum, rank, i = 0.0, 0, 0
    while i < len(scores):
        j = i
        while j < len(scores) and scores[j][0] == scores[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            if scores[k][1] == 1:
                rank_sum += avg_rank
        i = j
    n_pos, n_neg = len(pos), len(neg)
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def main():
    OUT.mkdir(exist_ok=True)

    gold = parse_task1b(str(GOLD_1B))
    e1 = parse_task1b(str(E1_RUN / "pred_task1b.json"))
    v2_frozen = parse_task1b(str(V2_PRED_1B))
    sources = {}
    probs = load_probs(V2_PROBS, sources)
    fp_probs = {s: load_probs(p) for s, p in FP_RUNS.items()}

    # ---- hard validation: probs@0.30 == frozen v2 predictions -------------
    # The frozen v2 run predicted only for gold-parity actors; the export
    # additionally carries 3 rows tagged article_only_actor_not_in_frozen_run.
    parity_probs = {k: v for k, v in probs.items()
                    if sources[k] == "gold_actor_trainer_parity"}
    n_article_only = sum(1 for s in sources.values()
                         if s == "article_only_actor_not_in_frozen_run")
    if len(parity_probs) + n_article_only != len(probs):
        raise AnalysisError(
            f"unexpected actor_source tags: {set(sources.values())}")
    derived = preds_from_probs(parity_probs, 0.30)
    if derived != v2_frozen:
        extra = set(derived) - set(v2_frozen)
        missing = set(v2_frozen) - set(derived)
        diff = [k for k in set(derived) & set(v2_frozen)
                if derived[k] != v2_frozen[k]]
        raise AnalysisError(
            f"v2 probabilities do not reproduce frozen predictions at 0.30: "
            f"{len(extra)} extra keys, {len(missing)} missing keys, "
            f"{len(diff)} differing keys (first: {diff[:3]})")
    print(f"[ok] v2 probs reproduce frozen v2 pred_task1b at 0.30 "
          f"({len(probs)} actor rows, {len(v2_frozen)} predicted keys)")

    targets = json.load(open(TARGETS_JSON))["targets"]
    t18 = {f"{t['direction']}:{t['l1_value_id']}" for t in targets}
    if len(t18) != 18:
        raise AnalysisError(f"expected 18 targets, got {len(t18)}")
    nt90 = [lab for lab in ALL_108 if lab not in t18]

    # ---- headline metrics -------------------------------------------------
    def headline(pred):
        r = evaluate(gold, pred, l1_dir_universe())
        drr, rev, den, amb = direction_reverse_rate_gold_excl(gold, pred)
        r["drr"] = drr
        return r

    head = {"E1": headline(e1), "v2@0.30": headline(v2_frozen)}
    for name, r in head.items():
        print(f"[headline] {name}: micro {r['micro_f1']:.4f} "
              f"(P {r['micro_precision']:.4f} R {r['micro_recall']:.4f}) "
              f"macro {r['macro_f1']:.4f} DRR {r['drr']:.4f}")

    # ---- per-class table --------------------------------------------------
    ce1 = per_label_counts(gold, e1)
    cv2 = per_label_counts(gold, v2_frozen)
    sup = defaultdict(int)
    for labs in gold.values():
        for lab in labs:
            sup[lab] += 1

    rows = []
    for lab in ALL_108:
        p1, r1, f1 = prf(ce1[lab])
        p2, r2, f2 = prf(cv2[lab])
        rows.append({
            "label": lab, "gold_support": sup.get(lab, 0),
            "is_target18": lab in t18,
            "e1_tp": ce1[lab]["tp"], "e1_fp": ce1[lab]["fp"], "e1_fn": ce1[lab]["fn"],
            "e1_p": round(p1, 4), "e1_r": round(r1, 4), "e1_f1": round(f1, 4),
            "v2_tp": cv2[lab]["tp"], "v2_fp": cv2[lab]["fp"], "v2_fn": cv2[lab]["fn"],
            "v2_p": round(p2, 4), "v2_r": round(r2, 4), "v2_f1": round(f2, 4),
        })
    import csv
    with open(OUT / "per_class_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    grp = {
        "E1": {"target18": group_micro(ce1, sorted(t18)),
               "nontarget90": group_micro(ce1, nt90)},
        "v2": {"target18": group_micro(cv2, sorted(t18)),
               "nontarget90": group_micro(cv2, nt90)},
    }

    # ---- gold-cell overlap ------------------------------------------------
    overlap = {"both": 0, "e1_only": 0, "v2_only": 0, "neither": 0}
    overlap_t18 = {"both": 0, "e1_only": 0, "v2_only": 0, "neither": 0}
    gold_cells = 0
    for iid, glabs in gold.items():
        for lab in glabs:
            gold_cells += 1
            in1 = lab in e1.get(iid, set())
            in2 = lab in v2_frozen.get(iid, set())
            key = ("both" if in1 and in2 else "e1_only" if in1
                   else "v2_only" if in2 else "neither")
            overlap[key] += 1
            if lab in t18:
                overlap_t18[key] += 1

    # ---- recovery sweep: add-if-v2>=tau on cells E1 does not predict ------
    # candidate universe: all (actor row in probs) x 108 labels not in E1 preds
    taus = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90]
    sweep_rows = []
    for tau in taus:
        for seed_gate in (False, True):
            n_add = tp_add = 0
            n_add_t18 = tp_add_t18 = 0
            n_add_dirconf = 0   # additions where E1 has same value, other dir
            for key, p in probs.items():
                e1labs = e1.get(key, set())
                e1_vals = {split_dir_l1(l)[1] for l in e1labs}
                for lab in ALL_108:
                    if lab in e1labs:
                        continue
                    if p[label_index(lab)] < tau:
                        continue
                    if seed_gate:
                        ok = all(
                            key in fp_probs[s]
                            and fp_probs[s][key][label_index(lab)] >= 0.30
                            for s in fp_probs)
                        if not ok:
                            continue
                    n_add += 1
                    hit = lab in gold.get(key, set())
                    tp_add += hit
                    if lab in t18:
                        n_add_t18 += 1
                        tp_add_t18 += hit
                    if split_dir_l1(lab)[1] in e1_vals:
                        n_add_dirconf += 1
            sweep_rows.append({
                "tau": tau, "seed_gate": seed_gate,
                "n_added": n_add, "tp_added": tp_add,
                "precision_of_added": round(safe_div(tp_add, n_add), 4),
                "n_added_t18": n_add_t18, "tp_added_t18": tp_add_t18,
                "precision_added_t18": round(safe_div(tp_add_t18, n_add_t18), 4),
                "n_added_conflicting_direction": n_add_dirconf,
            })
    with open(OUT / "recovery_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sweep_rows[0].keys())
        w.writeheader()
        w.writerows(sweep_rows)

    # E1 baseline micro precision for context: additions above this precision
    # raise micro F1; below it they trade precision for recall.
    e1p = head["E1"]["micro_precision"]

    # ---- filter analysis: does v2 prob separate E1 TP from E1 FP? --------
    tp_scores, fp_scores = [], []
    tp_scores_val, fp_scores_val = [], []   # max over both directions of value
    for iid, plabs in e1.items():
        pr = probs.get(iid)
        for lab in plabs:
            g = lab in gold.get(iid, set())
            if pr is None:
                raise AnalysisError(f"E1 predicts for {iid} but no v2 prob row")
            s = pr[label_index(lab)]
            d, v = split_dir_l1(lab)
            sval = max(pr[int(v) * 2], pr[int(v) * 2 + 1])
            (tp_scores if g else fp_scores).append(s)
            (tp_scores_val if g else fp_scores_val).append(sval)

    def dist(xs):
        xs = sorted(xs)
        n = len(xs)
        if n == 0:
            return {}
        q = lambda f: xs[min(n - 1, int(f * n))]
        return {"n": n, "p10": round(q(.10), 4), "p25": round(q(.25), 4),
                "median": round(q(.50), 4), "p75": round(q(.75), 4),
                "mean": round(sum(xs) / n, 4)}

    filter_report = {
        "auc_exact_label": auc(tp_scores, fp_scores),
        "auc_value_max_dir": auc(tp_scores_val, fp_scores_val),
        "e1_tp_score_dist": dist(tp_scores),
        "e1_fp_score_dist": dist(fp_scores),
        "removal_sweep": [],
    }
    for tau_low in (0.01, 0.02, 0.05, 0.10, 0.15, 0.20):
        rm_tp = sum(1 for s in tp_scores if s < tau_low)
        rm_fp = sum(1 for s in fp_scores if s < tau_low)
        filter_report["removal_sweep"].append({
            "tau_low": tau_low, "removed_tp": rm_tp, "removed_fp": rm_fp,
            "fp_per_tp_removed": round(safe_div(rm_fp, rm_tp), 3) if rm_tp else None})
    with open(OUT / "filter_analysis.json", "w") as f:
        json.dump(filter_report, f, indent=2)

    # ---- direction analysis ----------------------------------------------
    # cells where E1 predicted value v (single direction) and gold contains v
    # with a unique direction: E1 right/wrong x v2-argmax right/wrong.
    dir_stats = defaultdict(int)
    margins_fix, margins_break = [], []
    for iid, plabs in e1.items():
        glabs = gold.get(iid, set())
        g_by_val = defaultdict(set)
        for lab in glabs:
            d, v = split_dir_l1(lab)
            g_by_val[v].add(d)
        p_by_val = defaultdict(set)
        for lab in plabs:
            d, v = split_dir_l1(lab)
            p_by_val[v].add(d)
        pr = probs.get(iid)
        for v, dirs in p_by_val.items():
            if len(dirs) != 1 or v not in g_by_val or len(g_by_val[v]) != 1:
                continue
            e1_d = next(iter(dirs))
            g_d = next(iter(g_by_val[v]))
            p1 = pr[int(v) * 2 + 1]
            p0 = pr[int(v) * 2]
            v2_d = "1" if p1 >= p0 else "0"
            margin = abs(p1 - p0)
            e1_ok = e1_d == g_d
            v2_ok = v2_d == g_d
            dir_stats[f"e1_{'ok' if e1_ok else 'rev'}_v2_{'ok' if v2_ok else 'rev'}"] += 1
            if not e1_ok and v2_ok:
                margins_fix.append(margin)
            if e1_ok and not v2_ok:
                margins_break.append(margin)
    dir_report = {
        "counts": dict(dir_stats),
        "margin_dist_would_fix": dist(margins_fix),
        "margin_dist_would_break": dist(margins_break),
        "flip_sweep": [],
    }
    for m in (0.0, 0.05, 0.10, 0.20, 0.30, 0.50):
        fixes = sum(1 for x in margins_fix if x >= m)
        breaks = sum(1 for x in margins_break if x >= m)
        dir_report["flip_sweep"].append(
            {"min_margin": m, "fixes": fixes, "breaks": breaks,
             "net": fixes - breaks})
    with open(OUT / "direction_analysis.json", "w") as f:
        json.dump(dir_report, f, indent=2)

    # ---- summary ----------------------------------------------------------
    summary = {
        "headline": head,
        "group_metrics": grp,
        "gold_cells": gold_cells,
        "overlap_all": overlap,
        "overlap_target18": overlap_t18,
        "e1_micro_precision_reference": e1p,
        "n_actor_rows_probs": len(probs),
        "n_e1_pred_keys": len(e1),
        "n_gold_keys": len(gold),
    }
    with open(OUT / "overlap_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    md = ["# E5 complementarity analysis (E1 vs augmented DeBERTa v2)", ""]
    md.append(f"- gold (guid,actor) keys: {len(gold)}; E1 pred keys: {len(e1)}; "
              f"v2 prob rows: {len(probs)}")
    for name, r in head.items():
        md.append(f"- **{name}**: 1b micro {r['micro_f1']:.4f} "
                  f"(P {r['micro_precision']:.4f} / R {r['micro_recall']:.4f}), "
                  f"macro {r['macro_f1']:.4f}, DRR {r['drr']:.4f}")
    md.append("")
    md.append(f"## Gold-cell coverage ({gold_cells} cells)")
    md.append(f"- all:     {overlap}")
    md.append(f"- target18: {overlap_t18}")
    md.append("")
    md.append("## Recovery sweep (see recovery_sweep.csv)")
    for row in sweep_rows:
        md.append(f"- tau={row['tau']:.2f} gate={row['seed_gate']}: "
                  f"+{row['n_added']} cells, prec {row['precision_of_added']:.3f} "
                  f"(t18: +{row['n_added_t18']}, prec {row['precision_added_t18']:.3f})")
    md.append("")
    md.append(f"E1 micro-precision reference: {e1p:.4f} — additions above this "
              f"precision raise micro-F1.")
    md.append("")
    md.append("## Filter (E1 TP vs FP separation by v2 prob)")
    md.append(f"- AUC exact label: {filter_report['auc_exact_label']:.4f}; "
              f"AUC value-max: {filter_report['auc_value_max_dir']:.4f}")
    md.append(f"- TP dist {filter_report['e1_tp_score_dist']}")
    md.append(f"- FP dist {filter_report['e1_fp_score_dist']}")
    for r in filter_report["removal_sweep"]:
        md.append(f"- tau_low={r['tau_low']}: -{r['removed_fp']} FP / "
                  f"-{r['removed_tp']} TP (ratio {r['fp_per_tp_removed']})")
    md.append("")
    md.append("## Direction (E1 value-correct cells, unique gold direction)")
    md.append(f"- counts: {dict(dir_stats)}")
    for r in dir_report["flip_sweep"]:
        md.append(f"- flip if v2 margin>={r['min_margin']}: "
                  f"{r['fixes']} fixes / {r['breaks']} breaks (net {r['net']:+d})")
    (OUT / "ANALYSIS_SUMMARY.md").write_text("\n".join(md) + "\n")
    print(f"[done] outputs in {OUT}")


if __name__ == "__main__":
    main()
