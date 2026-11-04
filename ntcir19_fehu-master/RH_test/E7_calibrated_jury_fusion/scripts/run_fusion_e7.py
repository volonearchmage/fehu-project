#!/usr/bin/env python3
"""E7 — calibrated jury fusion (method doc §3, pre-registered grid).

Primary generator's predictions pass through by default; a jury of frozen
systems (E1, Liu, and the other E6-family generators) plus the DeBERTa-v2
probabilities provide per-cell evidence. Two calibrated arms act on it:

  removal  (veto): drop a primary cell iff its cross-fitted calibrated
           P(gold) < theta = F1_primary/2, class in the frequent tier
           (official-train count > 130), actor keeps >= 1 label.
  addition: add a juror-supported non-primary cell iff calibrated
           P(gold) >= theta, frequent tier, value not held by the primary
           in either direction, <= 2 additions per actor.

Evidence scores (monotone composites; PAV makes them probabilities):
  s_rm(cell)  = n_jurors_exact + 0.25 * n_jurors_value_only + v2_value_score
  s_add(cell) = n_jurors_exact + v2_exact_prob

Cells (report all; no post-hoc selection):
  G0_passthrough   primary unchanged (identity anchor; byte-equal enforced)
  G1_veto          MAIN: removal arm
  G2_veto_noliu    G1 with Liu removed from the jury (is Liu load-bearing?)
  G3_veto_add      G1 + addition arm
  G5_veto_nogate   G1 without the frequent gate (expected macro harm)
(G4 = G3 + direction-QA flips is produced by apply_direction_qa.py.)

Calibration is 2-fold cross-fitted by md5(guid) %% 2 — an article's own gold
never influences its own fusion decisions. Fail-fast everywhere; no
fallbacks. Reuses the E5 library (PAV, folds, loaders, writers) verbatim.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
E5_SCRIPTS = ROOT / "RH_test/E5_deberta_auxiliary_fusion/scripts"
sys.path.insert(0, str(E5_SCRIPTS))

from fusion_lib import (  # noqa: E402  (E5 library, frozen)
    FusionError, all_labels, load_articles, load_task1b, load_probs,
    load_l1_to_l2, frequent_classes, crossfit_fold_of, micro_f1,
    pav_fit, pav_apply, project_1a, write_pred_files, sha256_file,
    split_label, value_score, index_of,
)

# ---- frozen inputs (dev) ---------------------------------------------------
D = {
    "articles": ROOT / "dataset/dev/dev_event_base.json",
    "gold_1b": ROOT / "dataset/gold_labels/dev/dev_human_values.json",
    "train_gold_1b": ROOT / "dataset/gold_labels/train/train_human_values.json",
    "v2_probs": ROOT / ("output/research_hybrid_deberta_v2_liu_flash/"
                        "20260714_184515/02_deberta_actor_probabilities.jsonl"),
    "hv_dir": ROOT / "dataset/hv_categories",
}
MEMBER_PREDS = {
    "E1": ROOT / "RH_test/E1_fewshot_repair/runs/20260722_152456/pred_task1b.json",
    "Liu": ROOT / ("output/task1/runs/dev_deepseek_deepseek-v4-flash_"
                   "targeted_more_shot_balanced_temp0p1_max8000/pred_task1b.json"),
    "E6": ROOT / "RH_test/E6_e3a_self_segmentation/runs/20260724_152658/pred_task1b.json",
    # E6b / E6c paths are appended at runtime via --member NAME=PATH
}

CELLS = {
    "G0_passthrough": dict(arms=set()),
    "G1_veto": dict(arms={"removal"}),
    "G2_veto_noliu": dict(arms={"removal"}, drop_juror="Liu"),
    "G3_veto_add": dict(arms={"removal", "addition"}),
    "G5_veto_nogate": dict(arms={"removal"}, nogate=True),
}


def build_scorers(jurors, probs):
    """Return (s_rm, s_add, support) closures over the jury."""
    def supports(key, lab):
        val = split_label(lab)[1]
        n_exact = n_val = 0
        for jp in jurors.values():
            labs = jp.get(key, set())
            if lab in labs:
                n_exact += 1
            if any(split_label(l)[1] == val for l in labs):
                n_val += 1
        return n_exact, n_val

    def s_rm(key, lab):
        p = probs.get(key)
        if p is None:
            raise FusionError(f"no v2 probability row for {key}")
        n_exact, n_val = supports(key, lab)
        return n_exact + 0.25 * (n_val - n_exact) + value_score(
            p, split_label(lab)[1])

    def s_add(key, lab):
        p = probs.get(key)
        if p is None:
            raise FusionError(f"no v2 probability row for {key}")
        n_exact, _ = supports(key, lab)
        return n_exact + p[index_of(lab)]

    return s_rm, s_add, supports


def fit_fold(primary, gold, actor_keys, jurors, probs, freq, keep):
    """Fit removal/addition PAV calibrators + theta on `keep`-filtered gold."""
    s_rm, s_add, _ = build_scorers(jurors, probs)
    removal_cells, addition_cells = [], []
    for key in actor_keys:
        if not keep(key[0]):
            continue
        plabs = primary.get(key, set())
        glabs = gold.get(key, set())
        p_vals = {split_label(l)[1] for l in plabs}
        cand = set()
        for jp in jurors.values():
            cand |= jp.get(key, set())
        for lab in sorted(plabs | cand):
            if lab not in freq:
                continue
            y = 1 if lab in glabs else 0
            if lab in plabs:
                removal_cells.append((s_rm(key, lab), y))
            elif split_label(lab)[1] not in p_vals:
                addition_cells.append((s_add(key, lab), y))
    gold_f = {k: v for k, v in gold.items() if keep(k[0])}
    prim_f = {k: v for k, v in primary.items() if keep(k[0])}
    theta = micro_f1(gold_f, prim_f) / 2.0
    if theta <= 0.0:
        raise FusionError("theta = 0 on calibration fold")
    return {"removal": pav_fit(removal_cells),
            "addition": pav_fit(addition_cells) if addition_cells else None,
            "theta": theta,
            "n_removal_cells": len(removal_cells),
            "n_addition_cells": len(addition_cells)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True, choices=sorted(CELLS))
    ap.add_argument("--primary_name", required=True)
    ap.add_argument("--member", action="append", default=[],
                    help="extra member as NAME=path/to/pred_task1b.json "
                         "(e.g. E6b=..., E6c=...)")
    ap.add_argument("--out_dir", type=Path, required=True)
    ap.add_argument("--max_add", type=int, default=2)
    # test-flow additions (method doc §7 / E5 pattern). Defaults preserve the
    # frozen dev behavior exactly.
    ap.add_argument("--calibration", default="crossfit",
                    choices=["crossfit", "fit", "apply"],
                    help="crossfit: dev experiments (2-fold). fit: fit on the "
                         "full labeled set, save calibration.json. apply: "
                         "load a saved calibration.json; no gold needed.")
    ap.add_argument("--calibration_file", type=Path, default=None,
                    help="output path for fit (default <out_dir>/"
                         "calibration.json); required input for apply")
    ap.add_argument("--articles", type=Path, default=D["articles"])
    ap.add_argument("--gold_1b", type=Path, default=D["gold_1b"])
    ap.add_argument("--v2_probs", type=Path, default=D["v2_probs"])
    args = ap.parse_args()

    members = dict(MEMBER_PREDS)
    for spec in args.member:
        name, _, path = spec.partition("=")
        if not path:
            raise FusionError(f"bad --member spec: {spec}")
        members[name] = Path(path)
    if args.primary_name not in members:
        raise FusionError(f"primary {args.primary_name} not among members "
                          f"{sorted(members)}")
    cfg = CELLS[args.cell]

    out = args.out_dir
    if out.exists() and any(out.iterdir()):
        raise FusionError(f"out_dir {out} exists and is not empty")
    out.mkdir(parents=True, exist_ok=True)

    guids, actors = load_articles(args.articles)
    actor_keys = sorted(actors)
    preds = {n: load_task1b(p) for n, p in members.items()}
    for n, pd in preds.items():
        stray = [k for k in pd if k not in actors]
        if stray:
            raise FusionError(f"{n} predicts {len(stray)} keys outside the "
                              f"articles (first: {stray[:2]})")
    primary = preds[args.primary_name]
    jurors = {n: p for n, p in preds.items() if n != args.primary_name}
    if cfg.get("drop_juror"):
        if cfg["drop_juror"] not in jurors:
            raise FusionError(f"cannot drop absent juror {cfg['drop_juror']}")
        jurors = {n: p for n, p in jurors.items() if n != cfg["drop_juror"]}
    probs, _ = load_probs(args.v2_probs)
    missing = [k for k in actor_keys if k not in probs]
    if missing:
        raise FusionError(f"{len(missing)} actors lack v2 probability rows")

    freq = (set(all_labels()) if cfg.get("nogate")
            else frequent_classes(D["train_gold_1b"]))
    s_rm, s_add, supports = build_scorers(jurors, probs)

    # ---- calibration ------------------------------------------------------
    calib_record = {"mode": "none"}
    models = None            # crossfit: {fold: model}
    single_model = None      # fit/apply: one model for every key
    if cfg["arms"] and args.calibration == "crossfit":
        gold = load_task1b(args.gold_1b)
        models = {}
        for fold in (0, 1):
            models[fold] = fit_fold(
                primary, gold, actor_keys, jurors, probs, freq,
                keep=lambda g, f=fold: crossfit_fold_of(g) != f)
        calib_record = {"mode": "crossfit", "folds": {
            str(f): {"theta": m["theta"],
                     "n_removal_cells": m["n_removal_cells"],
                     "n_addition_cells": m["n_addition_cells"]}
            for f, m in models.items()}}
    elif cfg["arms"] and args.calibration == "fit":
        gold = load_task1b(args.gold_1b)
        single_model = fit_fold(primary, gold, actor_keys, jurors, probs,
                                freq, keep=lambda g: True)
        cf = args.calibration_file or out / "calibration.json"
        cf.write_text(json.dumps({
            "cell": args.cell, "primary": args.primary_name,
            "jurors": sorted(jurors),
            "removal": single_model["removal"],
            "addition": single_model["addition"],
            "theta": single_model["theta"],
            "n_removal_cells": single_model["n_removal_cells"],
            "n_addition_cells": single_model["n_addition_cells"],
            "fitted_on": {"gold_1b": str(args.gold_1b),
                          "articles": str(args.articles),
                          "members": {n: str(p) for n, p in members.items()},
                          "v2_probs": str(args.v2_probs)},
        }, indent=2))
        calib_record = {"mode": "fit", "theta": single_model["theta"],
                        "saved_to": str(cf)}
    elif cfg["arms"] and args.calibration == "apply":
        if not args.calibration_file:
            raise FusionError("--calibration apply requires --calibration_file")
        loaded = json.loads(args.calibration_file.read_text())
        if loaded["cell"] != args.cell:
            raise FusionError(f"calibration fitted for cell {loaded['cell']} "
                              f"but running {args.cell}")
        if loaded["primary"] != args.primary_name:
            raise FusionError(f"calibration fitted with primary "
                              f"{loaded['primary']} != {args.primary_name}")
        if loaded["jurors"] != sorted(jurors):
            raise FusionError(f"calibration jurors {loaded['jurors']} != "
                              f"current {sorted(jurors)}")
        single_model = {
            "removal": [tuple(x) for x in loaded["removal"]],
            "addition": ([tuple(x) for x in loaded["addition"]]
                         if loaded["addition"] else None),
            "theta": loaded["theta"]}
        calib_record = {"mode": "apply", "theta": loaded["theta"],
                        "loaded_from": str(args.calibration_file)}

    # ---- fuse -------------------------------------------------------------
    fused = {key: set(primary.get(key, set())) for key in actor_keys}
    actions = []
    for key in actor_keys:
        labs = fused[key]
        cal = (models[crossfit_fold_of(key[0])] if models
               else single_model)
        if "removal" in cfg["arms"] and labs:
            scored = []
            for lab in sorted(labs):
                if lab not in freq:
                    continue
                p = pav_apply(cal["removal"], s_rm(key, lab))
                if p < cal["theta"]:
                    scored.append((p, lab))
            scored.sort()
            for p, lab in scored:
                if len(labs) <= 1:
                    break
                labs.discard(lab)
                ne, nv = supports(key, lab)
                actions.append({"key": list(key), "label": lab,
                                "action": "remove",
                                "calibrated_p": round(p, 4),
                                "jury_exact": ne, "jury_value": nv})
        if "addition" in cfg["arms"]:
            if cal["addition"] is None:
                raise FusionError("addition arm active but no addition "
                                  "calibrator was fitted")
            p_vals = {split_label(l)[1] for l in labs}
            cand = set()
            for jp in jurors.values():
                cand |= jp.get(key, set())
            scored = []
            for lab in sorted(cand - labs):
                if lab not in freq or split_label(lab)[1] in p_vals:
                    continue
                p = pav_apply(cal["addition"], s_add(key, lab))
                if p >= cal["theta"]:
                    scored.append((-p, lab))
            scored.sort()
            for negp, lab in scored[:args.max_add]:
                labs.add(lab)
                ne, nv = supports(key, lab)
                actions.append({"key": list(key), "label": lab,
                                "action": "add",
                                "calibrated_p": round(-negp, 4),
                                "jury_exact": ne, "jury_value": nv})

    if not cfg["arms"]:  # identity anchor must be byte-equal to the primary
        if {k: v for k, v in fused.items() if v} != primary:
            raise FusionError("G0 output differs from the primary — bug")

    # ---- annotations: per-cell jury evidence for the direction-QA stage ---
    annotations = []
    for key in actor_keys:
        for lab in sorted(fused[key]):
            val = split_label(lab)[1]
            opp = f"{'0' if split_label(lab)[0] == '1' else '1'}:{val}"
            n_opp = sum(1 for jp in jurors.values()
                        if opp in jp.get(key, set()))
            ne, nv = supports(key, lab)
            annotations.append({
                "guid": key[0], "actor_id": key[1], "label": lab,
                "jury_exact": ne, "jury_value": nv,
                "jury_opposite_direction": n_opp,
                "v2_prob": round(probs[key][index_of(lab)], 4),
            })

    fused = {k: v for k, v in fused.items() if v}
    l1_to_l2 = load_l1_to_l2(D["hv_dir"])
    write_pred_files(out, guids, fused, project_1a(fused, l1_to_l2))
    with open(out / "actions.jsonl", "w") as f:
        for a in actions:
            f.write(json.dumps(a) + "\n")
    with open(out / "annotations.jsonl", "w") as f:
        for a in annotations:
            f.write(json.dumps(a) + "\n")

    n_by = {}
    for a in actions:
        n_by[a["action"]] = n_by.get(a["action"], 0) + 1
    manifest = {
        "experiment": "E7_calibrated_jury_fusion",
        "cell": args.cell,
        "primary": args.primary_name,
        "jurors": sorted(jurors),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "calibration": calib_record,
        "inputs": {n: {"path": str(p), "sha256": sha256_file(p)}
                   for n, p in members.items()} | {
            "v2_probs": {"path": str(args.v2_probs),
                         "sha256": sha256_file(args.v2_probs)},
            "articles": {"path": str(args.articles),
                         "sha256": sha256_file(args.articles)}},
        "counts": {
            "primary_labels": sum(len(v) for v in primary.values()),
            "fused_labels": sum(len(v) for v in fused.values()),
            "actions": n_by,
            "frequent_classes": len(freq),
        },
    }
    (out / "fusion_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["counts"], indent=2))
    print(f"[done] {args.cell} -> {out}")


if __name__ == "__main__":
    main()
