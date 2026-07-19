#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V2 — taxonomy loading, validation, rarity metadata, hashing.

This module is the single source of truth for:
  * loading the official human-value taxonomy from dataset/hv_categories/,
  * validating its completeness (54 L1, 20 L2, complete L1→L2 mapping,
    official direction mapping aligned="1" / contradictory="0"),
  * building rarity metadata from TRAIN gold labels only,
  * canonical hashing used for cache identity and run provenance.

No part of the taxonomy is hard-coded here; everything is read from the
official JSON files. Any inconsistency raises TaxonomyValidationError and
must abort the run.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
HV_DIR = BASE_DIR / "dataset" / "hv_categories"

L1_VALUES_PATH = HV_DIR / "human_value_level1_values.json"
L2_VALUES_PATH = HV_DIR / "human_value_level2_values.json"
TAXONOMY_PATH = HV_DIR / "human_value_taxonomy.json"
L1_TO_L2_PATH = HV_DIR / "level_1_to_level_2.json"
L2_TO_L1_PATH = HV_DIR / "level_2_to_level_1.json"
DIRECTION_PATH = HV_DIR / "direction_mapping.json"

TRAIN_LABELS_PATH = BASE_DIR / "dataset" / "gold_labels" / "train" / "train_human_values.json"

N_L1 = 54
N_L2 = 20

# Rarity thresholds on TRAIN gold label counts (deterministic, documented).
# These control *search attention* in the prompt only — never the evidence
# standard and never the acceptance threshold.
RARITY_THRESHOLDS = (
    ("frequent", 300),   # train_gold_count >= 300
    ("medium", 100),     # 100..299
    ("rare", 30),        # 30..99
    ("very_rare", 0),    # < 30
)


class TaxonomyValidationError(RuntimeError):
    """Raised when any official taxonomy file fails completeness validation."""


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class L1Entry:
    l1_id: str
    l1_name: str
    alternative_name: str
    descriptions: tuple
    l2_id: str
    l2_name: str
    taxonomy_code: str  # e.g. "SDT1" from human_value_taxonomy.json


@dataclass
class Taxonomy:
    l1_by_id: Dict[str, L1Entry]
    l2_id_to_name: Dict[str, str]
    l1_id_to_l2_id: Dict[str, str]
    direction_mapping: Dict[str, str]
    taxonomy_hash: str = field(default="")

    @property
    def l1_ids(self) -> List[str]:
        return sorted(self.l1_by_id.keys(), key=int)

    @property
    def l2_ids(self) -> List[str]:
        return sorted(self.l2_id_to_name.keys(), key=int)


