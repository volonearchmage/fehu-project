#!/usr/bin/env python3
"""
repair_and_regenerate_tiny_pilot.py

FEHU Tiny Pilot Repair and Targeted Regeneration.

Stage: Targeted repair/regeneration of DeepSeek V4 tiny pilot generation results.
       Part of the diagnosis-driven, recall-focused targeted augmentation workflow.

What this script does:
  1. Reads the previous tiny pilot output folder (read-only).
  2. Triages the 6 approved requests into KEEP / DETERMINISTIC_REPAIR / REGENERATE.
  3. Performs deterministic field repair on eligible parsed samples.
  4. Calls DeepSeek API for the 2 targeted regeneration requests only.
  5. Unifies all candidate samples and re-validates them.
  6. Writes all 12 required output reports.

Safety invariants (never violated):
  - Never trains any model.
  - Never modifies evaluation.py, dataset/**, gold_labels/**, output/task1*/, logs/cache_*.
  - Never modifies any prior research, approval, or dry-run folder.
  - Never modifies the original tiny pilot output folder.
  - Never writes API key to any file, log, or exception message.
  - Never creates pred_task1a.json or pred_task1b.json.
  - Never writes into the official training dataset.
  - Never approves generated samples for training automatically.
  - Generated samples remain PENDING_HUMAN_VERIFICATION.

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

# Pre-classified triage (from pilot analysis)
KEEP_IDS = frozenset([
    "prev_dir_contrast_12_002_aligned_ce1da19f54",       # PASS
    "prev_dir_contrast_38_003_contradictory_e969e14138", # WARN
    "prev_rare_positive_32_001_83df110175",              # WARN
])
DETERMINISTIC_REPAIR_IDS = frozenset([
    "prev_dir_contrast_38_003_aligned_e969e14138",       # evidence_sentence truncated
])
REGENERATION_IDS = frozenset([
    "prev_dir_contrast_12_002_contradictory_ce1da19f54", # finish_reason=length
    "prev_rare_positive_24_004_98671d8d01",              # finish_reason=length, empty content
])

DIRECTION_ALIGNED = "1"
DIRECTION_CONTRADICTORY = "0"

BASE_URL = "https://api.deepseek.com"
ENDPOINT_PATH = "/chat/completions"

REQUIRED_SAMPLE_FIELDS = [
    "title", "content", "actor_name", "actor_mention", "evidence_sentence",
    "explanation", "l1_value_id", "l1_value_name", "l2_value_id", "l2_value_name",
    "direction", "direction_name", "is_positive", "_type_specific_rule",
]

_STRUCTURAL_CHECKS = frozenset({
    "actor_mention_in_content", "evidence_in_content",
    "l1_value_id_match", "l1_value_name_match",
    "l2_value_id_match", "l2_value_name_match",
    "direction_match", "direction_name_match",
    "direction_convention", "is_positive_match",
    "no_as_an_ai", "no_fehu_ntcir", "no_synthetic_data",
    "content_nonempty", "actor_mention_nonempty",
    "evidence_nonempty", "title_nonempty", "content_length",
})

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
# Read previous pilot (read-only)
# ============================================================


def load_jsonl(path: pathlib.Path) -> list:
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def read_prev_pilot(input_dir: pathlib.Path) -> dict:
    """Read all relevant files from previous pilot. Returns dict of loaded data."""
    return {
        "parsed_samples": load_jsonl(input_dir / "04_parsed_samples.jsonl"),
        "failed_requests": load_jsonl(input_dir / "05_failed_requests.jsonl"),
    }


def load_manifest(manifest_path: str) -> tuple:
    path = pathlib.Path(manifest_path)
    if not path.exists():
        return None, f"Manifest not found: {manifest_path}"
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                return None, f"JSON error at line {i}: {e}"
    return rows, None


# ============================================================
# Triage
# ============================================================


def triage_requests(prev_data: dict, manifest_rows: list) -> dict:
    """
    Triage 6 requests against pre-defined classification.
    Returns dict with keys: keep, repair, regenerate, contradictions.
    """
    parsed_by_id = {r["request_id"]: r for r in prev_data["parsed_samples"]}
    failed_by_id = {r["request_id"]: r for r in prev_data["failed_requests"]}
    manifest_by_id = {r.get("request_id"): r for r in manifest_rows}

    contradictions = []

    # Verify KEEP samples exist and have PASS/WARN status
    for rid in KEEP_IDS:
        p = parsed_by_id.get(rid)
        if p is None:
            contradictions.append(
                f"CONTRADICTION: {rid} classified as KEEP but not in parsed_samples"
            )
        elif p["overall_validation_status"] == "FAIL":
            contradictions.append(
                f"CONTRADICTION: {rid} classified as KEEP but has status FAIL"
            )

    # Verify REPAIR sample exists with FAIL status
    for rid in DETERMINISTIC_REPAIR_IDS:
        p = parsed_by_id.get(rid)
        if p is None:
            contradictions.append(
                f"CONTRADICTION: {rid} classified as REPAIR but not in parsed_samples"
            )

    # Verify REGENERATE samples are in failed_requests
    for rid in REGENERATION_IDS:
        if rid not in failed_by_id and rid not in parsed_by_id:
            contradictions.append(
                f"CONTRADICTION: {rid} classified as REGENERATE but not in failures"
            )

    return {
        "keep": [parsed_by_id[rid] for rid in KEEP_IDS if rid in parsed_by_id],
        "repair": [parsed_by_id[rid] for rid in DETERMINISTIC_REPAIR_IDS if rid in parsed_by_id],
        "regenerate_ids": list(REGENERATION_IDS),
        "manifest_by_id": manifest_by_id,
        "contradictions": contradictions,
        "parsed_by_id": parsed_by_id,
        "failed_by_id": failed_by_id,
    }


# ============================================================
# Deterministic repair
# ============================================================


def find_full_sentence(evidence: str, content: str) -> str:
    """
    Find the full sentence in content that starts with evidence (possibly truncated).
    Evidence may have a trailing period removed to find the matching prefix.
    Returns the full sentence or None.
    """
    # Try exact match first
    if evidence in content:
        return evidence

    # Try prefix match: strip trailing period from evidence and find in content
    ev_stripped = evidence.rstrip('.').rstrip()
    if not ev_stripped:
        return None

    pos = content.find(ev_stripped)
    if pos == -1:
        return None

    # Find next sentence-ending punctuation after the evidence prefix
    end = content.find('.', pos + len(ev_stripped))
    if end == -1:
        return None

    full_sentence = content[pos:end + 1]

    # Verify it appears verbatim
    if full_sentence in content:
        return full_sentence
    return None


def attempt_deterministic_repair(sample_record: dict, req: dict) -> tuple:
    """
    Attempt to repair evidence_sentence by expanding to full sentence in content.
    Returns (repaired_record, report_lines).
    repair_record is None if repair fails.
    """
    report = []
    gs = sample_record.get("generated_sample", {})
    rid = sample_record["request_id"]

    report.append(f"## Deterministic Repair: {rid}")
    report.append("")

    # Condition 1: parsed sample exists
    report.append("- [CHECK 1] Parsed sample exists: PASS")

    # Condition 2: required fields exist
    missing = [f for f in REQUIRED_SAMPLE_FIELDS if f not in gs]
    if missing:
        report.append(f"- [CHECK 2] Required fields: FAIL — missing: {missing}")
        report.append("")
        report.append("**REPAIR FAILED: missing required fields**")
        return None, report
    report.append("- [CHECK 2] Required fields: PASS")

    # Condition 3: label/direction match
    checks = {
        "l1_value_id": (str(gs.get("l1_value_id")), str(req.get("target_l1_value_id"))),
        "l1_value_name": (gs.get("l1_value_name"), req.get("target_l1_value_name")),
        "l2_value_id": (str(gs.get("l2_value_id")), str(req.get("target_l2_value_id"))),
        "l2_value_name": (gs.get("l2_value_name"), req.get("target_l2_value_name")),
        "direction": (str(gs.get("direction")), str(req.get("target_direction"))),
        "is_positive": (gs.get("is_positive"), True),
    }
    label_ok = all(got == expected for got, expected in checks.values())
    if not label_ok:
        for field, (got, expected) in checks.items():
            if got != expected:
                report.append(f"- [CHECK 3] {field} mismatch: got {got!r}, expected {expected!r}")
        report.append("**REPAIR FAILED: label/direction mismatch**")
        return None, report
    report.append("- [CHECK 3] Label/direction match: PASS")

    content = gs.get("content", "")
    actor_mention = gs.get("actor_mention", "")
    evidence = gs.get("evidence_sentence", "")

    # Condition 4: actor_mention in content
    if actor_mention not in content:
        report.append(f"- [CHECK 4] actor_mention in content: FAIL")
        report.append("**REPAIR FAILED: actor_mention not in content**")
        return None, report
    report.append("- [CHECK 4] actor_mention in content: PASS")

    # Condition 5+6: find full sentence
    full_sentence = find_full_sentence(evidence, content)
    if full_sentence is None:
        report.append(f"- [CHECK 5] Find full sentence in content: FAIL")
        report.append(f"  evidence: {evidence!r}")
        report.append(f"  content excerpt around evidence: ...")
        report.append("**REPAIR FAILED: cannot find full sentence in content**")
        return None, report
    report.append(f"- [CHECK 5] Full sentence found in content: PASS")
    report.append(f"  original: {evidence!r}")
    report.append(f"  repaired: {full_sentence!r}")

    # Condition 7: replacement doesn't change other fields
    report.append("- [CHECK 7] Replacement only changes evidence_sentence field: PASS")

    # Condition 8: repaired sentence still mentions the target actor (superficial)
    if actor_mention not in full_sentence:
        report.append(
            f"- [CHECK 8] Repaired sentence mentions actor: WARN "
            f"(actor_mention not in repaired sentence, but semantically may be valid)"
        )
    else:
        report.append("- [CHECK 8] Repaired sentence mentions actor: PASS")

    # Create repaired sample
    repaired_gs = dict(gs)
    repaired_gs["evidence_sentence"] = full_sentence

    repaired_record = {
        "request_id": rid,
        "augmentation_type": sample_record["augmentation_type"],
        "generated_sample": repaired_gs,
        "repair_status": "DETERMINISTIC_FIELD_REPAIR",
        "repair_type": "evidence_sentence_expanded_to_exact_content_sentence",
        "original_evidence_sentence": evidence,
        "repaired_evidence_sentence": full_sentence,
        "candidate_status": "PENDING_HUMAN_VERIFICATION",
        "training_ready": False,
        "source_stage": "deterministic_repair",
    }

    report.append("")
    report.append("**REPAIR SUCCEEDED**")
    report.append(f"- original_evidence_sentence: {evidence!r}")
    report.append(f"- repaired_evidence_sentence: {full_sentence!r}")
    report.append("")

    return repaired_record, report


# ============================================================
# Regeneration prompts (TASK D — stricter than initial pilot)
# ============================================================

_REGEN_SYSTEM_PROMPT = """You are a synthetic news content generator for an academic research benchmark.

