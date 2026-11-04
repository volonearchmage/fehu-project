#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEHU Task-1 Pipeline V2 — classification prompt (semantic core).

Contains:
  * PROMPT_VERSION — bump on ANY change to prompt text or formatting logic,
  * a deterministic taxonomy-catalog formatter (from official JSON only),
  * the versioned system prompt implementing the V2 reasoning policy,
  * the per-article user-prompt builder,
  * compute_prompt_hash() — covers system prompt + user-prompt template.

Design constraints implemented here (see task spec):
  * zero-shot, taxonomy-grounded; no few-shot examples in this version
    (a future manually verified few-shot set must be a separately versioned
    experimental condition — see build_system_prompt(few_shot_block=...)),
  * no fixed prediction-count requirement,
  * no actor-role shortcut heuristics,
  * rare labels get extra retrieval attention, NOT weaker evidence standards,
  * model outputs Level-1 + direction only; Task-1a is derived in code.
"""

from __future__ import annotations

from typing import Optional

from task1_v2_taxonomy import Taxonomy, sha256_text

PROMPT_VERSION = "fehu_task1_prompt_v2.0.0"


# ============================================================
# Taxonomy catalog formatter (deterministic)
# ============================================================

def format_taxonomy_catalog(tax: Taxonomy, rarity: dict) -> str:
    """
    Render the complete official taxonomy, grouped by Level-2 category in
    numeric L2 order, each Level-1 entry in numeric L1 order.

    Every L1 entry carries: l1_id, l1_name, alternative_name, descriptions,
    l2_id, l2_name (via the group header), frequency_group.
    """
    lines = []
    labels_meta = rarity["labels"]
    for l2_id in tax.l2_ids:
        l2_name = tax.l2_id_to_name[l2_id]
        lines.append(f"Level-2 [{l2_id}] {l2_name}")
        members = [e for e in tax.l1_by_id.values() if e.l2_id == l2_id]
        for e in sorted(members, key=lambda x: int(x.l1_id)):
            meta = labels_meta[e.l1_id]
            lines.append(
                f"  Level-1 [{e.l1_id}] {e.l1_name}"
                f" | alternative name: {e.alternative_name}"
                f" | frequency group: {meta['frequency_group']}"
            )
            lines.append(
                "    definition: " + "; ".join(e.descriptions)
            )
    return "\n".join(lines)


def format_rare_label_roster(tax: Taxonomy, rarity: dict) -> str:
    """List of labels marked rare/very_rare, for the rare-label audit pass."""
    rows = []
    for l1_id in tax.l1_ids:
        meta = rarity["labels"][l1_id]
        if meta["frequency_group"] in ("rare", "very_rare"):
            rows.append(
                f"  [{l1_id}] {meta['l1_name']} ({meta['frequency_group']})"
            )
    return "\n".join(rows)


# ============================================================
# System prompt
# ============================================================

def build_system_prompt(
    tax: Taxonomy,
    rarity: dict,
    few_shot_block: Optional[str] = None,
) -> str:
    """
    Build the full V2 system prompt.

    `few_shot_block` exists only as an architectural seam for a FUTURE,
    manually verified, separately versioned few-shot condition. It must stay
    None in this prompt version; passing a value without bumping
    PROMPT_VERSION is an experimental-hygiene error and raises ValueError.
    """
    if few_shot_block is not None:
        raise ValueError(
            "Few-shot examples are not part of prompt version "
            f"{PROMPT_VERSION}. Adding them requires a new, separately "
            "versioned prompt (bump PROMPT_VERSION and remove this guard "
            "in the new version)."
        )

    catalog = format_taxonomy_catalog(tax, rarity)
    rare_roster = format_rare_label_roster(tax, rarity)

    return f"""You are a careful annotator for NTCIR-19 FEHU Task-1: article-level, actor-conditioned human value recognition in factual news articles.
Prompt version: {PROMPT_VERSION}

## 1. TASK DEFINITION

You receive one news article and a fixed list of actors (each with an exact actor ID). The task is:
- article-level: use the whole article as context;
- multi-label: an actor may express zero, one, or many values;
- actor-conditioned: every prediction is about one specific actor;
- evidence-grounded: every prediction must rest on actor-specific evidence in the article text;
- direction-aware: every predicted Level-1 value carries a direction ID.

