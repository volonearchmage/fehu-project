#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V3 — ensemble logic, verifier validation, and
label-aware policy application.

Ensemble semantics (deterministic, two generators A and B + verifier):
  * A prediction tuple is (actor_id, l1_value_id, direction).
  * For each (actor_id, l1_value_id) PAIR:
      - if A and B predict the pair with IDENTICAL direction sets → accepted
        as-is (full agreement; both-direction agreement is kept as both);
      - any other pair predicted by at least one generator is UNCERTAIN and
        goes to the verifier. Directions the generators do agree on
        (intersection of their direction sets) stay accepted; on top of that
        the verifier may accept the pair with the direction IT finds
        supported.
  * Without the verifier, uncertain pairs contribute only their agreed
    directions — i.e. the unverified fallback is exactly the strict
    intersection. Nothing is ever silently defaulted to "aligned"; a
    direction conflict without a verifier verdict is dropped and counted.
  * The verifier never sees proposed directions or proposer identities and
    never adds candidates of its own.

Stages exported for ablation and for label-aware policies:
  variant_a, variant_b, union, intersection, verified.
A frozen label-aware policy maps "direction:l1_id" → strategy; "default"
resolves to the run's default stage (verified when the verifier is on,
intersection otherwise); "drop" suppresses the label entirely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from task1_v2_taxonomy import Taxonomy, canonical_json, sha256_text
from task1_v2_schema import (
    ERR_SCHEMA, ERR_SEMANTIC, ValidationIssue, article_actor_ids,
)

VERIFIER_SCHEMA_VERSION = "task1_v3_verifier_response.v1"
POLICY_VERSION = "task1_v3_policy.v1"

PredTuple = Tuple[str, str, str]          # (actor_id, l1_value_id, direction)
Pair = Tuple[str, str]                    # (actor_id, l1_value_id)

STAGE_NAMES = ("variant_a", "variant_b", "union", "intersection", "verified")
POLICY_STRATEGIES = ("default",) + STAGE_NAMES + ("drop",)


# ============================================================
# Candidate analysis
# ============================================================

def preds_to_tuples(predictions: List[dict]) -> Set[PredTuple]:
    """Schema-valid prediction items → set of tuples."""
    return {(str(p["actor_id"]), str(p["l1_value_id"]), str(p["direction"]))
            for p in predictions}


def analyze_pairs(a_tuples: Set[PredTuple],
                  b_tuples: Set[PredTuple]) -> Dict[Pair, Tuple[FrozenSet[str], FrozenSet[str]]]:
    """Group both generators' tuples by (actor, l1) pair.

    Returns pair → (directions_from_A, directions_from_B)."""
    dirs_a: Dict[Pair, Set[str]] = {}
    dirs_b: Dict[Pair, Set[str]] = {}
    for actor, l1, d in a_tuples:
        dirs_a.setdefault((actor, l1), set()).add(d)
    for actor, l1, d in b_tuples:
        dirs_b.setdefault((actor, l1), set()).add(d)
    out = {}
    for pair in set(dirs_a) | set(dirs_b):
        out[pair] = (frozenset(dirs_a.get(pair, set())),
                     frozenset(dirs_b.get(pair, set())))
    return out


def verifier_candidates(pairs: Dict[Pair, Tuple[FrozenSet[str], FrozenSet[str]]],
                        article: dict) -> List[Pair]:
    """Uncertain pairs (single support, or any direction disagreement),
    deterministically ordered by article actor order then numeric L1 ID."""
    order = {aid: i for i, aid in enumerate(article_actor_ids(article))}
    cands = [pair for pair, (da, db) in pairs.items()
             if not (da and da == db)]
    cands.sort(key=lambda p: (order.get(p[0], len(order)), int(p[1])))
    return cands


def classify_pair(da: FrozenSet[str], db: FrozenSet[str]) -> str:
    """Diagnostic category for a pair: agreed / direction_conflict /
    single_a / single_b / partial."""
    if da and da == db:
        return "agreed"
    if da and db:
        return "direction_conflict" if not (da & db) else "partial"
    return "single_a" if da else "single_b"


def candidates_hash(candidates: List[Pair]) -> str:
    return sha256_text(canonical_json([list(c) for c in candidates]))


# ============================================================
# Verifier response validation (strict, all-or-nothing)
# ============================================================