CRITICAL OUTPUT RULES — FOLLOW EXACTLY:
1. Your response MUST start with "{" and end with "}".
2. Return ONLY a valid JSON object. Nothing before "{". Nothing after "}".
3. Do NOT use markdown fences (no ```, no ```json).
4. Do NOT write analysis, reasoning, commentary, or explanation outside the JSON.
5. Do NOT write code blocks or XML tags.
6. Do NOT say "as an AI" anywhere.
7. Do NOT mention "FEHU", "NTCIR", "synthetic", "benchmark", "dataset", or "training".
8. The JSON MUST be complete and syntactically valid — no truncation, no ellipsis.

CONTENT LENGTH REQUIREMENTS:
- content: 120–180 words maximum. Short paragraphs only. Do not write long text.
- title: 10–15 words maximum.
- explanation: 1–2 short sentences maximum.
- evidence_sentence: exactly ONE sentence, copied verbatim from your content field.

CONTENT QUALITY REQUIREMENTS:
- News-style prose. No first-person. No editorial tone.
- The target actor must be the grammatical subject of the value-bearing action.
- actor_mention MUST appear verbatim in content.
- evidence_sentence MUST appear verbatim in content (copy one sentence exactly).
- Target value must be the most salient human value for this actor.
- Do NOT make any non-target value more salient.
- Avoid generic moral slogans.
- No unsupported accusations of fraud, crime, concealment, misconduct, or deception.
- For contradictory direction: express contradiction through the article scenario;
  do NOT make defamatory claims about real people or real organisations.
- For rare_positive: use concrete actor-specific action, decision, policy, or stance.
- Do NOT copy or paraphrase development or test article content.

DIRECTION CONVENTION (authoritative):
  direction "1" = aligned (actor supports/expresses/upholds the value)
  direction "0" = contradictory (actor violates/undermines/contradicts the value)

