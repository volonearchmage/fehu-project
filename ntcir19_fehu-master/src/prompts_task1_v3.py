#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V3 — prompt variants for the DeepSeek V4 ensemble.

Three complementary prompts, individually versioned and hashed:

  * Variant A ("variant_a_concise")  — a substantially shorter, balanced
    classifier prompt. Preserves the complete official taxonomy definitions
    and exact IDs, drops the long procedural sections of Pipeline 2 that made
    smaller models overly conservative.
  * Variant B ("variant_b_recall")   — a targeted-recall classifier with a
    low-frequency checklist (cues generated ONLY from the official taxonomy
    text: alternative names + descriptions) and few-shot demonstrations
    selected deterministically from TRAIN data only.
  * Verifier ("verifier")            — a compact precision-oriented prompt
    that accepts/rejects a fixed candidate list and resolves direction. It
    never re-scans the full taxonomy.

Scientific constraints implemented here:
  * demonstrations come exclusively from dataset/train/ (+ train gold); their
    GUIDs and selection rule are exported as provenance;
  * rarity metadata comes from TRAIN gold counts only (task1_v2_taxonomy);
  * no gold labels, metrics, or dev-error observations appear in any prompt;
  * the output contract is identical to Pipeline 2's, so Pipeline 2's strict
    validators are reused unchanged for variants A and B.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from task1_v2_taxonomy import (
    Taxonomy, canonical_json, sha256_text, compute_article_hash,
    TRAIN_LABELS_PATH, BASE_DIR,
)
from prompts_task1_v2 import build_user_prompt  # shared per-article user prompt

# v3.1.0: Variant B gains a generic DIRECTION CUES block and a same-L2-group
# sibling-specificity rule (portable mechanisms from the Liu reference audit,
# docs/liu_method_pipeline3_audit.md — label lists were NOT ported).
PROMPT_VERSION_V3 = "fehu_task1_prompt_v3.1.0"

VARIANT_A = "variant_a_concise"
VARIANT_B = "variant_b_recall"
VARIANT_VERIFIER = "verifier"

TRAIN_ARTICLES_PATH = BASE_DIR / "dataset" / "train" / "train_event_base.json"

# Deterministic demonstration-selection parameters (part of the prompt
# identity via the demo-set hash).
DEMO_DEFAULT_N = 2
DEMO_MAX_CONTENT_CHARS = 2000
DEMO_MIN_GOLD_TUPLES = 3
DEMO_MAX_GOLD_TUPLES = 10
DEMO_MAX_ACTORS = 3
DEMO_SELECTION_RULE = (
    "TRAIN articles with 1..3 actors, 3..10 deduplicated gold tuples, "
    "content <= 2000 chars, all gold actor IDs present in the actor list, "
    ">= 1 rare/very_rare Level-1 label; sorted by (-n_rare_labels, guid); "
    "first n taken."
)


# ============================================================
# Shared building blocks
# ============================================================

def format_taxonomy_catalog_compact(tax: Taxonomy) -> str:
    """Complete official taxonomy, one line per Level-1 value.

    Keeps every official ID and every official description sentence; drops
    alternative names and frequency metadata (Variant B reintroduces both
    where they are useful for recall)."""
    lines = []
    for l2_id in tax.l2_ids:
        lines.append(f"L2 [{l2_id}] {tax.l2_id_to_name[l2_id]}:")
        members = [e for e in tax.l1_by_id.values() if e.l2_id == l2_id]
        for e in sorted(members, key=lambda x: int(x.l1_id)):
            lines.append(f"  [{e.l1_id}] {e.l1_name} — {'; '.join(e.descriptions)}")
    return "\n".join(lines)


_OUTPUT_CONTRACT = """OUTPUT — exactly one JSON object, nothing else (no markdown fences, no prose, no extra keys):
{
  "guid": "<GUID copied exactly from the input>",
  "predictions": [
    {"actor_id": "<actor ID copied exactly from the input actor list>",
     "l1_value_id": "<Level-1 ID as a string, '0'..'53'>",
     "direction": "<'1' aligned or '0' contradictory, as a string>"}
  ]
}
All three fields are strings. No duplicate (actor_id, l1_value_id, direction) entries. "predictions": [] is the correct output when nothing is supported."""

_DIRECTION_BLOCK = """DIRECTION (exact string IDs — no other token exists):
- "1" = aligned: the actor-specific evidence promotes, protects, realizes, or positively instantiates the value.
- "0" = contradictory: the actor-specific evidence violates, damages, obstructs, or undermines the value."""