def validate_verifier_response(obj: object, article: dict, tax: Taxonomy,
                               candidates: List[Pair],
                               retry: int) -> List[ValidationIssue]:
    """Return [] iff the verifier response is fully valid: exact keys, string
    fields, accept/direction in {'0','1'}, and verdicts covering EXACTLY the
    candidate list (no omission, no addition, no duplication)."""
    guid = str(article["guid"])
    issues: List[ValidationIssue] = []

    def schema(field, value, reason):
        issues.append(ValidationIssue(guid=guid, error_type=ERR_SCHEMA,
                                      field=field, invalid_value=value,
                                      reason=reason, retry=retry))

    def semantic(field, value, reason):
        issues.append(ValidationIssue(guid=guid, error_type=ERR_SEMANTIC,
                                      field=field, invalid_value=value,
                                      reason=reason, retry=retry))

    if not isinstance(obj, dict):
        schema("<response>", obj,
               f"Top-level value must be a JSON object, got {type(obj).__name__}.")
        return issues

    expected = {"guid", "verdicts"}
    extra = set(obj.keys()) - expected
    missing = expected - set(obj.keys())
    if extra:
        schema("<response>", sorted(extra),
               f"Unexpected top-level keys: {sorted(extra)}.")
    if missing:
        schema("<response>", sorted(missing),
               f"Missing required top-level keys: {sorted(missing)}.")
        return issues

    if not isinstance(obj["guid"], str):
        schema("guid", obj["guid"], "guid must be a string.")
    elif obj["guid"] != guid:
        semantic("guid", obj["guid"],
                 f"guid must exactly match the input article guid {guid!r}.")

    verdicts = obj["verdicts"]
    if not isinstance(verdicts, list):
        schema("verdicts", verdicts,
               f"verdicts must be a list, got {type(verdicts).__name__}.")
        return issues

    cand_set = set(candidates)
    seen: Set[Pair] = set()
    item_keys = {"actor_id", "l1_value_id", "accept", "direction"}
    for i, item in enumerate(verdicts):
        path = f"verdicts[{i}]"
        if not isinstance(item, dict):
            schema(path, item,
                   f"Verdict must be an object, got {type(item).__name__}.")
            continue
        extra_i = set(item.keys()) - item_keys
        missing_i = item_keys - set(item.keys())
        if extra_i:
            schema(path, sorted(extra_i),
                   f"Unexpected keys {sorted(extra_i)}; only "
                   f"{sorted(item_keys)} are allowed.")
        if missing_i:
            schema(path, sorted(missing_i),
                   f"Missing required keys {sorted(missing_i)}.")
            continue
        bad_type = False
        for fname in ("actor_id", "l1_value_id", "accept", "direction"):
            if not isinstance(item[fname], str):
                schema(f"{path}.{fname}", item[fname],
                       f"{fname} must be a string, got "
                       f"{type(item[fname]).__name__}.")
                bad_type = True
        if bad_type:
            continue
        pair = (item["actor_id"], item["l1_value_id"])
        if pair not in cand_set:
            semantic(path, list(pair),
                     "Verdict does not correspond to any listed candidate; "
                     "the verifier must not add candidates.")
            continue
        if pair in seen:
            semantic(path, list(pair),
                     "Duplicate verdict for the same candidate.")
        seen.add(pair)
        for fname in ("accept", "direction"):
            if item[fname] not in ("0", "1"):
                semantic(f"{path}.{fname}", item[fname],
                         f"{fname} must be exactly the string '0' or '1'.")

    not_covered = cand_set - seen
    if not_covered and not issues:
        # only report omissions when nothing else already invalidates coverage
        semantic("verdicts", sorted(map(list, not_covered)),
                 f"Missing verdicts for {len(not_covered)} candidate(s); "
                 f"exactly one verdict per candidate is required.")
    elif not_covered:
        semantic("verdicts", sorted(map(list, not_covered)),
                 f"Missing verdicts for {len(not_covered)} candidate(s).")
    return issues


def verdicts_from_response(obj: dict) -> Dict[Pair, dict]:
    """Validated verifier response → pair → {'accept', 'direction'}."""
    return {(v["actor_id"], v["l1_value_id"]):
            {"accept": v["accept"], "direction": v["direction"]}
            for v in obj["verdicts"]}


def build_verifier_json_schema(article: dict, candidates: List[Pair]) -> dict:
    """Strict structured-output schema for providers that support it."""
    return {
        "name": "fehu_task1_v3_verifier_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["guid", "verdicts"],
            "properties": {
                "guid": {"type": "string", "enum": [str(article["guid"])]},
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["actor_id", "l1_value_id",
                                     "accept", "direction"],
                        "properties": {
                            "actor_id": {"type": "string",
                                         "enum": sorted({c[0] for c in candidates})},
                            "l1_value_id": {"type": "string",
                                            "enum": sorted({c[1] for c in candidates})},
                            "accept": {"type": "string", "enum": ["0", "1"]},
                            "direction": {"type": "string", "enum": ["0", "1"]},
                        },
                    },
                },
            },
        },
    }