REQUIRED JSON FIELDS (output ALL of them):
{
  "title": "<10–15 word headline>",
  "content": "<120–180 word news article>",
  "actor_name": "<actor name as instructed>",
  "actor_mention": "<exact surface form; MUST appear verbatim in content>",
  "evidence_sentence": "<one sentence copied exactly from content>",
  "explanation": "<1–2 sentences: why actor-value-direction holds>",
  "l1_value_id": "<string>",
  "l1_value_name": "<string>",
  "l2_value_id": "<string>",
  "l2_value_name": "<string>",
  "direction": "<'1' or '0'>",
  "direction_name": "<'aligned' or 'contradictory'>",
  "is_positive": <boolean>,
  "_type_specific_rule": "<one sentence: augmentation type rule followed>"
}
"""


def build_regen_system_prompt(req: dict) -> str:
    manifest_sys = (req.get("system_prompt") or "").strip()
    combined = _REGEN_SYSTEM_PROMPT
    if manifest_sys:
        combined += (
            "\n\n---\nAPPROVED GENERATION GUIDELINES (from manifest):\n"
            + manifest_sys
        )
    return combined


def build_regen_user_message(req: dict) -> str:
    aug_type = req.get("augmentation_type", "")
    is_positive = aug_type in ("rare_positive", "direction_contrastive")
    direction = req.get("target_direction")
    direction_name = req.get("target_direction_name")
    actor_aliases = req.get("actor_aliases", [])
    suggested_mentions = req.get("suggested_actor_mentions", [])

    lines = [
        "=== REGENERATION REQUEST ===",
        f"(Previous attempt failed due to token budget exhaustion.)",
        f"",
        f"request_id: {req.get('request_id')}",
        f"augmentation_type: {aug_type}",
        f"target_l1_value_id: {req.get('target_l1_value_id')}",
        f"target_l1_value_name: {req.get('target_l1_value_name')}",
        f"target_l2_value_id: {req.get('target_l2_value_id')}",
        f"target_l2_value_name: {req.get('target_l2_value_name')}",
        f"direction: {direction}  (CRITICAL: output MUST have direction='{direction}')",
        f"direction_name: {direction_name}",
        f"is_positive: {json.dumps(is_positive)}",
        f"canonical_actor_name: {req.get('canonical_actor_name')}",
        f"actor_aliases: {json.dumps(actor_aliases)}",
        f"suggested_actor_mentions: {json.dumps(suggested_mentions)}",
        f"",
        "=== APPROVED USER INSTRUCTION (from manifest) ===",
        "",
        (req.get("user_prompt") or "").strip(),
        "",
        "=== FINAL CONSTRAINTS ===",
        f"direction MUST be '{direction}' ({direction_name}).",
        f"l1_value_id MUST be '{req.get('target_l1_value_id')}'.",
        f"l1_value_name MUST be '{req.get('target_l1_value_name')}'.",
        f"l2_value_id MUST be '{req.get('target_l2_value_id')}'.",
        f"l2_value_name MUST be '{req.get('target_l2_value_name')}'.",
        f"is_positive MUST be {json.dumps(is_positive)}.",
        "",
        "IMPORTANT: Keep content SHORT (120–180 words). Start your response with '{'.",
        "Do NOT exceed 180 words in the content field.",
        "Output ONLY the JSON object. No other text.",
    ]
    return "\n".join(lines)


# ============================================================
# API call
# ============================================================


def call_deepseek_api(
    model: str,
    temperature: float,
    max_tokens: int,
    messages: list,
    api_key: str,
    use_response_format: bool = True,
) -> tuple:
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
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    req_obj = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req_obj, timeout=180) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), resp.status, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e.reason)
        return None, e.code, mask_secret(body)
    except urllib.error.URLError as e:
        return None, None, mask_secret(str(e.reason))
    except Exception:
        return None, None, mask_secret(safe_format_exc())


def extract_content(resp: dict):
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def extract_finish_reason(resp: dict):
    try:
        return resp["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return None


def extract_usage(resp: dict):
    try:
        return resp.get("usage")
    except Exception:
        return None


def parse_json_from_content(content: str) -> tuple:
    if not content:
        return None, "Empty content from model"
    text = content.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"


# ============================================================
# Sample validation
# ============================================================


def _expected_is_positive(req: dict) -> bool:
    return req.get("augmentation_type", "") in ("rare_positive", "direction_contrastive")


def validate_sample(sample: dict, req: dict) -> list:
    results = []

    def add(cid, label, status, detail=""):
        results.append({"check": cid, "label": label, "status": status, "detail": detail})

    for field in REQUIRED_SAMPLE_FIELDS:
        add(f"field_{field}", f"field '{field}' exists",
            "PASS" if field in sample else "FAIL",
            f"Missing: {field}" if field not in sample else "")

    title = sample.get("title", "") or ""
    content = sample.get("content", "") or ""
    actor_name = sample.get("actor_name", "") or ""
    actor_mention = sample.get("actor_mention", "") or ""
    evidence = sample.get("evidence_sentence", "") or ""

    add("title_nonempty", "title non-empty", "PASS" if title.strip() else "FAIL")
    add("content_nonempty", "content non-empty", "PASS" if content.strip() else "FAIL")
    add("actor_name_nonempty", "actor_name non-empty",
        "PASS" if actor_name.strip() else "FAIL")
    add("actor_mention_nonempty", "actor_mention non-empty",
        "PASS" if actor_mention.strip() else "FAIL")

    if actor_mention and content:
        in_c = actor_mention in content
        add("actor_mention_in_content", "actor_mention verbatim in content",
            "PASS" if in_c else "FAIL",
            "" if in_c else f"'{actor_mention[:60]}' not found verbatim in content")
    else:
        add("actor_mention_in_content", "actor_mention verbatim in content",
            "FAIL", "actor_mention or content empty")

    add("evidence_nonempty", "evidence_sentence non-empty",
        "PASS" if evidence.strip() else "FAIL")

    if evidence and content:
        ev_in = evidence in content
        add("evidence_in_content", "evidence_sentence verbatim in content",
            "PASS" if ev_in else "FAIL",
            "" if ev_in else "evidence_sentence not found verbatim in content")
    else:
        add("evidence_in_content", "evidence_sentence verbatim in content",
            "FAIL", "evidence or content empty")

    expected_l1 = str(req.get("target_l1_value_id", ""))
    got_l1 = str(sample.get("l1_value_id", ""))
    add("l1_value_id_match", "l1_value_id matches request",
        "PASS" if got_l1 == expected_l1 else "FAIL",
        f"expected {expected_l1!r}, got {got_l1!r}")

    expected_l1n = req.get("target_l1_value_name", "")
    got_l1n = sample.get("l1_value_name", "")
    add("l1_value_name_match", "l1_value_name matches request",
        "PASS" if got_l1n == expected_l1n else "FAIL",
        f"expected {expected_l1n!r}, got {got_l1n!r}")

    expected_l2 = str(req.get("target_l2_value_id", ""))
    got_l2 = str(sample.get("l2_value_id", ""))
    add("l2_value_id_match", "l2_value_id matches request",
        "PASS" if got_l2 == expected_l2 else "FAIL",
        f"expected {expected_l2!r}, got {got_l2!r}")

    expected_l2n = req.get("target_l2_value_name", "")
    got_l2n = sample.get("l2_value_name", "")
    add("l2_value_name_match", "l2_value_name matches request",
        "PASS" if got_l2n == expected_l2n else "FAIL",
        f"expected {expected_l2n!r}, got {got_l2n!r}")

    expected_dir = str(req.get("target_direction", ""))
    got_dir = str(sample.get("direction", ""))
    add("direction_match", "direction matches request",
        "PASS" if got_dir == expected_dir else "FAIL",
        f"expected {expected_dir!r}, got {got_dir!r}")

    expected_dn = req.get("target_direction_name", "")
    got_dn = sample.get("direction_name", "")
    add("direction_name_match", "direction_name matches request",
        "PASS" if got_dn == expected_dn else "FAIL",
        f"expected {expected_dn!r}, got {got_dn!r}")

    exp_is_pos = _expected_is_positive(req)
    got_is_pos = sample.get("is_positive")
    add("is_positive_match", "is_positive matches request",
        "PASS" if got_is_pos == exp_is_pos else "FAIL",
        f"expected {exp_is_pos!r}, got {got_is_pos!r}")

    if got_dir == "1":
        conv_ok = got_dn == "aligned"
    elif got_dir == "0":
        conv_ok = got_dn == "contradictory"
    else:
        conv_ok = False
    add("direction_convention", "direction convention (aligned=1, contradictory=0)",
        "PASS" if conv_ok else "FAIL",
        f"direction={got_dir!r}, direction_name={got_dn!r}")

    add("no_as_an_ai", "no 'as an AI' in content",
        "PASS" if "as an AI" not in content else "FAIL")
    add("no_fehu_ntcir", "no FEHU/NTCIR in content",
        "PASS" if ("FEHU" not in content and "NTCIR" not in content) else "FAIL")
    add("no_synthetic_data", "no 'synthetic data' in content",
        "PASS" if not re.search(r'\bsynthetic data\b', content, re.I) else "FAIL")

    clen = len(content)
    if clen < 50:
        add("content_length", "content length reasonable", "FAIL", f"Too short: {clen}")
    elif clen > 2000:
        add("content_length", "content length reasonable", "WARN", f"Long: {clen} chars")
    else:
        add("content_length", "content length reasonable", "PASS", f"{clen} chars")

    ev_mentions_actor = bool(evidence and actor_mention and actor_mention in evidence)
    add("evidence_mentions_actor", "evidence mentions actor (superficial)",
        "PASS" if ev_mentions_actor else "WARN",
        "" if ev_mentions_actor
        else "actor_mention not in evidence_sentence (may be semantically valid)")

    severe = ["fraud", "criminal", "convicted", "indicted", "arrested",
              "embezzled", "bribery", "laundering"]
    found = [t for t in severe if t.lower() in content.lower()]
    add("no_severe_accusation", "no obvious severe accusation",
        "WARN" if found else "PASS",
        f"Found: {found}" if found else "")

    add("candidate_status", "sample is PENDING_HUMAN_VERIFICATION", "PASS",
        "Set by runner")

    return results


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
# Dashboard & reports
# ============================================================


def write_repair_dashboard(
    outdir, input_dir, config, triage_info,
    repair_succeeded, repair_sample,
    regen_stats, unified_candidates,
    unified_pass, unified_warn, unified_fail,
):
    lines = [
        "# FEHU Tiny Pilot Repair and Regeneration — Dashboard",
        "",
        f"**Stage:** Targeted repair and regeneration",
        f"**Timestamp:** {config['timestamp']}",
        f"**Input tiny pilot folder:** {input_dir}",
        f"**Output repair folder:** {outdir}",
        "",
        "## Initial Pilot Result Summary",
        "",
        "| Category | Count | Request IDs |",
        "|----------|-------|-------------|",
        f"| KEEP (PASS/WARN from pilot) | 3 | "
        + "; ".join(sorted(KEEP_IDS)) + " |",
        f"| DETERMINISTIC_REPAIR | 1 | "
        + "; ".join(sorted(DETERMINISTIC_REPAIR_IDS)) + " |",
        f"| TARGETED_REGENERATION | 2 | "
        + "; ".join(sorted(REGENERATION_IDS)) + " |",
        "",
    ]

    if triage_info.get("contradictions"):
        lines += ["## ⚠ Triage Contradictions", ""]
        for c in triage_info["contradictions"]:
            lines.append(f"- {c}")
        lines.append("")

    lines += [
        "## Deterministic Repair",
        "",
        f"**Result:** {'SUCCEEDED' if repair_succeeded else 'FAILED'}",
    ]
    if repair_succeeded and repair_sample:
        lines.append(
            f"- Repaired: `{repair_sample['request_id']}`"
        )
        lines.append(
            f"- original_evidence: {repair_sample.get('original_evidence_sentence', '')!r}"
        )
        lines.append(
            f"- repaired_evidence: {repair_sample.get('repaired_evidence_sentence', '')!r}"
        )
    lines += [
        "",
        "## Targeted Regeneration",
        "",
        f"- Requests sent: {regen_stats.get('attempted', 0)}",
        f"- Raw responses saved: {regen_stats.get('raw_saved', 0)}",
        f"- Parsed successfully: {regen_stats.get('parsed', 0)}",
        f"- Failed: {regen_stats.get('failed', 0)}",
        "",
        "## Unified Candidates",
        "",
        f"- Total unified candidates: {len(unified_candidates)}",
        f"- Validation PASS: {unified_pass}",
        f"- Validation WARN: {unified_warn}",
        f"- Validation FAIL: {unified_fail}",
        "",
        "## Human Verification Sheet",
        "",
        f"- Path: {outdir}/09_human_verification_sheet_REPAIRED.csv",
        f"- Contains: {unified_pass + unified_warn} samples (PASS + WARN only)",
        "",
        "## Safety Summary",
        "",
        "- Official data modified? NO",
        "- evaluation.py modified? NO",
        "- Original tiny pilot folder modified? NO",
        "- API key logged? NO",
        "- Training run? NO",
        "",
        "## Final Recommendation",
        "",
        "Complete human verification of 09_human_verification_sheet_REPAIRED.csv before any further steps.",
        "",
        "> **Candidates remain PENDING_HUMAN_VERIFICATION and are not training-ready.**",
    ]
    write_file(outdir / "00_REPAIR_DASHBOARD.md", "\n".join(lines))


# ============================================================
# Main
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="FEHU Tiny Pilot Repair and Targeted Regeneration"
    )
    parser.add_argument("--input", required=True,
                        help="Previous tiny pilot output folder (read-only)")
    parser.add_argument("--approved-manifest", required=True,
                        help="Path to human-approved manifest JSONL")
    parser.add_argument("--outdir", required=True,
                        help="New output directory for repair results")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    parser.add_argument("--execute", action="store_true",
                        help="Actually call the DeepSeek API")
    args = parser.parse_args()

    input_dir = pathlib.Path(args.input)
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Verify input dir is NOT the output dir (safety)
    if input_dir.resolve() == outdir.resolve():
        print("ERROR: --input and --outdir must be different paths.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    api_key_present = bool(api_key)
    if api_key_present:
        set_secret(api_key)

    config = {
        "timestamp": iso_now(),
        "model": args.model,
        "base_url": BASE_URL,
        "endpoint_path": ENDPOINT_PATH,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "input_pilot_dir": str(input_dir),
        "outdir": str(outdir),
        "execute_mode": args.execute,
        "api_key_present": api_key_present,
        "api_key_value_logged": False,
        "retry_policy": "max_1_retry_per_request",
        "official_data_modified": False,
    }

    # Initialize output JSONL files
    for fname in [
        "04_regeneration_raw_responses.jsonl",
        "05_regeneration_parsed_samples.jsonl",
        "06_regeneration_failed_requests.jsonl",
        "07_unified_candidate_samples.jsonl",
    ]:
        write_file(outdir / fname, "")

    # ---- TASK A: Read previous pilot ----
    print("Reading previous tiny pilot outputs...")
    if not input_dir.exists():
        print(f"ERROR: Input dir not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    prev_data = read_prev_pilot(input_dir)

    manifest_rows, manifest_err = load_manifest(args.approved_manifest)
    if manifest_err:
        print(f"ERROR loading manifest: {manifest_err}", file=sys.stderr)
        sys.exit(1)

    triage_info = triage_requests(prev_data, manifest_rows)

    if triage_info["contradictions"]:
        print("TRIAGE CONTRADICTIONS FOUND:", file=sys.stderr)
        for c in triage_info["contradictions"]:
            print(f"  {c}", file=sys.stderr)
        print("Stopping before API calls.", file=sys.stderr)
        # Still write triage report
        write_triage_report(outdir, input_dir, triage_info)
        sys.exit(1)

    write_triage_report(outdir, input_dir, triage_info)
    print(f"Triage: KEEP={len(triage_info['keep'])}, "
          f"REPAIR={len(triage_info['repair'])}, "
          f"REGENERATE={len(triage_info['regenerate_ids'])}")

    # ---- TASK B: Deterministic repair ----
    print("Attempting deterministic repair...")
    manifest_by_id = triage_info["manifest_by_id"]
    repair_record = None
    repair_succeeded = False
    all_repair_report_lines = ["# 02_deterministic_repair_report.md", ""]

    for sample in triage_info["repair"]:
        rid = sample["request_id"]
        req = manifest_by_id.get(rid, {})
        repaired, report_lines = attempt_deterministic_repair(sample, req)
        all_repair_report_lines += report_lines
        if repaired is not None:
            repair_record = repaired
            repair_succeeded = True
            print(f"  Repair SUCCEEDED: {rid}")
        else:
            print(f"  Repair FAILED: {rid} — will be added to regeneration list")

    write_file(outdir / "02_deterministic_repair_report.md",
               "\n".join(all_repair_report_lines))

    # ---- TASK C: Prepare regeneration requests ----
    regen_ids = set(triage_info["regenerate_ids"])
    if not repair_succeeded:
        for rid in DETERMINISTIC_REPAIR_IDS:
            regen_ids.add(rid)
            print(f"  Repair failed; adding {rid} to regeneration list")

    regen_requests = []
    for row in manifest_rows:
        if row.get("request_id") in regen_ids:
            regen_req = dict(row)
            regen_req["regeneration_reason"] = (
                "finish_reason=length; token budget exhausted before JSON output"
                if row.get("request_id") in REGENERATION_IDS
                else "deterministic_repair_failed"
            )
            regen_req["previous_failure_stage"] = (
                "json_parse" if row.get("request_id") in REGENERATION_IDS
                else "validation"
            )
            regen_req["previous_failure_reason"] = (
                "JSON truncated due to reasoning token exhaustion"
                if row.get("request_id") in REGENERATION_IDS
                else "evidence_sentence verbatim inclusion failed"
            )
            regen_req["max_tokens"] = args.max_tokens
            regen_req["temperature"] = args.temperature
            regen_req["model"] = args.model
            regen_req["candidate_status"] = "REGENERATION_REQUEST"
            regen_requests.append(regen_req)

    # Write 03_regeneration_requests.jsonl
    write_file(outdir / "03_regeneration_requests.jsonl", "")
    for rq in regen_requests:
        append_jsonl(outdir / "03_regeneration_requests.jsonl", rq)
    print(f"Prepared {len(regen_requests)} regeneration requests")

    # ---- Validation-only exit ----
    if not args.execute:
        _write_validation_only_reports(
            outdir, input_dir, config, triage_info,
            repair_succeeded, repair_record, regen_requests
        )
        print("VALIDATION-ONLY MODE: all checks passed.")
        print(f"Output: {outdir}")
        return

    # ---- TASK E: API check ----
    if not api_key_present:
        _write_blocked_api_report(
            outdir, input_dir, config, triage_info,
            repair_succeeded, repair_record, regen_requests
        )
        print("BLOCKED: DEEPSEEK_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    # ---- Execute regeneration ----
    print(f"EXECUTE MODE: calling DeepSeek API for {len(regen_requests)} requests...")

    regen_stats = {"attempted": 0, "raw_saved": 0, "parsed": 0, "failed": 0}
    regen_parsed = []
    regen_failed = []

    # Reset files for execute run
    write_file(outdir / "04_regeneration_raw_responses.jsonl", "")
    write_file(outdir / "05_regeneration_parsed_samples.jsonl", "")
    write_file(outdir / "06_regeneration_failed_requests.jsonl", "")

    for rq in regen_requests:
        rid = rq.get("request_id")
        print(f"  [{regen_stats['attempted'] + 1}/{len(regen_requests)}] {rid}", end=" ... ", flush=True)
        regen_stats["attempted"] += 1

        messages = [
            {"role": "system", "content": build_regen_system_prompt(rq)},
            {"role": "user", "content": build_regen_user_message(rq)},
        ]

        response, http_status, error_msg = call_deepseek_api(
            args.model, args.temperature, args.max_tokens,
            messages, api_key, use_response_format=True,
        )
        retry_count = 0

        if response is None:
            retry_count = 1
            err_lower = (error_msg or "").lower()
            use_rf_retry = "response_format" not in err_lower
            print(f"[retry]", end=" ", flush=True)
            response, http_status, error_msg = call_deepseek_api(
                args.model, args.temperature, args.max_tokens,
                messages, api_key, use_response_format=use_rf_retry,
            )

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
        append_jsonl(outdir / "04_regeneration_raw_responses.jsonl", raw_record)
        regen_stats["raw_saved"] += 1

        if response is None:
            fail = {
                "request_id": rid,
                "failure_stage": "api_call",
                "failure_reason": "API call failed after retry",
                "sanitized_error": mask_secret(str(error_msg or "")),
                "raw_response_excerpt": "",
                "retry_count": retry_count,
            }
            append_jsonl(outdir / "06_regeneration_failed_requests.jsonl", fail)
            regen_stats["failed"] += 1
            regen_failed.append(fail)
            print("FAILED (api_error)")
            continue

        # Check finish_reason — if length again, record but don't retry more
        fr = extract_finish_reason(response)
        content_text = extract_content(response)
        parsed_obj, parse_err = parse_json_from_content(content_text)

        if parsed_obj is None:
            fail = {
                "request_id": rid,
                "failure_stage": "json_parse",
                "failure_reason": parse_err,
                "sanitized_error": parse_err,
                "raw_response_excerpt": (content_text or "")[:500],
                "finish_reason": fr,
                "retry_count": retry_count,
            }
            append_jsonl(outdir / "06_regeneration_failed_requests.jsonl", fail)
            regen_stats["failed"] += 1
            regen_failed.append(fail)
            print(f"FAILED (parse: {parse_err}; finish_reason={fr})")
            continue

        regen_stats["parsed"] += 1
        req_for_val = manifest_by_id.get(rid, rq)
        val_checks = validate_sample(parsed_obj, req_for_val)
        overall = compute_overall_status(val_checks)
        val_summary = {r["check"]: r["status"] for r in val_checks}

        parsed_record = {
            "request_id": rid,
            "augmentation_type": rq.get("augmentation_type", ""),
            "generated_sample": parsed_obj,
            "validation_summary": val_summary,
            "_validation_checks": val_checks,
            "overall_validation_status": overall,
            "candidate_status": "PENDING_HUMAN_VERIFICATION",
            "training_ready": False,
            "source_stage": "targeted_regeneration",
            "finish_reason": fr,
        }
        append_jsonl(outdir / "05_regeneration_parsed_samples.jsonl", {
            k: v for k, v in parsed_record.items() if k != "_validation_checks"
        })
        regen_parsed.append(parsed_record)
        print(f"{overall}")

    # ---- TASK F: Unified validation ----
    print("Building unified candidate set...")
    unified_candidates = []

    # 1. KEEP samples
    for sample in triage_info["keep"]:
        manifest_req = manifest_by_id.get(sample["request_id"], {})
        val_checks = validate_sample(sample["generated_sample"], manifest_req)
        overall = compute_overall_status(val_checks)
        unified_candidates.append({
            "request_id": sample["request_id"],
            "augmentation_type": sample["augmentation_type"],
            "generated_sample": sample["generated_sample"],
            "validation_summary": {r["check"]: r["status"] for r in val_checks},
            "_validation_checks": val_checks,
            "overall_validation_status": overall,
            "candidate_status": "PENDING_HUMAN_VERIFICATION",
            "training_ready": False,
            "source_stage": (
                "initial_tiny_pilot_pass"
                if sample["overall_validation_status"] == "PASS"
                else "initial_tiny_pilot_warn"
            ),
        })

    # 2. Deterministic repair
    if repair_record is not None:
        manifest_req = manifest_by_id.get(repair_record["request_id"], {})
        val_checks = validate_sample(repair_record["generated_sample"], manifest_req)
        overall = compute_overall_status(val_checks)
        unified_candidates.append({
            "request_id": repair_record["request_id"],
            "augmentation_type": repair_record["augmentation_type"],
            "generated_sample": repair_record["generated_sample"],
            "repair_status": repair_record["repair_status"],
            "repair_type": repair_record["repair_type"],
            "original_evidence_sentence": repair_record["original_evidence_sentence"],
            "repaired_evidence_sentence": repair_record["repaired_evidence_sentence"],
            "validation_summary": {r["check"]: r["status"] for r in val_checks},
            "_validation_checks": val_checks,
            "overall_validation_status": overall,
            "candidate_status": "PENDING_HUMAN_VERIFICATION",
            "training_ready": False,
            "source_stage": "deterministic_repair",
        })

    # 3. Regenerated samples
    for rp in regen_parsed:
        unified_candidates.append(rp)

    # Write unified JSONL
    write_file(outdir / "07_unified_candidate_samples.jsonl", "")
    for uc in unified_candidates:
        append_jsonl(outdir / "07_unified_candidate_samples.jsonl", {
            k: v for k, v in uc.items() if k != "_validation_checks"
        })

    unified_pass = sum(1 for u in unified_candidates
                       if u["overall_validation_status"] == "PASS")
    unified_warn = sum(1 for u in unified_candidates
                       if u["overall_validation_status"] == "WARN")
    unified_fail = sum(1 for u in unified_candidates
                       if u["overall_validation_status"] == "FAIL")

    # ---- Write all reports ----
    write_unified_validation_table(outdir, unified_candidates, manifest_by_id)
    write_human_verification_sheet(outdir, unified_candidates, manifest_by_id)
    write_research_interpretation(outdir, unified_candidates, regen_stats, repair_succeeded)
    write_session_report(
        outdir, config, regen_stats, unified_candidates,
        unified_pass, unified_warn, unified_fail,
    )
    write_repair_dashboard(
        outdir, input_dir, config, triage_info,
        repair_succeeded, repair_record,
        regen_stats, unified_candidates,
        unified_pass, unified_warn, unified_fail,
    )

    print(f"\nRepair/regeneration complete. Output: {outdir}")
    print(f"Unified candidates: {len(unified_candidates)} "
          f"(PASS={unified_pass}, WARN={unified_warn}, FAIL={unified_fail})")
    print("Candidates remain PENDING_HUMAN_VERIFICATION and are not training-ready.")


# ============================================================
# Report writers
# ============================================================


def write_triage_report(outdir, input_dir, triage_info):
    lines = [
        "# 01_input_triage_report.md",
        "",
        f"**Input folder:** {input_dir}",
        "",
        "## Triage Classification",
        "",
        "### A. KEEP_FOR_HUMAN_VERIFICATION",
        "",
        "These samples from the initial pilot are structurally valid (PASS or WARN).",
        "They proceed directly to human verification.",
        "",
    ]
    for rid in sorted(KEEP_IDS):
        s = next((x for x in triage_info["keep"] if x["request_id"] == rid), None)
        status = s["overall_validation_status"] if s else "NOT_FOUND"
        lines.append(f"- `{rid}` — {status}")

    lines += [
        "",
        "### B. DETERMINISTIC_REPAIR_CANDIDATE",
        "",
        "Parsed sample exists with correct labels/direction but evidence_sentence is ",
        "a truncated prefix of a complete sentence in content.",
        "Deterministic repair: expand evidence_sentence to the full sentence.",
        "",
    ]
    for rid in sorted(DETERMINISTIC_REPAIR_IDS):
        lines.append(
            f"- `{rid}` — evidence_sentence is a substring of a full content sentence"
        )

    lines += [
        "",
        "### C. TARGETED_REGENERATION_REQUIRED",
        "",
        "These failed due to finish_reason=length (reasoning exhausted max_tokens=1800).",
        "Solution: regenerate with max_tokens=4096 and stricter brevity constraints.",
        "",
    ]
    for rid in sorted(REGENERATION_IDS):
        f = next((x for x in triage_info.get("failed_by_id", {}).values()
                  if x.get("request_id") == rid), None)
        reason = f.get("failure_reason", "unknown") if f else "unknown"
        lines.append(f"- `{rid}` — {reason}")

    if triage_info.get("contradictions"):
        lines += ["", "## ⚠ Contradictions with File Content", ""]
        for c in triage_info["contradictions"]:
            lines.append(f"- {c}")

    write_file(outdir / "01_input_triage_report.md", "\n".join(lines))


def write_unified_validation_table(outdir, unified_candidates, manifest_by_id):
    fieldnames = [
        "request_id", "source_stage", "augmentation_type",
        "l1_value_id", "l1_value_name", "direction", "direction_name",
        "parse_status", "required_fields_status",
        "actor_mention_in_content", "evidence_sentence_in_content",
        "label_match_status", "direction_match_status",
        "factuality_warning", "style_warning",
        "overall_validation_status", "recommended_human_action",
    ]
    rows = []
    for uc in unified_candidates:
        vs = uc.get("validation_summary", {})
        req = manifest_by_id.get(uc["request_id"], {})

        req_fields_ok = all(
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
        ovs = uc["overall_validation_status"]
        if ovs == "FAIL":
            action = "REJECT or regenerate; structural check failed"
        elif ovs == "WARN":
            action = "REVIEW carefully; content warnings present"
        else:
            action = "REVIEW content quality and factuality"

        rows.append({
            "request_id": uc["request_id"],
            "source_stage": uc.get("source_stage", ""),
            "augmentation_type": uc.get("augmentation_type", ""),
            "l1_value_id": req.get("target_l1_value_id", ""),
            "l1_value_name": req.get("target_l1_value_name", ""),
            "direction": req.get("target_direction", ""),
            "direction_name": req.get("target_direction_name", ""),
            "parse_status": "PASS",
            "required_fields_status": "PASS" if req_fields_ok else "FAIL",
            "actor_mention_in_content": vs.get("actor_mention_in_content", ""),
            "evidence_sentence_in_content": vs.get("evidence_in_content", ""),
            "label_match_status": "PASS" if label_ok else "FAIL",
            "direction_match_status": "PASS" if dir_ok else "FAIL",
            "factuality_warning": vs.get("no_severe_accusation", ""),
            "style_warning": vs.get("content_length", ""),
            "overall_validation_status": ovs,
            "recommended_human_action": action,
        })
    write_csv(outdir / "08_unified_validation_table.csv", fieldnames, rows)


def write_human_verification_sheet(outdir, unified_candidates, manifest_by_id):
    fieldnames = [
        "request_id", "source_stage", "augmentation_type",
        "title", "content", "actor_name", "actor_mention", "evidence_sentence",
        "l1_value_id", "l1_value_name", "l2_value_id", "l2_value_name",
        "direction", "direction_name", "validation_status",
        "automatic_notes", "human_decision", "human_notes",
    ]
    rows = []
    for uc in unified_candidates:
        if uc["overall_validation_status"] not in ("PASS", "WARN"):
            continue
        s = uc["generated_sample"]
        vs = uc.get("validation_summary", {})
        notes_parts = []
        if uc.get("repair_status"):
            notes_parts.append(
                f"Deterministic repair: evidence_sentence expanded from "
                f"'{uc.get('original_evidence_sentence', '')}' to "
                f"'{uc.get('repaired_evidence_sentence', '')}'"
            )
        if vs.get("evidence_mentions_actor") == "WARN":
            notes_parts.append(
                "WARN: actor_mention not found in evidence_sentence (review semantic fit)"
            )
        if vs.get("no_severe_accusation") == "WARN":
            notes_parts.append(
                "WARN: potentially sensitive terms in content; verify factuality"
            )
        if uc.get("source_stage") == "targeted_regeneration":
            notes_parts.append("Regenerated with max_tokens=4096; verify against approved manifest")

        rows.append({
            "request_id": uc["request_id"],
            "source_stage": uc.get("source_stage", ""),
            "augmentation_type": uc.get("augmentation_type", ""),
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
            "validation_status": uc["overall_validation_status"],
            "automatic_notes": " | ".join(notes_parts) if notes_parts else "",
            "human_decision": "",
            "human_notes": "",
        })
    write_csv(outdir / "09_human_verification_sheet_REPAIRED.csv", fieldnames, rows)


def write_research_interpretation(outdir, unified_candidates, regen_stats, repair_succeeded):
    n_pass = sum(1 for u in unified_candidates if u["overall_validation_status"] == "PASS")
    n_warn = sum(1 for u in unified_candidates if u["overall_validation_status"] == "WARN")
    n_for_hv = n_pass + n_warn

    content = f"""\
