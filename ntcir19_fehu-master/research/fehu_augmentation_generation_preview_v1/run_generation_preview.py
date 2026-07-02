#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research/fehu_augmentation_generation_preview_v1/run_generation_preview.py

Convert an existing FEHU augmentation plan into a set of ready-to-review
**request objects** that future generation scripts would dispatch to an LLM.

⚠ This script never calls an API. Every request object has
   "preview_only": true and "do_not_execute": true so any future runner
   can refuse to forward them directly.

Run from project root:
    python research/fehu_augmentation_generation_preview_v1/run_generation_preview.py \\
        --plan_dir output/research_augmentation_plan/20260614_131524 \\
        --profile tiny_pilot_v1 \\
        --max_total_requests 20
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ============================================================
# PROFILES — quotas per augmentation type
# ============================================================

PROFILES: Dict[str, Dict[str, int]] = {
    # 4 paraphrase + 4 rare_positive + 4 hard_negative + 4 dir-contrastive PAIRS = 20
    # (pair counts as 2 requests, so up to 16-20 requests total)
    "tiny_pilot_v1": {
        "paraphrase":            4,
        "rare_positive":         4,
        "hard_negative":         4,
        "direction_contrastive_pairs": 4,
    },
}

DIRECTION_NAME = {"1": "aligned", "0": "contradictory"}

RECOMMENDED_GENERATOR_PROVIDER = "deepseek"
RECOMMENDED_GENERATOR_MODEL_TIER = (
    "deepseek-v4-pro for tiny pilot; deepseek-v4-flash for larger generation"
)
RECOMMENDED_VERIFIER_MODEL = "deepseek-v4-pro"

# Bump this when prompts / schema change so future runners can detect drift.
PREVIEW_REVISION = 2

# ============================================================
# IO
# ============================================================

