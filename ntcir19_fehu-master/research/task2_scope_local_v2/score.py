"""Tune-only official export/scoring and fixed mechanism diagnostics, no model tuning."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from sklearn.metrics import average_precision_score

from research.task2_scope_local_v1.data import taxonomy, sha256
from research.task2_scope_local_v1.prepare import PROJECT, write_json
from .common import arrays, read_guard, setup
from .metrics import at_threshold, counts, evaluate


def export(rows, mapping, threshold, *, product=False):
    """Only keyed probabilities enter this function; no labels or explanations."""
    if not (0 <= threshold <= 1 or threshold == 2.): raise ValueError("Invalid threshold")
    articles = {}; seen = set(); candidate_count = 0
    for r in rows:
        article = articles.setdefault(r["guid"], {e: {"a": set(), "b": []} for e in r["event_ids"]})
        if list(article) != r["event_ids"]: raise ValueError("Event coverage differs across actors")
        a = np.asarray(r["article_probability"], dtype=np.float32)
        s = np.asarray(r["event_probability"], dtype=np.float32)
        if product: s = s * a[None, :]
        if s.shape != (len(r["event_ids"]), 108) or not np.isfinite(s).all() or not ((s >= 0) & (s <= 1)).all():
            raise ValueError("Invalid inference output")
        selected = s.astype(np.float64) >= threshold
        for event, positives in zip(r["event_ids"], selected):
            key = r["guid"], r["actor_id"], event
            if key in seen: raise ValueError("Duplicate candidate")
            seen.add(key); candidate_count += 1
            for i in np.flatnonzero(positives):
                article[event]["b"].append(dict(actor=r["actor_id"], l1_value=str(i//2), direction=str(i%2)))
                article[event]["a"].add((r["actor_id"], mapping[str(i//2)]))
    arows, brows = [], []
    for guid, events in articles.items():
        arows.append(dict(guid=guid, subevents_human_values=[dict(subevent_id=e,
            subevent_human_values=[dict(actor=aid, l2_value=l2) for aid, l2 in sorted(v["a"])]) for e, v in events.items()]))
        brows.append(dict(guid=guid, subevents_human_values=[dict(subevent_id=e, subevent_human_values=v["b"]) for e, v in events.items()]))
    return dict(task2a=arows, task2b=brows, coverage=dict(articles=len(articles),
        events=sum(map(len, articles.values())), candidates=candidate_count, candidate_keys=sorted(seen)))


def tune_gold(plans, gold, mapping):
    """Reconstruct official rows from hash-verified TRAIN-derived tune supervision.

    The earlier supervision audit pins TRAIN gold and split; no held-out gold is
    opened here. Both L1+direction and official L2 mapping are retained.
    """
    rows = []
    for p in plans:
        g = gold[p.key]; e = np.zeros((len(p.event_ids), 108), dtype=np.float32)
        for j, indices in enumerate(g["children"]): e[j, indices] = 1
        rows.append(dict(guid=p.key[0], actor_id=p.key[1], event_ids=list(p.event_ids),
            article_probability=[0.]*108, event_probability=e.tolist()))
    output = export(rows, mapping, .5)["task2b"]
    for a in output:
        for e in a["subevents_human_values"]:
            for v in e["subevent_human_values"]: v["l2_value"] = mapping[v["l1_value"]]
    return output


def official(out, gold_path, prediction, expected):
    out.mkdir(parents=True, exist_ok=False)
    for task in ("task2a", "task2b"):
        write_json(out / f"pred_{task}.json", prediction[task])
    write_json(out / "coverage.json", prediction["coverage"])
    evaluator = PROJECT / "research/task2_prompt_baseline_v1/evaluator/official_cli.py"
    cmd = [sys.executable, str(evaluator), "--gold_task2", str(gold_path),
        "--pred_task2a", str(out / "pred_task2a.json"), "--pred_task2b", str(out / "pred_task2b.json")]
    result = subprocess.run(cmd, text=True, capture_output=True)
    write_json(out / "command.json", dict(argv=cmd, evaluator_sha256=sha256(evaluator), returncode=result.returncode,
        upstream_commit="c27e19d97c24bd764c2ea520217dba9873fab455", upstream_change="DEBUG=False CLI only"))
    (out / "stdout.json").write_text(result.stdout); (out / "stderr.txt").write_text(result.stderr)
    result.check_returncode()
    metrics = json.loads(result.stdout)
    from research.task2_prompt_baseline_v1.evaluator import official_cli as ev
    for task, parser in (("task2a", ev.parse_task2a), ("task2b", ev.parse_task2b)):
        g, p = parser(str(gold_path)), parser(str(out / f"pred_{task}.json"))
        tp, fp, fn = ev.micro_counts(g, p, set(g) | set(p))
        metrics[task].update(tp=tp, fp=fp, fn=fn)
    for key in ("tp", "fp", "fn"):
        if metrics["task2b"][key] != expected[key]:
            raise AssertionError("Official/parser/scan mismatch")
    if abs(metrics["task2b"]["micro_f1"] - expected["micro_f1"]) > 1e-12:
        raise AssertionError("Official F1 differs")
    write_json(out / "metrics.json", metrics)
    return metrics


def diagnostics(rows, gold, fit_support, threshold, *, product=False):
    s, y, keys, ap = arrays(rows, gold, product=product)
    raw, _, _, _ = arrays(rows, gold)
    p = s.astype(np.float64) >= threshold
    empty = ~y.any(1)
    perclass = []
    for i in range(108):
        m = at_threshold(s[:, i], y[:, i], threshold)
        perclass.append(dict(index=i, value=str(i//2), direction="aligned" if i%2 else "contradictory",
            fit_support=int(fit_support[i]), tune_support=int(y[:, i].sum()),
            ap=float(average_precision_score(y[:, i], s[:, i])) if y[:, i].any() else None, **m))
    mechanism = {sign: dict(article_only=0, child_only=0, tie_article_child=0) for sign in ("positive", "negative")}
    article_only_count = article_only_transferred = article_only_event_fp = 0
    mvalues = []; actor_pairs = []; by_guid = {}; offset = 0
    for r in rows:
        g = gold[(r["guid"], r["actor_id"])]; a = np.asarray(r["article_probability"])
        e = np.asarray(r["event_probability"]); m = len(e); yy = y[offset:offset+m]; pp = p[offset:offset+m]; offset += m
        ya = np.zeros(108, dtype=bool); ya[g["article"]] = True
        positive_max = np.where(yy, e, -np.inf).max(0)
        child_max = e.max(0)
        for sign, mask, cm in (("positive", ya, positive_max), ("negative", ~ya, child_max)):
            mechanism[sign]["article_only"] += int((mask & (a > cm)).sum())
            mechanism[sign]["child_only"] += int((mask & (a < cm)).sum())
            mechanism[sign]["tie_article_child"] += int((mask & (a == cm)).sum())
        exclusive = ya & ~yy.any(0)
        article_only_count += int(exclusive.sum())
        article_only_transferred += int((exclusive & pp.any(0)).sum())
        article_only_event_fp += int(pp[:, exclusive].sum())
        mvalues.append(m)
        by_guid.setdefault(r["guid"], []).append((r, pp))
    for guid, rr in by_guid.items():
        for (a, pa), (b, pb) in itertools.combinations(rr, 2):
            ea, eb = np.array(a["event_probability"]), np.array(b["event_probability"])
            actor_pairs.append(dict(guid=guid, actors=[a["actor_id"], b["actor_id"]], candidates=len(ea),
                mean_absolute_raw_probability_difference=float(np.abs(ea-eb).mean()), identical_prediction_candidates=int((pa == pb).all(1).sum())))
    return dict(per_class=perclass, zero_fit_positive_classes=[r for r in perclass if r["fit_support"] == 0],
        direction={name: at_threshold(s[:, start::2], y[:, start::2], threshold) for start, name in ((0, "contradictory"), (1, "aligned"))},
        empty_candidates=dict(denominator=int(empty.sum()), candidates_with_fp=int(p[empty].any(1).sum()), fp_labels=int(p[empty].sum())),
        raw_event_gt_article=dict(numerator=int((raw > ap).sum()), denominator=raw.size, rate=float((raw > ap).mean()),
            predicted_positive_numerator=int(((raw > ap) & p).sum()), predicted_positive_denominator=int(p.sum())),
        article_only=dict(article_label_pairs=article_only_count, pairs_with_event_fp=article_only_transferred, event_fp=article_only_event_fp),
        max_responsibility=mechanism, max_responsibility_note="S rule applied to raw probabilities; ties separate; no upward-max zero-violation success claim",
        bag_event_counts=mvalues, multi_actor_pairs=actor_pairs)


def execute(run, method_dirs=None, output=None):
    read_guard(); frozen, data, gold = setup(run)
    out = output or run / "tune_evaluation"; out.mkdir(exist_ok=False)
    method_dirs = method_dirs or {}
    mapping = taxonomy(PROJECT / "dataset/hv_categories")
    write_json(out / "tune_gold.json", tune_gold(data["tune"], gold, mapping))
    write_json(out / "gold_provenance.json", dict(source="hash-verified TRAIN-derived tune.supervision.jsonl",
        supervision_dir=frozen["supervision_dir"], binding=frozen["binding"],
        reconstruction="Same published directed label sets and official fine-to-coarse mapping; no explanations, held-out labels, or gold-selected candidates"))
    support = np.zeros(108, dtype=np.int64); n = 0
    for plan in data["fit"]:
        for indices in gold[plan.key]["children"]: support[indices] += 1; n += 1
    if n != 23783 or support.sum() != 14624: raise ValueError("Fit frequency denominator differs")
    summary = {}; selected_rows = {}; all_scores = {}; gold_array = None; all_keys = None
    for method in ("T", "J", "S", "P"):
        source = "J" if method == "P" else method
        method_dir = method_dirs.get(source, run / source)
        run_selection = json.loads((method_dir / "selection.json").read_text())
        selection = run_selection["selected"]
        epoch = selection["epoch"]
        epoch_dir = Path(run_selection["epoch_sources"][str(epoch)])
        rows = json.loads((epoch_dir / f"tune_scores_epoch_{epoch}.json").read_text())
        scores, y, keys, _ = arrays(rows, gold, product=method == "P")
        expected_keys = {(p.key[0], p.key[1], e) for p in data["tune"] for e in p.event_ids}
        if set(keys) != expected_keys or len(keys) != 3843: raise ValueError("Missing candidate inference")
        metrics, curve = evaluate(scores, y)
        if method != "P" and metrics["selected"] != {k:v for k,v in selection.items() if k != "epoch"}:
            raise ValueError("Reloaded threshold/selection differs")
        mdir = out / method; mdir.mkdir()
        np.savez_compressed(mdir / "pr_curve.npz", **curve)
        write_json(mdir / "scores.json", dict(source_checkpoint=str(epoch_dir/f"epoch_{epoch}.pt"),
            candidate_keys=keys, event_probability=scores.tolist()))
        selected = metrics["selected"]; results = {}
        for kind, threshold, expected in (("selected", selected["threshold"], selected), ("fixed_05", .5, metrics["fixed_05"])):
            pred = export(rows, mapping, threshold, product=method == "P")
            if set(map(tuple, pred["coverage"]["candidate_keys"])) != expected_keys:
                raise ValueError("Export candidate coverage differs")
            results[kind] = official(mdir / kind, out / "tune_gold.json", pred, expected)
        write_json(mdir / "diagnostics.json", diagnostics(rows, gold, support, selected["threshold"], product=method == "P"))
        summary[method] = dict(epoch=epoch, selected_checkpoint=str(epoch_dir/f"epoch_{epoch}.pt"),
            metrics=metrics, official=results, raw_scores_sha256=sha256(epoch_dir/f"tune_scores_epoch_{epoch}.json"))
        write_json(mdir / "selection.json", summary[method])
        selected_rows[method] = rows; all_scores[method] = scores
        gold_array, all_keys = y, keys
    baseline = np.broadcast_to(support.astype(np.float64)/n, gold_array.shape)
    bm, bc = evaluate(baseline, gold_array)
    np.savez_compressed(out / "fit_frequency_pr_curve.npz", **bc)
    write_json(out / "fit_frequency_baseline.json", dict(fit_candidates=n, class_positive_counts=support.tolist(),
        class_probability=(support/n).tolist(), tune_metrics=bm, note="Candidate-frequency baseline; AP partly reflects cross-class frequency"))
    comparisons = {}
    for a, b in (("J", "T"), ("S", "J"), ("P", "J")):
        pa = all_scores[a].astype(np.float64) >= summary[a]["metrics"]["selected"]["threshold"]
        pb = all_scores[b].astype(np.float64) >= summary[b]["metrics"]["selected"]["threshold"]
        examples = {}
        for name, mask in dict(new_tp=pa & ~pb & gold_array, lost_tp=~pa & pb & gold_array,
                               removed_fp=~pa & pb & ~gold_array, new_fp=pa & ~pb & ~gold_array).items():
            positions = np.argwhere(mask)
            examples[name] = dict(count=len(positions), examples=[dict(key=all_keys[i], label=int(j),
                score_a=float(all_scores[a][i,j]), score_b=float(all_scores[b][i,j])) for i,j in positions[:20]])
        comparisons[a+"-"+b] = dict(delta_f1=summary[a]["metrics"]["selected"]["micro_f1"]-summary[b]["metrics"]["selected"]["micro_f1"],
            delta_ap=summary[a]["metrics"]["micro_ap"]-summary[b]["metrics"]["micro_ap"], changes=examples)
    write_json(out / "comparisons.json", comparisons)
    write_json(out / "summary.json", dict(scope="tune development only", methods=summary,
        fit_frequency_baseline=bm, comparisons=comparisons, holdout_dev_test_evaluated=False))
    print(json.dumps({m: v["metrics"] for m,v in summary.items()}, indent=2), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--run", type=Path, required=True)
    for method in ("T", "J", "S"): p.add_argument("--"+method.lower()+"-dir", type=Path)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    execute(args.run.resolve(), {m:getattr(args,m.lower()+"_dir").resolve() for m in ("T","J","S") if getattr(args,m.lower()+"_dir")}, args.out.resolve() if args.out else None)