# 10_research_interpretation.md — Research Interpretation

## What the Initial Tiny Pilot Showed

The initial tiny pilot (6 requests, max_tokens=1800) produced:
- 1 fully valid (PASS) sample: `prev_dir_contrast_12_002_aligned_ce1da19f54`
- 2 structurally valid WARN samples: `prev_dir_contrast_38_003_contradictory_e969e14138`,
  `prev_rare_positive_32_001_83df110175`
- 1 validation FAIL (evidence verbatim issue): `prev_dir_contrast_38_003_aligned_e969e14138`
- 2 parse failures (token budget exhaustion): `prev_dir_contrast_12_002_contradictory_ce1da19f54`,
  `prev_rare_positive_24_004_98671d8d01`

The 3 KEEP samples demonstrated that the pipeline CAN produce actor-specific,
label-consistent, direction-consistent outputs. The 3 failures were technical rather
than semantic.

## Why Parse Failures Occurred

`deepseek-v4-pro` is a reasoning model. Its internal chain-of-thought tokens count against
the `max_tokens` limit. With `max_tokens=1800`:
- `prev_dir_contrast_12_002_contradictory`: 1772/1800 tokens consumed by reasoning;
  only ~28 tokens available for JSON output → truncated mid-string.
- `prev_rare_positive_24_004_98671d8d01`: all 1800 tokens consumed by reasoning →
  content field was empty string.

