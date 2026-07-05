#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_submission_safety/augmented_training_data_guard.py

Local-only validator for future augmented_samples.jsonl. Enforces the schema
in research/fehu_augmentation_v1/augmentation_schema.json plus FEHU-specific
semantic checks.

Run from project root:
    python research/fehu_submission_safety/augmented_training_data_guard.py \\
        --input path/to/augmented_samples.jsonl

If --input is omitted, prints usage and exits cleanly (no augmented data
exists yet at the time of writing).

Exit codes:
    0 = clean (or no input given)
    2 = at least one issue found
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Re-use the existing schema validator from the planning-stage module to avoid drift.
sys.path.insert(0, str(PROJECT_ROOT))

# Direct file paths (no network)
L1_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level1_values.json"
L2_VALUES_PATH = PROJECT_ROOT / "dataset/hv_categories/human_value_level2_values.json"
L1_TO_L2_PATH  = PROJECT_ROOT / "dataset/hv_categories/level_1_to_level_2.json"
SCHEMA_PATH    = PROJECT_ROOT / "research/fehu_augmentation_v1/augmentation_schema.json"
DEV_EVENT_BASE = PROJECT_ROOT / "dataset/dev/dev_event_base.json"
TEST_EVENT_BASE_ARTICLE  = PROJECT_ROOT / "dataset/test/test_article_event_base.json"
TEST_EVENT_BASE_SUBEVENT = PROJECT_ROOT / "dataset/test/test_subevent_event_base.json"

ALLOWED_TYPES = {"paraphrase", "rare_positive", "hard_negative", "direction_contrastive"}


# ============================================================
# IO
# ============================================================

def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def load_taxonomy() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    l1_name_to_id = load_json(L1_VALUES_PATH)
    l2_name_to_id = load_json(L2_VALUES_PATH)
    raw           = load_json(L1_TO_L2_PATH)["level_1_to_level_2"]
    l1_id_to_name = {v: k for k, v in l1_name_to_id.items()}
    l2_id_to_name = {v: k for k, v in l2_name_to_id.items()}
    l1_id_to_l2_id = {l1_name_to_id[k]: l2_name_to_id[v] for k, v in raw.items()}
    return l1_id_to_name, l2_id_to_name, l1_id_to_l2_id


def load_reserved_guids() -> set:
    """Collect every dev/test guid — these must never appear as seed_guid."""
    reserved: set = set()
    for p in [DEV_EVENT_BASE, TEST_EVENT_BASE_ARTICLE, TEST_EVENT_BASE_SUBEVENT]:
        if not p.exists():
            continue
        try:
            data = load_json(p)
        except Exception:
            continue
        for art in data:
            if isinstance(art, dict) and "guid" in art:
                reserved.add(str(art["guid"]))
    return reserved


# ============================================================
# Lightweight schema validation
# ============================================================

def _schema_value_errors(item: Dict, schema: Dict) -> List[str]:
    errs: List[str] = []
    required = schema.get("required", [])
    props = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for key in required:
        if key not in item:
            errs.append(f"missing required field: {key}")

    if additional is False:
        for key in item.keys():
            if key not in props:
                errs.append(f"unknown field (additionalProperties=false): {key}")

    for key, val in item.items():
        spec = props.get(key)
        if spec is None:
            continue
        t = spec.get("type")
        if t == "string" and not isinstance(val, str):
            errs.append(f"{key}: expected string, got {type(val).__name__}"); continue
        if t == "boolean" and not isinstance(val, bool):
            errs.append(f"{key}: expected boolean, got {type(val).__name__}"); continue
        if t == "integer" and not isinstance(val, int):
            errs.append(f"{key}: expected integer, got {type(val).__name__}"); continue

        enum = spec.get("enum")
        if enum is not None and val not in enum:
            errs.append(f"{key}: value {val!r} not in enum {enum}")
        pat = spec.get("pattern")
        if pat is not None and isinstance(val, str) and not re.match(pat, val):
            errs.append(f"{key}: value {val!r} does not match pattern {pat}")

        if isinstance(val, str):
            mn = spec.get("minLength"); mx = spec.get("maxLength")
            if mn is not None and len(val) < mn:
                errs.append(f"{key}: length {len(val)} < minLength {mn}")
            if mx is not None and len(val) > mx:
                errs.append(f"{key}: length {len(val)} > maxLength {mx}")
    return errs