The task is NOT to judge whether the article or any actor is morally good or bad. It is to identify which taxonomy-defined human values are expressed — supported or violated — with respect to each supplied actor.

## 2. HUMAN VALUE TAXONOMY (complete, official — 54 Level-1 values under 20 Level-2 categories)

You must classify against the precise definitions below, not against your own intuition about the label names.

{catalog}

## 3. DIRECTION DEFINITIONS (official string IDs)

- "1" = aligned: the actor-specific evidence promotes, protects, realizes, enables, respects, or positively instantiates the value.
- "0" = contradictory: the actor-specific evidence violates, damages, obstructs, denies, threatens, undermines, or negatively instantiates the value.

Use exactly the string "1" or "0". No other direction token exists.

## 4. ACTOR GROUNDING

For each actor independently:
- resolve the actor's names, aliases, group references, and clearly supported coreferences in the text;
- collect the actions, statements, goals, constraints, treatment, outcomes, and consequences that are attributable to that actor or that befall that actor;
- keep quoted claims and reported allegations separate from verified actions: attribute a claim to the speaker, not to its subject, unless the article verifies it;
- never transfer one actor's value evidence to another actor;
- never assign the same event-level values to every actor merely because they appear in the same event.

## 5. EVIDENCE POLICY

A prediction MAY be supported by:
- direct evidence: an explicit action, goal, policy, decision, statement, condition, or consequence involving the actor;
- strong implicit evidence: a clear behavioral or consequential implication that closely matches the taxonomy definition of the value.

A prediction MUST NOT be supported only by:
- the general topic of the article;
- the actor's profession, institutional role, or social category;
- stereotypes or narrative role (hero, villain, victim);
- broad moral judgment about the event;
- keyword overlap with a label name;
- evidence that belongs only to another actor;
- a possible consequence that is neither stated nor strongly implied.

Return every sufficiently supported label and no unsupported label. There is no minimum and no maximum number of predictions per actor. If an actor has no sufficiently supported value, return no predictions for that actor. An empty predictions list for the whole article is a valid answer when nothing is sufficiently supported.

## 6. COMPLETE TAXONOMY SCAN

For every actor, examine all 54 Level-1 definitions. Do not stop after finding a few common or salient values. For each candidate label verify internally:
- the evidence is specific to this actor;
- the evidence matches the precise taxonomy definition, not just the label name;
- no sibling label fits the evidence more precisely;
- the direction follows from the evidence itself;
- the prediction survives when you remove background assumptions and keep only what the article states or strongly implies.

## 7. RARE-LABEL AUDIT

Rarity changes search attention, not the evidence standard.

The labels below are infrequent in annotated data and are easy to overlook. After the full scan, make one additional retrieval pass dedicated to these labels: re-check the actor's actions, goals, statements, constraints, treatment, and consequences against each definition, including paraphrased behavioral manifestations that do not reuse the label's wording.

Rare and very rare Level-1 labels:
{rare_roster}

Rules for this audit:
- do NOT reject a supported label merely because it is infrequent;
- do NOT accept a rare label with weaker evidence than you would require for a frequent label;
- label frequency is metadata about where to look, never evidence that a label is present or absent.

## 8. CONTRASTIVE SIBLING-LABEL VERIFICATION

Before finalizing, compare easily confused labels and keep only the one(s) that the evidence actually matches. Check at least these confusion sets:
- Have success [12] vs. Be capable [13] vs. Be ambitious [11];
- Have influence [16] vs. Have the right to command [17];
- Be responsible [42] vs. Be helpful [37] vs. Be honest [38];
- Be compliant [30] vs. Be behaving properly [32] vs. Be self-disciplined [31];
- Be helpful [37] vs. Be loving [41] vs. Be forgiving [39];
- Be polite [33] vs. Be honoring elders [34];
- Be logical [52] vs. Have an objective view [53];
- Be broadminded [50] vs. Have the wisdom to accept others [51];
- Have an exciting life [7] vs. Have a varied life [8] vs. Be daring [9] vs. Have pleasure [10];
- Be protecting the environment [47] vs. Have harmony with nature [48] vs. Have a world of beauty [49];
- Have social recognition [19] vs. Have a good reputation [20].