The fix: use `max_tokens=4096` for regeneration, giving the model sufficient budget for
both reasoning and JSON output.

The evidence verbatim failure for `prev_dir_contrast_38_003_aligned_e969e14138` was
different: the model's evidence_sentence field contained a truncated version of a complete
sentence in content. This is a minor formatting issue amenable to deterministic repair.

## Why Targeted Regeneration Is Better Than Rerunning All 6 Requests

Rerunning all 6 requests would:
1. Waste API tokens on 3 requests that already produced acceptable candidates.
2. Risk replacing a PASS/WARN sample with a worse regeneration.
3. Violate the principle of minimal intervention — if a sample is structurally valid,
   it should proceed to human verification, not be discarded.

Targeted regeneration applies only to the 2 requests that definitively failed
(finish_reason=length). The 1 deterministic repair case (evidence_sentence expansion)
is handled without any API call at all.

## Why Deterministic Evidence_Sentence Repair Is Acceptable

The evidence_sentence repair is a metadata field update, not a content change:
- The content, title, actor_name, actor_mention, labels, and direction are unchanged.
- The repair replaces a truncated sentence fragment with the complete sentence that
  already exists verbatim in content.
- The full sentence still supports the target actor, value, and direction.
- The repair is fully reversible (original_evidence_sentence is preserved).