# ============================================================
# FEHU-specific checks
# ============================================================

def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


SECRET_PAT = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
DEEPSEEK_KEY_PAT = re.compile(r"\bds-[A-Za-z0-9_-]{16,}\b")
GENERIC_API_PAT = re.compile(r'(?i)api[_-]?key\s*[:=]\s*"[A-Za-z0-9_-]{16,}"')


def scan_for_secrets(item: Dict) -> List[str]:
    """Return list of fields that contain a secret-looking string."""
    hits: List[str] = []
    for k, v in item.items():
        if isinstance(v, str):
            if SECRET_PAT.search(v) or DEEPSEEK_KEY_PAT.search(v) or GENERIC_API_PAT.search(v):
                hits.append(k)
    return hits


def validate_jsonl(path: Path,
                   strict: bool) -> Tuple[Dict, List[Dict]]:
    schema = load_json(SCHEMA_PATH)
    l1_id_to_name, l2_id_to_name, l1_id_to_l2_id = load_taxonomy()
    reserved_guids = load_reserved_guids()

    invalid: List[Dict] = []
    n_total = 0
    type_counts: Counter = Counter()
    seen_aug_ids: set = set()
    duplicate_aug_ids: set = set()
    hashes: Dict[str, List[Tuple[int, str, str, str]]] = defaultdict(list)
    n_secret_hits = 0
    n_official_gold = 0
    n_reserved_seed = 0
    n_dir_contrast_no_pair = 0
    n_hard_neg_no_target = 0
    n_no_gen_model = 0
    n_no_verification = 0

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            n_total += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                invalid.append({"line": line_no, "augmentation_id": "?", "issue": f"JSON parse error: {e}"})
                continue

            errs = _schema_value_errors(item, schema)

            # ── FEHU-specific semantic checks ──────────────────────────────
            atype = item.get("augmentation_type")
            if atype not in ALLOWED_TYPES:
                errs.append(f"augmentation_type={atype!r} not in {sorted(ALLOWED_TYPES)}")
            else:
                type_counts[atype] += 1

            src = item.get("source")
            if src == "official_gold":
                n_official_gold += 1
                errs.append("source='official_gold' is forbidden for augmented samples")

            l1_id = item.get("source_label_id")
            l2_id = item.get("l2_value_id")
            if isinstance(l1_id, str) and isinstance(l2_id, str):
                expected = l1_id_to_l2_id.get(l1_id)
                if expected is not None and l2_id != expected:
                    errs.append(
                        f"L1→L2 mismatch: l1={l1_id} maps to l2={expected}, "
                        f"but l2_value_id={l2_id}"
                    )

            direction = item.get("direction")
            direction_name = item.get("direction_name")
            if direction == "1" and direction_name != "aligned":
                errs.append(f"direction='1' expects direction_name='aligned' (got {direction_name!r})")
            elif direction == "0" and direction_name != "contradictory":
                errs.append(f"direction='0' expects direction_name='contradictory' (got {direction_name!r})")

            actor_name = item.get("actor_name", "") or ""
            content    = item.get("content", "") or ""
            evidence   = item.get("evidence_sentence", "") or ""
            if actor_name and actor_name not in content:
                errs.append("actor_name not present in content")
            if evidence and not evidence.startswith("[derived] "):
                norm_c = re.sub(r"\s+", " ", content).strip().lower()
                norm_e = re.sub(r"\s+", " ", evidence).strip().lower()
                if norm_e and norm_e not in norm_c:
                    errs.append("evidence_sentence not in content (use '[derived] ' prefix for paraphrased evidence)")

            aug_id = item.get("augmentation_id")
            if isinstance(aug_id, str):
                if aug_id in seen_aug_ids:
                    duplicate_aug_ids.add(aug_id)
                    errs.append(f"duplicate augmentation_id: {aug_id}")
                else:
                    seen_aug_ids.add(aug_id)

            if isinstance(content, str):
                h = _content_hash(content)
                hashes[h].append((line_no, aug_id or "?", l1_id or "?", direction or "?"))

            if atype == "hard_negative" and not item.get("negative_target_label_id"):
                n_hard_neg_no_target += 1
                errs.append("hard_negative sample missing negative_target_label_id")

            if atype == "direction_contrastive" and not item.get("paired_augmentation_id"):
                n_dir_contrast_no_pair += 1
                errs.append("direction_contrastive sample missing paired_augmentation_id")

            seed_guid = item.get("seed_guid")
            if isinstance(seed_guid, str) and seed_guid in reserved_guids:
                n_reserved_seed += 1
                errs.append(f"seed_guid={seed_guid!r} is reserved (dev or test split)")

            if not item.get("generation_model"):
                n_no_gen_model += 1
                if strict:
                    errs.append("strict mode: generation_model is required")

            if strict and "verification_status" not in item:
                n_no_verification += 1
                errs.append("strict mode: verification_status is required")

            secret_fields = scan_for_secrets(item)
            if secret_fields:
                n_secret_hits += 1
                errs.append(f"secret-shaped string detected in fields {secret_fields}")

            for e in errs:
                invalid.append({"line": line_no, "augmentation_id": aug_id or "?", "issue": e})

    # Post-pass: content-hash conflicts
    n_conflicts = 0
    for h, entries in hashes.items():
        if len(entries) <= 1:
            continue
        labels = {(l1, d) for (_, _, l1, d) in entries}
        if len(labels) > 1:
            n_conflicts += 1
            for (line_no, aug_id, l1, d) in entries:
                invalid.append({
                    "line": line_no, "augmentation_id": aug_id,
                    "issue": f"content_hash {h[:12]} collides with conflicting label "
                             f"({l1},{d}); see other entries with same hash",
                })

    summary = {
        "input_file":          str(path),
        "lines_total":         n_total,
        "n_invalid":           len(invalid),
        "by_augmentation_type": dict(type_counts),
        "n_duplicate_aug_ids": len(duplicate_aug_ids),
        "n_content_hash_conflicts": n_conflicts,
        "n_secret_hits":       n_secret_hits,
        "n_official_gold_source": n_official_gold,
        "n_reserved_seed":     n_reserved_seed,
        "n_hard_neg_missing_target": n_hard_neg_no_target,
        "n_dir_contrast_missing_pair": n_dir_contrast_no_pair,
        "n_missing_generation_model": n_no_gen_model,
        "n_missing_verification": n_no_verification,
        "status":              "clean" if not invalid else "issues_found",
        "timestamp":           datetime.now().isoformat(timespec="seconds"),
        "strict":              strict,
    }
    return summary, invalid


# ============================================================
# MAIN
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser(description="Validate augmented FEHU samples (local-only).")
    ap.add_argument("--input", type=str, default=None,
                    help="Path to augmented_samples.jsonl. If omitted, prints usage and exits.")
    ap.add_argument("--strict", action="store_true",
                    help="Require generation_model and verification_status on every sample.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if args.input is None:
        print("Usage:")
        print("  python research/fehu_submission_safety/augmented_training_data_guard.py "
              "--input PATH.jsonl [--strict]")
        print()
        print("No augmented data has been generated yet — the future generator script")
        print("`research/fehu_augmentation_v1/run_generation.py` will produce it.")
        sys.exit(0)

    p = Path(args.input)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        print(f"ERROR: input does not exist: {p}")
        sys.exit(1)

    summary, invalid = validate_jsonl(p, args.strict)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if invalid:
        print()
        print(f"First 20 issues (of {len(invalid)}):")
        for r in invalid[:20]:
            print(f"  line {r['line']}  id={r['augmentation_id']}  {r['issue']}")
    sys.exit(0 if not invalid else 2)


if __name__ == "__main__":
    main()
