#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V2 — strict output schema, validation, and deterministic
post-processing.

Principles (see task spec §5–§7):
  * The model outputs Level-1 + direction only. Task-1a (Level-2) is derived
    deterministically in code from accepted Task-1b predictions.
  * Validation is all-or-nothing per response: any issue rejects the whole
    response (with structured errors) and triggers a correction retry.
    Nothing is silently repaired, wrapped, coerced, or dropped.
  * Direction must be exactly the official string "0" or "1". No
    normalization of any other token.
  * A valid empty predictions list is a legitimate model decision and is
    distinct from every failure mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from task1_v2_taxonomy import Taxonomy

SCHEMA_VERSION = "task1_v2_response.v1"

# Failure taxonomy — used in validation_errors.jsonl and retry routing.
ERR_API = "api_failure"
ERR_EMPTY = "empty_response"
ERR_JSON = "json_parse_failure"
ERR_SCHEMA = "schema_failure"
ERR_SEMANTIC = "semantic_failure"


@dataclass
class ValidationIssue:
    guid: str
    error_type: str          # one of ERR_* above
    field: str               # dotted path, e.g. "predictions[3].direction"
    invalid_value: object
    reason: str
    retry: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Keep invalid_value JSON-serializable and bounded.
        try:
            json.dumps(d["invalid_value"])
        except (TypeError, ValueError):
            d["invalid_value"] = repr(d["invalid_value"])
        if isinstance(d["invalid_value"], str) and len(d["invalid_value"]) > 500:
            d["invalid_value"] = d["invalid_value"][:500] + "...[truncated]"
        return d


def article_actor_ids(article: dict) -> List[str]:
    """Actor IDs in article order (order matters for deterministic sorting)."""
    ids = []
    for actor_dict in article["actors"]:
        for _, aid in actor_dict.items():
            ids.append(str(aid))
    return ids


# ============================================================
# JSON parsing (strict — no markdown stripping)
# ============================================================

def parse_response_json(raw_text: str, guid: str, retry: int) -> Tuple[Optional[object], List[ValidationIssue]]:
    """Parse raw model output as JSON. No fence stripping, no repair."""
    if raw_text is None or not raw_text.strip():
        return None, [ValidationIssue(
            guid=guid, error_type=ERR_EMPTY, field="<response>",
            invalid_value=raw_text, reason="Model returned an empty response body.",
            retry=retry,
        )]
    try:
        return json.loads(raw_text), []
    except json.JSONDecodeError as e:
        return None, [ValidationIssue(
            guid=guid, error_type=ERR_JSON, field="<response>",
            invalid_value=raw_text,
            reason=f"Response is not valid JSON: {e}", retry=retry,
        )]


# ============================================================
# Structural + semantic validation (all-or-nothing)
# ============================================================