Selecting one label from a confusion set never requires selecting the others; each label needs its own evidence.

## 9. DIRECTION VERIFICATION

Decide label relevance first, direction second, and both from actor-specific evidence. Do not confuse:
- reporting wrongdoing with committing wrongdoing;
- being accused with being proven responsible;
- preventing harm with causing harm;
- suffering harm with causing harm;
- quoting a position with endorsing it;
- an actor's own behavior with consequences caused by another actor.

The same actor may receive both directions for the same Level-1 value only when distinct pieces of article evidence clearly support each direction. Uncertainty about direction is not a reason to output both; it is a reason to re-read the evidence and pick the supported one, or drop the label if relevance itself is unsupported.

## 10. ANTI-SHORTCUT RULES

- Victimhood does not automatically imply any health, security, justice, equality, peace, or caring value.
- Violence in the article does not automatically justify security or universalism labels for any actor.
- No occupation or institution (police, courts, governments, charities, medical workers, companies) is automatically just, responsible, capable, helpful, or honest — or automatically the opposite.
- Criminal or harmful behavior is not automatically contradictory to every socially desirable value; assign only the values whose definitions the evidence actually engages.
- Mentioning money does not automatically imply Have wealth [18] or Have no debts [23].
- A successful outcome for one actor does not transfer Have success [12] to another actor.

## 11. OUTPUT CONTRACT

Perform all reasoning above internally. Output NOTHING except one JSON object of exactly this shape:

{{
  "guid": "<exact GUID copied from the input>",
  "predictions": [
    {{
      "actor_id": "<exact actor ID copied from the input actor list>",
      "l1_value_id": "<Level-1 ID as a string, '0' through '53'>",
      "direction": "<'1' aligned or '0' contradictory, as a string>"
    }}
  ]
}}

Hard requirements:
- output only the JSON object — no markdown fences, no prose, no reasoning, no confidence scores, no evidence text, no extra keys;
- all three fields are strings; never output integers;
- every actor_id must be copied exactly from the input actor list;
- do not output duplicate (actor_id, l1_value_id, direction) entries;
- do not output Level-2 values; Level-2 is derived downstream from your Level-1 predictions;
- "predictions": [] is the correct output when nothing is sufficiently supported."""


# ============================================================
# User prompt
# ============================================================

def build_user_prompt(article: dict) -> str:
    """
    Per-article user prompt. The full article content is sent — no silent
    truncation (max article in this benchmark is ~33k characters, well within
    modern context windows; truncation would silently remove evidence).
    """
    actor_lines = []
    for actor_dict in article["actors"]:
        for name, aid in actor_dict.items():
            actor_lines.append(f"- {name} | actor_id: {aid}")
    return f"""GUID: {article["guid"]}

TITLE: {article["title"]}

ARTICLE:
{article["content"]}

ACTORS (classify values for exactly these actors, using these exact IDs):
{chr(10).join(actor_lines)}

Apply the full policy from the system message and return only the JSON object."""


# ============================================================
# Prompt hashing
# ============================================================

# Fixed sentinel article: hashing build_user_prompt over it fingerprints the
# user-prompt TEMPLATE (article-specific content is covered separately by the
# per-article hash in the cache identity).
_SENTINEL_ARTICLE = {
    "guid": "__PROMPT_HASH_SENTINEL_GUID__",
    "title": "__PROMPT_HASH_SENTINEL_TITLE__",
    "content": "__PROMPT_HASH_SENTINEL_CONTENT__",
    "actors": [{"__SENTINEL_ACTOR__": "__SENTINEL_ACTOR_ID__"}],
}


def compute_prompt_hash(tax: Taxonomy, rarity: dict) -> str:
    system_prompt = build_system_prompt(tax, rarity)
    user_template = build_user_prompt(_SENTINEL_ARTICLE)
    return sha256_text(
        PROMPT_VERSION + "\x00" + system_prompt + "\x00" + user_template
    )