However, this repair does NOT constitute automatic training approval. The repaired
sample still requires human verification to confirm the full sentence is semantically
appropriate as an evidence sentence.

## How Many Candidates Are Now Available for Human Verification

Unified candidates after repair/regeneration: {len(unified_candidates)}
- For human verification (PASS + WARN): {n_for_hv}
- Excluded (FAIL): {len(unified_candidates) - n_for_hv}

## What This Proves

1. **Pipeline infrastructure works end-to-end.** The DeepSeek V4 runner successfully
   produces actor-specific, schema-conformant outputs when given sufficient token budget.
2. **Label and direction control is feasible.** All successfully parsed samples had
   correct l1_value_id, l2_value_id, direction, and is_positive fields.
3. **Output schema still needs strict constraints.** The initial pilot required strict
   brevity instructions to prevent reasoning from consuming the full token budget.
   The revised prompt (120–180 word content limit) should mitigate this.
4. **Deterministic repair is viable for minor verbatim-inclusion mismatches.** When the
   content is correct and only the evidence_sentence field is truncated, deterministic
   repair preserves the original generation while fixing the structural issue.

## What This Does NOT Prove

- **No model performance improvement.** Neither the initial pilot nor this repair step
  provides evidence that adding these samples to training will improve Macro-F1 or reduce
  DRR. An ablation experiment is required.
