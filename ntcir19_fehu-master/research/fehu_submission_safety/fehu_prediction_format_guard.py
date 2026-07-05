#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_submission_safety/fehu_prediction_format_guard.py

Local-only validator for final FEHU prediction files (pred_task1a.json /
pred_task1b.json) against the official schema. Reads only; never modifies
prediction files; never calls an API.

Run from project root:
    python research/fehu_submission_safety/fehu_prediction_format_guard.py \\
        --event_base dataset/dev/dev_event_base.json \\
        --pred_task1a output/<dir>/pred_task1a.json \\
        --pred_task1b output/<dir>/pred_task1b.json \\
        --mode dev

Exit codes:
    0 = clean
    2 = at least one issue found

Output: output/research_submission_safety/YYYYMMDD_HHMMSS/
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

L2_VALID = {str(i) for i in range(20)}    # "0".."19"
L1_VALID = {str(i) for i in range(54)}    # "0".."53"
DIR_VALID = {"0", "1"}                     # contradictory / aligned


# ============================================================
# IO
# ============================================================

def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def write_csv(rows: List[Dict], p: Path, fieldnames: Optional[List[str]] = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


# ============================================================
# EVENT BASE
# ============================================================

def load_event_base(p: Path) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """
    Return (guid set, {guid -> set of actor ids}).
    """
    data = load_json(p)
    guids: Set[str] = set()
    actors_by_guid: Dict[str, Set[str]] = {}
    for art in data:
        guid = str(art["guid"])
        guids.add(guid)
        actor_set: Set[str] = set()
        for d in art.get("actors", []):
            for _, aid in d.items():
                actor_set.add(str(aid))
        actors_by_guid[guid] = actor_set
    return guids, actors_by_guid


# ============================================================
# CHECKERS
# ============================================================

def check_task1a(data: Any,
                 event_guids: Set[str],
                 actors_by_guid: Dict[str, Set[str]],
                 strict: bool) -> Tuple[List[Dict], Dict]:
    """Return (invalid_rows, stats)."""
    invalid: List[Dict] = []
    stats = {
        "n_articles": 0, "n_predictions": 0,
        "n_unique_guids": 0, "n_duplicates": 0,
        "n_bad_actor": 0, "n_bad_l2": 0,
        "n_unknown_guid": 0,
        "n_extra_fields": 0,
        "n_entries_missing_actor": 0,
        "n_entries_missing_l2": 0,
    }
    seen_pairs: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
    pred_guids: Set[str] = set()
    allowed_entry_keys = {"actor", "l2_value"}

    if not isinstance(data, list):
        invalid.append({"file": "pred_task1a", "issue": "top-level JSON is not a list"})
        return invalid, stats

    for art in data:
        if not isinstance(art, dict) or "guid" not in art or "article_human_values" not in art:
            invalid.append({"file": "pred_task1a", "issue": "article missing guid/article_human_values"})
            continue
        guid = str(art["guid"])
        pred_guids.add(guid)
        stats["n_articles"] += 1
        if guid not in event_guids:
            stats["n_unknown_guid"] += 1
            invalid.append({"file": "pred_task1a", "guid": guid, "issue": "guid not in event_base"})

        for entry in art.get("article_human_values", []) or []:
            stats["n_predictions"] += 1
            if not isinstance(entry, dict):
                invalid.append({"file": "pred_task1a", "guid": guid, "issue": "entry is not a dict"})
                continue
            if "actor" not in entry:
                stats["n_entries_missing_actor"] += 1
                invalid.append({"file": "pred_task1a", "guid": guid, "issue": "missing 'actor'"})
            if "l2_value" not in entry:
                stats["n_entries_missing_l2"] += 1
                invalid.append({"file": "pred_task1a", "guid": guid, "issue": "missing 'l2_value'"})
            actor = str(entry.get("actor", ""))
            l2 = str(entry.get("l2_value", ""))

            if guid in actors_by_guid and actor and actor not in actors_by_guid[guid]:
                stats["n_bad_actor"] += 1
                invalid.append({"file": "pred_task1a", "guid": guid, "actor": actor,
                                "issue": "actor not declared in event_base"})
            if l2 not in L2_VALID:
                stats["n_bad_l2"] += 1
                invalid.append({"file": "pred_task1a", "guid": guid, "actor": actor,
                                "issue": f"l2_value={l2!r} not in 0..19"})

            key = (actor, l2)
            if key in seen_pairs[guid]:
                stats["n_duplicates"] += 1
                invalid.append({"file": "pred_task1a", "guid": guid, "actor": actor,
                                "issue": f"duplicate (actor, l2_value)={key}"})
            else:
                seen_pairs[guid].add(key)

            if strict:
                extra = set(entry.keys()) - allowed_entry_keys
                if extra:
                    stats["n_extra_fields"] += 1
                    invalid.append({"file": "pred_task1a", "guid": guid, "actor": actor,
                                    "issue": f"strict mode: unknown fields {sorted(extra)}"})

    stats["n_unique_guids"] = len(pred_guids)
    return invalid, stats


def check_task1b(data: Any,
                 event_guids: Set[str],
                 actors_by_guid: Dict[str, Set[str]],
                 strict: bool) -> Tuple[List[Dict], Dict]:
    invalid: List[Dict] = []
    stats = {
        "n_articles": 0, "n_predictions": 0,
        "n_unique_guids": 0, "n_duplicates": 0,
        "n_bad_actor": 0, "n_bad_l1": 0, "n_bad_direction": 0,
        "n_unknown_guid": 0,
        "n_extra_fields": 0,
        "n_entries_missing_actor": 0,
        "n_entries_missing_l1": 0,
        "n_entries_missing_direction": 0,
    }
    seen_tuples: Dict[str, Set[Tuple[str, str, str]]] = defaultdict(set)
    pred_guids: Set[str] = set()
    allowed_entry_keys = {"actor", "l1_value", "direction"}

    if not isinstance(data, list):
        invalid.append({"file": "pred_task1b", "issue": "top-level JSON is not a list"})
        return invalid, stats

    for art in data:
        if not isinstance(art, dict) or "guid" not in art or "article_human_values" not in art:
            invalid.append({"file": "pred_task1b", "issue": "article missing guid/article_human_values"})
            continue
        guid = str(art["guid"])
        pred_guids.add(guid)
        stats["n_articles"] += 1
        if guid not in event_guids:
            stats["n_unknown_guid"] += 1
            invalid.append({"file": "pred_task1b", "guid": guid, "issue": "guid not in event_base"})

        for entry in art.get("article_human_values", []) or []:
            stats["n_predictions"] += 1
            if not isinstance(entry, dict):
                invalid.append({"file": "pred_task1b", "guid": guid, "issue": "entry is not a dict"})
                continue
            if "actor" not in entry:
                stats["n_entries_missing_actor"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "issue": "missing 'actor'"})
            if "l1_value" not in entry:
                stats["n_entries_missing_l1"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "issue": "missing 'l1_value'"})
            if "direction" not in entry:
                stats["n_entries_missing_direction"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "issue": "missing 'direction'"})
            actor = str(entry.get("actor", ""))
            l1 = str(entry.get("l1_value", ""))
            direction = str(entry.get("direction", ""))

            if guid in actors_by_guid and actor and actor not in actors_by_guid[guid]:
                stats["n_bad_actor"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "actor": actor,
                                "issue": "actor not declared in event_base"})
            if l1 not in L1_VALID:
                stats["n_bad_l1"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "actor": actor,
                                "issue": f"l1_value={l1!r} not in 0..53"})
            if direction not in DIR_VALID:
                stats["n_bad_direction"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "actor": actor,
                                "issue": f"direction={direction!r} not in {{'0','1'}}"})

            key = (actor, l1, direction)
            if key in seen_tuples[guid]:
                stats["n_duplicates"] += 1
                invalid.append({"file": "pred_task1b", "guid": guid, "actor": actor,
                                "issue": f"duplicate (actor, l1_value, direction)={key}"})
            else:
                seen_tuples[guid].add(key)

            if strict:
                extra = set(entry.keys()) - allowed_entry_keys
                if extra:
                    stats["n_extra_fields"] += 1
                    invalid.append({"file": "pred_task1b", "guid": guid, "actor": actor,
                                    "issue": f"strict mode: unknown fields {sorted(extra)}"})

    stats["n_unique_guids"] = len(pred_guids)
    return invalid, stats


