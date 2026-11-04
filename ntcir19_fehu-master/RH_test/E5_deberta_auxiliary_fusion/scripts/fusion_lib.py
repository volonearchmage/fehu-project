#!/usr/bin/env python3
"""E5 fusion library — E1 primary + augmented DeBERTa-v2 LoRA auxiliary.

Design (from analysis/outputs/, 2026-07-24):
  * E1 predictions pass through unchanged by default. The auxiliary can act
    only through two narrow, calibrated arms plus an annotation layer:
      - removal arm ("veto"): an E1 cell may be removed only when the
        cross-fitted calibrated probability that it is gold falls below the
        plug-in expected-F1 threshold theta = F1_cal / 2, AND the cell's
        class is in the frequent tier (official-train count > 130), AND the
        actor keeps at least one label. Rare/target-18 classes are never
        touched (v2's low probability there is ignorance, not evidence).
      - addition arm ("recovery"): a non-E1 cell may be added only when its
        calibrated probability >= theta, class is frequent-tier, the actor
        does not already carry the same value in either direction, and at
        most `max_add` additions per actor. (Analysis: v2 addition precision
        never exceeded 0.22 < theta ~ 0.27, so this arm is expected to stay
        nearly inactive — it is kept because it is the principled form and
        self-limiting.)
      - annotation layer: every cell is tagged with v2 agreement tier and
        seed consistency for downstream verification stages. Never changes
        outputs.
  * Direction is never taken from v2 (dev DRR 0.288 vs E1 0.0347; flipping
    is net-harmful at every margin — see direction_analysis.json).
  * Task-1a is recomputed as the L2 projection of the fused Task-1b set
    (verified byte-equivalent to E1's own 1a for the identity fusion).

Fail-fast policy: malformed or missing inputs raise FusionError. There are
no fallback paths that substitute defaults for missing data.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

NUM_LABELS = 108
FREQ_MIN_TRAIN_COUNT = 131  # frequent tier: official-train count > 130
                            # (reuses the frozen rarity cutoff of the
                            # target-selection policy, 02_selected_targets)


class FusionError(RuntimeError):
    """A required input is missing or malformed, or an invariant failed."""


# --------------------------------------------------------------- label space
def label_of(idx: int) -> str:
    return f"{idx % 2}:{idx // 2}"


def index_of(label: str) -> int:
    d, l1 = label.split(":", 1)
    return int(l1) * 2 + int(d)


def split_label(label: str):
    d, l1 = label.split(":", 1)
    return d, l1


def all_labels():
    return [label_of(i) for i in range(NUM_LABELS)]


# ------------------------------------------------------------------- loading
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_articles(path: Path):
    """Return (ordered list of guids, {(guid, actor_id): actor_name})."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list) or not data:
        raise FusionError(f"articles file is not a non-empty list: {path}")
    guids, actors = [], {}
    for art in data:
        guid = str(art["guid"])
        guids.append(guid)
        for d in art.get("actors", []):
            for name, aid in d.items():
                actors[(guid, str(aid))] = name
    if len(set(guids)) != len(guids):
        raise FusionError(f"duplicate guids in {path}")
    if not actors:
        raise FusionError(f"no actors found in {path}")
    return guids, actors