def _load_json(path: Path):
    if not path.exists():
        raise TaxonomyValidationError(f"Required taxonomy file missing: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_taxonomy() -> Taxonomy:
    """Load and strictly validate the official taxonomy. Raise on any defect."""
    l1_name_to_id = _load_json(L1_VALUES_PATH)
    l2_name_to_id = _load_json(L2_VALUES_PATH)
    tax_values = _load_json(TAXONOMY_PATH).get("values", [])
    l1_to_l2_names = _load_json(L1_TO_L2_PATH).get("level_1_to_level_2", {})
    l2_to_l1_names = _load_json(L2_TO_L1_PATH).get("level_2_to_level_1", {})
    direction_mapping = _load_json(DIRECTION_PATH)

    errors: List[str] = []

    # --- direction mapping: exact official IDs -----------------------------
    if direction_mapping != {"aligned": "1", "contradictory": "0"}:
        errors.append(
            f"direction_mapping.json must be exactly "
            f"{{'aligned': '1', 'contradictory': '0'}}, got {direction_mapping!r}"
        )

    # --- Level-1: exactly 54, IDs "0".."53" ---------------------------------
    if len(l1_name_to_id) != N_L1:
        errors.append(f"Expected {N_L1} Level-1 values, got {len(l1_name_to_id)}")
    l1_ids = sorted(l1_name_to_id.values(), key=lambda x: int(x) if str(x).isdigit() else 10**9)
    if l1_ids != [str(i) for i in range(N_L1)]:
        errors.append(f"Level-1 IDs must be exactly '0'..'{N_L1-1}', got {l1_ids}")

    # --- Level-2: exactly 20, IDs "0".."19" ---------------------------------
    if len(l2_name_to_id) != N_L2:
        errors.append(f"Expected {N_L2} Level-2 values, got {len(l2_name_to_id)}")
    l2_ids = sorted(l2_name_to_id.values(), key=lambda x: int(x) if str(x).isdigit() else 10**9)
    if l2_ids != [str(i) for i in range(N_L2)]:
        errors.append(f"Level-2 IDs must be exactly '0'..'{N_L2-1}', got {l2_ids}")

    # --- L1→L2 mapping: complete and consistent both ways -------------------
    missing_map = set(l1_name_to_id) - set(l1_to_l2_names)
    if missing_map:
        errors.append(f"level_1_to_level_2.json missing L1 names: {sorted(missing_map)}")
    bad_l2 = {v for v in l1_to_l2_names.values() if v not in l2_name_to_id}
    if bad_l2:
        errors.append(f"level_1_to_level_2.json maps to unknown L2 names: {sorted(bad_l2)}")
    reverse_pairs = {
        (l1n, l2n) for l2n, l1list in l2_to_l1_names.items() for l1n in l1list
    }
    forward_pairs = {(l1n, l2n) for l1n, l2n in l1_to_l2_names.items()}
    if forward_pairs != reverse_pairs:
        errors.append(
            "level_1_to_level_2.json and level_2_to_level_1.json are inconsistent: "
            f"forward-only={sorted(forward_pairs - reverse_pairs)}, "
            f"reverse-only={sorted(reverse_pairs - forward_pairs)}"
        )

    # --- human_value_taxonomy.json: one entry per L1 with descriptions ------
    tax_by_l1_name = {}
    for entry in tax_values:
        name = entry.get("level-1")
        if name in tax_by_l1_name:
            errors.append(f"human_value_taxonomy.json duplicate level-1 entry: {name!r}")
        tax_by_l1_name[name] = entry
    if set(tax_by_l1_name) != set(l1_name_to_id):
        errors.append(
            "human_value_taxonomy.json level-1 names do not match "
            f"human_value_level1_values.json: only-taxonomy="
            f"{sorted(set(tax_by_l1_name) - set(l1_name_to_id))}, only-values="
            f"{sorted(set(l1_name_to_id) - set(tax_by_l1_name))}"
        )

    if errors:
        raise TaxonomyValidationError(
            "Taxonomy validation failed:\n  - " + "\n  - ".join(errors)
        )

    l1_by_id: Dict[str, L1Entry] = {}
    l1_id_to_l2_id: Dict[str, str] = {}
    for l1_name, l1_id in l1_name_to_id.items():
        tax_entry = tax_by_l1_name[l1_name]
        l2_name_from_map = l1_to_l2_names[l1_name]
        l2_name_from_tax = tax_entry.get("level-2")
        if l2_name_from_tax != l2_name_from_map:
            raise TaxonomyValidationError(
                f"L1 {l1_name!r}: level-2 disagrees between "
                f"human_value_taxonomy.json ({l2_name_from_tax!r}) and "
                f"level_1_to_level_2.json ({l2_name_from_map!r})"
            )
        alt = tax_entry.get("alternativeName", "")
        descs = tuple(tax_entry.get("descriptions", []))
        if not alt or not descs:
            raise TaxonomyValidationError(
                f"L1 {l1_name!r}: missing alternativeName or descriptions "
                f"in human_value_taxonomy.json"
            )
        l2_id = l2_name_to_id[l2_name_from_map]
        l1_by_id[l1_id] = L1Entry(
            l1_id=l1_id,
            l1_name=l1_name,
            alternative_name=alt,
            descriptions=descs,
            l2_id=l2_id,
            l2_name=l2_name_from_map,
            taxonomy_code=tax_entry.get("id", ""),
        )
        l1_id_to_l2_id[l1_id] = l2_id

    l2_id_to_name = {v: k for k, v in l2_name_to_id.items()}

    tax = Taxonomy(
        l1_by_id=l1_by_id,
        l2_id_to_name=l2_id_to_name,
        l1_id_to_l2_id=l1_id_to_l2_id,
        direction_mapping=dict(direction_mapping),
    )
    tax.taxonomy_hash = compute_taxonomy_hash(tax)
    return tax


def compute_taxonomy_hash(tax: Taxonomy) -> str:
    payload = {
        "l1": {
            lid: {
                "name": e.l1_name,
                "alt": e.alternative_name,
                "descriptions": list(e.descriptions),
                "l2_id": e.l2_id,
                "l2_name": e.l2_name,
                "code": e.taxonomy_code,
            }
            for lid, e in tax.l1_by_id.items()
        },
        "l2": tax.l2_id_to_name,
        "direction": tax.direction_mapping,
    }
    return sha256_text(canonical_json(payload))


# ============================================================
# Rarity metadata — TRAIN gold counts only (never dev/test gold)
# ============================================================

def frequency_group_for_count(count: int) -> str:
    for group, threshold in RARITY_THRESHOLDS:
        if count >= threshold:
            return group
    return RARITY_THRESHOLDS[-1][0]


def build_rarity_metadata(tax: Taxonomy, train_labels_path: Path = TRAIN_LABELS_PATH) -> dict:
    """
    Rarity metadata per L1 label, computed from TRAIN gold labels only.

    Returns:
      {
        "source": ...,
        "thresholds": [...],
        "labels": {l1_id: {"l1_id", "l1_name", "train_gold_count",
                            "frequency_group"}},
        "rarity_hash": sha256 of the canonical labels+thresholds payload,
      }
    """
    if not train_labels_path.exists():
        raise TaxonomyValidationError(f"Train gold labels missing: {train_labels_path}")
    with open(train_labels_path, "r", encoding="utf-8") as f:
        train_gold = json.load(f)

    counts: Counter = Counter()
    for item in train_gold:
        for hv in item.get("article_human_values", []):
            l1 = str(hv.get("l1_value", ""))
            if l1 in tax.l1_by_id:
                counts[l1] += 1

    labels = {}
    for l1_id in tax.l1_ids:
        c = counts.get(l1_id, 0)
        labels[l1_id] = {
            "l1_id": l1_id,
            "l1_name": tax.l1_by_id[l1_id].l1_name,
            "train_gold_count": c,
            "frequency_group": frequency_group_for_count(c),
        }

    payload = {"thresholds": [list(t) for t in RARITY_THRESHOLDS], "labels": labels}
    return {
        "source": str(train_labels_path.relative_to(BASE_DIR)),
        "thresholds": [list(t) for t in RARITY_THRESHOLDS],
        "labels": labels,
        "rarity_hash": sha256_text(canonical_json(payload)),
    }


def compute_article_hash(article: dict) -> str:
    """Hash of the classification-relevant article content."""
    payload = {
        "guid": str(article.get("guid", "")),
        "title": article.get("title", ""),
        "content": article.get("content", ""),
        "actors": article.get("actors", []),
    }
    return sha256_text(canonical_json(payload))
