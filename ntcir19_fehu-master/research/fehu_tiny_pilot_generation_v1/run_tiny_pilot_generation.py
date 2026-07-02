#!/usr/bin/env python3
"""
run_tiny_pilot_generation.py

FEHU DeepSeek V4 Tiny Pilot Generation Runner.

Stage: Tiny pilot generation for FEHU/NTCIR-19 Task-1 controlled augmentation.
       Part of the diagnosis-driven, recall-focused targeted augmentation workflow.

Safety invariants (never violated by this script):
  - Never trains any model
  - Never modifies evaluation.py
  - Never modifies dataset/** or gold_labels/**
  - Never modifies output/task1*/ or logs/cache_*
  - Never modifies prior research/approval/dry-run folders
  - Never writes API key to any file, log, or exception message
  - Never creates final pred_task1a.json or pred_task1b.json
  - Never writes generated samples into the official training dataset
  - Never approves generated samples automatically for training
  - Generated samples remain PENDING_HUMAN_VERIFICATION

Usage:
  Validation-only (no API calls):
    python run_tiny_pilot_generation.py --manifest <path> --outdir <path>

  Execute mode (calls DeepSeek API):
    DEEPSEEK_API_KEY=... python run_tiny_pilot_generation.py --manifest <path> --outdir <path> --execute

Dependencies: Python 3.7+ standard library only.
"""

import argparse
import csv
import datetime
import json
import os
import pathlib
import re
import sys
import traceback
import urllib.error
import urllib.request

# ============================================================
# Constants
# ============================================================

APPROVED_REQUEST_IDS = frozenset([
    "prev_rare_positive_24_004_98671d8d01",
    "prev_rare_positive_32_001_83df110175",
    "prev_dir_contrast_12_002_aligned_ce1da19f54",
    "prev_dir_contrast_12_002_contradictory_ce1da19f54",
    "prev_dir_contrast_38_003_aligned_e969e14138",
    "prev_dir_contrast_38_003_contradictory_e969e14138",
])

# (aligned_id, contradictory_id, l1_id, l1_name)
REQUIRED_DIRECTION_PAIRS = [
    (
        "prev_dir_contrast_12_002_aligned_ce1da19f54",
        "prev_dir_contrast_12_002_contradictory_ce1da19f54",
        "12",
        "Have success",
    ),
    (
        "prev_dir_contrast_38_003_aligned_e969e14138",
        "prev_dir_contrast_38_003_contradictory_e969e14138",
        "38",
        "Be honest",
    ),
]

DIRECTION_ALIGNED = "1"
DIRECTION_CONTRADICTORY = "0"

BASE_URL = "https://api.deepseek.com"
ENDPOINT_PATH = "/chat/completions"

REQUIRED_SAMPLE_FIELDS = [
    "title",
    "content",
    "actor_name",
    "actor_mention",
    "evidence_sentence",
    "explanation",
    "l1_value_id",
    "l1_value_name",
    "l2_value_id",
    "l2_value_name",
    "direction",
    "direction_name",
    "is_positive",
    "_type_specific_rule",
]

FORBIDDEN_AUG_TYPES = {"hard_negative", "paraphrase", "sensitive_label"}

# ============================================================
# Secret masking
# ============================================================

_SECRET_VALUE: str = ""


def set_secret(val: str) -> None:
    global _SECRET_VALUE
    _SECRET_VALUE = val


def mask_secret(text: str) -> str:
    if _SECRET_VALUE and isinstance(text, str) and _SECRET_VALUE in text:
        return text.replace(_SECRET_VALUE, "***MASKED***")
    return text


def safe_format_exc() -> str:
    return mask_secret(traceback.format_exc())


# ============================================================
# Time helpers
# ============================================================


def iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ============================================================
# File helpers
# ============================================================