def load_task1b(path: Path):
    """Parse a Task-1b prediction/gold file to {(guid, actor): set(labels)}."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise FusionError(f"not a list: {path}")
    out = defaultdict(set)
    for item in data:
        guid = str(item["guid"])
        for hv in item.get("article_human_values", []):
            lab = f"{hv['direction']}:{hv['l1_value']}"
            idx = index_of(lab)
            if not 0 <= idx < NUM_LABELS:
                raise FusionError(f"label out of range in {path}: {lab}")
            out[(guid, str(hv["actor"]))].add(lab)
    return dict(out)


def load_probs(path: Path):
    """Load probability jsonl -> ({key: [108 floats]}, {key: actor_source})."""
    rows, sources = {}, {}
    with open(path) as f:
        for ln, line in enumerate(f, 1):
            r = json.loads(line)
            key = (str(r["guid"]), str(r["actor_id"]))
            p = r["probabilities_108"]
            if len(p) != NUM_LABELS:
                raise FusionError(f"{path}:{ln}: prob vector length {len(p)}")
            if any(not (0.0 <= x <= 1.0) for x in p):
                raise FusionError(f"{path}:{ln}: probability out of [0,1]")
            if key in rows:
                raise FusionError(f"{path}:{ln}: duplicate key {key}")
            rows[key] = p
            sources[key] = r.get("actor_source", "")
    if not rows:
        raise FusionError(f"no rows in {path}")
    return rows, sources


def load_l1_to_l2(hv_dir: Path):
    """Return {l1_id: l2_id} from the official category files."""
    l1_names = json.loads((hv_dir / "human_value_level1_values.json").read_text())
    l2_names = json.loads((hv_dir / "human_value_level2_values.json").read_text())
    l1_to_l2 = json.loads(
        (hv_dir / "level_1_to_level_2.json").read_text())["level_1_to_level_2"]
    out = {}
    for l1_name, l2_name in l1_to_l2.items():
        out[str(l1_names[l1_name])] = str(l2_names[l2_name])
    if len(out) != 54:
        raise FusionError(f"expected 54 L1->L2 entries, got {len(out)}")
    return out


def frequent_classes(train_gold_path: Path):
    """Classes with official-train count >= FREQ_MIN_TRAIN_COUNT."""
    counts = defaultdict(int)
    for labs in load_task1b(train_gold_path).values():
        for lab in labs:
            counts[lab] += 1
    freq = {lab for lab in all_labels()
            if counts.get(lab, 0) >= FREQ_MIN_TRAIN_COUNT}
    if not freq:
        raise FusionError("frequent-class set is empty — wrong train gold file?")
    return freq


# ------------------------------------------------------------------ scoring
def value_score(p, l1: str) -> float:
    """Direction-agnostic evidence that value l1 is present."""
    v = int(l1)
    return max(p[v * 2], p[v * 2 + 1])


def make_scorer(kind: str, probs: dict, seed_probs: list):
    """Return score(key, label) using the configured probability source.

    kind: "value" (max over directions), "exact" (exact label prob).
    seed_probs: optional list of extra prob dicts; scores are averaged over
    the main model and every seed model that has the key (seed models that
    lack the key are a hard error — coverage must be decided upfront).
    """
    if kind not in ("value", "exact"):
        raise FusionError(f"unknown score kind: {kind}")

    def score(key, label):
        d, l1 = split_label(label)
        sources = [probs] + seed_probs
        vals = []
        for src in sources:
            p = src.get(key)
            if p is None:
                raise FusionError(
                    f"no probability row for {key} in one of the sources")
            vals.append(value_score(p, l1) if kind == "value"
                        else p[index_of(label)])
        return sum(vals) / len(vals)

    return score


# ----------------------------------------------------- isotonic calibration
def pav_fit(pairs):
    """Pool-adjacent-violators isotonic regression.

    pairs: iterable of (score, y) with y in {0,1}. Returns a list of
    (max_score_of_block, block_mean) with strictly increasing means, usable
    by pav_apply. Deterministic; ties in score are pooled before fitting.
    """
    pairs = sorted(pairs)
    if not pairs:
        raise FusionError("cannot fit isotonic calibration on zero cells")
    # pre-pool exact score ties
    grouped = []
    i = 0
    while i < len(pairs):
        j = i
        s = pairs[i][0]
        ysum = 0
        while j < len(pairs) and pairs[j][0] == s:
            ysum += pairs[j][1]
            j += 1
        grouped.append([s, ysum / (j - i), j - i])
        i = j
    # PAV merge
    blocks = []
    for s, mean, n in grouped:
        blocks.append([s, mean, n])
        while len(blocks) >= 2 and blocks[-2][1] >= blocks[-1][1]:
            s2, m2, n2 = blocks.pop()
            s1, m1, n1 = blocks.pop()
            blocks.append([s2, (m1 * n1 + m2 * n2) / (n1 + n2), n1 + n2])
    return [(s, m) for s, m, _ in blocks]


def pav_apply(model, score: float) -> float:
    """Right-continuous step function: value of first block whose max score
    is >= score; scores above every block get the last block's value."""
    for s, m in model:
        if score <= s:
            return m
    return model[-1][1]