def cross_check_guids(data_1a: Any, data_1b: Any) -> List[Dict]:
    if not (isinstance(data_1a, list) and isinstance(data_1b, list)):
        return []
    g1a = {str(a["guid"]) for a in data_1a if isinstance(a, dict) and "guid" in a}
    g1b = {str(a["guid"]) for a in data_1b if isinstance(a, dict) and "guid" in a}
    msgs = []
    only_a = g1a - g1b
    only_b = g1b - g1a
    if only_a:
        msgs.append({"file": "cross", "issue": f"{len(only_a)} guid(s) present in task1a but not task1b"})
    if only_b:
        msgs.append({"file": "cross", "issue": f"{len(only_b)} guid(s) present in task1b but not task1a"})
    return msgs


# ============================================================
# REPORT
# ============================================================

def write_report(args, summary: Dict, invalid: List[Dict], out_dir: Path) -> None:
    lines = [
        "# FEHU Prediction Format Guard Report",
        "",
        f"**Timestamp:** {datetime.now().isoformat(timespec='seconds')}",
        f"**Mode:** `{args.mode}`",
        f"**Event base:** `{args.event_base}`",
        f"**Pred Task-1a:** `{args.pred_task1a}`",
        f"**Pred Task-1b:** `{args.pred_task1b}`",
        f"**Strict mode:** `{args.strict}`",
        "",
        "## Verdict",
        "",
    ]
    if summary["status"] == "clean":
        lines.append("✅ **All checks passed. Predictions are FEHU-conformant.**")
    else:
        lines.append(f"❌ **{len(invalid)} issue(s) found. See `invalid_entries.csv` for details.**")
    lines += [
        "",
        "## Summary",
        "",
        "| Metric | Task-1a | Task-1b |",
        "|---|---|---|",
        f"| articles | {summary['task1a']['n_articles']} | {summary['task1b']['n_articles']} |",
        f"| unique guids | {summary['task1a']['n_unique_guids']} | {summary['task1b']['n_unique_guids']} |",
        f"| predictions | {summary['task1a']['n_predictions']} | {summary['task1b']['n_predictions']} |",
        f"| avg preds/article | {summary['task1a']['avg_preds_per_article']:.2f} | {summary['task1b']['avg_preds_per_article']:.2f} |",
        f"| duplicates | {summary['task1a']['n_duplicates']} | {summary['task1b']['n_duplicates']} |",
        f"| bad actor | {summary['task1a']['n_bad_actor']} | {summary['task1b']['n_bad_actor']} |",
        f"| bad label id | {summary['task1a']['n_bad_l2']} | {summary['task1b']['n_bad_l1']} |",
        f"| bad direction | n/a | {summary['task1b']['n_bad_direction']} |",
        f"| unknown guid | {summary['task1a']['n_unknown_guid']} | {summary['task1b']['n_unknown_guid']} |",
        f"| extra fields (strict) | {summary['task1a']['n_extra_fields']} | {summary['task1b']['n_extra_fields']} |",
        "",
        f"**Event base guid count:** {summary['event_guid_count']}",
        f"**Likely full submission:** {summary['likely_full_submission']}",
    ]
    if not summary["likely_full_submission"]:
        lines.append("> ⚠ Article count is less than event_base guid count — this looks like "
                     "a **limit/debug** run. Do NOT submit as a final result.")

    if summary["cross_issues"]:
        lines += ["", "## Cross-file consistency issues", ""]
        for x in summary["cross_issues"]:
            lines.append(f"- {x['issue']}")

    lines += [
        "",
        "## Constraints honoured",
        "",
        "- No API call.",
        "- No modification of any prediction file.",
        "- No reading of `.env` values.",
        "",
    ]
    (out_dir / "format_guard_report.md").write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# MAIN
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser(description="Validate FEHU Task-1 prediction files (local-only).")
    ap.add_argument("--event_base", type=str, required=True,
                    help="dataset/dev/dev_event_base.json or dataset/test/test_article_event_base.json")
    ap.add_argument("--pred_task1a", type=str, required=True)
    ap.add_argument("--pred_task1b", type=str, required=True)
    ap.add_argument("--mode", choices=["dev", "test"], default="dev")
    ap.add_argument("--strict", action="store_true",
                    help="Reject any extra fields in prediction entries.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    eb = Path(args.event_base);   eb = eb if eb.is_absolute() else PROJECT_ROOT / eb
    p1a = Path(args.pred_task1a); p1a = p1a if p1a.is_absolute() else PROJECT_ROOT / p1a
    p1b = Path(args.pred_task1b); p1b = p1b if p1b.is_absolute() else PROJECT_ROOT / p1b

    if not eb.exists():
        print(f"ERROR: event_base does not exist: {eb}"); sys.exit(1)
    if not p1a.exists():
        print(f"ERROR: pred_task1a does not exist: {p1a}"); sys.exit(1)
    if not p1b.exists():
        print(f"ERROR: pred_task1b does not exist: {p1b}"); sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "output" / "research_submission_safety" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("FEHU Prediction Format Guard")
    print("=" * 64)
    print(f"event_base   : {eb}")
    print(f"pred_task1a  : {p1a}")
    print(f"pred_task1b  : {p1b}")
    print(f"mode         : {args.mode}   strict: {args.strict}")
    print(f"out_dir      : {out_dir}")
    print()

    event_guids, actors_by_guid = load_event_base(eb)
    print(f"Event base has {len(event_guids)} guids.")

    try:
        data_1a = load_json(p1a)
    except Exception as e:
        print(f"ERROR parsing pred_task1a: {e}")
        sys.exit(2)
    try:
        data_1b = load_json(p1b)
    except Exception as e:
        print(f"ERROR parsing pred_task1b: {e}")
        sys.exit(2)

    invalid_a, stats_a = check_task1a(data_1a, event_guids, actors_by_guid, args.strict)
    invalid_b, stats_b = check_task1b(data_1b, event_guids, actors_by_guid, args.strict)
    cross_issues = cross_check_guids(data_1a, data_1b)

    invalid = invalid_a + invalid_b + cross_issues

    # Derived
    stats_a["avg_preds_per_article"] = (
        stats_a["n_predictions"] / max(stats_a["n_articles"], 1)
    )
    stats_b["avg_preds_per_article"] = (
        stats_b["n_predictions"] / max(stats_b["n_articles"], 1)
    )

    likely_full = (
        stats_a["n_unique_guids"] == len(event_guids)
        and stats_b["n_unique_guids"] == len(event_guids)
    )

    summary = {
        "event_base":        str(eb),
        "pred_task1a":       str(p1a),
        "pred_task1b":       str(p1b),
        "mode":              args.mode,
        "strict":            args.strict,
        "event_guid_count":  len(event_guids),
        "task1a":            stats_a,
        "task1b":            stats_b,
        "cross_issues":      cross_issues,
        "likely_full_submission": likely_full,
        "status":            "clean" if not invalid else "issues_found",
        "n_invalid_entries": len(invalid),
        "out_dir":           str(out_dir),
        "timestamp":         ts,
    }

    (out_dir / "format_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if invalid:
        # Normalise keys for CSV
        cols = ["file", "guid", "actor", "issue"]
        flat = [{c: r.get(c, "") for c in cols} for r in invalid]
        write_csv(flat, out_dir / "invalid_entries.csv", cols)

    write_report(args, summary, invalid, out_dir)

    # ── Console summary ────────────────────────────────────────────────────
    print()
    print("Task-1a:")
    print(f"  articles={stats_a['n_articles']}  preds={stats_a['n_predictions']}  "
          f"avg={stats_a['avg_preds_per_article']:.2f}")
    print(f"  duplicates={stats_a['n_duplicates']}  bad_actor={stats_a['n_bad_actor']}  "
          f"bad_l2={stats_a['n_bad_l2']}  unknown_guid={stats_a['n_unknown_guid']}")
    print("Task-1b:")
    print(f"  articles={stats_b['n_articles']}  preds={stats_b['n_predictions']}  "
          f"avg={stats_b['avg_preds_per_article']:.2f}")
    print(f"  duplicates={stats_b['n_duplicates']}  bad_actor={stats_b['n_bad_actor']}  "
          f"bad_l1={stats_b['n_bad_l1']}  bad_direction={stats_b['n_bad_direction']}  "
          f"unknown_guid={stats_b['n_unknown_guid']}")
    if cross_issues:
        print("Cross issues:")
        for x in cross_issues:
            print(f"  - {x['issue']}")
    print()
    print(f"Likely full submission: {likely_full}")
    print(f"Verdict: {'CLEAN ✅' if not invalid else 'ISSUES FOUND ❌  ('+str(len(invalid))+' rows)'}")
    print(f"Report folder: {out_dir}")

    sys.exit(0 if not invalid else 2)


if __name__ == "__main__":
    main()