# ============================================================
# Stage assembly
# ============================================================

def build_stage_sets(a_tuples: Set[PredTuple], b_tuples: Set[PredTuple],
                     pairs: Dict[Pair, Tuple[FrozenSet[str], FrozenSet[str]]],
                     verdicts: Optional[Dict[Pair, dict]]) -> Dict[str, Set[PredTuple]]:
    """All ensemble stages for one article. `verdicts` is None when the
    verifier is disabled; then 'verified' degrades to the strict
    intersection (agreed directions only)."""
    verified: Set[PredTuple] = set()
    for (actor, l1), (da, db) in pairs.items():
        if da and da == db:
            verified |= {(actor, l1, d) for d in da}
            continue
        verified |= {(actor, l1, d) for d in (da & db)}
        if verdicts is not None:
            v = verdicts.get((actor, l1))
            if v is not None and v["accept"] == "1":
                verified.add((actor, l1, v["direction"]))
    return {
        "variant_a": set(a_tuples),
        "variant_b": set(b_tuples),
        "union": a_tuples | b_tuples,
        "intersection": a_tuples & b_tuples,
        "verified": verified,
    }


def apply_policy(stages: Dict[str, Set[PredTuple]],
                 policy_labels: Dict[str, str],
                 default_strategy: str) -> Set[PredTuple]:
    """Apply a frozen label-aware policy. The candidate universe is
    union ∪ verified (the verifier may flip a direction, creating a tuple
    outside the generators' union)."""
    if default_strategy not in STAGE_NAMES:
        raise ValueError(f"default_strategy must be one of {STAGE_NAMES}, "
                         f"got {default_strategy!r}")
    universe = stages["union"] | stages["verified"]
    out: Set[PredTuple] = set()
    for t in universe:
        strategy = policy_labels.get(f"{t[2]}:{t[1]}", "default")
        if strategy == "default":
            strategy = default_strategy
        if strategy == "drop":
            continue
        if t in stages[strategy]:
            out.add(t)
    return out


def tuples_to_prediction_items(tuples: Set[PredTuple]) -> List[dict]:
    """Tuples → schema-shaped prediction items (unsorted; use
    task1_v2_schema.sorted_task1b_values for the official row order)."""
    return [{"actor_id": a, "l1_value_id": l, "direction": d}
            for a, l, d in tuples]


# ============================================================
# Per-article offline diagnostics (deterministic; computed AFTER inference
# and never fed back into inference decisions of the same run)
# ============================================================

def compute_pair_diagnostics(
    a_tuples: Set[PredTuple],
    b_tuples: Set[PredTuple],
    pairs: Dict[Pair, Tuple[FrozenSet[str], FrozenSet[str]]],
    verdicts: Optional[Dict[Pair, dict]],
    rarity: dict,
) -> dict:
    """Agreement, complementarity, and verifier-behavior diagnostics for one
    article. `rarity` is the TRAIN-derived metadata from
    task1_v2_taxonomy.build_rarity_metadata."""
    union = a_tuples | b_tuples
    inter = a_tuples & b_tuples
    only_a = a_tuples - b_tuples
    only_b = b_tuples - a_tuples

    both_pairs = [p for p, (da, db) in pairs.items() if da and db]
    dir_agree = sum(1 for p in both_pairs
                    if pairs[p][0] == pairs[p][1])

    rare_groups = ("rare", "very_rare")
    labels_only_a = sorted({f"{d}:{l1}" for _, l1, d in only_a})
    labels_only_b = sorted({f"{d}:{l1}" for _, l1, d in only_b})
    rare_added_by_b = sorted({
        f"{d}:{l1}" for _, l1, d in only_b
        if rarity["labels"][l1]["frequency_group"] in rare_groups})

    by_category = {c: {"candidates": 0, "accepted": 0}
                   for c in ("single_a", "single_b", "direction_conflict",
                             "partial")}
    conflict_decisions = {"accepted_direction_0": 0, "accepted_direction_1": 0,
                          "rejected": 0}
    if verdicts is not None:
        for pair, verdict in verdicts.items():
            da, db = pairs[pair]
            category = classify_pair(da, db)
            if category == "agreed":       # defensive: should never be sent
                continue
            by_category[category]["candidates"] += 1
            if verdict["accept"] == "1":
                by_category[category]["accepted"] += 1
            if category == "direction_conflict":
                if verdict["accept"] == "1":
                    conflict_decisions[
                        f"accepted_direction_{verdict['direction']}"] += 1
                else:
                    conflict_decisions["rejected"] += 1

    return {
        "ab_exact_agreement": a_tuples == b_tuples,
        "tuple_jaccard": (len(inter) / len(union)) if union else 1.0,
        "pairs_proposed_by_both": len(both_pairs),
        "pairs_direction_agreed": dir_agree,
        "tuples_only_a": len(only_a),
        "tuples_only_b": len(only_b),
        "labels_only_a": labels_only_a,
        "labels_only_b": labels_only_b,
        "rare_labels_added_by_b": rare_added_by_b,
        "verifier_by_category": by_category,
        "conflict_direction_decisions": conflict_decisions,
    }