# ------------------------------------------------------------------ folding
def crossfit_fold_of(guid: str) -> int:
    """Deterministic 2-fold assignment by md5 of the guid (salt-free)."""
    return int(hashlib.md5(guid.encode()).hexdigest(), 16) % 2


def micro_f1(gold: dict, pred: dict) -> float:
    tp = fp = fn = 0
    for iid in set(gold) | set(pred):
        g = gold.get(iid, set())
        p = pred.get(iid, set())
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
    if tp == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    return 2 * prec * rec / (prec + rec)


# ------------------------------------------------------------- calibration
def fit_calibration(e1: dict, gold: dict, actor_keys, score_rm, score_add,
                    freq: set, guid_filter=None):
    """Fit removal and addition calibrators plus theta on labeled cells.

    score_rm scores E1-predicted cells (value-level by default — immune to
    v2 direction noise); score_add scores candidate additions (exact-label —
    adding a directed label requires directed evidence).
    guid_filter: optional predicate(guid) restricting the fitting population
    (used by cross-fitting). Returns dict with 'removal', 'addition' PAV
    models and 'theta'.
    """
    def keep(key):
        return guid_filter is None or guid_filter(key[0])

    removal_cells, addition_cells = [], []
    for key in actor_keys:
        if not keep(key):
            continue
        e1labs = e1.get(key, set())
        glabs = gold.get(key, set())
        e1_vals = {split_label(l)[1] for l in e1labs}
        for lab in all_labels():
            if lab not in freq:
                continue
            y = 1 if lab in glabs else 0
            if lab in e1labs:
                removal_cells.append((score_rm(key, lab), y))
            elif split_label(lab)[1] not in e1_vals:
                addition_cells.append((score_add(key, lab), y))

    gold_f = {k: v for k, v in gold.items() if keep(k)}
    e1_f = {k: v for k, v in e1.items() if keep(k)}
    theta = micro_f1(gold_f, e1_f) / 2.0
    if theta <= 0.0:
        raise FusionError("theta = 0 — E1 has no true positives on the "
                          "calibration population")
    return {
        "removal": pav_fit(removal_cells),
        "addition": pav_fit(addition_cells),
        "theta": theta,
        "n_removal_cells": len(removal_cells),
        "n_addition_cells": len(addition_cells),
    }


