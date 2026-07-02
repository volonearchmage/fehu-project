#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_augmentation_v1/validate_augmented_data.py

Local-only schema + semantic validator for future augmented FEHU data.
No API calls, no model loading.

Run from project root:
    python research/fehu_augmentation_v1/validate_augmented_data.py \
        --input path/to/augmented_samples.jsonl

If --input is omitted, prints usage and exits cleanly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

L1_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level1_values.json"
L2_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_PATH  = PROJECT_ROOT / "dataset/hv_categories/level_1_to_level_2.json"
SCHEMA_PATH    = Path(__file__).resolve().parent / "augmentation_schema.json"


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def load_taxonomy() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """Return (l1_id_to_name, l2_id_to_name, l1_id_to_l2_id)."""
    l1_name_to_id = load_json(L1_VALUES_PATH)
    l2_name_to_id = load_json(L2_VALUES_PATH)
    raw           = load_json(L1_TO_L2_PATH)["level_1_to_level_2"]

    l1_id_to_name = {v: k for k, v in l1_name_to_id.items()}
    l2_id_to_name = {v: k for k, v in l2_name_to_id.items()}
    l1_id_to_l2_id = {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}
    return l1_id_to_name, l2_id_to_name, l1_id_to_l2_id


# ============================================================
# Lightweight schema validation (no jsonschema dep)
# ============================================================

def _check_pattern(s: Optional[str], pattern: str) -> bool:
    if not isinstance(s, str):
        return False
    return bool(re.match(pattern, s))


def _schema_value_errors(item: Dict, schema: Dict) -> List[str]:
    """Minimal structural validator for our schema (required + type + enum + pattern + length)."""
    errors: List[str] = []
    required = schema.get("required", [])
    props = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for key in required:
        if key not in item:
            errors.append(f"missing required field: {key}")

    if additional is False:
        for key in item.keys():
            if key not in props:
                errors.append(f"unknown field (additionalProperties=false): {key}")

    for key, val in item.items():
        spec = props.get(key)
        if spec is None:
            continue  # already flagged if needed
        t = spec.get("type")
        if t == "string" and not isinstance(val, str):
            errors.append(f"{key}: expected string, got {type(val).__name__}")
            continue
        if t == "boolean" and not isinstance(val, bool):
            errors.append(f"{key}: expected boolean, got {type(val).__name__}")
            continue
        if t == "integer" and not isinstance(val, int):
            errors.append(f"{key}: expected integer, got {type(val).__name__}")
            continue

        enum = spec.get("enum")
        if enum is not None and val not in enum:
            errors.append(f"{key}: value {val!r} not in enum {enum}")

        pat = spec.get("pattern")
        if pat is not None and isinstance(val, str) and not re.match(pat, val):
            errors.append(f"{key}: value {val!r} does not match pattern {pat}")

        if isinstance(val, str):
            mn = spec.get("minLength")
            mx = spec.get("maxLength")
            if mn is not None and len(val) < mn:
                errors.append(f"{key}: length {len(val)} < minLength {mn}")
            if mx is not None and len(val) > mx:
                errors.append(f"{key}: length {len(val)} > maxLength {mx}")

    return errors


# ============================================================
# Semantic checks
# ============================================================

def _l1_l2_matches(l1_id: str, l2_id: str, l1_id_to_l2_id: Dict[str, str]) -> bool:
    return l1_id_to_l2_id.get(l1_id) == l2_id


def _direction_name_matches(direction: str, direction_name: str) -> bool:
    return (
        (direction == "1" and direction_name == "aligned")
        or (direction == "0" and direction_name == "contradictory")
    )


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _evidence_check(item: Dict) -> Optional[str]:
    """Return error string or None."""
    content = item.get("content", "")
    evidence = item.get("evidence_sentence", "")
    actor = item.get("actor_name", "")
    if actor and actor not in content:
        return "actor_name not found verbatim in content"
    if evidence.startswith("[derived] "):
        return None  # explicit derivation flag — accepted
    # require a normalised substring match (whitespace-collapsed, lowercased)
    norm_content = re.sub(r"\s+", " ", content).strip().lower()
    norm_ev      = re.sub(r"\s+", " ", evidence).strip().lower()
    if norm_ev and norm_ev not in norm_content:
        return "evidence_sentence not found in content (use '[derived] ' prefix for paraphrased evidence)"
    return None


# ============================================================
# Main validation
# ============================================================

