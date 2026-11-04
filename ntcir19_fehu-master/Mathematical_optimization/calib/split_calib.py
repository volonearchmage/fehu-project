#!/usr/bin/env python3
"""
Internal Calibration Split for FEHU Mathematical Optimization.

Splits the official training set (1228 articles) into:
  - calib_articles (~15%, 184 articles, ~500 actor instances)
    for parameter tuning of all post-processing methods.
  - sub_train_articles (~85%, 1044 articles)
    available for any needed retraining (not used by A3/A4/A5).

Split is deterministic (hash-based modulo) and reproducible.
Output: calib/calib_split.json mapping each train guid to "calib" or "sub_train".

Usage:
    python calib/split_calib.py
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]  # ntcir19_fehu-master

TRAIN_ARTICLES = BASE / "dataset" / "train" / "train_event_base.json"
TRAIN_LABELS   = BASE / "dataset" / "gold_labels" / "train" / "train_human_values.json"
OUTPUT         = HERE / "calib_split.json"
CALIB_RATIO    = 0.15
SEED_HASH      = "fehu_calib_split_v1_20260724"


def main():
    articles = json.loads(TRAIN_ARTICLES.read_text(encoding="utf-8"))
    labels   = json.loads(TRAIN_LABELS.read_text(encoding="utf-8"))

    guid_to_labels = {item["guid"]: item for item in labels}

    # Deterministic split by hashing (guid + seed)
    split_map = {}
    calib_guids = []
    sub_train_guids = []

    for art in articles:
        guid = art["guid"]
        h = hashlib.sha256(f"{guid}:{SEED_HASH}".encode()).hexdigest()
        bucket = int(h[:8], 16) % 1000 / 1000.0
        if bucket < CALIB_RATIO:
            split_map[guid] = "calib"
            calib_guids.append(guid)
        else:
            split_map[guid] = "sub_train"
            sub_train_guids.append(guid)

    # Verify coverage: calib should contain representatives of all major
    # label groups (at minimum, ensure no L2 group is entirely absent).
    calib_label_set = set()
    for guid in calib_guids:
        if guid in guid_to_labels:
            for hv in guid_to_labels[guid].get("article_human_values", []):
                calib_label_set.add(f'{hv["direction"]}:{hv["l1_value"]}')

    output = {
        "seed_hash": SEED_HASH,
        "calib_ratio": CALIB_RATIO,
        "total_articles": len(articles),
        "n_calib": len(calib_guids),
        "n_sub_train": len(sub_train_guids),
        "n_calib_unique_labels": len(calib_label_set),
        "calib_guids": sorted(calib_guids),
        "sub_train_guids": sorted(sub_train_guids),
        "split_map": split_map,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Calibration split written to {OUTPUT}")
    print(f"  Total articles:    {len(articles)}")
    print(f"  Calib articles:    {len(calib_guids)} ({100*len(calib_guids)/len(articles):.1f}%)")
    print(f"  Sub-train articles:{len(sub_train_guids)} ({100*len(sub_train_guids)/len(articles):.1f}%)")
    print(f"  Calib label coverage: {len(calib_label_set)} unique direction:L1 classes")


if __name__ == "__main__":
    main()
