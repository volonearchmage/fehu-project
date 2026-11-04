#!/usr/bin/env python3
"""
DS_final Ensemble: 3-Way Majority Vote + Flash Direction Verification.

Takes predictions from 3 Pro prompt variants + Flash, outputs final ensemble.

Usage:
    python DS_final/scripts/ensemble.py \
        --baseline runs/baseline/pred_task1b.json \
        --targeted runs/targeted/pred_task1b.json \
        --compact   runs/compact/pred_task1b.json \
        --flash     runs/flash/pred_task1b.json \
        --event_base dataset/test/test_article_event_base.json \
        --output_1b DS_final/outputs/pred_task1b.json \
        --output_1a DS_final/outputs/pred_task1a.json
"""

from __future__ import annotations
import json, argparse, os, sys
from collections import defaultdict, Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]  # ntcir19_fehu-master/


def load_atoms(path: str) -> set[tuple[str, str, str, str]]:
    """Load predictions as set of (guid, actor, l1_value, direction)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    atoms = set()
    for art in data:
        guid = str(art["guid"])
        for hv in art.get("article_human_values", []):
            atoms.add((guid, str(hv["actor"]), str(hv["l1_value"]),
                       str(hv.get("direction", "1"))))
    return atoms


def load_flash_dir(path: str) -> dict[tuple[str, str, str], str]:
    """Load Flash predictions as (guid, actor, l1) -> direction map."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    result = {}
    for art in data:
        guid = str(art["guid"])
        for hv in art.get("article_human_values", []):
            result[(guid, str(hv["actor"]), str(hv["l1_value"]))] = \
                str(hv.get("direction", "1"))
    return result


def derive_1a(atoms: set[tuple[str, str, str, str]],
              l1_to_l2: dict[str, str],
              guid_order: list[str]) -> list[dict]:
    """Derive Task-1a predictions from Task-1b via L1->L2 mapping."""
    by_guid = defaultdict(set)
    for guid, aid, l1, _ in atoms:
        l2 = l1_to_l2.get(l1)
        if l2:
            by_guid[guid].add((aid, l2))

    result = []
    for guid in guid_order:
        pairs = by_guid.get(guid, set())
        hvs = [{"actor": a, "l2_value": l2} for a, l2 in sorted(pairs)]
        result.append({"guid": guid, "article_human_values": hvs})
    return result