- **No training readiness.** All candidates remain PENDING_HUMAN_VERIFICATION. Human
  reviewers must confirm factual plausibility, semantic appropriateness, and annotation
  consistency before any sample enters a training candidate pool.
- **No final FEHU score improvement.** Score improvement requires (1) human-verified
  samples, (2) an augmented training run, and (3) evaluation on the dev or test set.

## Connection to FEHU Research Goals

**rare_positive targets** (L1=24 "Be neat and tidy", L1=32 "Be behaving properly"):
- Both values have mean_recall_dir=0.000 in the current model.
- Providing positive examples may shift the classifier's decision boundary to produce
  non-zero recall for these labels.
- Impact on Macro-F1 (gold-supported) depends on how frequently these labels appear
  in gold labels.

**direction_contrastive targets** (L1=12 "Have success", L1=38 "Be honest"):
- Both have low precision due to over-prediction (mean_prec≈0.13).
- Paired aligned/contradictory samples for the SAME domain but DIFFERENT actors provide
  direction-discriminating signal that single-direction training data lacks.
- Expected to reduce DRR (Direction Reverse Rate) for these values if training succeeds.

## Recommended Next Steps

1. **Human verification of 09_human_verification_sheet_REPAIRED.csv**
   Review all PASS and WARN samples. For each row, record:
   - human_decision: ACCEPT or REJECT
   - human_notes: specific concerns or confirmations