def validate_jsonl(path: Path) -> Dict:
    """Validate every line of a JSONL file. Returns a summary dict."""
    schema = load_json(SCHEMA_PATH)
    l1_id_to_name, l2_id_to_name, l1_id_to_l2_id = load_taxonomy()

    n_total = 0
    n_ok    = 0
    issues_by_line: List[Tuple[int, List[str]]] = []

    seen_aug_ids: set = set()
    duplicate_aug_ids: set = set()
    seen_hashes: defaultdict = defaultdict(list)
    label_conflict: defaultdict = defaultdict(list)
    type_counts: Counter = Counter()
    paired_ids: set = set()

    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            n_total += 1
            errs: List[str] = []
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                issues_by_line.append((i, [f"JSON parse error: {e}"]))
                continue

            errs.extend(_schema_value_errors(item, schema))

            # Cross-field semantic checks (only if structurally usable)
            l1_id = item.get("source_label_id")
            l2_id = item.get("l2_value_id")
            direction = item.get("direction")
            direction_name = item.get("direction_name")
            atype = item.get("augmentation_type")

            if isinstance(l1_id, str) and isinstance(l2_id, str):
                if not _l1_l2_matches(l1_id, l2_id, l1_id_to_l2_id):
                    errs.append(f"l1_value_id={l1_id} does not map to l2_value_id={l2_id}")

            if isinstance(direction, str) and isinstance(direction_name, str):
                if not _direction_name_matches(direction, direction_name):
                    errs.append(f"direction={direction!r} inconsistent with direction_name={direction_name!r}")

            if atype == "hard_negative" and "negative_target_label_id" not in item:
                errs.append("hard_negative samples must include negative_target_label_id")

            if atype == "direction_contrastive" and "paired_augmentation_id" not in item:
                errs.append("direction_contrastive samples must include paired_augmentation_id")
            elif atype == "direction_contrastive" and "paired_augmentation_id" in item:
                paired_ids.add(item["augmentation_id"])

            # Evidence and content
            ev_err = _evidence_check(item)
            if ev_err:
                errs.append(ev_err)

            # Duplicate ID
            aug_id = item.get("augmentation_id")
            if isinstance(aug_id, str):
                if aug_id in seen_aug_ids:
                    duplicate_aug_ids.add(aug_id)
                    errs.append(f"duplicate augmentation_id: {aug_id}")
                else:
                    seen_aug_ids.add(aug_id)

            # Content-hash duplicate / conflicting labels
            content = item.get("content")
            if isinstance(content, str):
                h = _content_hash(content)
                seen_hashes[h].append((i, aug_id, l1_id, direction))
                # detect later

            type_counts[atype] += 1

            if errs:
                issues_by_line.append((i, errs))
            else:
                n_ok += 1

    # Post-pass: same-content conflicting-label detection
    for h, entries in seen_hashes.items():
        if len(entries) <= 1:
            continue
        labels = {(l1, d) for (_, _, l1, d) in entries}
        if len(labels) > 1:
            for (i, aug_id, l1, d) in entries:
                label_conflict[h].append(i)

    # Verify direction_contrastive pairing
    pair_errors: List[str] = []
    # (we don't fully crawl pairs here; just count)
    pair_warning_count = 0
    if paired_ids:
        # We'd need to re-read to confirm referenced pair ids exist — keep light:
        pass

    summary = {
        "file":                 str(path),
        "lines_total":          n_total,
        "lines_clean":          n_ok,
        "lines_with_errors":    n_total - n_ok,
        "duplicate_aug_ids":    sorted(duplicate_aug_ids),
        "content_hash_conflicts": {h: ls for h, ls in label_conflict.items()},
        "by_augmentation_type": dict(type_counts),
        "first_20_issues":      issues_by_line[:20],
    }
    return summary


# ============================================================
# CLI
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Validate augmented FEHU samples (local-only).")
    ap.add_argument("--input", type=str, default=None,
                    help="Path to a JSONL file of augmented samples.")
    args = ap.parse_args()

    if args.input is None:
        print("Usage:")
        print("  python research/fehu_augmentation_v1/validate_augmented_data.py --input PATH.jsonl")
        print()
        print("This validator reads existing augmented samples only.")
        print("No augmented data exists yet — the generator has not been run.")
        sys.exit(0)

    p = Path(args.input)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        print(f"ERROR: input file does not exist: {p}")
        sys.exit(1)

    summary = validate_jsonl(p)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if summary["lines_with_errors"] == 0 else 2)


if __name__ == "__main__":
    main()