# ============================================================
# Variant A — concise balanced classifier
# ============================================================

def build_system_prompt_a(tax: Taxonomy) -> str:
    catalog = format_taxonomy_catalog_compact(tax)
    return f"""You classify the human values expressed by actors in one factual news article (NTCIR-19 FEHU Task-1, article level).
Prompt: {PROMPT_VERSION_V3} / {VARIANT_A}

You receive the article and a fixed actor list with exact actor IDs. For each actor, output every Level-1 value that actor-specific evidence in the article supports, each with a direction.

TAXONOMY (official — judge against these definitions, not label-name intuition):
{catalog}

{_DIRECTION_BLOCK}

RULES:
1. Judge each actor independently. Use only actions, statements, goals, treatment, or consequences attributable to that actor (or befalling that actor) in this article. Never transfer another actor's evidence.
2. Decide label relevance first (does the evidence match the definition?), then direction — both from the same actor-specific evidence.
3. Do not assign a value from the actor's profession, institutional role, narrative role, or the article's general topic alone.
4. Distinguish reporting/being-accused-of wrongdoing from committing it, and suffering harm from causing it.
5. There is no required number of predictions per actor: output every supported value and no unsupported one. Zero predictions for an actor — or for the whole article — is a valid answer.

{_OUTPUT_CONTRACT}"""


# ============================================================
# Variant B — targeted recall classifier
# ============================================================

def format_low_frequency_checklist(tax: Taxonomy, rarity: dict) -> str:
    """Behavioral cue list for rare/very_rare labels, generated ONLY from the
    official taxonomy text (alternative name + descriptions)."""
    rows = []
    for l1_id in tax.l1_ids:
        meta = rarity["labels"][l1_id]
        if meta["frequency_group"] not in ("rare", "very_rare"):
            continue
        e = tax.l1_by_id[l1_id]
        rows.append(f"  [{e.l1_id}] {e.l1_name} ({e.alternative_name}) — cues: "
                    f"{'; '.join(e.descriptions)}")
    return "\n".join(rows)


def _demo_output_json(guid: str, article: dict, gold_tuples: List[Tuple[str, str, str]]) -> str:
    """Render gold tuples in the exact output contract, deterministically
    sorted (actor order in article, numeric L1 ID, direction)."""
    order: Dict[str, int] = {}
    for actor_dict in article["actors"]:
        for _, aid in actor_dict.items():
            order[str(aid)] = len(order)
    rows = sorted(set(gold_tuples),
                  key=lambda t: (order[t[0]], int(t[1]), t[2]))
    obj = {"guid": guid,
           "predictions": [{"actor_id": a, "l1_value_id": l, "direction": d}
                           for a, l, d in rows]}
    return json.dumps(obj, ensure_ascii=False, indent=2)


def select_demonstrations(
    tax: Taxonomy,
    rarity: dict,
    n: int = DEMO_DEFAULT_N,
    train_articles_path: Path = TRAIN_ARTICLES_PATH,
    train_labels_path: Path = TRAIN_LABELS_PATH,
) -> Tuple[List[dict], dict]:
    """Deterministically select few-shot demonstrations from TRAIN data only.

    Returns (demos, provenance). Each demo: {"guid", "article", "gold_tuples",
    "rare_l1_ids"}. Provenance records the selection rule, source split,
    article GUIDs, and the demo-set hash.
    """
    articles = json.loads(Path(train_articles_path).read_text(encoding="utf-8"))
    labels = json.loads(Path(train_labels_path).read_text(encoding="utf-8"))
    guid_to_article = {str(a["guid"]): a for a in articles}
    rare_ids = {l1 for l1, m in rarity["labels"].items()
                if m["frequency_group"] in ("rare", "very_rare")}

    candidates = []
    for item in labels:
        guid = str(item["guid"])
        art = guid_to_article.get(guid)
        if art is None:
            continue
        if not (1 <= len(art.get("actors", [])) <= DEMO_MAX_ACTORS):
            continue
        if len(art.get("content", "")) > DEMO_MAX_CONTENT_CHARS:
            continue
        actor_ids = {str(aid) for ad in art["actors"] for aid in ad.values()}
        tuples = {(str(hv["actor"]), str(hv["l1_value"]), str(hv["direction"]))
                  for hv in item.get("article_human_values", [])}
        if not all(a in actor_ids for a, _, _ in tuples):
            continue  # data hygiene: skip articles with misaligned gold actors
        if not all(l in tax.l1_by_id and d in ("0", "1") for _, l, d in tuples):
            continue
        if not (DEMO_MIN_GOLD_TUPLES <= len(tuples) <= DEMO_MAX_GOLD_TUPLES):
            continue
        demo_rare = sorted({l for _, l, _ in tuples if l in rare_ids}, key=int)
        if not demo_rare:
            continue
        candidates.append({"guid": guid, "article": art,
                           "gold_tuples": sorted(tuples),
                           "rare_l1_ids": demo_rare})

    candidates.sort(key=lambda c: (-len(c["rare_l1_ids"]), c["guid"]))
    demos = candidates[:n]

    demo_set_hash = sha256_text(canonical_json([
        {"guid": d["guid"],
         "article_hash": compute_article_hash(d["article"]),
         "gold_tuples": d["gold_tuples"]}
        for d in demos
    ]))
    provenance = {
        "source_split": "train",
        "selection_rule": DEMO_SELECTION_RULE,
        "n_requested": n,
        "n_selected": len(demos),
        "articles": [{"guid": d["guid"],
                      "n_actors": len(d["article"]["actors"]),
                      "n_gold_tuples": len(d["gold_tuples"]),
                      "rare_l1_ids": d["rare_l1_ids"]} for d in demos],
        "demo_set_hash": demo_set_hash,
    }
    return demos, provenance