# ----------------------------------------------------------------- fusion
def fuse(e1: dict, actor_keys, score_rm, score_add, freq: set, calib_for_key,
         arms: set, max_add: int = 2, v2_pred_tau: float = 0.30,
         probs: dict | None = None):
    """Apply the fusion. Returns (fused, actions, annotations).

    calib_for_key: callable key -> calibration dict (crossfit dispatch);
    may be None only when neither the removal nor the addition arm is active.
    arms: subset of {"removal", "addition", "backfill", "union_diag"}.
    probs: required for annotation tiers and the backfill / union arms.
    """
    unknown = arms - {"removal", "addition", "backfill", "union_diag"}
    if unknown:
        raise FusionError(f"unknown arms: {unknown}")
    if probs is None:
        raise FusionError("probs required")
    if calib_for_key is None and arms & {"removal", "addition"}:
        raise FusionError("removal/addition arms require calibration")

    fused = {key: set(e1.get(key, set())) for key in actor_keys}
    for key in e1:
        if key not in fused:
            raise FusionError(
                f"E1 predicts for {key} which is absent from the articles "
                f"input — prediction/articles mismatch")
    actions = []

    for key in actor_keys:
        cal = calib_for_key(key) if calib_for_key is not None else None
        theta = cal["theta"] if cal else None
        labs = fused[key]
        e1_vals = {split_label(l)[1] for l in labs}

        if "removal" in arms and labs:
            # lowest calibrated p first; keep at least one label per actor
            scored = []
            for lab in sorted(labs):
                if lab not in freq:
                    continue
                p = pav_apply(cal["removal"], score_rm(key, lab))
                if p < theta:
                    scored.append((p, lab))
            scored.sort()
            for p, lab in scored:
                if len(labs) <= 1:
                    break
                labs.discard(lab)
                actions.append({"key": list(key), "label": lab,
                                "action": "remove", "calibrated_p": round(p, 4)})

        if "addition" in arms:
            cands = []
            for lab in all_labels():
                if lab not in freq or lab in labs:
                    continue
                if split_label(lab)[1] in e1_vals:
                    continue  # never fight E1 on direction
                p = pav_apply(cal["addition"], score_add(key, lab))
                if p >= theta:
                    cands.append((-p, lab))
            cands.sort()
            for negp, lab in cands[:max_add]:
                labs.add(lab)
                actions.append({"key": list(key), "label": lab,
                                "action": "add", "calibrated_p": round(-negp, 4)})

        if "backfill" in arms and not e1.get(key) and not labs:
            pr = probs[key]
            idx = max(range(NUM_LABELS), key=lambda i: pr[i])
            lab = label_of(idx)
            labs.add(lab)
            actions.append({"key": list(key), "label": lab,
                            "action": "backfill",
                            "calibrated_p": round(pr[idx], 4)})

        if "union_diag" in arms:
            pr = probs[key]
            for i in range(NUM_LABELS):
                if pr[i] >= v2_pred_tau:
                    lab = label_of(i)
                    if lab not in labs:
                        labs.add(lab)
                        actions.append({"key": list(key), "label": lab,
                                        "action": "union_add",
                                        "calibrated_p": round(pr[i], 4)})

    # annotation layer (never mutates)
    annotations = []
    for key in actor_keys:
        pr = probs[key]
        for lab in sorted(fused[key]):
            i = index_of(lab)
            annotations.append({
                "guid": key[0], "actor_id": key[1], "label": lab,
                "from_e1": lab in e1.get(key, set()),
                "v2_prob": round(pr[i], 4),
                "v2_value_score": round(value_score(pr, split_label(lab)[1]), 4),
                "v2_agree_at_030": pr[i] >= 0.30,
            })

    fused = {k: v for k, v in fused.items() if v}
    return fused, actions, annotations


# ------------------------------------------------------------------ output
def project_1a(fused_1b: dict, l1_to_l2: dict):
    out = {}
    for key, labs in fused_1b.items():
        s = set()
        for lab in labs:
            _, l1 = split_label(lab)
            if l1 not in l1_to_l2:
                raise FusionError(f"l1 id {l1} missing from L1->L2 mapping")
            s.add(l1_to_l2[l1])
        out[key] = s
    return out


def write_pred_files(out_dir: Path, guids, fused_1b: dict, fused_1a: dict):
    """Write pred_task1a.json / pred_task1b.json in official format,
    deterministic order (article order, then actor id, then label)."""
    by_guid_b = defaultdict(list)
    by_guid_a = defaultdict(list)
    for (guid, actor), labs in fused_1b.items():
        for lab in sorted(labs, key=lambda l: (int(split_label(l)[1]),
                                               split_label(l)[0])):
            d, l1 = split_label(lab)
            by_guid_b[guid].append(
                {"actor": actor, "l1_value": l1, "direction": d})
    for (guid, actor), l2s in fused_1a.items():
        for l2 in sorted(l2s, key=int):
            by_guid_a[guid].append({"actor": actor, "l2_value": l2})
    for g in by_guid_b:
        by_guid_b[g].sort(key=lambda h: (h["actor"], int(h["l1_value"]),
                                         h["direction"]))
    for g in by_guid_a:
        by_guid_a[g].sort(key=lambda h: (h["actor"], int(h["l2_value"])))

    pred_b = [{"guid": g, "article_human_values": by_guid_b.get(g, [])}
              for g in guids]
    pred_a = [{"guid": g, "article_human_values": by_guid_a.get(g, [])}
              for g in guids]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pred_task1b.json").write_text(
        json.dumps(pred_b, ensure_ascii=False, indent=2))
    (out_dir / "pred_task1a.json").write_text(
        json.dumps(pred_a, ensure_ascii=False, indent=2))
