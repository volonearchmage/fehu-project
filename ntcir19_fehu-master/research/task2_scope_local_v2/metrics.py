"""Exact global threshold selection, including ties and finite empty boundary."""
import json
import numpy as np
from sklearn.metrics import average_precision_score


def checked(scores, gold):
    # This is also the export comparison type. No threshold rounding or float32
    # scalar casting can add a boundary-tied prediction during JSON round-trip.
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(gold)
    if s.shape != y.shape or s.size == 0 or not np.isfinite(s).all() or not ((s >= 0) & (s <= 1)).all():
        raise ValueError("Invalid probabilities/shape")
    if not ((y == 0) | (y == 1)).all():
        raise ValueError("Nonbinary labels")
    return s, y.astype(bool)


def counts(tp, fp, fn):
    tp, fp, fn = int(tp), int(fp), int(fn)
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else 0.,
                recall=tp/(tp+fn) if tp+fn else 0., micro_f1=2*tp/(2*tp+fp+fn) if tp+fp+fn else 0.,
                predicted_positives=tp+fp)


def at_threshold(scores, gold, threshold):
    s, y = checked(scores, gold)
    if not np.isfinite(threshold) or not (0 <= threshold <= 1 or threshold == 2.):
        raise ValueError("Invalid decision threshold")
    p = s >= threshold
    return dict(threshold=float(threshold), **counts((p & y).sum(), (p & ~y).sum(), (~p & y).sum()))


def exact_scan(scores, gold):
    s, y = checked(scores, gold)
    order = np.argsort(-s.ravel(), kind="stable")
    v = s.ravel()[order]; labels = y.ravel()[order]
    ends = np.r_[np.flatnonzero(v[:-1] != v[1:]), len(v)-1]
    tp = np.r_[0, np.cumsum(labels, dtype=np.int64)[ends]]
    fp = np.r_[0, ends+1] - tp
    fn = int(labels.sum()) - tp
    thresholds = np.r_[2., v[ends]]
    den = 2*tp+fp+fn
    f1 = np.divide(2*tp, den, out=np.zeros_like(tp, dtype=float), where=den != 0)
    # Order is descending threshold, so first max handles tied F1 correctly.
    best = int(np.argmax(f1))
    selected = dict(threshold=float(thresholds[best]), **counts(tp[best], fp[best], fn[best]))
    if at_threshold(s, y, json.loads(json.dumps(selected["threshold"]))) != selected:
        raise AssertionError("Scan/export threshold round-trip mismatch")
    curve = dict(threshold=thresholds, tp=tp, fp=fp, fn=fn,
        precision=np.divide(tp, tp+fp, out=np.zeros_like(f1), where=tp+fp != 0),
        recall=np.divide(tp, tp+fn, out=np.zeros_like(f1), where=tp+fn != 0), micro_f1=f1)
    return selected, curve


def evaluate(scores, gold):
    s, y = checked(scores, gold)
    selected, curve = exact_scan(s, y)
    return dict(selected=selected, fixed_05=at_threshold(s, y, .5),
                micro_ap=float(average_precision_score(y.ravel(), s.ravel())),
                candidates=len(s), label_cells=s.size, gold_positive_labels=int(y.sum())), curve


def better(candidate, previous):
    return previous is None or (candidate["micro_f1"], candidate["threshold"], -candidate["epoch"]) > (
        previous["micro_f1"], previous["threshold"], -previous["epoch"])
