#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_augmentation_generation_preview_v1/inspect_generation_preview.py

Read-only summary of a generation-preview folder produced by
`run_generation_preview.py`. No API calls; no modifications.

Run from project root:
    python research/fehu_augmentation_generation_preview_v1/inspect_generation_preview.py \\
        --preview_dir output/research_generation_preview/<YYYYMMDD_HHMMSS>
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_jsonl(p: Path) -> List[Dict]:
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def parse_args():
    ap = argparse.ArgumentParser(description="Inspect a generation-preview folder (read-only).")
    ap.add_argument("--preview_dir", type=str, required=True,
                    help="Path to output/research_generation_preview/<YYYYMMDD_HHMMSS>/.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    p = Path(args.preview_dir)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        print(f"ERROR: preview_dir does not exist: {p}")
        sys.exit(1)

    prev_file = p / "generation_requests_preview.jsonl"
    if not prev_file.exists():
        print(f"ERROR: generation_requests_preview.jsonl missing in {p}")
        sys.exit(1)

    requests = load_jsonl(prev_file)
    print("=" * 64)
    print("Preview Folder Inspection")
    print("=" * 64)
    print(f"Folder       : {p}")
    print(f"Total requests: {len(requests)}")
    print()

    # ── Type breakdown ─────────────────────────────────────────────────────
    by_type = Counter(r["augmentation_type"] for r in requests)
    print("Requests by augmentation type:")
    for k in ["paraphrase", "rare_positive", "hard_negative", "direction_contrastive"]:
        print(f"  {k:<26} {by_type.get(k, 0):>3}")
    print(f"  {'TOTAL':<26} {sum(by_type.values()):>3}")
    print()

    # ── Label breakdown ────────────────────────────────────────────────────
    by_label = Counter((r["target_l1_value_id"], r["target_l1_value_name"]) for r in requests)
    print("Requests by L1 label:")
    for (lid, name), n in sorted(by_label.items(), key=lambda kv: (-kv[1], kv[0][0])):
        print(f"  L1={lid:<3} {name:<35} {n}")
    print()

    # ── Seed coverage ──────────────────────────────────────────────────────
    n_with_seed = sum(1 for r in requests if r.get("seed_guid"))
    n_no_seed   = sum(1 for r in requests if not r.get("seed_guid"))
    print(f"Requests requiring a seed (paraphrase): "
          f"{by_type.get('paraphrase', 0)}")
    print(f"Requests with a seed (paraphrase + seeded rare_positive): {n_with_seed}")
    print(f"Requests without a seed (definition-only generation):     {n_no_seed}")
    print()

    # ── Direction-contrastive pairs ────────────────────────────────────────
    pair_ids = defaultdict(list)
    for r in requests:
        if r["augmentation_type"] == "direction_contrastive":
            pair_ids[r["request_id"]].append(r.get("paired_request_id"))
    n_dc = by_type.get("direction_contrastive", 0)
    n_pairs = n_dc // 2
    print(f"Direction-contrastive requests: {n_dc}  ({n_pairs} pairs)")
    # Cross-check: every dir-contrastive request has paired_request_id that points
    # to another request in this file
    all_ids = {r["request_id"] for r in requests}
    dangling = [r["request_id"] for r in requests
                if r["augmentation_type"] == "direction_contrastive"
                and r.get("paired_request_id") not in all_ids]
    if dangling:
        print(f"  [WARN] {len(dangling)} dir-contrastive requests have a paired_request_id "
              f"that is not present in this preview:")
        for rid in dangling[:5]:
            print(f"    - {rid}")
    else:
        print("  pair linkage OK (every paired_request_id resolves within this preview)")
    print()

    # ── Top 10 shortened prompts ───────────────────────────────────────────
    print("Top 10 preview prompts (shortened):")
    for i, r in enumerate(requests[:10], 1):
        sp = (r.get("system_prompt") or "")
        up = (r.get("user_prompt") or "")
        short_sp = sp.split("\n", 1)[0][:90]
        short_up = up.split("\n", 1)[0][:90]
        print(f"  [{i:>2}] {r['request_id']}")
        print(f"       type={r['augmentation_type']}  L1={r['target_l1_value_id']} "
              f"({r['target_l1_value_name']})  dir={r.get('target_direction')}")
        print(f"       sys : {short_sp}")
        print(f"       user: {short_up}")
    print()

    # ── Risk warnings ──────────────────────────────────────────────────────
    print("Risk warnings:")
    warned = False
    if dangling:
        print(f"  - {len(dangling)} dangling pair references"); warned = True
    no_seed_para = [r for r in requests
                    if r["augmentation_type"] == "paraphrase" and not r.get("seed_guid")]
    if no_seed_para:
        print(f"  - {len(no_seed_para)} paraphrase requests without a seed (unexpected)"); warned = True
    # Hard-negative without alternative_label_id
    bad_hn = [r for r in requests
              if r["augmentation_type"] == "hard_negative"
              and not r.get("alternative_label_id")]
    if bad_hn:
        print(f"  - {len(bad_hn)} hard_negative requests missing alternative_label_id "
              f"(generator will need to pick one)"); warned = True
    # All requests should be marked preview_only
    not_preview = [r for r in requests if not r.get("preview_only")]
    if not_preview:
        print(f"  - {len(not_preview)} requests NOT marked preview_only (BUG)"); warned = True
    # Recommended models recorded
    no_model = [r for r in requests if not r.get("recommended_generator_model")]
    if no_model:
        print(f"  - {len(no_model)} requests missing recommended_generator_model"); warned = True
    if not warned:
        print("  (none — all checks passed)")

    print()
    print("Done. This script is read-only.")


if __name__ == "__main__":
    main()