def final_contribution_by_stage(final: Set[PredTuple],
                                stages: Dict[str, Set[PredTuple]]) -> dict:
    """Attribute every final tuple to its provenance stage."""
    from_intersection = final & stages["intersection"]
    from_verifier = (final & stages["verified"]) - stages["intersection"]
    from_policy = final - stages["verified"]
    return {
        "from_generator_agreement": len(from_intersection),
        "from_verifier_acceptance": len(from_verifier),
        "from_label_policy_override": len(from_policy),
    }


# ============================================================
# Frozen policy files
# ============================================================

class PolicyValidationError(RuntimeError):
    """Raised when a label-aware policy file is malformed."""


REQUIRED_POLICY_PROVENANCE = (
    "run_dir", "gold_path", "gold_sha256", "calibration_guid_hash",
    "provider", "model", "temperature", "prompt_hashes", "taxonomy_hash",
    "rarity_hash", "demo_set_hash", "schema_version",
    "verifier_schema_version", "verifier_enabled",
)


def load_policy(path: Path) -> dict:
    """Load and structurally validate a frozen label-aware policy."""
    path = Path(path)
    if not path.exists():
        raise PolicyValidationError(f"Policy file not found: {path}")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PolicyValidationError(f"Policy file is not valid JSON: {e}")
    if policy.get("policy_version") != POLICY_VERSION:
        raise PolicyValidationError(
            f"Unsupported policy_version {policy.get('policy_version')!r}; "
            f"expected {POLICY_VERSION!r}.")
    if policy.get("default_strategy") not in STAGE_NAMES:
        raise PolicyValidationError(
            f"default_strategy must be one of {STAGE_NAMES}.")
    labels = policy.get("labels")
    if not isinstance(labels, dict):
        raise PolicyValidationError("labels must be an object.")
    for key, rec in labels.items():
        d, _, l1 = key.partition(":")
        if d not in ("0", "1") or not l1.isdigit() or not (0 <= int(l1) <= 53):
            raise PolicyValidationError(f"Invalid label key {key!r}.")
        if not isinstance(rec, dict) or rec.get("strategy") not in POLICY_STRATEGIES:
            raise PolicyValidationError(
                f"Label {key!r}: strategy must be one of {POLICY_STRATEGIES}.")
    calib = policy.get("calibration")
    if not isinstance(calib, dict):
        raise PolicyValidationError("Missing calibration provenance block.")
    missing = [f for f in REQUIRED_POLICY_PROVENANCE if f not in calib]
    if missing:
        raise PolicyValidationError(
            f"Calibration provenance is missing fields: {missing}.")
    return policy


def policy_label_strategies(policy: dict) -> Dict[str, str]:
    return {k: v["strategy"] for k, v in policy["labels"].items()}


def check_policy_compatibility(policy: dict, run_identity: dict) -> List[str]:
    """Compare the policy's calibration provenance with the current run.
    Returns a list of human-readable mismatches (empty = compatible)."""
    calib = policy["calibration"]
    mismatches = []
    for field in ("provider", "model", "temperature", "taxonomy_hash",
                  "rarity_hash", "demo_set_hash", "schema_version",
                  "verifier_schema_version", "verifier_enabled"):
        if calib.get(field) != run_identity.get(field):
            mismatches.append(
                f"{field}: policy={calib.get(field)!r} "
                f"run={run_identity.get(field)!r}")
    p_hashes = calib.get("prompt_hashes", {})
    r_hashes = run_identity.get("prompt_hashes", {})
    for variant in sorted(set(p_hashes) | set(r_hashes)):
        if p_hashes.get(variant) != r_hashes.get(variant):
            mismatches.append(
                f"prompt_hashes[{variant}]: policy={p_hashes.get(variant)!r} "
                f"run={r_hashes.get(variant)!r}")
    return mismatches