def write_file(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def append_jsonl(path: pathlib.Path, obj: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_csv(path: pathlib.Path, fieldnames: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


# ============================================================
# Manifest loading and preflight validation
# ============================================================


def load_manifest(manifest_path: str):
    """Load JSONL manifest. Returns (rows, error_string_or_None)."""
    path = pathlib.Path(manifest_path)
    if not path.exists():
        return None, f"Manifest path does not exist: {manifest_path}"
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                return None, f"JSON parse error at line {lineno}: {e}"
    return rows, None


def validate_manifest(rows: list, execute_mode: bool, api_key_present: bool):
    """
    Run all preflight checks (TASK B).
    Returns (errors: list[str], warnings: list[str]).
    """
    errors: list = []
    warnings: list = []

    # Check 2: exactly 6 rows
    if len(rows) != 6:
        errors.append(
            f"Manifest must have exactly 6 rows; found {len(rows)}"
        )

    found_ids: set = set()

    for i, row in enumerate(rows):
        rid = row.get("request_id", f"<missing_id_row_{i}>")
        found_ids.add(rid)

        # Check 3: manual_approval_status = APPROVED_BY_HUMAN
        status = row.get("manual_approval_status")
        if status != "APPROVED_BY_HUMAN":
            errors.append(
                f"Row '{rid}': manual_approval_status must be "
                f"'APPROVED_BY_HUMAN', got {status!r}"
            )

        # Check 4: api_generation_authorized_now = false
        if row.get("api_generation_authorized_now") is not False:
            errors.append(
                f"Row '{rid}': api_generation_authorized_now must be false"
            )

        # Check 5: requires_separate_generation_runner_approval = true
        if row.get("requires_separate_generation_runner_approval") is not True:
            errors.append(
                f"Row '{rid}': requires_separate_generation_runner_approval "
                f"must be true"
            )

        # Check 6: no PENDING_HUMAN_APPROVAL
        if row.get("manual_approval_status") == "PENDING_HUMAN_APPROVAL":
            errors.append(
                f"Row '{rid}': has PENDING_HUMAN_APPROVAL status (not approved)"
            )

        # Check 7: no execute or should_execute_now fields
        for bad_field in ("execute", "should_execute_now"):
            if bad_field in row:
                errors.append(
                    f"Row '{rid}': must not contain field '{bad_field}'"
                )

        # Checks 8-10: forbidden augmentation types
        aug_type = row.get("augmentation_type", "")
        if aug_type in FORBIDDEN_AUG_TYPES:
            errors.append(
                f"Row '{rid}': augmentation_type '{aug_type}' is not "
                f"permitted in this pilot"
            )

        # Check 13: direction convention
        direction = row.get("target_direction")
        direction_name = row.get("target_direction_name")
        if direction is not None and direction_name is not None:
            if direction == "1" and direction_name != "aligned":
                errors.append(
                    f"Row '{rid}': direction='1' requires direction_name='aligned', "
                    f"got {direction_name!r}"
                )
            elif direction == "0" and direction_name != "contradictory":
                errors.append(
                    f"Row '{rid}': direction='0' requires "
                    f"direction_name='contradictory', got {direction_name!r}"
                )

        # Check 14: no secret-shaped tokens in manifest content
        row_str = json.dumps(row)
        if re.search(r'\bsk-[A-Za-z0-9]{20,}\b', row_str):
            errors.append(f"Row '{rid}': appears to contain an OpenAI-style secret token")
        if re.search(r'\bBearer [A-Za-z0-9]{20,}\b', row_str):
            errors.append(f"Row '{rid}': appears to contain a Bearer token")

    # Check 11: exact set of approved IDs
    if found_ids != APPROVED_REQUEST_IDS:
        missing = APPROVED_REQUEST_IDS - found_ids
        extra = found_ids - APPROVED_REQUEST_IDS
        if missing:
            errors.append(f"Missing required request IDs: {sorted(missing)}")
        if extra:
            errors.append(f"Unexpected request IDs: {sorted(extra)}")

    # Check 12: both direction-contrastive pairs complete and internally consistent
    rows_by_id = {r.get("request_id"): r for r in rows}
    for aligned_id, contradictory_id, l1_id, l1_name in REQUIRED_DIRECTION_PAIRS:
        aligned_row = rows_by_id.get(aligned_id)
        contradictory_row = rows_by_id.get(contradictory_id)

        if not aligned_row:
            errors.append(f"Missing aligned pair member: {aligned_id}")
        else:
            if aligned_row.get("target_direction") != DIRECTION_ALIGNED:
                errors.append(
                    f"Pair member {aligned_id}: expected direction='1' (aligned), "
                    f"got {aligned_row.get('target_direction')!r}"
                )

        if not contradictory_row:
            errors.append(f"Missing contradictory pair member: {contradictory_id}")
        else:
            if contradictory_row.get("target_direction") != DIRECTION_CONTRADICTORY:
                errors.append(
                    f"Pair member {contradictory_id}: expected direction='0' "
                    f"(contradictory), got {contradictory_row.get('target_direction')!r}"
                )

    # Check 15: DEEPSEEK_API_KEY required only in execute mode
    if execute_mode and not api_key_present:
        errors.append(
            "DEEPSEEK_API_KEY environment variable is not set. "
            "Cannot proceed with --execute mode. "
            "Set it with: export DEEPSEEK_API_KEY=<your_key>"
        )

    return errors, warnings


# ============================================================
# Prompt construction (TASK C + TASK D)
# ============================================================

_SYSTEM_PROMPT_CORE = """You are a synthetic news content generator for an academic research benchmark.

STRICT OUTPUT RULES — NEVER VIOLATE:
1. Return exactly one valid JSON object. Nothing else.
2. Do NOT use markdown fences (no ```, no ```json, no ```).
3. Do NOT include any text, commentary, or explanation outside the JSON object.
4. Do NOT say "as an AI" anywhere in the output.
5. Do NOT mention "FEHU" or "NTCIR" inside the generated article content field.
6. Do NOT mention "synthetic data", "benchmark", "dataset", "training data", or "annotation" inside the generated article content field.
7. The JSON must be complete and well-formed — no trailing commas, no unmatched brackets.

CONTENT REQUIREMENTS:
- Generate a plausible short news-style article snippet (50–1500 characters in the content field).
- Concrete factual news style; no first-person; no editorial.
- The target actor must be the SUBJECT of the value-bearing action, stance, decision, or behavior.
- Include actor_mention verbatim in the content field.
- Include evidence_sentence verbatim in the content field.
- The evidence_sentence must be a single sentence that:
    (a) appears verbatim in content,
    (b) describes the target actor's action/stance/decision/behavior,
    (c) makes the target value relationship with that actor unambiguous in the specified direction.
- Keep the target value as the most salient human value for the target actor.
- Do NOT make any other human value more salient than the target value for the target actor.
- Avoid generic moral slogans.
- Avoid unsupported real-world accusations of deception, fraud, concealment, misconduct, or criminality.
- For direction_contrastive contradictory samples: express contradiction through the scenario described in the article; do NOT make defamatory real-world assertions about real individuals or organisations.
- For rare_positive: use a concrete, actor-specific action, stance, decision, or policy — not a vague value claim.
- Do NOT copy or paraphrase any development or test article content.
- Do NOT output any prediction file format.

DIRECTION CONVENTION (authoritative):
  direction "1" = aligned   (actor supports / expresses / upholds the value)
  direction "0" = contradictory  (actor violates / undermines / contradicts the value)

REQUIRED JSON OUTPUT SCHEMA:
{
  "title": "<string, news headline, ≤200 chars>",
  "content": "<string, 50–1500 chars, news-style article>",
  "actor_name": "<string, the actor name as instructed>",
  "actor_mention": "<string, exact surface form used in content; MUST appear verbatim in content>",
  "evidence_sentence": "<string, one sentence that appears verbatim in content>",
  "explanation": "<string, one sentence: why the actor-value-direction relationship holds>",
  "l1_value_id": "<string, e.g. '12'>",
  "l1_value_name": "<string, e.g. 'Have success'>",
  "l2_value_id": "<string, e.g. '4'>",
  "l2_value_name": "<string, e.g. 'Achievement'>",
  "direction": "<string, '1' or '0'>",
  "direction_name": "<string, 'aligned' or 'contradictory'>",
  "is_positive": <boolean>,
  "_type_specific_rule": "<string, briefly state the augmentation type rule followed>"
}
"""


def build_system_prompt(req: dict) -> str:
    manifest_sys = req.get("system_prompt", "").strip()
    combined = _SYSTEM_PROMPT_CORE
    if manifest_sys:
        combined += (
            "\n\n---\nADDITIONAL CONTEXT FROM APPROVED REQUEST MANIFEST:\n"
            + manifest_sys
        )
    return combined


def build_user_message(req: dict) -> str:
    aug_type = req.get("augmentation_type", "")
    # All approved types in this manifest are is_positive=True
    is_positive = aug_type in ("rare_positive", "direction_contrastive")
    direction = req.get("target_direction")
    direction_name = req.get("target_direction_name")

    actor_aliases = req.get("actor_aliases", [])
    suggested_mentions = req.get("suggested_actor_mentions", [])

    lines = [
        "=== GENERATION REQUEST METADATA ===",
        f"request_id: {req.get('request_id')}",
        f"augmentation_type: {aug_type}",
        f"seed_guid: {req.get('seed_guid')}",
        f"seed_actor_id: {req.get('seed_actor_id')}",
        f"canonical_actor_name: {req.get('canonical_actor_name')}",
        f"actor_aliases: {json.dumps(actor_aliases)}",
        f"suggested_actor_mentions: {json.dumps(suggested_mentions)}",
        f"target_l1_value_id: {req.get('target_l1_value_id')}",
        f"target_l1_value_name: {req.get('target_l1_value_name')}",
        f"target_l2_value_id: {req.get('target_l2_value_id')}",
        f"target_l2_value_name: {req.get('target_l2_value_name')}",
        f"direction: {direction}",
        f"direction_name: {direction_name}",
        f"is_positive: {is_positive}",
        "",
        "=== APPROVED SYSTEM INSTRUCTIONS (from manifest) ===",
        "",
        req.get("system_prompt", "").strip(),
        "",
        "=== APPROVED USER INSTRUCTION (from manifest) ===",
        "",
        req.get("user_prompt", "").strip(),
        "",
        "=== ACTOR MENTION GUIDANCE ===",
        f"The actor_mention field in your JSON output must appear verbatim in the content field.",
        f"Acceptable actor mentions include any of: {json.dumps(suggested_mentions)}",
        f"You may also use the canonical name or any other natural surface form.",
        "",
        "=== FINAL CONSTRAINT ===",
        "Generate exactly ONE JSON object. No markdown. No extra text. No fences.",
        f"direction MUST be '{direction}' ({direction_name}).",
        f"l1_value_id MUST be '{req.get('target_l1_value_id')}'.",
        f"l1_value_name MUST be '{req.get('target_l1_value_name')}'.",
        f"l2_value_id MUST be '{req.get('target_l2_value_id')}'.",
        f"l2_value_name MUST be '{req.get('target_l2_value_name')}'.",
        f"is_positive MUST be {json.dumps(is_positive)}.",
    ]
    return "\n".join(lines)


# ============================================================
# API call implementation (TASK E)
# ============================================================


def call_deepseek_api(
    model: str,
    temperature: float,
    max_tokens: int,
    messages: list,
    api_key: str,
    use_response_format: bool = True,
):
    """
    POST to DeepSeek Chat Completions.
    Returns (response_dict_or_None, http_status_or_None, error_msg_or_None).
    Never logs the API key.
    """
    url = BASE_URL + ENDPOINT_PATH
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if use_response_format:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode("utf-8")
    # Build request without storing key in any local variable that gets logged
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    req_obj = urllib.request.Request(
        url, data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req_obj, timeout=120) as resp:
            http_status = resp.status
            body = resp.read().decode("utf-8")
            return json.loads(body), http_status, None
    except urllib.error.HTTPError as e:
        http_status = e.code
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e.reason)
        return None, http_status, mask_secret(body)
    except urllib.error.URLError as e:
        return None, None, mask_secret(str(e.reason))
    except Exception:
        return None, None, mask_secret(safe_format_exc())


def extract_content(response_dict: dict):
    try:
        return response_dict["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def extract_finish_reason(response_dict: dict):
    try:
        return response_dict["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return None


def extract_usage(response_dict: dict):
    try:
        return response_dict.get("usage")
    except Exception:
        return None


def parse_json_from_content(content: str):
    """Parse exactly one JSON object from content. Returns (obj, error)."""
    if not content:
        return None, "Empty content from model"
    text = content.strip()
    # Strip markdown fences if the model ignores instructions
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"


# ============================================================
# Sample validation (TASK F)
# ============================================================


def _expected_is_positive(req: dict) -> bool:
    aug_type = req.get("augmentation_type", "")
    return aug_type in ("rare_positive", "direction_contrastive")


def validate_sample(sample: dict, req: dict):
    """
    Validate a parsed sample against its approved request.
    Returns list of dicts: {check, label, status, detail}.
    """
    results = []

    def add(cid, label, status, detail=""):
        results.append({"check": cid, "label": label, "status": status, "detail": detail})

    # --- Checks 1: required fields ---
    for field in REQUIRED_SAMPLE_FIELDS:
        if field not in sample:
            add(f"field_{field}", f"field '{field}' exists", "FAIL",
                f"Missing required field: {field}")
        else:
            add(f"field_{field}", f"field '{field}' exists", "PASS", "")

    title = sample.get("title", "") or ""
    content = sample.get("content", "") or ""
    actor_name = sample.get("actor_name", "") or ""
    actor_mention = sample.get("actor_mention", "") or ""
    evidence = sample.get("evidence_sentence", "") or ""

    # --- Checks 2-7: non-empty fields and verbatim checks ---
    add("title_nonempty", "title non-empty",
        "PASS" if title.strip() else "FAIL", "")

    add("content_nonempty", "content non-empty",
        "PASS" if content.strip() else "FAIL", "")

    add("actor_name_nonempty", "actor_name non-empty",
        "PASS" if actor_name.strip() else "FAIL", "")

    add("actor_mention_nonempty", "actor_mention non-empty",
        "PASS" if actor_mention.strip() else "FAIL", "")

    if actor_mention and content:
        in_content = actor_mention in content
        add("actor_mention_in_content", "actor_mention verbatim in content",
            "PASS" if in_content else "FAIL",
            "" if in_content else f"'{actor_mention}' not found verbatim in content")
    else:
        add("actor_mention_in_content", "actor_mention verbatim in content",
            "FAIL", "actor_mention or content is empty")

    add("evidence_nonempty", "evidence_sentence non-empty",
        "PASS" if evidence.strip() else "FAIL", "")

    if evidence and content:
        ev_in_content = evidence in content
        add("evidence_in_content", "evidence_sentence verbatim in content",
            "PASS" if ev_in_content else "FAIL",
            "" if ev_in_content else "evidence_sentence not found verbatim in content")
    else:
        add("evidence_in_content", "evidence_sentence verbatim in content",
            "FAIL", "evidence_sentence or content is empty")

    # --- Checks 9-15: label and direction matching ---
    expected_l1 = str(req.get("target_l1_value_id", ""))
    got_l1 = str(sample.get("l1_value_id", ""))
    add("l1_value_id_match", "l1_value_id matches request",
        "PASS" if got_l1 == expected_l1 else "FAIL",
        f"expected {expected_l1!r}, got {got_l1!r}")

    expected_l1_name = req.get("target_l1_value_name", "")
    got_l1_name = sample.get("l1_value_name", "")
    add("l1_value_name_match", "l1_value_name matches request",
        "PASS" if got_l1_name == expected_l1_name else "FAIL",
        f"expected {expected_l1_name!r}, got {got_l1_name!r}")

    expected_l2 = str(req.get("target_l2_value_id", ""))
    got_l2 = str(sample.get("l2_value_id", ""))
    add("l2_value_id_match", "l2_value_id matches request",
        "PASS" if got_l2 == expected_l2 else "FAIL",
        f"expected {expected_l2!r}, got {got_l2!r}")

    expected_l2_name = req.get("target_l2_value_name", "")
    got_l2_name = sample.get("l2_value_name", "")
    add("l2_value_name_match", "l2_value_name matches request",
        "PASS" if got_l2_name == expected_l2_name else "FAIL",
        f"expected {expected_l2_name!r}, got {got_l2_name!r}")

    expected_dir = str(req.get("target_direction", ""))
    got_dir = str(sample.get("direction", ""))
    add("direction_match", "direction matches request",
        "PASS" if got_dir == expected_dir else "FAIL",
        f"expected {expected_dir!r}, got {got_dir!r}")

    expected_dir_name = req.get("target_direction_name", "")
    got_dir_name = sample.get("direction_name", "")
    add("direction_name_match", "direction_name matches request",
        "PASS" if got_dir_name == expected_dir_name else "FAIL",
        f"expected {expected_dir_name!r}, got {got_dir_name!r}")

    expected_is_pos = _expected_is_positive(req)
    got_is_pos = sample.get("is_positive")
    add("is_positive_match", "is_positive matches request",
        "PASS" if got_is_pos == expected_is_pos else "FAIL",
        f"expected {expected_is_pos!r}, got {got_is_pos!r}")

    # --- Check 16: direction convention ---
    if got_dir == "1":
        dir_conv_ok = got_dir_name == "aligned"
    elif got_dir == "0":
        dir_conv_ok = got_dir_name == "contradictory"
    else:
        dir_conv_ok = False
    add("direction_convention", "direction convention (aligned=1, contradictory=0)",
        "PASS" if dir_conv_ok else "FAIL",
        f"direction={got_dir!r}, direction_name={got_dir_name!r}")

    # --- Checks 17-19: forbidden content ---
    add("no_as_an_ai", "content does not contain 'as an AI'",
        "PASS" if "as an AI" not in content else "FAIL", "")

    fehu_present = "FEHU" in content or "NTCIR" in content
    add("no_fehu_ntcir", "content does not mention FEHU or NTCIR",
        "PASS" if not fehu_present else "FAIL", "")

    syn_present = re.search(r'\bsynthetic data\b', content, re.IGNORECASE) is not None
    add("no_synthetic_data", "content does not mention synthetic data",
        "PASS" if not syn_present else "FAIL", "")

    # --- Check 20: content length ---
    clen = len(content)
    if clen < 50:
        add("content_length", "content length (50–1500 chars)", "FAIL",
            f"Too short: {clen} chars")
    elif clen > 1500:
        add("content_length", "content length (50–1500 chars)", "WARN",
            f"Exceeds 1500 chars: {clen} chars")
    else:
        add("content_length", "content length (50–1500 chars)", "PASS",
            f"{clen} chars")

    # --- Check 21: evidence superficially mentions actor (WARN only) ---
    ev_mentions_actor = bool(evidence and actor_mention and actor_mention in evidence)
    add("evidence_mentions_actor",
        "evidence_sentence mentions actor (superficial)",
        "PASS" if ev_mentions_actor else "WARN",
        "" if ev_mentions_actor
        else "actor_mention not in evidence_sentence (may still be semantically valid)")

    # --- Check 22: no obvious unsupported severe accusation ---
    severe_terms = ["fraud", "criminal", "convicted", "indicted", "arrested",
                    "embezzled", "bribery", "laundering"]
    found_severe = [t for t in severe_terms if t.lower() in content.lower()]
    add("no_severe_accusation",
        "no obvious unsupported severe accusation",
        "WARN" if found_severe else "PASS",
        f"Found potentially sensitive terms: {found_severe}" if found_severe else "")

    # --- Check 23: candidate_status (set by runner, always PASS) ---
    add("candidate_status", "sample marked PENDING_HUMAN_VERIFICATION",
        "PASS", "Set by runner")

    return results


_STRUCTURAL_CHECKS = frozenset({
    "actor_mention_in_content",
    "evidence_in_content",
    "l1_value_id_match",
    "l1_value_name_match",
    "l2_value_id_match",
    "l2_value_name_match",
    "direction_match",
    "direction_name_match",
    "direction_convention",
    "is_positive_match",
    "no_as_an_ai",
    "no_fehu_ntcir",
    "no_synthetic_data",
    "content_nonempty",
    "actor_mention_nonempty",
    "evidence_nonempty",
    "title_nonempty",
    "content_length",
})


def compute_overall_status(val_results: list) -> str:
    for r in val_results:
        if r["status"] == "FAIL" and (
            r["check"].startswith("field_") or r["check"] in _STRUCTURAL_CHECKS
        ):
            return "FAIL"
    if any(r["status"] == "WARN" for r in val_results):
        return "WARN"
    return "PASS"


# ============================================================
# Report writers (TASK G)
# ============================================================


def write_dashboard(outdir, exec_status, config, stats, results_table):
    lines = [
        "# FEHU DeepSeek V4 Tiny Pilot Generation — Dashboard",
        "",
        f"**Stage:** DeepSeek V4 tiny pilot generation",
        f"**Status:** {exec_status}",
        f"**Timestamp:** {config.get('timestamp')}",
        f"**Model:** {config.get('model')}",
        f"**Execute Mode:** {config.get('execute_mode')}",
        f"**Manifest:** {config.get('manifest_path')}",
        f"**Output Folder:** {config.get('outdir')}",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Approved requests | {stats.get('approved_requests', 6)} |",
        f"| Attempted | {stats.get('attempted', 0)} |",
        f"| Raw responses saved | {stats.get('raw_responses_saved', 0)} |",
        f"| Parsed successfully | {stats.get('parsed', 0)} |",
        f"| Failed (API or parse) | {stats.get('failed', 0)} |",
        f"| Validation PASS | {stats.get('val_pass', 0)} |",
        f"| Validation WARN | {stats.get('val_warn', 0)} |",
        f"| Validation FAIL | {stats.get('val_fail', 0)} |",
        "",
        "## Results Table",
        "",
        "| request_id | augmentation_type | label | direction | parse_status | validation_status | recommended_human_action |",
        "|------------|-------------------|-------|-----------|--------------|-------------------|--------------------------|",
    ]
    for r in results_table:
        lines.append(
            f"| {r['request_id']} | {r['augmentation_type']} | "
            f"{r['label']} | {r['direction']} | {r['parse_status']} | "
            f"{r['validation_status']} | {r['recommended_action']} |"
        )
    lines += [
        "",
        "---",
        "",
        "> **Generated samples are candidates only and are not training-ready "
        "until human verification.**",
        "",
        "## Research Statement",
        "",
        "This tiny pilot tests whether the controlled FEHU augmentation pipeline "
        "can produce actor-specific, label-consistent, direction-consistent, "
        "evidence-grounded samples from a human-approved manifest. "
        "It does not yet claim model performance improvement.",
    ]
    write_file(outdir / "00_GENERATION_DASHBOARD.md", "\n".join(lines))


def write_run_config(outdir, config):
    safe = {k: v for k, v in config.items() if k != "api_key"}
    safe["api_key_value_logged"] = False
    write_file(
        outdir / "01_run_config.json",
        json.dumps(safe, indent=2, ensure_ascii=False),
    )


def write_research_interpretation(outdir):
    content = """\
# 09_research_interpretation.md — Research Interpretation

## Why This Tiny Pilot Was Run

The FEHU Task-1 evaluation reveals two persistent, measurable problems:
(1) Rare labels suffer from near-zero recall, dragging down Macro-F1 (gold-supported).
(2) Direction-contrastive label pairs suffer from elevated Direction Reverse Rate (DRR),
    indicating the classifier confounds aligned and contradictory instances.

Both problems are plausibly attributable to training data sparsity and distributional
imbalance. This tiny pilot tests whether a controlled, human-approved LLM-based
augmentation pipeline can generate article-level training candidates that are:
  - Actor-specific (target actor is the grammatical subject of the value-bearing action)
  - Label-consistent (l1_value_id, l2_value_id match the approved request)
  - Direction-consistent (aligned="1", contradictory="0" per direction_mapping.json)
  - Evidence-grounded (evidence_sentence appears verbatim in content and supports the
    actor-value-direction relationship)

## Why Only 6 Requests Were Used

Six requests represent the smallest viable test of the end-to-end pipeline:
  - 2 rare_positive requests test generation on underrepresented label classes
    (L1=24 "Be neat and tidy", L1=32 "Be behaving properly")
  - 4 direction_contrastive requests (2 complete pairs) test whether the pipeline
    can produce direction-discriminating pairs without conflating aligned/contradictory

Starting with exactly 6 requests reduces API budget risk, limits safety exposure, and
ensures every generated sample can receive thorough human verification. All 6 requests
received explicit human approval by name before this script was run.

## Why rare_positive and direction_contrastive Were Selected First

These two augmentation types address the most directly measurable FEHU weaknesses:

  **rare_positive:** L1=24 and L1=32 both have mean_recall_dir=0.000 in the current
  model evaluation. Zero recall means the classifier never predicts these labels;
  even a small number of targeted training examples may shift the decision boundary
  and produce non-zero recall.

  **direction_contrastive:** L1=12 (Have success) and L1=38 (Be honest) have low
  precision due to over-prediction (mean_prec≈0.13). Paired contrastive samples —
  one aligned, one contradictory, same domain, different actors — provide direction-
  discriminating signal that is absent from single-direction training data. The
  hypothesis is that direction-contrastive augmentation should reduce DRR for these
  values.

## Why paraphrase, hard_negative, and sensitive-label Requests Were Deferred

  **paraphrase:** Adds density but not new class coverage or direction signal.
  Low marginal value at the pilot stage.

  **hard_negative:** Higher risk of confusing the model's decision boundary. Requires
  careful validation of what the "wrong" label is before use.

  **sensitive-label:** Requires additional ethical review before deployment as
  training data. Deferred to a later stage with specialist oversight.

## What This Generation Result Can Prove

If samples pass structural validation:
  - The pipeline produces schema-conformant, structurally valid JSON outputs.
  - The DeepSeek V4 model can follow the actor_mention/evidence_sentence verbatim
    inclusion constraint.
  - Label and direction fields can be mechanically verified against the approved
    manifest.
  - The pipeline is safe: it does not modify official data, evaluation code, or
    prediction files.

## What It Cannot Prove

  - It does NOT prove that adding these samples to training improves Macro-F1 or
    reduces DRR. An ablation experiment is required for that claim.
  - It does NOT prove that generated content is factually accurate or free from bias.
  - It does NOT prove that samples are annotation-consistent with the FEHU gold labels.
  - It does NOT prove that human verifiers will approve any sample for training use.

## Relationship to Rare-Label Recall, Macro-F1, and Direction Reverse Rate

  **Rare-label recall:** If human-verified samples for L1=24 and L1=32 are added to
  training, the classifier may begin predicting these labels. Increased recall for
  rare labels raises Macro-F1 (gold-supported), which averages F1 only over labels
  present in gold.

  **Macro-F1:** Currently near-zero recall for rare labels (L1=24, L1=32) drags the
  macro average below what the raw frequency distribution would suggest. Even one
  correct prediction per label moves recall from 0 to non-zero and may have outsized
  effect on the macro average.

  **Direction Reverse Rate (DRR):** Paired direction-contrastive samples for L1=12
  and L1=38 provide explicit contrastive signal for direction classification. The
  hypothesis is that they reduce DRR; this is to be tested in an ablation experiment,
  not assumed from generation quality.

## Why Generated Samples Are Not Training-Ready Until Human Verification

Human verifiers must confirm:
  1. Content is plausible and newsworthy, not hallucinated or misleading.
  2. actor_mention and evidence_sentence are factually appropriate for the scenario.
  3. The label and direction assignments match the article's semantic intent, not
     just the lexical surface of the evidence sentence.
  4. No defamatory, sensitive, factually incorrect, or ethically problematic content.
  5. The generated sample is distinct enough from training data to add value.

Only after human approval should samples enter a candidate augmentation set — and
even then, an ablation experiment is required to confirm impact before use in
official submissions.

## Recommended Next Experimental Steps

1. **Human verification first:** Review all samples in 08_human_verification_sheet.csv.
   For each sample with overall_validation_status = PASS or WARN, record a human
   decision (ACCEPT / REJECT) and notes.

2. **Create a small verified training candidate set:** Only human-ACCEPT samples
   should be collected into a candidate augmentation file. This is NOT the official
   training dataset; it is a controlled candidate pool.

3. **Run ablation experiment:** Fine-tune (or retrain) the classifier with and without
   the verified augmented samples. Measure delta in:
     - Macro-F1 (gold-supported) on dev set
     - Per-class recall for L1=24, L1=32
     - DRR for L1=12, L1=38

4. **Report delta only; do not claim general improvement:** Document which labels
   improve, which are unaffected, and any regressions introduced.

5. **Expand if ablation is positive:** If the ablation shows meaningful improvement,
   expand to more rare-label and direction-contrastive requests using a larger
   approved manifest — with the same human-approval gating.
"""
    write_file(outdir / "09_research_interpretation.md", content)


# ============================================================
# Blocked report (preflight failure)
# ============================================================


def write_blocked_report(outdir, config, errors, warnings):
    # 00_GENERATION_DASHBOARD.md
    lines = [
        "# FEHU DeepSeek V4 Tiny Pilot Generation — Dashboard",
        "",
        "**Status: BLOCKED — Preflight validation failed. No API calls were made.**",
        "",
        "## Validation Errors",
        "",
    ]
    for e in errors:
        lines.append(f"- {e}")
    if warnings:
        lines += ["", "## Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")
    lines += [
        "",
        "> **Generated samples are candidates only and are not training-ready "
        "until human verification.**",
    ]
    write_file(outdir / "00_GENERATION_DASHBOARD.md", "\n".join(lines))

    # 01_run_config.json
    write_run_config(outdir, config)

    # Empty required JSONL files
    for fname in [
        "02_generation_requests_used.jsonl",
        "03_raw_responses.jsonl",
        "04_parsed_samples.jsonl",
        "05_failed_requests.jsonl",
    ]:
        fpath = outdir / fname
        if not fpath.exists():
            write_file(fpath, "")

    # 10_session_report.md
    session = [
        "# 10_session_report.md — BLOCKED",
        "",
        "## Preflight Validation Result: BLOCKED",
        "",
        "### Errors",
        "",
    ]
    for e in errors:
        session.append(f"- {e}")
    if warnings:
        session += ["", "### Warnings", ""]
        for w in warnings:
            session.append(f"- {w}")
    session += [
        "",
        "## Safety Audit",
        "",
        "- API called? NO",
        "- API key printed or saved? NO",
        "- .env read? NO",
        "- Model training run? NO",
        "- evaluation.py modified? NO",
        "- dataset/** modified? NO",
        "- dataset/gold_labels/** modified? NO",
        "- output/task1*/ modified? NO",
        "- logs/cache_* modified? NO",
        "- Previous research/approval/dry-run folders modified? NO",
        "",
        "## Final Statement",
        "",
        "DeepSeek V4 tiny pilot generation BLOCKED. Preflight validation failed. "
        "No API calls were made. Generated samples are candidates only and are not "
        "training-ready until human verification.",
    ]
    write_file(outdir / "10_session_report.md", "\n".join(session))


# ============================================================
# Validation-only report
# ============================================================


def write_validation_only_report(outdir, config, rows, warnings):
    stats = {
        "approved_requests": len(rows),
        "attempted": 0,
        "raw_responses_saved": 0,
        "parsed": 0,
        "failed": 0,
        "val_pass": 0,
        "val_warn": 0,
        "val_fail": 0,
    }
    table = []
    for row in rows:
        table.append({
            "request_id": row.get("request_id", ""),
            "augmentation_type": row.get("augmentation_type", ""),
            "label": (
                f"L1={row.get('target_l1_value_id')} "
                f"({row.get('target_l1_value_name')})"
            ),
            "direction": (
                f"{row.get('target_direction')} ({row.get('target_direction_name')})"
            ),
            "parse_status": "NOT_RUN",
            "validation_status": "NOT_RUN",
            "recommended_action": "Run with --execute to generate",
        })

    write_dashboard(outdir, "VALIDATION_ONLY_PASSED", config, stats, table)
    write_run_config(outdir, config)

    # Empty JSONL files
    for fname in [
        "03_raw_responses.jsonl",
        "04_parsed_samples.jsonl",
        "05_failed_requests.jsonl",
    ]:
        if not (outdir / fname).exists():
            write_file(outdir / fname, "")

    # 06_validation_report.md
    val_lines = [
        "# 06_validation_report.md — Validation-Only Mode",
        "",
        "**Result: All preflight checks PASSED.**",
        "",
        "Execution was not requested (--execute not provided). No API calls were made.",
        "",
        "## Checks Verified",
        "",
        "- [PASS] Manifest exists and has exactly 6 rows",
        "- [PASS] All rows have manual_approval_status = APPROVED_BY_HUMAN",
        "- [PASS] All rows have api_generation_authorized_now = false",
        "- [PASS] All rows have requires_separate_generation_runner_approval = true",
        "- [PASS] No PENDING_HUMAN_APPROVAL rows",
        "- [PASS] No 'execute' or 'should_execute_now' fields",
        "- [PASS] No hard_negative, paraphrase, or sensitive_label requests",
        "- [PASS] Exact approved request IDs confirmed",
        "- [PASS] Both direction-contrastive pairs complete (L1=12 Have success, L1=38 Be honest)",
        "- [PASS] Direction convention: aligned=1, contradictory=0",
        "- [PASS] No secret-shaped tokens in manifest",
        "",
        "## Warnings",
        "",
    ]
    if warnings:
        for w in warnings:
            val_lines.append(f"- {w}")
    else:
        val_lines.append("None.")
    val_lines += [
        "",
        "## Next Step",
        "",
        "Set DEEPSEEK_API_KEY and rerun with --execute to begin generation:",
        "",
        "```",
        "read -s DEEPSEEK_API_KEY",
        "export DEEPSEEK_API_KEY",
        "python run_tiny_pilot_generation.py --manifest <path> --outdir <same_outdir> --execute",
        "```",
        "",
        "> Generated samples are candidates only and are not training-ready until human verification.",
    ]
    write_file(outdir / "06_validation_report.md", "\n".join(val_lines))

    # Placeholder CSVs
    write_file(outdir / "07_validation_table.csv",
               "# Not available in validation-only mode — rerun with --execute\n")
    write_file(outdir / "08_human_verification_sheet.csv",
               "# Not available in validation-only mode — rerun with --execute\n")

    write_research_interpretation(outdir)

    # 10_session_report.md
    session = [
        "# 10_session_report.md — Validation-Only Mode",
        "",
        "- API called? NO (validation-only mode; --execute not provided)",
        "- API key printed or saved? NO",
        "- .env read? NO",
        "- Model training run? NO",
        "- evaluation.py modified? NO",
        "- dataset/** modified? NO",
        "- dataset/gold_labels/** modified? NO",
        "- output/task1*/ modified? NO",
        "- logs/cache_* modified? NO",
        "- Previous research/approval/dry-run folders modified? NO",
        f"- New code folder: research/fehu_tiny_pilot_generation_v1/",
        f"- New output folder: {outdir}",
        "",
        "## Requests",
        "",
        "- Requests attempted: 0 (validation-only)",
        "- Requests parsed: 0",
        "- Requests failed: 0",
        "- Validation PASS/WARN/FAIL: 0/0/0 (not run)",
        "",
        "## Final Statement",
        "",
        "DeepSeek V4 tiny pilot generation validation-only mode passed. "
        "No API calls were made. Run with --execute to begin generation. "
        "Generated samples are candidates only and are not training-ready "
        "until human verification.",
    ]
    write_file(outdir / "10_session_report.md", "\n".join(session))


# ============================================================
# Execute-mode reports
# ============================================================


def write_execute_reports(outdir, config, stats, results_table, all_parsed, all_failed, rows):
    n_fail = stats["failed"]
    n_att = stats["attempted"]
    if n_att == 0:
        exec_status = "NO_REQUESTS_ATTEMPTED"
    elif n_fail == n_att:
        exec_status = "ALL_FAILED"
    elif n_fail > 0:
        exec_status = "PARTIAL"
    else:
        exec_status = "COMPLETED"

    write_dashboard(outdir, exec_status, config, stats, results_table)
    write_run_config(outdir, config)

    # 06_validation_report.md
    val_lines = [
        "# 06_validation_report.md — Validation Report",
        "",
        "## Summary",
        "",
        f"- Total attempted: {stats['attempted']}",
        f"- Parsed successfully: {stats['parsed']}",
        f"- Failed (API or parse): {stats['failed']}",
        f"- Validation PASS: {stats['val_pass']}",
        f"- Validation WARN: {stats['val_warn']}",
        f"- Validation FAIL: {stats['val_fail']}",
        "",
        "## Per-Request Validation",
        "",
    ]
    for row in results_table:
        val_lines += [
            f"### {row['request_id']}",
            f"- augmentation_type: {row['augmentation_type']}",
            f"- label: {row['label']}",
            f"- direction: {row['direction']}",
            f"- parse_status: {row['parse_status']}",
            f"- validation_status: {row['validation_status']}",
            f"- recommended_action: {row['recommended_action']}",
            "",
        ]

    # Per-parsed detailed checks
    val_lines.append("## Detailed Validation Results\n")
    for pr in all_parsed:
        val_lines.append(f"### {pr['request_id']}\n")
        for check in pr.get("_validation_checks", []):
            val_lines.append(
                f"- [{check['status']}] {check['label']}"
                + (f" — {check['detail']}" if check.get("detail") else "")
            )
        val_lines.append("")

    usable = stats["val_fail"] == 0 and stats["parsed"] > 0
    val_lines += [
        "## Usability Assessment",
        "",
        "Samples appear usable for human verification." if usable
        else "Some samples have structural issues. Review failed checks before proceeding.",
        "",
        "> **Generated samples are not training-ready until human verification.**",
    ]
    write_file(outdir / "06_validation_report.md", "\n".join(val_lines))

    # 07_validation_table.csv
    csv07_fieldnames = [
        "request_id", "augmentation_type", "l1_value_id", "l1_value_name",
        "direction", "direction_name", "parse_status", "required_fields_status",
        "actor_mention_in_content", "evidence_sentence_in_content",
        "label_match_status", "direction_match_status",
        "factuality_warning", "style_warning",
        "overall_validation_status", "recommended_human_action",
    ]
    csv07_rows = []
    rows_by_id = {r.get("request_id"): r for r in rows}
    rt_by_id = {r["request_id"]: r for r in results_table}

    for pr in all_parsed:
        rid = pr["request_id"]
        req = rows_by_id.get(rid, {})
        vs = pr.get("validation_summary", {})
        rt = rt_by_id.get(rid, {})

        required_fields_ok = all(
            vs.get(f"field_{f}") != "FAIL" for f in REQUIRED_SAMPLE_FIELDS
        )
        label_ok = all(
            vs.get(k) == "PASS"
            for k in ["l1_value_id_match", "l1_value_name_match",
                      "l2_value_id_match", "l2_value_name_match"]
        )
        dir_ok = all(
            vs.get(k) == "PASS"
            for k in ["direction_match", "direction_name_match",
                      "direction_convention", "is_positive_match"]
        )
        csv07_rows.append({
            "request_id": rid,
            "augmentation_type": pr["augmentation_type"],
            "l1_value_id": req.get("target_l1_value_id", ""),
            "l1_value_name": req.get("target_l1_value_name", ""),
            "direction": req.get("target_direction", ""),
            "direction_name": req.get("target_direction_name", ""),
            "parse_status": "PASS",
            "required_fields_status": "PASS" if required_fields_ok else "FAIL",
            "actor_mention_in_content": vs.get("actor_mention_in_content", "UNKNOWN"),
            "evidence_sentence_in_content": vs.get("evidence_in_content", "UNKNOWN"),
            "label_match_status": "PASS" if label_ok else "FAIL",
            "direction_match_status": "PASS" if dir_ok else "FAIL",
            "factuality_warning": vs.get("no_severe_accusation", "UNKNOWN"),
            "style_warning": vs.get("content_length", "UNKNOWN"),
            "overall_validation_status": pr["overall_validation_status"],
            "recommended_human_action": rt.get("recommended_action", "REVIEW"),
        })

    for f in all_failed:
        csv07_rows.append({
            "request_id": f["request_id"],
            "augmentation_type": "",
            "l1_value_id": "",
            "l1_value_name": "",
            "direction": "",
            "direction_name": "",
            "parse_status": "FAIL",
            "required_fields_status": "N/A",
            "actor_mention_in_content": "N/A",
            "evidence_sentence_in_content": "N/A",
            "label_match_status": "N/A",
            "direction_match_status": "N/A",
            "factuality_warning": "N/A",
            "style_warning": "N/A",
            "overall_validation_status": "FAIL",
            "recommended_human_action": "Check API or parse error",
        })

    write_csv(outdir / "07_validation_table.csv", csv07_fieldnames, csv07_rows)

    # 08_human_verification_sheet.csv
    csv08_fieldnames = [
        "request_id", "augmentation_type", "title", "content", "actor_name",
        "actor_mention", "evidence_sentence", "l1_value_id", "l1_value_name",
        "l2_value_id", "l2_value_name", "direction", "direction_name",
        "validation_status", "human_decision", "human_notes",
    ]
    csv08_rows = []
    for pr in all_parsed:
        s = pr["generated_sample"]
        csv08_rows.append({
            "request_id": pr["request_id"],
            "augmentation_type": pr["augmentation_type"],
            "title": s.get("title", ""),
            "content": s.get("content", ""),
            "actor_name": s.get("actor_name", ""),
            "actor_mention": s.get("actor_mention", ""),
            "evidence_sentence": s.get("evidence_sentence", ""),
            "l1_value_id": s.get("l1_value_id", ""),
            "l1_value_name": s.get("l1_value_name", ""),
            "l2_value_id": s.get("l2_value_id", ""),
            "l2_value_name": s.get("l2_value_name", ""),
            "direction": s.get("direction", ""),
            "direction_name": s.get("direction_name", ""),
            "validation_status": pr["overall_validation_status"],
            "human_decision": "",
            "human_notes": "",
        })
    write_csv(outdir / "08_human_verification_sheet.csv", csv08_fieldnames, csv08_rows)

    write_research_interpretation(outdir)

    # Collect token usage from raw responses for session report
    token_info_lines = ["See 03_raw_responses.jsonl for per-request 'usage' field."]

    # 10_session_report.md
    files_created = [
        "00_GENERATION_DASHBOARD.md",
        "01_run_config.json",
        "02_generation_requests_used.jsonl",
        "03_raw_responses.jsonl",
        "04_parsed_samples.jsonl",
        "05_failed_requests.jsonl",
        "06_validation_report.md",
        "07_validation_table.csv",
        "08_human_verification_sheet.csv",
        "09_research_interpretation.md",
        "10_session_report.md",
    ]
    session = [
        "# 10_session_report.md",
        "",
        "## Safety Audit",
        "",
        f"- API called? {'YES' if stats['attempted'] > 0 else 'NO'}",
        "- API key printed or saved? NO",
        "- .env read? NO",
        "- Model training run? NO",
        "- evaluation.py modified? NO",
        "- dataset/** modified? NO",
        "- dataset/gold_labels/** modified? NO",
        "- output/task1*/ modified? NO",
        "- logs/cache_* modified? NO",
        "- Previous research/approval/dry-run folders modified? NO",
        "",
        "## Paths",
        "",
        f"- New code folder: research/fehu_tiny_pilot_generation_v1/",
        f"- New output folder: {outdir}",
        "",
        "## Files Created",
        "",
    ]
    for fn in files_created:
        session.append(f"- {fn}")

    session += [
        "",
        "## Execution Summary",
        "",
        f"- Requests attempted: {stats['attempted']}",
        f"- Requests parsed: {stats['parsed']}",
        f"- Requests failed: {stats['failed']}",
        f"- Validation PASS: {stats['val_pass']}",
        f"- Validation WARN: {stats['val_warn']}",
        f"- Validation FAIL: {stats['val_fail']}",
        "",
        "## Cost / Token Usage",
        "",
    ]
    session += token_info_lines
    session += [
        "API key value was not logged in any file.",
        "",
        "## Final Statement",
        "",
        "DeepSeek V4 tiny pilot generation completed. "
        "Generated samples are candidates only and are not training-ready "
        "until human verification.",
    ]
    write_file(outdir / "10_session_report.md", "\n".join(session))


# ============================================================
# Main
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="FEHU DeepSeek V4 Tiny Pilot Generation Runner"
    )
    parser.add_argument("--manifest", required=True,
                        help="Path to human-approved manifest JSONL")
    parser.add_argument("--outdir", required=True,
                        help="Output directory path")
    parser.add_argument("--model", default="deepseek-v4-pro",
                        help="DeepSeek model ID (default: deepseek-v4-pro)")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1800, dest="max_tokens")
    parser.add_argument("--execute", action="store_true",
                        help="Run actual API generation (requires DEEPSEEK_API_KEY)")
    args = parser.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Read API key from environment only — never from .env or arguments
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    api_key_present = bool(api_key)
    if api_key_present:
        set_secret(api_key)  # Register for masking in all output

    config = {
        "timestamp": iso_now(),
        "model": args.model,
        "base_url": BASE_URL,
        "endpoint_path": ENDPOINT_PATH,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "response_format_requested": True,
        "manifest_path": str(args.manifest),
        "outdir": str(outdir),
        "approved_request_count": 6,
        "execute_mode": args.execute,
        "api_key_present": api_key_present,
        "api_key_value_logged": False,
        "retry_policy": "max_1_retry_per_request",
        "official_data_modified": False,
    }

    # Initialize JSONL output files early (for append safety)
    for fname in [
        "03_raw_responses.jsonl",
        "04_parsed_samples.jsonl",
        "05_failed_requests.jsonl",
    ]:
        fpath = outdir / fname
        if not fpath.exists():
            write_file(fpath, "")

    # --- Load manifest ---
    rows, load_err = load_manifest(args.manifest)
    if load_err:
        write_blocked_report(outdir, config, [f"Manifest load error: {load_err}"], [])
        print(f"ERROR: {load_err}", file=sys.stderr)
        sys.exit(1)

    # --- Preflight validation ---
    errors, warnings = validate_manifest(rows, args.execute, api_key_present)

    if errors:
        write_blocked_report(outdir, config, errors, warnings)
        print("PREFLIGHT VALIDATION FAILED — no API calls made.", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Preflight validation: PASSED ({len(rows)} approved requests)")

    # --- Write 02_generation_requests_used.jsonl ---
    req_used_path = outdir / "02_generation_requests_used.jsonl"
    write_file(req_used_path, "")  # reset
    for row in rows:
        append_jsonl(req_used_path, row)

    # --- Validation-only mode ---
    if not args.execute:
        write_validation_only_report(outdir, config, rows, warnings)
        print("VALIDATION-ONLY MODE: All preflight checks passed.")
        print("To run generation: set DEEPSEEK_API_KEY and add --execute")
        print(f"Output: {outdir}")
        return

    # --- Execute mode ---
    print(f"EXECUTE MODE: Calling DeepSeek API for {len(rows)} requests.")
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}", file=sys.stderr)

    results_table = []
    all_parsed = []
    all_failed = []
    stats = {
        "approved_requests": len(rows),
        "attempted": 0,
        "raw_responses_saved": 0,
        "parsed": 0,
        "failed": 0,
        "val_pass": 0,
        "val_warn": 0,
        "val_fail": 0,
    }

    # Reset JSONL files for execute run
    write_file(outdir / "03_raw_responses.jsonl", "")
    write_file(outdir / "04_parsed_samples.jsonl", "")
    write_file(outdir / "05_failed_requests.jsonl", "")

    for req in rows:
        rid = req.get("request_id", "UNKNOWN")
        aug_type = req.get("augmentation_type", "")
        direction = req.get("target_direction", "")
        direction_name = req.get("target_direction_name", "")
        l1_id = req.get("target_l1_value_id", "")
        l1_name = req.get("target_l1_value_name", "")
        label = f"L1={l1_id} ({l1_name})"

        print(f"  [{stats['attempted'] + 1}/6] {rid}", end=" ... ", flush=True)
        stats["attempted"] += 1

        messages = [
            {"role": "system", "content": build_system_prompt(req)},
            {"role": "user", "content": build_user_message(req)},
        ]

        # First attempt with response_format
        response, http_status, error_msg = call_deepseek_api(
            args.model, args.temperature, args.max_tokens,
            messages, api_key, use_response_format=True,
        )
        retry_count = 0

        if response is None:
            retry_count = 1
            # Decide retry strategy: drop response_format if the error mentions it
            err_lower = (error_msg or "").lower()
            use_rf_on_retry = "response_format" not in err_lower
            print(f"[retry {retry_count}]", end=" ", flush=True)
            response, http_status, error_msg = call_deepseek_api(
                args.model, args.temperature, args.max_tokens,
                messages, api_key, use_response_format=use_rf_on_retry,
            )

        # --- Save raw response ---
        raw_record = {
            "request_id": rid,
            "model": args.model,
            "timestamp": iso_now(),
            "http_status": http_status,
            "raw_response_text": mask_secret(
                json.dumps(response, ensure_ascii=False) if response
                else f"ERROR: {error_msg or 'unknown'}"
            ),
            "finish_reason": extract_finish_reason(response) if response else None,
            "usage": extract_usage(response) if response else None,
            "retry_count": retry_count,
            "secret_logged": False,
        }
        append_jsonl(outdir / "03_raw_responses.jsonl", raw_record)
        stats["raw_responses_saved"] += 1

        # --- Handle API failure ---
        if response is None:
            failed_record = {
                "request_id": rid,
                "failure_stage": "api_call",
                "failure_reason": "API call failed after retry",
                "sanitized_error": mask_secret(str(error_msg or "")),
                "raw_response_excerpt": "",
                "retry_count": retry_count,
            }
            append_jsonl(outdir / "05_failed_requests.jsonl", failed_record)
            stats["failed"] += 1
            all_failed.append(failed_record)
            results_table.append({
                "request_id": rid,
                "augmentation_type": aug_type,
                "label": label,
                "direction": f"{direction} ({direction_name})",
                "parse_status": "FAIL",
                "validation_status": "FAIL",
                "recommended_action": "API failed; check DEEPSEEK_API_KEY and retry",
            })
            print("FAILED (api_error)")
            continue

        # --- Parse JSON ---
        content_text = extract_content(response)
        parsed_obj, parse_error = parse_json_from_content(content_text)

        if parsed_obj is None:
            failed_record = {
                "request_id": rid,
                "failure_stage": "json_parse",
                "failure_reason": parse_error,
                "sanitized_error": parse_error,
                "raw_response_excerpt": (content_text or "")[:500],
                "retry_count": retry_count,
            }
            append_jsonl(outdir / "05_failed_requests.jsonl", failed_record)
            stats["failed"] += 1
            all_failed.append(failed_record)
            results_table.append({
                "request_id": rid,
                "augmentation_type": aug_type,
                "label": label,
                "direction": f"{direction} ({direction_name})",
                "parse_status": "FAIL",
                "validation_status": "FAIL",
                "recommended_action": f"JSON parse failed: {parse_error}",
            })
            print(f"FAILED (parse: {parse_error})")
            continue

        stats["parsed"] += 1

        # --- Validate ---
        val_checks = validate_sample(parsed_obj, req)
        overall_status = compute_overall_status(val_checks)
        val_summary = {r["check"]: r["status"] for r in val_checks}

        if overall_status == "PASS":
            stats["val_pass"] += 1
            recommended = "REVIEW: structural checks pass; verify content quality"
        elif overall_status == "WARN":
            stats["val_warn"] += 1
            recommended = "REVIEW: content warnings present; human judgment required"
        else:
            stats["val_fail"] += 1
            recommended = "REJECT: structural validation failed; review and discard"

        parsed_record = {
            "request_id": rid,
            "augmentation_type": aug_type,
            "generated_sample": parsed_obj,
            "validation_summary": val_summary,
            "_validation_checks": val_checks,  # full detail for reports
            "overall_validation_status": overall_status,
            "candidate_status": "PENDING_HUMAN_VERIFICATION",
        }
        append_jsonl(outdir / "04_parsed_samples.jsonl", {
            k: v for k, v in parsed_record.items() if k != "_validation_checks"
        })
        all_parsed.append(parsed_record)

        results_table.append({
            "request_id": rid,
            "augmentation_type": aug_type,
            "label": label,
            "direction": f"{direction} ({direction_name})",
            "parse_status": "PASS",
            "validation_status": overall_status,
            "recommended_action": recommended,
        })
        print(f"{overall_status}")

    # --- Write all final reports ---
    write_execute_reports(
        outdir, config, stats, results_table, all_parsed, all_failed, rows
    )

    print()
    print(f"Generation complete. Output: {outdir}")
    print(
        f"Attempted: {stats['attempted']} | "
        f"Parsed: {stats['parsed']} | "
        f"Failed: {stats['failed']}"
    )
    print(
        f"Validation: PASS={stats['val_pass']} | "
        f"WARN={stats['val_warn']} | "
        f"FAIL={stats['val_fail']}"
    )
    print(
        "Generated samples are candidates only and are not training-ready "
        "until human verification."
    )


if __name__ == "__main__":
    main()
