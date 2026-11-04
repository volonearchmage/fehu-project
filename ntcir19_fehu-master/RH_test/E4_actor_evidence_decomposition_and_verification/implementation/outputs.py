"""Official Task-1a/1b output conversion and (opt-in) dev evaluation.

Conversion reuses the frozen E1 process_results unchanged, then re-validates
the produced files against the official schema (valid actor ids, l1 in
0..53, direction in {"0","1"}, l2 in 0..19) so any conversion regression is
a hard error, not a bad submission.
"""

import json
import os
import sys

from e4_common import E4ValidationError


def write_pred_files(e1, articles, items_by_guid, out_dir):
    """items_by_guid: {guid: [{"actor_id","l1_value_id","direction"}, ...]}.

    `direction` is the prompt-side word ("aligned"/"contradictory"); the
    frozen E1 process_results converts to official "1"/"0".
    """
    os.makedirs(out_dir, exist_ok=True)
    all_1a, all_1b = [], []
    for article in articles:
        guid = article["guid"]
        if guid not in items_by_guid:
            raise E4ValidationError(f"no assembled items for article {guid}")
        t1a, t1b = e1.process_results(guid, article["actors"],
                                      items_by_guid[guid])
        all_1a.append({"guid": guid, "article_human_values": t1a})
        all_1b.append({"guid": guid, "article_human_values": t1b})

    path_1a = os.path.join(out_dir, "pred_task1a.json")
    path_1b = os.path.join(out_dir, "pred_task1b.json")
    with open(path_1a, "w", encoding="utf-8") as f:
        json.dump(all_1a, f, indent=2, ensure_ascii=False)
    with open(path_1b, "w", encoding="utf-8") as f:
        json.dump(all_1b, f, indent=2, ensure_ascii=False)
    validate_pred_files(articles, path_1a, path_1b)
    return path_1a, path_1b


def validate_pred_files(articles, path_1a, path_1b):
    """Hard schema validation of the written official prediction files."""
    valid_actors_by_guid = {
        a["guid"]: {aid for d in a["actors"] for aid in d.values()}
        for a in articles}
    with open(path_1a, "r", encoding="utf-8") as f:
        data_1a = json.load(f)
    with open(path_1b, "r", encoding="utf-8") as f:
        data_1b = json.load(f)
    if [x["guid"] for x in data_1a] != [a["guid"] for a in articles]:
        raise E4ValidationError("pred_task1a guid list mismatch")
    if [x["guid"] for x in data_1b] != [a["guid"] for a in articles]:
        raise E4ValidationError("pred_task1b guid list mismatch")
    for entry in data_1a:
        for v in entry["article_human_values"]:
            if set(v) != {"actor", "l2_value"}:
                raise E4ValidationError(f"task1a bad keys: {v}")
            if v["actor"] not in valid_actors_by_guid[entry["guid"]]:
                raise E4ValidationError(f"task1a invalid actor: {v}")
            if not (v["l2_value"].isdigit() and 0 <= int(v["l2_value"]) <= 19):
                raise E4ValidationError(f"task1a invalid l2_value: {v}")
    for entry in data_1b:
        seen = set()
        for v in entry["article_human_values"]:
            if set(v) != {"actor", "l1_value", "direction"}:
                raise E4ValidationError(f"task1b bad keys: {v}")
            if v["actor"] not in valid_actors_by_guid[entry["guid"]]:
                raise E4ValidationError(f"task1b invalid actor: {v}")
            if not (v["l1_value"].isdigit() and 0 <= int(v["l1_value"]) <= 53):
                raise E4ValidationError(f"task1b invalid l1_value: {v}")
            if v["direction"] not in ("0", "1"):
                raise E4ValidationError(f"task1b invalid direction: {v}")
            key = (v["actor"], v["l1_value"], v["direction"])
            if key in seen:
                raise E4ValidationError(f"task1b duplicate: {v}")
            seen.add(key)


def run_dev_evaluation(e1, path_1a, path_1b, eval_guids=None):
    """Official dev evaluation — only called with an explicit --evaluate flag."""
    sys.path.insert(0, e1.BASE_DIR)
    from evaluation import (parse_task1a, parse_task1b, evaluate,
                            l2_universe, l1_dir_universe,
                            direction_reverse_rate_gold_excl)

    def filt(labels):
        if eval_guids is None:
            return labels
        return {iid: v for iid, v in labels.items() if iid[0] in eval_guids}

    gold_1a = filt(parse_task1a(e1.DEV_LABELS))
    pred_1a = filt(parse_task1a(path_1a))
    gold_1b = filt(parse_task1b(e1.DEV_LABELS))
    pred_1b = filt(parse_task1b(path_1b))

    results_1a = evaluate(gold_1a, pred_1a, l2_universe())
    results_1b = evaluate(gold_1b, pred_1b, l1_dir_universe())
    drr, rev, denom, _amb = direction_reverse_rate_gold_excl(gold_1b, pred_1b)
    print(f"\nTask-1a  micro F1 {results_1a['micro_f1']:.4f}  "
          f"macro F1 {results_1a['macro_f1']:.4f}  "
          f"P {results_1a['micro_precision']:.4f}  "
          f"R {results_1a['micro_recall']:.4f}")
    print(f"Task-1b  micro F1 {results_1b['micro_f1']:.4f}  "
          f"macro F1 {results_1b['macro_f1']:.4f}  "
          f"P {results_1b['micro_precision']:.4f}  "
          f"R {results_1b['micro_recall']:.4f}  "
          f"DRR {drr:.4f} ({rev}/{denom})")
    return results_1a, results_1b, drr