def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(p: Path) -> List[Dict]:
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_csv(p: Path) -> List[Dict]:
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(rows: List[Dict], p: Path, fieldnames: Optional[List[str]] = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_jsonl(items: List[Dict], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def safe_float(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def safe_int(s, default=0):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def short_hash(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


# ============================================================
# REVISION-v2 HELPERS
# ============================================================

def smart_truncate(text: str, max_len: int) -> Tuple[str, bool]:
    """
    Truncate `text` to <= max_len characters at the last sentence boundary
    when possible. Returns (truncated_text, was_truncated).

    Strategy:
      1. If `text` is short enough, return unchanged.
      2. Look back from max_len for the last sentence-terminating
         punctuation ('.', '!', '?') followed by whitespace or end-of-string.
      3. If no such boundary exists within the last ~400 chars, fall back to
         the last whitespace and append an ellipsis.
    """
    if not text:
        return "", False
    if len(text) <= max_len:
        return text, False

    cut = text[:max_len]
    best = -1
    for i, ch in enumerate(cut):
        if ch in ".!?":
            nxt = cut[i + 1] if i + 1 < len(cut) else ""
            if nxt == "" or nxt in " \n\r\t":
                best = i

    # Only accept the boundary if it leaves enough content (avoid 5-char cut).
    if best >= max(200, max_len // 3):
        return cut[: best + 1], True

    # Fall back to whitespace boundary.
    sp = cut.rfind(" ")
    if sp > 0:
        return cut[: sp].rstrip() + "…", True
    return cut + "…", True


def derive_actor_mentions(canonical: str) -> Dict[str, Any]:
    """
    Convert a long canonical actor name like

        "Identitarian and Far-Right Activists (including Génération
         Identitaire, youth nationalists, supporters of Marine Le Pen,
         and affiliated online communities)"

    into a short primary mention and a list of natural-sounding aliases the
    LLM may use verbatim inside news prose. Pure string manipulation; no API.

    Returns: {"primary": str, "aliases": [str, ...]}
    """
    if not canonical or not canonical.strip():
        return {"primary": "", "aliases": []}

    s = canonical.strip()
    head = re.split(r"\s*\(", s, maxsplit=1)[0].strip().rstrip(",;:- ")
    if not head:
        head = s[:120]

    aliases: List[str] = []
    seen = {head.lower()}

    # 1. Names enumerated inside parentheses.
    m = re.search(r"\(([^)]*)\)", s)
    if m:
        inside = m.group(1)
        inside = re.sub(
            r"\b(including|such as|like|e\.g\.|i\.e\.)\b", "", inside, flags=re.I
        )
        for part in re.split(r",|\band\b|;", inside, flags=re.I):
            p = re.sub(r"\s+", " ", part).strip(" .,;:-").strip()
            if 2 <= len(p) <= 80 and p.lower() not in seen:
                aliases.append(p)
                seen.add(p.lower())

    # 2. Split head on " and " (e.g. "Police and Emergency Services").
    if re.search(r"\s+and\s+", head, flags=re.I):
        for part in re.split(r"\s+and\s+", head, flags=re.I):
            p = part.strip(" .,;:-").strip()
            if 2 <= len(p) <= 80 and p.lower() not in seen:
                aliases.append(p)
                seen.add(p.lower())

    return {
        "primary": head[:120] if head else canonical[:120],
        "aliases": aliases[:6],
    }


def expected_output_schema(req_type: str) -> Dict[str, str]:
    """
    Strict output schema the LLM must follow. All four request types share
    the same shape, with type-specific constraints documented inline.
    """
    type_note = {
        "paraphrase":
            "paraphrase: is_positive=true; direction MUST match target direction.",
        "rare_positive":
            "rare_positive: is_positive=true; direction MUST match target direction.",
        "hard_negative":
            "hard_negative: is_positive=false; direction MAY be null; "
            "explanation MUST state why target label does NOT apply to the actor.",
        "direction_contrastive":
            "direction_contrastive: is_positive=true; direction MUST match THIS "
            "request's direction; paired_request_id is fixed by metadata.",
    }
    return {
        "title":            "string (≤ 200 chars)",
        "content":          "string (50..1500 chars, news-style)",
        "actor_name":       "string (must equal canonical_actor_name from request metadata)",
        "actor_mention":    "string (the actual surface form used in content; MUST appear verbatim in content; "
                            "may be the canonical name or any provided alias or any other natural mention)",
        "evidence_sentence": "string (verbatim sentence from content that describes the target actor's "
                             "action/stance/decision/behavior and supports the target value+direction; "
                             "for hard_negative, supports the ALTERNATIVE value instead)",
        "explanation":      "string (one sentence: WHY the (actor, value, direction) relationship holds; "
                            "for hard_negative, WHY the target label does NOT apply to the actor)",
        "l1_value_id":      "string ('0'..'53')",
        "l1_value_name":    "string (must match l1_value_id)",
        "l2_value_id":      "string ('0'..'19')",
        "l2_value_name":    "string (must match l2_value_id)",
        "direction":        "'0' | '1' | null  ('1'=aligned, '0'=contradictory; null only for hard_negative)",
        "direction_name":   "'aligned' | 'contradictory' | null  (must match direction)",
        "is_positive":      "boolean",
        "_type_specific_rule": type_note.get(req_type, ""),
    }


# ============================================================
# SELECTION
# ============================================================

def _label_priority(plan_rows: List[Dict]) -> Dict[str, float]:
    """Map l1_id → priority_score from the plan."""
    out = {}
    for r in plan_rows:
        out[r["l1_value_id"]] = safe_float(r.get("priority_score"))
    return out


def select_paraphrase_labels(plan_rows: List[Dict], k: int) -> List[Dict]:
    cands = [r for r in plan_rows
             if "paraphrase" in (r.get("augmentation_types") or "").split("|")
             and r.get("seed_status") == "has_seeds"]
    cands.sort(key=lambda r: -safe_float(r.get("priority_score")))
    return cands[:k]


def select_rare_positive_labels(plan_rows: List[Dict], k: int) -> List[Dict]:
    cands = [r for r in plan_rows
             if "rare_positive" in (r.get("augmentation_types") or "").split("|")]
    cands.sort(key=lambda r: -safe_float(r.get("priority_score")))
    return cands[:k]


def select_hard_negative_labels(plan_rows: List[Dict], k: int) -> List[Dict]:
    cands = [r for r in plan_rows
             if "hard_negative" in (r.get("augmentation_types") or "").split("|")]
    cands.sort(key=lambda r: -safe_float(r.get("priority_score")))
    return cands[:k]


def select_direction_contrastive_labels(plan_rows: List[Dict], k_pairs: int) -> List[Dict]:
    cands = [r for r in plan_rows
             if "direction_contrastive" in (r.get("augmentation_types") or "").split("|")]
    cands.sort(key=lambda r: -safe_float(r.get("priority_score")))
    return cands[:k_pairs]


# ============================================================
# SEED HELPERS
# ============================================================

def seeds_by_label(seed_records: List[Dict]) -> Dict[str, List[Dict]]:
    out: Dict[str, List[Dict]] = defaultdict(list)
    for s in seed_records:
        out[str(s["l1_value_id"])].append(s)
    return out


def pick_seed_for_label(seeds_for_l1: List[Dict], used_ids: set) -> Optional[Dict]:
    """Return the first unused seed for this label (deterministic order)."""
    for s in seeds_for_l1:
        key = (s.get("guid"), s.get("actor_id"), s.get("direction"))
        if key not in used_ids:
            used_ids.add(key)
            return s
    return seeds_for_l1[0] if seeds_for_l1 else None


# ============================================================
# RELATED-LABEL HEURISTIC (for hard_negative)
# ============================================================

# Map L1 → suggested confusable L1 (same L2 family).
def build_confusable_map(label_defs: Dict[str, Dict]) -> Dict[str, Tuple[str, str]]:
    by_l2: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for l1_id, d in label_defs.items():
        by_l2[d["l2_value_id"]].append((l1_id, d["l1_value_name"]))
    out: Dict[str, Tuple[str, str]] = {}
    for l1_id, d in label_defs.items():
        siblings = [(i, n) for (i, n) in by_l2[d["l2_value_id"]] if i != l1_id]
        if siblings:
            out[l1_id] = siblings[0]
    return out


# ============================================================
# REQUEST BUILDERS
# ============================================================

EVIDENCE_REQUIREMENT_RARE_POS = (
    "`evidence_sentence` MUST: (1) appear verbatim in `content`; "
    "(2) describe the TARGET ACTOR's action, stance, decision, or behavior; "
    "(3) make the target L1 value's relationship with the actor the SALIENT one "
    "in that sentence, in the specified direction (aligned/contradictory)."
)
EVIDENCE_REQUIREMENT_PARAPHRASE = (
    "`evidence_sentence` MUST: (1) appear verbatim in the rewritten `content`; "
    "(2) describe the SAME actor's action/stance as the seed; "
    "(3) support the SAME L1 value and the SAME direction as the seed. "
    "Use different wording than the seed's evidence."
)
EVIDENCE_REQUIREMENT_HARD_NEG = (
    "`evidence_sentence` MUST: (1) appear verbatim in `content`; "
    "(2) describe the target actor's action/stance supporting the ALTERNATIVE L1 "
    "value (not the target). `explanation` MUST state explicitly WHY the target "
    "L1 value does NOT apply to this actor, even though the topic appears related."
)
EVIDENCE_REQUIREMENT_DIR_CONTR = (
    "`evidence_sentence` MUST: (1) appear verbatim in `content`; "
    "(2) describe THIS member's actor in the labelled direction; "
    "(3) make the value relationship unambiguous so that flipping the direction "
    "would contradict the article."
)

SAFETY_FOOTER = (
    "\n\n# Safety constraints\n"
    "- Do not copy or reference dev/test article content.\n"
    "- Do not output any final FEHU prediction file (`pred_task1a.json` / `pred_task1b.json`).\n"
    "- Output MUST be a single JSON object that conforms to `expected_output_schema`. "
    "No markdown fences. No commentary outside JSON.\n"
    "- FEHU is multi-label: other values may be present in the article, but **do not "
    "make any other human value more salient than the target value** for the target actor."
)


def _common_metadata(request_id: str,
                     augmentation_type: str,
                     l1_id: str,
                     l1_name: str,
                     l2_id: str,
                     l2_name: str,
                     direction: Optional[str],
                     plan_dir: str) -> Dict:
    return {
        "request_id":                 request_id,
        "preview_only":               True,
        "do_not_execute":             True,
        "preview_revision":           PREVIEW_REVISION,
        "augmentation_type":          augmentation_type,
        "target_l1_value_id":         l1_id,
        "target_l1_value_name":       l1_name,
        "target_l2_value_id":         l2_id,
        "target_l2_value_name":       l2_name,
        "target_direction":           direction,
        "target_direction_name":      DIRECTION_NAME.get(direction) if direction else None,
        "recommended_generator_provider": RECOMMENDED_GENERATOR_PROVIDER,
        "recommended_generator_model":    RECOMMENDED_GENERATOR_MODEL_TIER,
        "recommended_verifier_model":     RECOMMENDED_VERIFIER_MODEL,
        "source_plan_dir":            plan_dir,
        "created_at":                 datetime.now(timezone.utc).isoformat(),
    }


# ── Paraphrase ──────────────────────────────────────────────────────────────

def build_paraphrase_request(idx: int, l1_def: Dict, seed: Dict, plan_dir: str) -> Dict:
    direction = str(seed["direction"])
    rid = f"prev_paraphrase_{l1_def['l1_value_id']}_{idx:03d}_{short_hash(seed['guid'] + seed['actor_id'])}"
    md = _common_metadata(
        rid, "paraphrase",
        l1_def["l1_value_id"], l1_def["l1_value_name"],
        l1_def["l2_value_id"], l1_def["l2_value_name"],
        direction, plan_dir,
    )

    canonical_actor = seed.get("actor_name", "") or ""
    mentions = derive_actor_mentions(canonical_actor)
    seed_excerpt_long, seed_truncated_long = smart_truncate(seed.get("content_excerpt") or "", 1500)
    seed_excerpt_short, seed_truncated_short = smart_truncate(seed.get("content_excerpt") or "", 600)

    system_prompt = (
        "You are a careful news-style rewriter for a research benchmark.\n"
        "Inputs: a TRAIN article excerpt, the actor of interest, an L1 human value, "
        "and a direction (aligned/contradictory).\n"
        "Your job: rewrite the article so the SAME actor still expresses (or contradicts) "
        "the SAME value in the SAME direction, but with different wording, sentence order, "
        "and incidental details.\n"
        "Hard rules:\n"
        "- Preserve actor identity (use the canonical actor name OR any provided alias; "
        "  do NOT over-generalise the actor — e.g. do not replace a named NGO with 'a group').\n"
        "- Preserve the L1 value and the direction exactly.\n"
        "- Keep the same value relation but use different wording and article structure.\n"
        "- Do not copy any whole sentence verbatim from the seed.\n"
        + SAFETY_FOOTER
    )

    actor_block = f"Canonical actor name: {canonical_actor}\nActor internal ID: {seed.get('actor_id','')}\n"
    if mentions["primary"]:
        actor_block += f"Suggested primary mention (use verbatim in content): \"{mentions['primary']}\"\n"
    if mentions["aliases"]:
        aliases_str = ", ".join(f'"{a}"' for a in mentions["aliases"])
        actor_block += f"Acceptable additional aliases (any one may appear in content): {aliases_str}\n"
    actor_block += (
        "Requirement: the field `actor_mention` in your output must appear verbatim in "
        "`content`. It may be the canonical name, the primary mention, an alias, or any "
        "other natural surface form that clearly refers to the same entity. "
        "The field `actor_name` in your output must equal the canonical actor name above.\n"
    )

    truncation_warning = ""
    if seed_truncated_long:
        truncation_warning = (
            "\n[Note] The seed excerpt below may be truncated at a sentence boundary "
            "(or with an ellipsis). Do NOT invent facts beyond the provided context; "
            "rewrite only what the excerpt actually conveys about the actor and value.\n"
        )

    user_prompt = (
        f"Seed (TRAIN) article excerpt:\n"
        f"---\n"
        f"Title: {seed.get('title','')}\n"
        f"{seed_excerpt_long}\n"
        f"---\n"
        f"{truncation_warning}"
        f"{actor_block}"
        f"L1 value to preserve: {l1_def['l1_value_id']} ({l1_def['l1_value_name']})\n"
        f"L2 category:          {l1_def['l2_value_id']} ({l1_def['l2_value_name']})\n"
        f"Direction to preserve: {DIRECTION_NAME[direction]} ({direction})\n"
        f"Evidence in seed (annotator note, paraphrase freely): "
        f"{(seed.get('explanation') or '')[:300]}\n\n"
        "Rewrite the article (≤ 1500 chars) while preserving the actor and the "
        "value/direction relationship. Output JSON only conforming to `expected_output_schema`."
    )

    md.update({
        "seed_guid":             seed.get("guid"),
        "seed_actor_id":         seed.get("actor_id"),
        "seed_actor_name":       canonical_actor,
        "canonical_actor_name":  canonical_actor,
        "actor_aliases":         mentions["aliases"],
        "suggested_actor_mentions": [mentions["primary"]] + mentions["aliases"]
                                    if mentions["primary"] else mentions["aliases"],
        "seed_content_excerpt":  seed_excerpt_short,
        "seed_excerpt_truncated": seed_truncated_short,
        "evidence_requirement":  EVIDENCE_REQUIREMENT_PARAPHRASE,
        "negative_target_label_id": None,
        "paired_request_id":     None,
        "system_prompt":         system_prompt,
        "user_prompt":           user_prompt,
        "expected_output_schema": expected_output_schema("paraphrase"),
        "quality_checklist": [
            "actor_mention appears verbatim in content",
            "actor_name in output equals canonical_actor_name",
            "evidence_sentence is verbatim in content and describes the actor's action/stance",
            "L1 value relationship preserved; no value drift",
            "direction preserved",
            "no whole-sentence verbatim copy from seed",
            "actor not over-generalised (e.g. specific group not replaced by 'people')",
            "is_positive = true; direction matches seed",
        ],
        "rejection_rules": [
            "actor_mention missing from content",
            "actor_name in output differs from canonical_actor_name",
            "evidence_sentence not in content",
            "direction inverted vs. seed",
            "L1 value drifted",
            "is_positive != true",
            "another L1 value made more salient than the target",
            "content < 50 chars or > 8000 chars",
        ],
    })
    return md


# ── Rare-positive ───────────────────────────────────────────────────────────

def build_rare_positive_request(idx: int, l1_def: Dict, seed: Optional[Dict], plan_dir: str) -> Dict:
    # Default to aligned ("1") for rare positives; the planner already records
    # both directions exist for any label in the rare-positive pool.
    direction = "1"
    base_for_id = (seed.get("guid", "") if seed else "no_seed") + l1_def["l1_value_id"]
    rid = f"prev_rare_positive_{l1_def['l1_value_id']}_{idx:03d}_{short_hash(base_for_id)}"
    md = _common_metadata(
        rid, "rare_positive",
        l1_def["l1_value_id"], l1_def["l1_value_name"],
        l1_def["l2_value_id"], l1_def["l2_value_name"],
        direction, plan_dir,
    )

    canonical_actor = (seed.get("actor_name") if seed else "") or ""
    mentions = derive_actor_mentions(canonical_actor) if canonical_actor else {"primary": "", "aliases": []}
    seed_excerpt_note = ""
    seed_excerpt_short, seed_truncated_short = ("", False)
    if seed:
        seed_excerpt_short, seed_truncated_short = smart_truncate(seed.get("content_excerpt") or "", 300)
        truncation_warning = (
            "(seed excerpt may be truncated; do not invent facts beyond the provided context)"
            if seed_truncated_short else ""
        )
        seed_excerpt_note = (
            f"\nOptional TRAIN seed (for style reference only — do NOT copy any sentence):\n"
            f"  guid={seed.get('guid')}\n"
            f"  canonical actor: {canonical_actor}\n"
            f"  excerpt {truncation_warning}: {seed_excerpt_short}\n"
        )

    system_prompt = (
        "You are a synthetic news writer for a research benchmark.\n"
        "Inputs: a target L1 human value, an L2 category, a direction, optional actor "
        "context. Write a short, news-style article (≤ 1500 chars) in which the named "
        "actor's behaviour clearly expresses the target value in the specified direction.\n"
        "Hard rules:\n"
        "- Concrete factual news style; no first-person; no editorial.\n"
        "- The named actor must be the SUBJECT of the value-bearing action/stance.\n"
        "- The target value must be the most salient value relationship for this actor.\n"
        "- Do not name real, identifiable individuals in negative/defamatory ways.\n"
        + SAFETY_FOOTER
    )

    actor_block = ""
    if canonical_actor:
        actor_block = (
            f"Canonical actor name (reuse in `actor_name`): {canonical_actor}\n"
            f"Acceptable actor mentions in content: {mentions['primary']!r}"
        )
        if mentions["aliases"]:
            actor_block += f", plus aliases: {', '.join(repr(a) for a in mentions['aliases'])}"
        actor_block += (
            "\nRequirement: `actor_mention` in your output must appear verbatim in `content`. "
            "It may be the canonical name, any alias, or any other natural surface form.\n"
        )
    else:
        actor_block = (
            "No TRAIN seed actor was provided. Invent a plausible newsworthy actor name "
            "(named individual, organisation, government body, or named community). "
            "Set `actor_name` and `actor_mention` to that name; ensure `actor_mention` "
            "appears verbatim in `content`.\n"
        )

    user_prompt = (
        f"Target L1 value: {l1_def['l1_value_id']} ({l1_def['l1_value_name']})\n"
        f"L2 category:    {l1_def['l2_value_id']} ({l1_def['l2_value_name']})\n"
        f"Direction:       {DIRECTION_NAME[direction]} ({direction})\n"
        f"Augmentation rationale: {l1_def.get('augmentation_rationale','')}\n"
        f"{actor_block}"
        f"{seed_excerpt_note}\n"
        "Generate ONE short news-style article. Output JSON only conforming to "
        "`expected_output_schema`."
    )

    md.update({
        "seed_guid":             seed.get("guid") if seed else None,
        "seed_actor_id":         seed.get("actor_id") if seed else None,
        "seed_actor_name":       canonical_actor or None,
        "canonical_actor_name":  canonical_actor or None,
        "actor_aliases":         mentions["aliases"] if canonical_actor else [],
        "suggested_actor_mentions": (
            [mentions["primary"]] + mentions["aliases"] if canonical_actor and mentions["primary"]
            else (mentions["aliases"] if canonical_actor else [])
        ),
        "seed_content_excerpt":  seed_excerpt_short if seed else None,
        "seed_excerpt_truncated": seed_truncated_short,
        "evidence_requirement":  EVIDENCE_REQUIREMENT_RARE_POS,
        "negative_target_label_id": None,
        "paired_request_id":     None,
        "system_prompt":         system_prompt,
        "user_prompt":           user_prompt,
        "expected_output_schema": expected_output_schema("rare_positive"),
        "quality_checklist": [
            "actor_mention appears verbatim in content",
            "actor is *subject* of the value-bearing action",
            "evidence_sentence verbatim in content and describes the actor's action",
            "target value is the most salient for the actor",
            "direction unambiguous and matches request",
            "is_positive = true; direction matches request",
        ],
        "rejection_rules": [
            "actor_mention absent from content",
            "target value not actually the salient one for the actor",
            "another L1 value made more salient than the target",
            "direction ambiguous or inverted",
            "real-person defamation",
            "is_positive != true",
            "content < 50 chars or > 8000 chars",
        ],
    })
    return md


# ── Hard-negative ───────────────────────────────────────────────────────────

def build_hard_negative_request(idx: int,
                                l1_def: Dict,
                                confusable: Optional[Tuple[str, str]],
                                plan_dir: str) -> Dict:
    rid = f"prev_hard_negative_{l1_def['l1_value_id']}_{idx:03d}_{short_hash(l1_def['l1_value_id'] + str(idx))}"
    md = _common_metadata(
        rid, "hard_negative",
        l1_def["l1_value_id"], l1_def["l1_value_name"],
        l1_def["l2_value_id"], l1_def["l2_value_name"],
        None, plan_dir,
    )

    alt_id, alt_name = confusable if confusable else (None, None)

    system_prompt = (
        "You are creating a near-miss training example for a research benchmark.\n"
        "Goal: produce an article whose TOPIC is plausibly related to the target L1 "
        "value (so a naive classifier might over-predict it), but in which the TARGET "
        "ACTOR's actual actions/stance do NOT support the target value either way.\n"
        "Distinction to enforce:\n"
        "- TOPIC relevance: the article surface (subject matter, keywords) is in the "
        "  same domain as the target value.\n"
        "- ACTOR-specific value expression: the named actor does NOT express, support, "
        "  uphold, violate, or undermine the target value. Some OTHER value (the "
        "  alternative) is the genuinely relevant one for this actor.\n"
        "Hard rules:\n"
        "- No statement of `content` should justify either direction of the target value "
        "  for the TARGET ACTOR.\n"
        "- At least one statement of `content` must clearly support the alternative L1 "
        "  value for the TARGET ACTOR.\n"
        "- `explanation` must SPECIFICALLY state why the target value does not apply to "
        "  the actor (point to absence of action/stance, not just topic differences).\n"
        "- Avoid ambiguous negatives: if a reasonable annotator could mark the target "
        "  value as applying with either direction, the example is not a clean negative.\n"
        + SAFETY_FOOTER
    )

    alt_block = ""
    if alt_id is not None:
        alt_block = (
            f"Actually-correct L1 value for this actor: {alt_id} ({alt_name})\n"
        )
    else:
        alt_block = (
            f"Actually-correct L1 value: (pick any plausible L1 from the SAME L2 family "
            f"as the target — see suggested L2 family below — do not pick "
            f"{l1_def['l1_value_id']}). Echo your pick in `l1_value_id` / `l1_value_name`.\n"
        )

    user_prompt = (
        f"Target L1 value (do NOT support for this actor in either direction): "
        f"{l1_def['l1_value_id']} ({l1_def['l1_value_name']})\n"
        f"Target L2 category (use as topic family): "
        f"{l1_def['l2_value_id']} ({l1_def['l2_value_name']})\n"
        f"{alt_block}"
        f"Augmentation rationale: {l1_def.get('augmentation_rationale','')}\n"
        f"\nRequirement: invent a plausible newsworthy actor (named individual, "
        f"organisation, government body, or named community). Set `actor_name` and "
        f"`actor_mention` to that name; ensure `actor_mention` appears verbatim in "
        f"`content`.\n\n"
        "Generate ONE short news-style article (≤ 1500 chars). The article should be "
        "topically related to the target value but the actor's actions/stance must NOT "
        "support the target value in any direction. Output JSON only conforming to "
        "`expected_output_schema`."
    )

    md.update({
        "seed_guid":             None,
        "seed_actor_id":         None,
        "seed_actor_name":       None,
        "canonical_actor_name":  None,  # generator will invent
        "actor_aliases":         [],
        "suggested_actor_mentions": [],
        "seed_content_excerpt":  None,
        "seed_excerpt_truncated": False,
        "evidence_requirement":  EVIDENCE_REQUIREMENT_HARD_NEG,
        "negative_target_label_id": l1_def["l1_value_id"],
        "alternative_label_id":  alt_id,
        "alternative_label_name": alt_name,
        "paired_request_id":     None,
        "system_prompt":         system_prompt,
        "user_prompt":           user_prompt,
        "expected_output_schema": expected_output_schema("hard_negative"),
        "quality_checklist": [
            "Article topic is related to target value",
            "Actor does not express or contradict the target value",
            "Actor clearly expresses the alternative L1 value",
            "actor_mention appears verbatim in content",
            "evidence_sentence supports the alternative value, not the target",
            "explanation specifically states why target value does not apply to actor",
            "is_positive = false; direction may be null",
            "Not ambiguous: a reasonable annotator would not mark the target value",
        ],
        "rejection_rules": [
            "Target value is actually expressed for the actor (would be a positive)",
            "Topic is unrelated to the target value (defeats hard-negative purpose)",
            "Neither target nor alternative value clearly expressed",
            "Actor cannot be identified by name in content",
            "explanation only cites topic difference rather than actor's stance",
            "is_positive != false",
            "content < 50 chars or > 8000 chars",
        ],
    })
    return md


# ── Direction-contrastive pair (2 requests linked) ─────────────────────────

def build_direction_contrastive_pair(idx: int, l1_def: Dict, plan_dir: str) -> List[Dict]:
    base_hash = short_hash(l1_def["l1_value_id"] + f"pair{idx}")
    rid_a = f"prev_dir_contrast_{l1_def['l1_value_id']}_{idx:03d}_aligned_{base_hash}"
    rid_b = f"prev_dir_contrast_{l1_def['l1_value_id']}_{idx:03d}_contradictory_{base_hash}"

    common_system = (
        "You are writing a PAIR of short news-style articles for the SAME L1 human value.\n"
        "Each member of the pair is generated by an INDEPENDENT request (this is one of "
        "the two). The two members will be reviewed together.\n"
        "Hard rules for the pair:\n"
        "- Share a closely related topic / domain (so direction is the discriminating signal).\n"
        "- Use DIFFERENT actor names — the contrast is between actors' stances, not lexical "
        "  direction words.\n"
        "- One member expresses the value in ALIGNED direction (actor supports/expresses).\n"
        "- The other expresses the value in CONTRADICTORY direction (actor violates/undermines).\n"
        "- Differ in SUBSTANCE (actor identity, action, decision), not only in surface words "
        "  ('supports' ↔ 'violates') glued onto the same sentence.\n"
        "Each article ≤ 1500 chars. Output JSON only conforming to `expected_output_schema`.\n"
        + SAFETY_FOOTER
    )

    def build_one(rid: str, direction: str, paired_rid: str) -> Dict:
        md = _common_metadata(
            rid, "direction_contrastive",
            l1_def["l1_value_id"], l1_def["l1_value_name"],
            l1_def["l2_value_id"], l1_def["l2_value_name"],
            direction, plan_dir,
        )
        user_prompt = (
            f"This is the {DIRECTION_NAME[direction]} member of a direction-contrastive pair.\n"
            f"Pair partner request_id (preserve in metadata): {paired_rid}\n"
            f"L1 value: {l1_def['l1_value_id']} ({l1_def['l1_value_name']})\n"
            f"L2 category: {l1_def['l2_value_id']} ({l1_def['l2_value_name']})\n"
            f"Direction for THIS article: {DIRECTION_NAME[direction]} ({direction})\n"
            f"Augmentation rationale: {l1_def.get('augmentation_rationale','')}\n\n"
            "Invent a plausible newsworthy actor (named individual, organisation, government "
            "body, or named community). Set both `actor_name` and `actor_mention` to that "
            "name; ensure `actor_mention` appears verbatim in `content`.\n"
            "Topic constraint: pick a domain plausibly newsworthy for this L1 value. The "
            "partner request will use a DIFFERENT actor in the OPPOSITE direction on the "
            "same domain. Output JSON only conforming to `expected_output_schema`."
        )
        md.update({
            "seed_guid":             None,
            "seed_actor_id":         None,
            "seed_actor_name":       None,
            "canonical_actor_name":  None,  # generator will invent
            "actor_aliases":         [],
            "suggested_actor_mentions": [],
            "seed_content_excerpt":  None,
            "seed_excerpt_truncated": False,
            "evidence_requirement":  EVIDENCE_REQUIREMENT_DIR_CONTR,
            "negative_target_label_id": None,
            "paired_request_id":     paired_rid,
            "system_prompt":         common_system,
            "user_prompt":           user_prompt,
            "expected_output_schema": expected_output_schema("direction_contrastive"),
            "quality_checklist": [
                "actor_mention appears verbatim in content",
                "evidence_sentence verbatim in content and describes the actor's action",
                "direction matches request (output direction == target_direction)",
                "topic overlaps with paired request's domain",
                "pair differs in actor + substance, not just lexical direction words",
                "is_positive = true",
            ],
            "rejection_rules": [
                "actor_mention absent from content",
                "direction inverted vs. request",
                "topic completely unrelated to pair partner",
                "pair differs only in surface direction words",
                "pair shares the same actor name",
                "is_positive != true",
            ],
        })
        return md

    a = build_one(rid_a, "1", rid_b)
    b = build_one(rid_b, "0", rid_a)
    return [a, b]


# ============================================================
# FIGURES
# ============================================================

def make_figures(requests: List[Dict], plan_rows: List[Dict], fig_dir: Path) -> None:
    if not HAS_MPL:
        return
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. requests by augmentation type
    by_type = Counter(r["augmentation_type"] for r in requests)
    fig, ax = plt.subplots(figsize=(7, 4))
    keys = ["paraphrase", "rare_positive", "hard_negative", "direction_contrastive"]
    vals = [by_type.get(k, 0) for k in keys]
    bars = ax.bar(range(len(keys)), vals, alpha=0.85)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.05, str(v),
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(keys, rotation=15, ha="right")
    ax.set_ylabel("Preview requests")
    ax.set_title("Tiny pilot preview — requests by augmentation type")
    plt.tight_layout(); plt.savefig(fig_dir / "requests_by_augmentation_type.png", dpi=150); plt.close()

    # 2. requests by label
    by_label_count = Counter((r["target_l1_value_id"], r["target_l1_value_name"]) for r in requests)
    items = sorted(by_label_count.items(), key=lambda kv: -kv[1])
    y = list(range(len(items)))
    fig, ax = plt.subplots(figsize=(10, max(3, 0.32 * max(len(items), 1) + 1)))
    ax.barh(y, [v for _, v in items], alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{lid}: {name}" for (lid, name), _ in items], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Preview requests")
    ax.set_title("Tiny pilot preview — requests by L1 label")
    plt.tight_layout(); plt.savefig(fig_dir / "requests_by_label.png", dpi=150); plt.close()

    # 3. preview vs plan budget
    plan_total_per_type = {
        "paraphrase":            sum(int(r["n_paraphrase"]) for r in plan_rows),
        "rare_positive":         sum(int(r["n_rare_positive"]) for r in plan_rows),
        "hard_negative":         sum(int(r["n_hard_negative"]) for r in plan_rows),
        "direction_contrastive": sum(int(r["n_direction_contrastive_pairs"]) for r in plan_rows) * 2,
    }
    pv = [by_type.get(k, 0) for k in keys]
    pl = [plan_total_per_type.get(k, 0) for k in keys]
    x = range(len(keys))
    bar_w = 0.4
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([xi - bar_w/2 for xi in x], pv, bar_w, label="preview (tiny pilot)", alpha=0.85)
    ax.bar([xi + bar_w/2 for xi in x], pl, bar_w, label="plan total (pilot profile)", alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(keys, rotation=15, ha="right")
    ax.set_ylabel("Sample count")
    ax.set_title("Preview vs Plan budget (pilot)")
    ax.legend(fontsize=8)
    plt.tight_layout(); plt.savefig(fig_dir / "request_budget_vs_plan.png", dpi=150); plt.close()


# ============================================================
# CSV / REPORT WRITERS
# ============================================================

def write_request_csv(requests: List[Dict], path: Path) -> None:
    cols = [
        "request_id", "augmentation_type",
        "target_l1_value_id", "target_l1_value_name",
        "target_l2_value_id", "target_l2_value_name",
        "target_direction", "target_direction_name",
        "seed_guid", "seed_actor_id", "seed_actor_name",
        "negative_target_label_id", "paired_request_id",
        "recommended_generator_model",
    ]
    flat = [{k: r.get(k) for k in cols} for r in requests]
    write_csv(flat, path, cols)


def write_summary_by_type(requests: List[Dict], path: Path) -> None:
    c = Counter(r["augmentation_type"] for r in requests)
    rows = [{"augmentation_type": k, "n_requests": v} for k, v in c.items()]
    rows.append({"augmentation_type": "TOTAL", "n_requests": sum(c.values())})
    write_csv(rows, path, ["augmentation_type", "n_requests"])


def write_summary_by_label(requests: List[Dict], path: Path) -> None:
    c: Counter = Counter()
    name = {}
    for r in requests:
        key = r["target_l1_value_id"]
        c[key] += 1
        name[key] = r["target_l1_value_name"]
    rows = [
        {"l1_value_id": k, "l1_value_name": name[k], "n_requests": v}
        for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    write_csv(rows, path, ["l1_value_id", "l1_value_name", "n_requests"])


def write_human_review_sheet(requests: List[Dict], path: Path) -> None:
    rows = []
    for r in requests:
        risk = "low"
        if r["augmentation_type"] == "direction_contrastive":
            risk = "medium (pair partner must be reviewed together)"
        if r["augmentation_type"] == "hard_negative":
            risk = "medium (alternative-label correctness depends on judgement)"
        if r["augmentation_type"] == "rare_positive" and r.get("seed_guid") is None:
            risk = "medium-high (no train seed; generated from definition only)"
        rows.append({
            "request_id":             r["request_id"],
            "augmentation_type":      r["augmentation_type"],
            "target_l1_value_id":     r["target_l1_value_id"],
            "target_l1_value_name":   r["target_l1_value_name"],
            "target_direction":       r["target_direction"],
            "seed_guid":              r.get("seed_guid"),
            "seed_actor_name":        r.get("seed_actor_name"),
            "recommended_model":      r["recommended_generator_model"],
            "review_status":          "pending",
            "reviewer_notes":         "",
            "risk_level":             risk,
            "should_execute_later":   "manual_review_required",
        })
    cols = list(rows[0].keys()) if rows else []
    write_csv(rows, path, cols)


def write_report(requests: List[Dict],
                 selected_seeds: List[Dict],
                 plan_dir: Path,
                 profile: str,
                 max_total: int,
                 quotas_actual: Dict[str, int],
                 quotas_target: Dict[str, int],
                 ts: str,
                 out_dir: Path) -> None:
    by_type = Counter(r["augmentation_type"] for r in requests)
    by_label = Counter(r["target_l1_value_name"] for r in requests)
    n_dir_pairs = by_type.get("direction_contrastive", 0) // 2

    n_with_seed = sum(1 for r in requests if r.get("seed_guid"))
    n_no_seed   = sum(1 for r in requests if not r.get("seed_guid"))

    lines = [
        "# Generation Preview Report (tiny pilot v1)",
        "",
        f"**Timestamp:** {ts}  ",
        f"**Profile:** `{profile}`  ",
        f"**Source plan:** `{plan_dir}`  ",
        f"**Max requests:** {max_total}  ",
        "",
        "> No API was called. Every request object has `\"preview_only\": true` "
        "and `\"do_not_execute\": true`.",
        "",
        "## Totals",
        "",
        f"- Preview requests written: **{len(requests)}**",
        f"- TRAIN seeds used: {len(selected_seeds)}",
        f"- Requests with a seed: {n_with_seed}",
        f"- Requests without a seed (definition-only): {n_no_seed}",
        f"- Direction-contrastive pairs: {n_dir_pairs}",
        "",
        "## Requests by augmentation type",
        "",
        "| Type | Target | Actual |",
        "|---|---|---|",
    ]
    for k in ["paraphrase", "rare_positive", "hard_negative", "direction_contrastive"]:
        target_k = quotas_target.get(k, 0)
        actual_k = by_type.get(k, 0)
        lines.append(f"| {k} | {target_k} | {actual_k} |")

    lines += [
        "",
        "## Requests by L1 label",
        "",
        "| L1 | Label | Requests |",
        "|---|---|---|",
    ]
    by_label_sorted = sorted(
        Counter((r["target_l1_value_id"], r["target_l1_value_name"]) for r in requests).items(),
        key=lambda kv: (-kv[1], kv[0][0])
    )
    for (lid, name), n in by_label_sorted:
        lines.append(f"| {lid} | {name} | {n} |")

    lines += [
        "",
        "## What this preview does",
        "",
        "1. Reads the existing plan and selects target labels per type by priority.",
        "2. Picks one TRAIN seed instance per `paraphrase` and (optionally) per `rare_positive`.",
        "3. Builds a complete request object — system prompt, user prompt, "
        "   expected output schema, quality checklist, rejection rules — but does not "
        "   call any API.",
        "4. Writes a human review sheet in CSV form with `review_status = pending` "
        "   for every request.",
        "5. Writes a small set of figures summarising the preview.",
        "",
        "## What this preview does NOT do",
        "",
        "- Does not call any LLM.",
        "- Does not produce any augmented sample.",
        "- Does not modify any existing file or output folder.",
        "- Does not write into `dataset/`, `output/task1*/`, or `logs/`.",
        "",
        "## Suggested next steps (for the human reviewer)",
        "",
        "1. Open `human_review_sheet.csv` and verify the request set.",
        "2. Inspect any non-trivial prompt by reading the matching line in "
        "   `generation_requests_preview.jsonl`.",
        "3. When ready, the next phase will be `run_generation.py` (not yet created), "
        "   which consumes the preview file, dispatches calls, and writes "
        "   `augmented_samples.jsonl` validated against "
        "   `research/fehu_augmentation_v1/augmentation_schema.json` and the "
        "   FEHU-specific augmented-data guard.",
        "",
        "## Constraints honoured",
        "",
        "- No API call.",
        "- No model training.",
        "- No reading of `.env` values.",
        "- TRAIN seeds only; no dev/test article content used.",
        "- All output written to a new timestamped folder; nothing overwritten.",
    ]
    (out_dir / "generation_preview_report.md").write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# MAIN
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser(description="Build augmentation generation request previews (no API).")
    ap.add_argument("--plan_dir", type=str, required=True,
                    help="Path to an existing output/research_augmentation_plan/<TS>/ folder.")
    ap.add_argument("--profile", choices=list(PROFILES.keys()), default="tiny_pilot_v1")
    ap.add_argument("--max_total_requests", type=int, default=20,
                    help="Hard cap on total preview requests written.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_absolute():
        plan_dir = PROJECT_ROOT / plan_dir
    if not plan_dir.exists():
        print(f"ERROR: plan_dir does not exist: {plan_dir}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "output" / "research_generation_preview" / ts
    fig_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("FEHU Augmentation Generation Preview")
    print("=" * 64)
    print(f"plan_dir : {plan_dir}")
    print(f"profile  : {args.profile}")
    print(f"out_dir  : {out_dir}")
    print()

    # ── Load plan artefacts ─────────────────────────────────────────────────
    plan_rows   = read_csv(plan_dir / "augmentation_plan_by_label.csv")
    seed_records = load_jsonl(plan_dir / "selected_seed_instances.jsonl")
    label_defs   = load_json(plan_dir / "target_label_definitions.json")

    if not plan_rows:
        print("ERROR: augmentation_plan_by_label.csv missing or empty.")
        sys.exit(1)
    print(f"Loaded {len(plan_rows)} planned labels and {len(seed_records)} seed records.")

    # ── Profile quotas ─────────────────────────────────────────────────────
    quotas = PROFILES[args.profile]
    quotas_target = {
        "paraphrase":            quotas["paraphrase"],
        "rare_positive":         quotas["rare_positive"],
        "hard_negative":         quotas["hard_negative"],
        "direction_contrastive": quotas["direction_contrastive_pairs"] * 2,
    }

    # ── Select labels ──────────────────────────────────────────────────────
    paraphrase_labels  = select_paraphrase_labels(plan_rows,   quotas["paraphrase"])
    rare_pos_labels    = select_rare_positive_labels(plan_rows, quotas["rare_positive"])
    hard_neg_labels    = select_hard_negative_labels(plan_rows, quotas["hard_negative"])
    dir_contr_labels   = select_direction_contrastive_labels(plan_rows, quotas["direction_contrastive_pairs"])

    seeds_per_label = seeds_by_label(seed_records)
    confusable = build_confusable_map({k: v for k, v in label_defs.items()})

    # ── Build requests ─────────────────────────────────────────────────────
    requests: List[Dict] = []
    selected_seeds: List[Dict] = []
    used_seed_ids: set = set()
    skipped_notes: List[str] = []
    plan_dir_str = str(plan_dir)

    # paraphrase (require seed)
    for i, lbl in enumerate(paraphrase_labels):
        l1_id = lbl["l1_value_id"]
        l1_def = label_defs.get(l1_id)
        if l1_def is None:
            skipped_notes.append(f"paraphrase skipped — label {l1_id} missing from definitions")
            continue
        seed = pick_seed_for_label(seeds_per_label.get(l1_id, []), used_seed_ids)
        if seed is None:
            skipped_notes.append(f"paraphrase skipped — no TRAIN seed for label {l1_id}")
            continue
        selected_seeds.append(seed)
        requests.append(build_paraphrase_request(i + 1, l1_def, seed, plan_dir_str))

    # rare_positive (seed is optional)
    for i, lbl in enumerate(rare_pos_labels):
        l1_id = lbl["l1_value_id"]
        l1_def = label_defs.get(l1_id)
        if l1_def is None:
            skipped_notes.append(f"rare_positive skipped — label {l1_id} missing from definitions")
            continue
        seed = pick_seed_for_label(seeds_per_label.get(l1_id, []), used_seed_ids)
        if seed is not None:
            selected_seeds.append(seed)
        requests.append(build_rare_positive_request(i + 1, l1_def, seed, plan_dir_str))

    # hard_negative
    for i, lbl in enumerate(hard_neg_labels):
        l1_id = lbl["l1_value_id"]
        l1_def = label_defs.get(l1_id)
        if l1_def is None:
            skipped_notes.append(f"hard_negative skipped — label {l1_id} missing from definitions")
            continue
        conf = confusable.get(l1_id)
        requests.append(build_hard_negative_request(i + 1, l1_def, conf, plan_dir_str))

    # direction_contrastive (PAIRS)
    for i, lbl in enumerate(dir_contr_labels):
        l1_id = lbl["l1_value_id"]
        l1_def = label_defs.get(l1_id)
        if l1_def is None:
            skipped_notes.append(f"direction_contrastive skipped — label {l1_id} missing from definitions")
            continue
        pair = build_direction_contrastive_pair(i + 1, l1_def, plan_dir_str)
        requests.extend(pair)

    # Enforce hard cap
    if len(requests) > args.max_total_requests:
        # Truncate but keep direction-contrastive pairs intact: drop in reverse build order
        # Simple policy: drop tail (lowest-priority within type) until under cap
        requests = requests[: args.max_total_requests]
        skipped_notes.append(f"truncated to --max_total_requests={args.max_total_requests}")

    # ── Write everything ───────────────────────────────────────────────────
    write_jsonl(requests, out_dir / "generation_requests_preview.jsonl")
    write_request_csv(requests, out_dir / "generation_requests_preview.csv")
    write_summary_by_type(requests, out_dir / "request_summary_by_type.csv")
    write_summary_by_label(requests, out_dir / "request_summary_by_label.csv")
    write_jsonl(selected_seeds, out_dir / "selected_preview_seed_instances.jsonl")
    write_human_review_sheet(requests, out_dir / "human_review_sheet.csv")

    config = {
        "timestamp":          ts,
        "plan_dir":           plan_dir_str,
        "profile":            args.profile,
        "preview_revision":   PREVIEW_REVISION,
        "max_total_requests": args.max_total_requests,
        "quotas_target":      quotas_target,
        "quotas_actual":      dict(Counter(r["augmentation_type"] for r in requests)),
        "n_requests":         len(requests),
        "n_train_seeds_used": len(selected_seeds),
        "skipped_notes":      skipped_notes,
        "preview_only":       True,
        "api_called":         False,
        "training_run":       False,
        "notes":              "Generation preview only. No API call, no augmented data produced.",
    }
    (out_dir / "generation_preview_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    write_report(requests, selected_seeds, plan_dir, args.profile,
                 args.max_total_requests, dict(Counter(r["augmentation_type"] for r in requests)),
                 quotas_target, ts, out_dir)

    make_figures(requests, plan_rows, fig_dir)

    # ── Final summary print ───────────────────────────────────────────────
    print()
    print("=" * 64)
    print("PREVIEW SUMMARY")
    print("=" * 64)
    by_type = Counter(r["augmentation_type"] for r in requests)
    for k in ["paraphrase", "rare_positive", "hard_negative", "direction_contrastive"]:
        print(f"  {k:<26} {by_type.get(k, 0):>3}")
    print(f"  {'TOTAL':<26} {len(requests):>3}")
    print()
    if skipped_notes:
        print("Notes:")
        for n in skipped_notes:
            print(f"  - {n}")
        print()
    print(f"Preview folder: {out_dir}")


if __name__ == "__main__":
    main()
