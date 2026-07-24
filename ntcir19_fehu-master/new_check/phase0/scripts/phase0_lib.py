#!/usr/bin/env python3
"""Phase-0 shared library.

Read-only analysis helpers over existing FEHU repository artifacts.
No file outside new_check/ is ever written by this code.

Conventions (mirroring the official evaluation.py exactly):
  * A Task-1b label is the string "{direction}:{l1_value}", direction "1" =
    aligned, "0" = contradictory (per dataset/hv_categories/direction_mapping.json).
    NOTE: evaluation.py's DRR docstring names the directions the other way
    round; the DRR arithmetic is symmetric so the official numbers are
    unaffected, but per-class reversal ATTRIBUTION here follows
    direction_mapping.json. Recorded as a HUMAN_CHECK item.
  * Instance id = (guid, actor_id). Metric instances = gold keys | pred keys.
  * safe_div(n, 0) = 0.0 — undefined precision/recall is reported as 0.0,
    identical to the official scorer.
  * "Gold-supported" macro averages only over labels with dev gold support
    >= 1 (official convention). "Full-universe" macro averages over every
    label in the group, so labels with no gold and no predictions contribute
    P = R = F1 = 0. Both variants are emitted, clearly tagged.

Fail-fast policy: any missing/malformed input raises Phase0InputError with
the offending path. There are no silent fallbacks.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

# Project root = ntcir19_fehu-master/ (three levels above this file).
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from evaluation import (  # noqa: E402  (official scorer, imported read-only)
    parse_task1b, evaluate, l1_dir_universe, macro_f1_gold_supported,
    direction_reverse_rate_gold_excl, safe_div, f1_from_pr, split_dir_l1,
)


class Phase0InputError(RuntimeError):
    """A required input is missing or malformed. Never silently ignored."""


def rp(rel: str) -> Path:
    """Resolve a project-root-relative path; fail clearly if absent."""
    p = ROOT / rel
    if not p.exists():
        raise Phase0InputError(f"required input does not exist: {p}")
    return p


def load_json(rel: str):
    p = rp(rel)
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise Phase0InputError(f"malformed JSON in {p}: {e}") from e


def sha256_file(rel: str) -> str:
    h = hashlib.sha256()
    with open(rp(rel), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- label space
ALL_108 = sorted(l1_dir_universe(), key=lambda s: (int(s.split(":")[1]), s))


def class_index(label: str) -> int:
    """Map "d:l1" to the trainer's 108-dim index: idx = l1*2 + d.

    Matches src/train_deberta.py (lv[l1 * 2 + d] = 1.0) and the exported
    probabilities_108 ordering validated by the hybrid run's
    03_export_probabilities.py (thresholding at 0.30 reproduced the frozen
    v2 predictions exactly).
    """
    d, l1 = split_dir_l1(label)
    return int(l1) * 2 + int(d)


def index_class(idx: int) -> str:
    return f"{idx % 2}:{idx // 2}"


# ---------------------------------------------------------------- counts
def per_label_counts(gold: dict, pred: dict) -> dict:
    """label -> dict(tp, fp, fn) over instances = gold | pred (official rule)."""
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


def gold_support(gold: dict) -> dict:
    sup = defaultdict(int)
    for labs in gold.values():
        for lab in labs:
            sup[lab] += 1
    return dict(sup)


def group_metrics(counts: dict, labels: list, gold_sup: dict) -> dict:
    """Six metrics for a label group, in both macro variants.

    micro sums tp/fp/fn over the group's labels only (an FP on a label
    outside the group does not enter this group's table).
    macro_*_gold  : mean over group labels with gold support >= 1.
    macro_*_full  : mean over ALL group labels (zero-gold labels enter as
                    P=R=F1=0 unless they have FPs, which give them P=0).
    Per-label F1 is computed from that label's own P and R, then averaged
    (never from the averaged P and R).
    """
    tp = sum(counts[l]["tp"] for l in labels)
    fp = sum(counts[l]["fp"] for l in labels)
    fn = sum(counts[l]["fn"] for l in labels)
    micro_p = safe_div(tp, tp + fp)
    micro_r = safe_div(tp, tp + fn)

    def macro_over(ls):
        if not ls:
            return 0.0, 0.0, 0.0, 0
        ps, rs, f1s = [], [], []
        for l in ls:
            c = counts[l]
            p = safe_div(c["tp"], c["tp"] + c["fp"])
            r = safe_div(c["tp"], c["tp"] + c["fn"])
            ps.append(p); rs.append(r); f1s.append(f1_from_pr(p, r))
        n = len(ls)
        return sum(ps) / n, sum(rs) / n, sum(f1s) / n, n

    supported = [l for l in labels if gold_sup.get(l, 0) > 0]
    mpg, mrg, mfg, ng = macro_over(supported)
    mpf, mrf, mff, nf = macro_over(labels)
    return {
        "n_labels_group": len(labels),
        "n_labels_gold_supported": ng,
        "sum_tp": tp, "sum_fp": fp, "sum_fn": fn,
        "micro_precision": micro_p, "micro_recall": micro_r,
        "micro_f1": f1_from_pr(micro_p, micro_r),
        "macro_precision_gold_supported": mpg,
        "macro_recall_gold_supported": mrg,
        "macro_f1_gold_supported": mfg,
        "macro_precision_full_universe": mpf,
        "macro_recall_full_universe": mrf,
        "macro_f1_full_universe": mff,
    }


# ---------------------------------------------------------------- reversals
def reversals_by_gold_class(gold: dict, pred: dict) -> dict:
    """Attribute official gold-exclusive direction reversals to the DIRECTED
    GOLD class "gold_dir:l1". Mirrors direction_reverse_rate_gold_excl():
    a reversal for gold class d:l1 exists on an instance when l1 appears in
    gold with direction d only (not both) and the prediction contains l1
    with the opposite direction. Sum over classes == official reverse count.
    Also returns the per-class gold-exclusive denominators.
    """
    rev = defaultdict(int)
    denom = defaultdict(int)
    for iid in set(gold) | set(pred):
        g = gold.get(iid, set())
        p = pred.get(iid, set())
        g_dirs = defaultdict(set)
        for lab in g:
            d, v = split_dir_l1(lab)
            g_dirs[v].add(d)
        p_dirs = defaultdict(set)
        for lab in p:
            d, v = split_dir_l1(lab)
            p_dirs[v].add(d)
        for v, dirs in g_dirs.items():
            if len(dirs) != 1:          # ambiguous in gold -> excluded
                continue
            d = next(iter(dirs))
            denom[f"{d}:{v}"] += 1
            opposite = "0" if d == "1" else "1"
            if opposite in p_dirs.get(v, set()):
                rev[f"{d}:{v}"] += 1
    return dict(rev), dict(denom)


# ---------------------------------------------------------------- io helpers
def write_csv(path: Path, rows: list, fieldnames: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def fmt(x, nd=4):
    return round(x, nd) if isinstance(x, float) else x