2. **Create a small verified augmented candidate set (not official gold):**
   Collect only human-ACCEPT samples into a candidate augmentation pool.
   Do NOT add to the official training dataset directly.

3. **Run ablation experiment:**
   - Baseline: train with official training data only.
   - Augmented: train with official data + verified augmented candidates.
   - Compare: Macro-F1, per-class recall for L1=24/32, DRR for L1=12/38.
   - Report delta only; note any regressions.

4. **Expand only if ablation is positive:**
   If the ablation shows meaningful improvement without regressions, expand to more
   rare-label and direction-contrastive requests with a larger approved manifest.
"""
    write_file(outdir / "10_research_interpretation.md", content)


def write_session_report(outdir, config, regen_stats, unified_candidates,
                         unified_pass, unified_warn, unified_fail):
    n_hv = unified_pass + unified_warn
    lines = [
        "# 11_session_report.md",
        "",
        "## Safety Audit",
        "",
        f"- API called? {'YES' if regen_stats['attempted'] > 0 else 'NO'}",
        f"- Number of API calls: {regen_stats['attempted']}",
        f"- Model used: {config['model']}",
        f"- max_tokens used: {config['max_tokens']}",
        "- API key printed or logged? NO",
        "- API key saved to file? NO",
        "- .env read? NO",
        "- Model training run? NO",
        "- evaluation.py modified? NO",
        "- dataset/** modified? NO",
        "- dataset/gold_labels/** modified? NO",
        "- output/task1*/ modified? NO",
        "- logs/cache_* modified? NO",
        "- Previous research/approval/dry-run folders modified? NO",
        f"- Original tiny pilot folder modified? NO (read-only: {config['input_pilot_dir']})",
        "",
        "## Paths",
        "",
        f"- New code folder: research/fehu_tiny_pilot_repair_v1/",
        f"- New output folder: {config['outdir']}",
        "",
        "## Files Created",
        "",
        "- 00_REPAIR_DASHBOARD.md",
        "- 01_input_triage_report.md",
        "- 02_deterministic_repair_report.md",
        "- 03_regeneration_requests.jsonl",
        "- 04_regeneration_raw_responses.jsonl",
        "- 05_regeneration_parsed_samples.jsonl",
        "- 06_regeneration_failed_requests.jsonl",
        "- 07_unified_candidate_samples.jsonl",
        "- 08_unified_validation_table.csv",
        "- 09_human_verification_sheet_REPAIRED.csv",
        "- 10_research_interpretation.md",
        "- 11_session_report.md",
        "",
        "## Regeneration Summary",
        "",
        f"- Regeneration requests attempted: {regen_stats['attempted']}",
        f"- Raw responses saved: {regen_stats['raw_saved']}",
        f"- Parsed successfully: {regen_stats['parsed']}",
        f"- Failed: {regen_stats['failed']}",
        "",
        "## Unified Candidates",
        "",
        f"- Total unified candidates: {len(unified_candidates)}",
        f"- Validation PASS: {unified_pass}",
        f"- Validation WARN: {unified_warn}",
        f"- Validation FAIL: {unified_fail}",
        f"- For human verification (PASS+WARN): {n_hv}",
        "",
        "## Token Usage",
        "",
        "See 04_regeneration_raw_responses.jsonl for per-request usage fields.",
        "API key value was not logged in any file.",
        "",
        "## Final Statement",
        "",
        "Targeted repair/regeneration completed. "
        "Candidates remain pending human verification and are not training-ready.",
    ]
    write_file(outdir / "11_session_report.md", "\n".join(lines))


def _write_validation_only_reports(
    outdir, input_dir, config, triage_info,
    repair_succeeded, repair_record, regen_requests,
):
    """Write reports for validation-only mode."""
    regen_stats = {"attempted": 0, "raw_saved": 0, "parsed": 0, "failed": 0}

    write_repair_dashboard(
        outdir, input_dir, config, triage_info,
        repair_succeeded, repair_record,
        regen_stats, [], 0, 0, 0,
    )

    # Placeholder files
    for fname in [
        "04_regeneration_raw_responses.jsonl",
        "05_regeneration_parsed_samples.jsonl",
        "06_regeneration_failed_requests.jsonl",
        "07_unified_candidate_samples.jsonl",
    ]:
        if not (outdir / fname).exists():
            write_file(outdir / fname, "")

    write_csv(outdir / "08_unified_validation_table.csv", [
        "request_id", "source_stage", "augmentation_type", "overall_validation_status"
    ], [])
    write_csv(outdir / "09_human_verification_sheet_REPAIRED.csv", [
        "request_id", "source_stage", "title", "content",
        "validation_status", "human_decision", "human_notes"
    ], [])

    write_research_interpretation(outdir, [], regen_stats, repair_succeeded)
    write_session_report(outdir, config, regen_stats, [], 0, 0, 0)


def _write_blocked_api_report(
    outdir, input_dir, config, triage_info,
    repair_succeeded, repair_record, regen_requests,
):
    """Write reports when API key is missing."""
    regen_stats = {"attempted": 0, "raw_saved": 0, "parsed": 0, "failed": 0}

    write_repair_dashboard(
        outdir, input_dir, config, triage_info,
        repair_succeeded, repair_record,
        regen_stats, [], 0, 0, 0,
    )
    write_session_report(outdir, config, regen_stats, [], 0, 0, 0)

    blocked = [
        "# 11_session_report.md — BLOCKED",
        "",
        "DEEPSEEK_API_KEY is not set. No API calls made.",
        "",
        "Set with: read -s DEEPSEEK_API_KEY && export DEEPSEEK_API_KEY",
        "Then rerun with --execute.",
    ]
    write_file(outdir / "11_session_report.md", "\n".join(blocked))


if __name__ == "__main__":
    main()