def main():
    parser = argparse.ArgumentParser(description="DS_final Ensemble")
    parser.add_argument("--baseline", required=True, help="Pro T=0.0 baseline pred_task1b.json")
    parser.add_argument("--targeted", required=True, help="Pro T=0.0 targeted_more_shot_balanced pred_task1b.json")
    parser.add_argument("--compact", required=True, help="Pro T=0.0 compact_strict pred_task1b.json")
    parser.add_argument("--flash", required=True, help="Flash T=0.0 pred_task1b.json")
    parser.add_argument("--event_base", required=True,
                        help="Official Task-1 event-base file defining all required guids")
    parser.add_argument("--output_1b", required=True, help="Output path for ensemble pred_task1b.json")
    parser.add_argument("--output_1a", required=True, help="Output path for ensemble pred_task1a.json")
    args = parser.parse_args()

    event_data = json.loads(Path(args.event_base).read_text(encoding="utf-8"))
    guid_order = [str(item["guid"]) for item in event_data]
    if len(guid_order) != len(set(guid_order)):
        raise ValueError("Duplicate guid in event-base file")
    expected_guids = set(guid_order)

    for name, path in {
        "baseline": args.baseline,
        "targeted": args.targeted,
        "compact": args.compact,
        "flash": args.flash,
    }.items():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        actual_guids = {str(item["guid"]) for item in data}
        if len(data) != len(actual_guids) or actual_guids != expected_guids:
            raise ValueError(
                f"{name} predictions do not exactly cover the event-base guids: "
                f"expected {len(expected_guids)}, got {len(actual_guids)}"
            )

    print("=" * 60)
    print("DS_final Ensemble: 3-Way Majority Vote + Flash Direction Fix")
    print("=" * 60)

    # ── Load predictions ──
    S_base = load_atoms(args.baseline)
    S_tmb  = load_atoms(args.targeted)
    S_cs   = load_atoms(args.compact)
    flash_dir = load_flash_dir(args.flash)

    print(f"\nbaseline:                {len(S_base)} predictions")
    print(f"targeted_more_shot:      {len(S_tmb)} predictions")
    print(f"compact_strict:          {len(S_cs)} predictions")
    print(f"Flash:                   {len(flash_dir)} predictions")

    # ── 3-Way Majority Vote (>=2/3) ──
    all_preds = list(S_base) + list(S_tmb) + list(S_cs)
    counts = Counter(all_preds)
    S_majority = {p for p, c in counts.items() if c >= 2}

    all3 = sum(1 for p, c in counts.items() if c == 3)
    two_of_3 = sum(1 for p, c in counts.items() if c == 2)

    print(f"\n3-way majority vote:")
    print(f"  3/3 agree:  {all3}")
    print(f"  2/3 agree:  {two_of_3}")
    print(f"  Total:      {len(S_majority)} predictions")

    # ── Flash Direction Verification ──
    S_final = set()
    n_flipped = 0
    for (guid, aid, l1, d_maj) in S_majority:
        flash_d = flash_dir.get((guid, aid, l1))
        if flash_d is None or flash_d == d_maj:
            S_final.add((guid, aid, l1, d_maj))
        else:
            S_final.add((guid, aid, l1, flash_d))
            n_flipped += 1

    print(f"\nFlash direction fix:")
    print(f"  Flipped:   {n_flipped} directions ({100*n_flipped/len(S_majority):.1f}%)")
    print(f"  S_final:   {len(S_final)} predictions")

    # ── Build Task-1b output ──
    by_guid = defaultdict(list)
    for guid, aid, l1, direction in sorted(S_final):
        by_guid[guid].append({
            "actor": aid,
            "l1_value": l1,
            "direction": direction,
        })

    output_1b = [
        {
            "guid": guid,
            "article_human_values": sorted(
                by_guid.get(guid, []),
                key=lambda x: (x["actor"], x["l1_value"], x["direction"]),
            ),
        }
        for guid in guid_order
    ]

    Path(args.output_1b).parent.mkdir(parents=True, exist_ok=True)
    json.dump(output_1b, open(args.output_1b, "w"), indent=2, ensure_ascii=False)
    print(f"\nTask-1b output: {args.output_1b}")
    print(f"  Articles: {len(output_1b)}")
    print(f"  Predictions: {sum(len(a['article_human_values']) for a in output_1b)}")

    # ── Derive Task-1a ──
    l1_to_l2_path = PROJECT / "dataset" / "hv_categories"
    l1n = json.loads((l1_to_l2_path / "human_value_level1_values.json").read_text(encoding="utf-8"))
    l2n = json.loads((l1_to_l2_path / "human_value_level2_values.json").read_text(encoding="utf-8"))
    l1_to_l2_raw = json.loads((l1_to_l2_path / "level_1_to_level_2.json").read_text(encoding="utf-8"))
    l1_to_l2 = {l1n[k]: l2n[v] for k, v in l1_to_l2_raw["level_1_to_level_2"].items()}

    output_1a = derive_1a(S_final, l1_to_l2, guid_order)

    Path(args.output_1a).parent.mkdir(parents=True, exist_ok=True)
    json.dump(output_1a, open(args.output_1a, "w"), indent=2, ensure_ascii=False)
    print(f"\nTask-1a output: {args.output_1a}")
    print(f"  Articles: {len(output_1a)}")
    print(f"  Predictions: {sum(len(a['article_human_values']) for a in output_1a)}")

    # ── Summary ──
    summary = {
        "method": "3-way majority vote + Flash direction verification",
        "variants": ["baseline", "targeted_more_shot_balanced", "compact_strict"],
        "flash_model": "deepseek-v4-flash",
        "pro_model": "deepseek-v4-pro",
        "temperature": 0.0,
        "thinking": "disabled",
        "event_base": str(Path(args.event_base).resolve()),
        "articles": len(guid_order),
        "majority_vote": {"3_of_3": all3, "2_of_3": two_of_3, "total": len(S_majority)},
        "flash_flipped": n_flipped,
        "final_predictions_1b": len(S_final),
    }
    summary_path = Path(args.output_1b).parent / "ensemble_summary.json"
    json.dump(summary, open(summary_path, "w"), indent=2, ensure_ascii=False)
    print(f"\nSummary: {summary_path}")
    print("\nDone!")


if __name__ == "__main__":
    main()
