#!/usr/bin/env python3
"""E5 fusion runner — E1 primary + augmented DeBERTa-v2 LoRA auxiliary.

Variants (pre-registered ablation grid; see reports/E5_HANDOFF_REPORT.md):
  F0_identity      annotation only; outputs must equal E1's (sanity anchor)
  F1_veto_value    MAIN: calibrated removal arm, value-level score,
                   frequent-class gate
  F2_veto_nogate   F1 without the frequent-class gate (expected: macro harm)
  F3_veto_exact    F1 with exact-label score (expected: direction-noise harm)
  F4_full          F1 + calibrated addition arm (expected: near-inactive)
  F5_full_backfill F4 + top-1 backfill for actors E1 left empty
  F6_union_diag    E1 union v2@0.30 (diagnostic harm bound, no calibration)
  F7_seedmean      F1 with scores averaged over v2 + the three Phase-3
                   Fp seed reproductions (robustness to single-seed noise)
  REF_v2_alone     v2@0.30 alone (reference system, no E1)

Calibration modes:
  crossfit  2-fold cross-fitting by md5(guid) — for dev experiments; an
            article's own gold never influences its own fusion decisions.
  fit       fit on the full labeled set and save calibration.json (for
            later application to test).
  apply     load a saved calibration.json; no gold needed (test mode).

Example (dev, main variant):
  python RH_test/E5_deberta_auxiliary_fusion/scripts/run_fusion_e5.py \
      --variant F1_veto_value --calibration crossfit \
      --out_dir RH_test/E5_deberta_auxiliary_fusion/runs/<ts>_F1
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from fusion_lib import (  # noqa: E402
    FusionError, all_labels, load_articles, load_task1b, load_probs,
    load_l1_to_l2, frequent_classes, make_scorer, fit_calibration,
    crossfit_fold_of, fuse, project_1a, write_pred_files, sha256_file,
    label_of, NUM_LABELS,
)

# frozen default inputs (dev)
D = {
    "articles": ROOT / "dataset/dev/dev_event_base.json",
    "gold_1b": ROOT / "dataset/gold_labels/dev/dev_human_values.json",
    "train_gold_1b": ROOT / "dataset/gold_labels/train/train_human_values.json",
    "e1_pred_1b": ROOT / ("RH_test/E1_fewshot_repair/runs/20260722_152456/"
                          "pred_task1b.json"),
    "v2_probs": ROOT / ("output/research_hybrid_deberta_v2_liu_flash/"
                        "20260714_184515/02_deberta_actor_probabilities.jsonl"),
    "hv_dir": ROOT / "dataset/hv_categories",
}
SEED_PROB_FILES = [
    ROOT / ("RH_test/E5_deberta_auxiliary_fusion/inputs/"
            f"dev_fp_seed{s}_probs.jsonl")
    for s in (42, 43, 44)]

VARIANTS = {
    "F0_identity": dict(arms=set(), rm_score="value"),
    "F1_veto_value": dict(arms={"removal"}, rm_score="value"),
    "F2_veto_nogate": dict(arms={"removal"}, rm_score="value", nogate=True),
    "F3_veto_exact": dict(arms={"removal"}, rm_score="exact"),
    "F4_full": dict(arms={"removal", "addition"}, rm_score="value"),
    "F5_full_backfill": dict(arms={"removal", "addition", "backfill"},
                             rm_score="value"),
    "F6_union_diag": dict(arms={"union_diag"}, rm_score="value", nocalib=True),
    "F7_seedmean": dict(arms={"removal"}, rm_score="value", seeds=True),
    "REF_v2_alone": dict(arms=set(), rm_score="value", v2_alone=True,
                         nocalib=True),
}


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    ap.add_argument("--calibration", default="crossfit",
                    choices=["crossfit", "fit", "apply"])
    ap.add_argument("--calibration_file", type=Path, default=None,
                    help="required for --calibration apply; output path "
                         "for --calibration fit (default <out_dir>/calibration.json)")
    ap.add_argument("--articles", type=Path, default=D["articles"])
    ap.add_argument("--gold_1b", type=Path, default=D["gold_1b"],
                    help="labeled 1b file for calibration (crossfit/fit)")
    ap.add_argument("--e1_pred_1b", type=Path, default=D["e1_pred_1b"])
    ap.add_argument("--v2_probs", type=Path, default=D["v2_probs"])
    ap.add_argument("--train_gold_1b", type=Path, default=D["train_gold_1b"])
    ap.add_argument("--out_dir", type=Path, required=True)
    ap.add_argument("--max_add", type=int, default=2)
    args = ap.parse_args()

    cfg = VARIANTS[args.variant]
    out = args.out_dir
    if out.exists() and any(out.iterdir()):
        raise FusionError(f"out_dir {out} exists and is not empty — refusing "
                          f"to overwrite a previous run")
    out.mkdir(parents=True, exist_ok=True)

    guids, actors = load_articles(args.articles)
    actor_keys = sorted(actors)
    e1 = load_task1b(args.e1_pred_1b)
    probs, sources = load_probs(args.v2_probs)
    missing = [k for k in actor_keys if k not in probs]
    if missing:
        raise FusionError(
            f"{len(missing)} article actors lack probability rows "
            f"(first: {missing[:3]}) — regenerate the probability export")
    stray = [k for k in e1 if k not in actors]
    if stray:
        raise FusionError(
            f"E1 predicts for {len(stray)} keys not present in the articles "
            f"input (first: {stray[:3]})")

    seed_probs = []
    if cfg.get("seeds"):
        for p in SEED_PROB_FILES:
            sp, _ = load_probs(p)
            seed_probs.append(sp)
        # seed exports cover gold-parity actors only; extend coverage with
        # the main model's rows is NOT allowed (silent fallback). Instead the
        # seed variant restricts scoring to the intersection and fails loudly
        # otherwise — so verify coverage up front.
        for k in actor_keys:
            for i, sp in enumerate(seed_probs):
                if k not in sp:
                    raise FusionError(
                        f"seed probability file {SEED_PROB_FILES[i].name} has "
                        f"no row for {k}; F7_seedmean requires full-coverage "
                        f"seed exports (re-export with export_v2_probs.py)")

    freq = (set(all_labels()) if cfg.get("nogate")
            else frequent_classes(args.train_gold_1b))
    score_rm = make_scorer(cfg["rm_score"], probs, seed_probs)
    score_add = make_scorer("exact", probs, seed_probs)

    # ---- calibration ------------------------------------------------------
    calib_for_key = None
    calib_record = {"mode": args.calibration}
    if cfg.get("nocalib") or not (cfg["arms"] & {"removal", "addition"}):
        calib_record["mode"] = "none"
    elif args.calibration == "crossfit":
        gold = load_task1b(args.gold_1b)
        models = {}
        for fold in (0, 1):
            models[fold] = fit_calibration(
                e1, gold, actor_keys, score_rm, score_add, freq,
                guid_filter=lambda g, f=fold: crossfit_fold_of(g) != f)
        calib_for_key = lambda key: models[crossfit_fold_of(key[0])]
        calib_record["folds"] = {
            str(f): {"theta": m["theta"],
                     "n_removal_cells": m["n_removal_cells"],
                     "n_addition_cells": m["n_addition_cells"]}
            for f, m in models.items()}
    elif args.calibration == "fit":
        gold = load_task1b(args.gold_1b)
        model = fit_calibration(e1, gold, actor_keys, score_rm, score_add,
                                freq, guid_filter=None)
        calib_for_key = lambda key: model
        cf = args.calibration_file or out / "calibration.json"
        cf.write_text(json.dumps(
            {"removal": model["removal"], "addition": model["addition"],
             "theta": model["theta"], "score_rm": cfg["rm_score"],
             "freq_gate": not cfg.get("nogate"),
             "fitted_on": str(args.gold_1b),
             "e1_pred_1b": str(args.e1_pred_1b)}, indent=2))
        calib_record["theta"] = model["theta"]
        calib_record["saved_to"] = str(cf)
    elif args.calibration == "apply":
        if not args.calibration_file:
            raise FusionError("--calibration apply requires --calibration_file")
        loaded = json.loads(args.calibration_file.read_text())
        if loaded.get("score_rm") != cfg["rm_score"]:
            raise FusionError(
                f"calibration was fitted with score_rm="
                f"{loaded.get('score_rm')} but variant uses {cfg['rm_score']}")
        model = {"removal": [tuple(x) for x in loaded["removal"]],
                 "addition": [tuple(x) for x in loaded["addition"]],
                 "theta": loaded["theta"]}
        calib_for_key = lambda key: model
        calib_record["theta"] = model["theta"]
        calib_record["loaded_from"] = str(args.calibration_file)

    # ---- fuse -------------------------------------------------------------
    if cfg.get("v2_alone"):
        fused = {}
        for key in actor_keys:
            labs = {label_of(i) for i in range(NUM_LABELS)
                    if probs[key][i] >= 0.30}
            if labs:
                fused[key] = labs
        actions, annotations = [], []
    else:
        fused, actions, annotations = fuse(
            e1, actor_keys, score_rm, score_add, freq, calib_for_key,
            cfg["arms"], max_add=args.max_add, probs=probs)

    l1_to_l2 = load_l1_to_l2(D["hv_dir"])
    fused_1a = project_1a(fused, l1_to_l2)
    write_pred_files(out, guids, fused, fused_1a)

    with open(out / "actions.jsonl", "w") as f:
        for a in actions:
            f.write(json.dumps(a) + "\n")
    with open(out / "annotations.jsonl", "w") as f:
        for a in annotations:
            f.write(json.dumps(a) + "\n")

    n_by_action = {}
    for a in actions:
        n_by_action[a["action"]] = n_by_action.get(a["action"], 0) + 1
    manifest = {
        "experiment": "E5_deberta_auxiliary_fusion",
        "variant": args.variant,
        "variant_config": {k: sorted(v) if isinstance(v, set) else v
                           for k, v in cfg.items()},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "calibration": calib_record,
        "inputs": {
            "articles": {"path": str(args.articles),
                         "sha256": sha256_file(args.articles)},
            "e1_pred_1b": {"path": str(args.e1_pred_1b),
                           "sha256": sha256_file(args.e1_pred_1b)},
            "v2_probs": {"path": str(args.v2_probs),
                         "sha256": sha256_file(args.v2_probs)},
            "train_gold_1b": {"path": str(args.train_gold_1b),
                              "sha256": sha256_file(args.train_gold_1b)},
            "seed_probs": [str(p) for p in
                           (SEED_PROB_FILES if cfg.get("seeds") else [])],
        },
        "counts": {
            "articles": len(guids),
            "article_actors": len(actor_keys),
            "e1_pred_keys": len(e1),
            "fused_pred_keys": len(fused),
            "e1_pred_labels": sum(len(v) for v in e1.values()),
            "fused_pred_labels": sum(len(v) for v in fused.values()),
            "actions": n_by_action,
            "frequent_classes": len(freq),
        },
    }
    (out / "fusion_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["counts"], indent=2))
    print(f"[done] predictions + manifest in {out}")


if __name__ == "__main__":
    main()