def format_demo_block(demos: List[dict]) -> str:
    parts = []
    for i, d in enumerate(demos, 1):
        parts.append(
            f"--- Demonstration {i} (train article {d['guid']}) ---\n"
            f"{build_user_prompt(d['article'])}\n"
            f"Correct output:\n"
            f"{_demo_output_json(d['guid'], d['article'], d['gold_tuples'])}"
        )
    return "\n\n".join(parts)


def build_system_prompt_b(tax: Taxonomy, rarity: dict, demos: List[dict]) -> str:
    catalog = format_taxonomy_catalog_compact(tax)
    checklist = format_low_frequency_checklist(tax, rarity)
    demo_block = format_demo_block(demos)
    return f"""You classify the human values expressed by actors in one factual news article (NTCIR-19 FEHU Task-1, article level). Your specific strength: you do not miss values that are easy to overlook.
Prompt: {PROMPT_VERSION_V3} / {VARIANT_B}

You receive the article and a fixed actor list with exact actor IDs. For each actor, output every Level-1 value that actor-specific evidence in the article supports, each with a direction.

TAXONOMY (official — judge against these definitions, not label-name intuition):
{catalog}

{_DIRECTION_BLOCK}

RULES:
1. Judge each actor independently. Use only actions, statements, goals, treatment, or consequences attributable to that actor (or befalling that actor) in this article. Never transfer another actor's evidence.
2. Decide label relevance first, then direction — both from the same actor-specific evidence.
3. Do not assign a value from the actor's profession, role, or the article's general topic alone.
4. When several labels in the same Level-2 group seem to fit, keep only those whose definitions the evidence matches precisely — do not add sibling labels by association.
5. There is no required number of predictions per actor; zero is valid.

DIRECTION CUES (apply to every label, always from the actor's own behavior):
- the actor protects, provides, restores, warns, enables, promotes, or realizes what the definition describes → "1";
- the actor causes, threatens, blocks, neglects, violates, or destroys what the definition describes → "0";
- if the actor merely suffers, reports, quotes, or is accused of something, first re-check which value (if any) their own behavior or treatment engages before assigning a direction.

SEARCH PROCEDURE (two passes per actor):
Pass 1 — scan all 54 definitions above against the actor's concrete behavior: what they did, said, sought, refused, enabled, prevented, suffered, or caused.
Pass 2 — re-check the LOW-FREQUENCY CHECKLIST below. These labels are commonly missed because articles express them through concrete behavior that does not reuse the label's wording. Match the actor's behavior against the cues:
{checklist}

Checklist rules:
- a checklist match still requires actor-specific evidence in this article — the same standard as every other label;
- never add a label because it is rare, listed here, or plausible for the actor's role;
- do not drop a supported frequent label to make room for rare ones; report everything supported.

{_OUTPUT_CONTRACT}

DEMONSTRATIONS (from training data; follow the same evidence standard and output format):

{demo_block}"""


# ============================================================
# Verifier — precision-oriented candidate verification
# ============================================================