def validate_response_object(
    obj: object,
    article: dict,
    tax: Taxonomy,
    retry: int,
) -> List[ValidationIssue]:
    """
    Validate a parsed response against the article and the official taxonomy.
    Returns [] iff the response is fully valid. Any issue rejects the whole
    response; nothing is repaired.
    """
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

    expected_keys = {"guid", "predictions"}
    extra = set(obj.keys()) - expected_keys
    missing = expected_keys - set(obj.keys())
    if extra:
        schema("<response>", sorted(extra),
               f"Unexpected top-level keys: {sorted(extra)}. "
               f"Only {sorted(expected_keys)} are allowed.")
    if missing:
        schema("<response>", sorted(missing),
               f"Missing required top-level keys: {sorted(missing)}.")
        return issues

    resp_guid = obj["guid"]
    if not isinstance(resp_guid, str):
        schema("guid", resp_guid, "guid must be a string.")
    elif resp_guid != guid:
        semantic("guid", resp_guid,
                 f"guid must exactly match the input article guid {guid!r}.")

    preds = obj["predictions"]
    if not isinstance(preds, list):
        schema("predictions", preds,
               f"predictions must be a list, got {type(preds).__name__}.")
        return issues

    valid_actors = set(article_actor_ids(article))
    valid_l1 = set(tax.l1_by_id.keys())
    seen: set = set()

    for i, item in enumerate(preds):
        path = f"predictions[{i}]"
        if not isinstance(item, dict):
            schema(path, item,
                   f"Prediction item must be an object, got {type(item).__name__}.")
            continue

        expected_item_keys = {"actor_id", "l1_value_id", "direction"}
        extra_i = set(item.keys()) - expected_item_keys
        missing_i = expected_item_keys - set(item.keys())
        if extra_i:
            schema(path, sorted(extra_i),
                   f"Unexpected keys {sorted(extra_i)}; only "
                   f"{sorted(expected_item_keys)} are allowed.")
        if missing_i:
            schema(path, sorted(missing_i),
                   f"Missing required keys {sorted(missing_i)}.")
            continue

        actor_id = item["actor_id"]
        l1_id = item["l1_value_id"]
        direction = item["direction"]

        item_ok = True
        for fname, fval in (("actor_id", actor_id),
                            ("l1_value_id", l1_id),
                            ("direction", direction)):
            if not isinstance(fval, str):
                schema(f"{path}.{fname}", fval,
                       f"{fname} must be a string, got {type(fval).__name__}.")
                item_ok = False
        if not item_ok:
            continue

        if actor_id not in valid_actors:
            semantic(f"{path}.actor_id", actor_id,
                     f"actor_id not in this article's actor list "
                     f"{sorted(valid_actors)}.")
        if l1_id not in valid_l1:
            semantic(f"{path}.l1_value_id", l1_id,
                     "l1_value_id is not an official Level-1 ID ('0'..'53').")
        if direction not in ("0", "1"):
            semantic(f"{path}.direction", direction,
                     "direction must be exactly the string '0' (contradictory) "
                     "or '1' (aligned). No other token is interpreted.")

        key = (actor_id, l1_id, direction)
        if key in seen:
            semantic(path, list(key),
                     "Duplicate (actor_id, l1_value_id, direction) tuple; "
                     "each tuple may appear at most once.")
        seen.add(key)

        # Hierarchical consistency: every accepted L1 must map to an L2.
        if l1_id in valid_l1 and l1_id not in tax.l1_id_to_l2_id:
            semantic(f"{path}.l1_value_id", l1_id,
                     "Level-1 ID has no Level-2 parent in the official mapping.")

    return issues


# ============================================================
# Deterministic post-processing of an ACCEPTED response
# ============================================================

def sorted_task1b_values(article: dict, predictions: List[dict]) -> List[dict]:
    """
    Official Task-1b rows, deterministically sorted by:
      1. actor order in the input article,
      2. numeric Level-1 ID,
      3. direction "0" before "1".
    Input must already be schema-valid (call validate_response_object first).
    """
    order = {aid: i for i, aid in enumerate(article_actor_ids(article))}
    rows = [
        {"actor": p["actor_id"], "l1_value": p["l1_value_id"],
         "direction": p["direction"]}
        for p in predictions
    ]
    rows.sort(key=lambda r: (order[r["actor"]], int(r["l1_value"]), r["direction"]))
    return rows


def derive_task1a_values(article: dict, task1b_values: List[dict], tax: Taxonomy) -> List[dict]:
    """
    Task-1a derived deterministically from accepted Task-1b rows via the
    official Level-1→Level-2 mapping, deduplicated on (actor, l2_value),
    sorted by actor order then numeric Level-2 ID.
    """
    order = {aid: i for i, aid in enumerate(article_actor_ids(article))}
    seen = set()
    rows = []
    for r in task1b_values:
        l2 = tax.l1_id_to_l2_id[r["l1_value"]]
        key = (r["actor"], l2)
        if key not in seen:
            seen.add(key)
            rows.append({"actor": r["actor"], "l2_value": l2})
    rows.sort(key=lambda r: (order[r["actor"]], int(r["l2_value"])))
    return rows


# ============================================================
# Structured-output JSON schema (for providers that support it)
# ============================================================

def build_response_json_schema(article: dict, tax: Taxonomy) -> dict:
    """Strict per-article JSON schema for structured-output providers."""
    return {
        "name": "fehu_task1_v2_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["guid", "predictions"],
            "properties": {
                "guid": {"type": "string", "enum": [str(article["guid"])]},
                "predictions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["actor_id", "l1_value_id", "direction"],
                        "properties": {
                            "actor_id": {"type": "string",
                                         "enum": article_actor_ids(article)},
                            "l1_value_id": {"type": "string",
                                            "enum": list(tax.l1_ids)},
                            "direction": {"type": "string", "enum": ["0", "1"]},
                        },
                    },
                },
            },
        },
    }