def build_verifier_system_prompt(tax: Taxonomy) -> str:
    return f"""You verify candidate human-value predictions for actors in one factual news article (NTCIR-19 FEHU Task-1).
Prompt: {PROMPT_VERSION_V3} / {VARIANT_VERIFIER}

You receive the article, its actor list, and a fixed list of candidates. Each candidate names one actor (exact actor_id) and one Level-1 value (exact l1_value_id, with its official definition). Your job is candidate verification only — do NOT scan the taxonomy for new labels and do NOT add candidates.

For each candidate, judge from the article text only:
- accept = "1" if evidence specific to that actor (their actions, statements, goals, treatment, or consequences) matches the value's official definition; accept = "0" otherwise.
- direction = "1" if the actor-specific evidence promotes, protects, or realizes the value; "0" if it violates, damages, or undermines it. Choose the direction the evidence best supports even when accept = "0".

Reject candidates supported only by the actor's profession, narrative role, the article's general topic, or another actor's evidence. Do not confuse reporting or being accused of wrongdoing with committing it, or suffering harm with causing it.

{_DIRECTION_BLOCK}

OUTPUT — exactly one JSON object, nothing else (no markdown fences, no prose, no extra keys):
{{
  "guid": "<GUID copied exactly from the input>",
  "verdicts": [
    {{"actor_id": "<exact actor ID>", "l1_value_id": "<exact Level-1 ID>",
      "accept": "<'1' or '0'>", "direction": "<'1' or '0'>"}}
  ]
}}
Exactly one verdict per listed candidate — no omissions, no additions, no duplicates. All four fields are strings."""


def build_verifier_user_prompt(article: dict, candidates: List[Tuple[str, str]],
                               tax: Taxonomy) -> str:
    """Candidates: ordered list of (actor_id, l1_value_id) pairs.

    Proposed directions and proposer identities are deliberately NOT shown:
    the verifier must judge relevance and direction independently from the
    article evidence, which prevents anchoring on generator disagreements."""
    id_to_name = {}
    for actor_dict in article["actors"]:
        for name, aid in actor_dict.items():
            id_to_name[str(aid)] = name
    actor_lines = [f"- {name} | actor_id: {aid}" for aid, name in id_to_name.items()]
    cand_lines = []
    for i, (aid, l1) in enumerate(candidates, 1):
        e = tax.l1_by_id[l1]
        cand_lines.append(
            f"{i}. actor_id: {aid} ({id_to_name.get(aid, '?')}) | "
            f"l1_value_id: {l1} ({e.l1_name}) — definition: "
            f"{'; '.join(e.descriptions)}"
        )
    return f"""GUID: {article["guid"]}

TITLE: {article["title"]}

ARTICLE:
{article["content"]}

ACTORS:
{chr(10).join(actor_lines)}

CANDIDATES (verify exactly these, one verdict each):
{chr(10).join(cand_lines)}

Return only the JSON object with one verdict per candidate."""


# ============================================================
# Prompt hashing (per variant; covers system prompt + user template)
# ============================================================

_SENTINEL_ARTICLE = {
    "guid": "__V3_PROMPT_HASH_SENTINEL_GUID__",
    "title": "__V3_PROMPT_HASH_SENTINEL_TITLE__",
    "content": "__V3_PROMPT_HASH_SENTINEL_CONTENT__",
    "actors": [{"__SENTINEL_ACTOR__": "__SENTINEL_ACTOR_ID__"}],
}
_SENTINEL_CANDIDATES = [("__SENTINEL_ACTOR_ID__", "0")]


def compute_prompt_hash_a(tax: Taxonomy) -> str:
    return sha256_text("\x00".join([
        PROMPT_VERSION_V3, VARIANT_A,
        build_system_prompt_a(tax),
        build_user_prompt(_SENTINEL_ARTICLE),
    ]))


def compute_prompt_hash_b(tax: Taxonomy, rarity: dict, demos: List[dict]) -> str:
    return sha256_text("\x00".join([
        PROMPT_VERSION_V3, VARIANT_B,
        build_system_prompt_b(tax, rarity, demos),
        build_user_prompt(_SENTINEL_ARTICLE),
    ]))


def compute_prompt_hash_verifier(tax: Taxonomy) -> str:
    return sha256_text("\x00".join([
        PROMPT_VERSION_V3, VARIANT_VERIFIER,
        build_verifier_system_prompt(tax),
        build_verifier_user_prompt(_SENTINEL_ARTICLE, _SENTINEL_CANDIDATES, tax),
    ]))
