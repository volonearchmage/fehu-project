"""E4a stage 2 / E4b global view: the FROZEN E1 prediction logic plus the
actor evidence units.

The system prompt is built by the frozen E1 module itself (same few-shot
demos, same variant text) and is therefore byte-identical to a real E1 run's
system prompt — asserted in the offline tests. The user prompt is E1's own
user prompt with ONE insertion: the evidence-unit block, spliced in front of
E1's closing instruction by an assert-exactly-once anchor replacement (the
same auditable technique the E1/E3a build scripts use). Parsing and
submission-format conversion for the E4a output reuse E1's parse_model_json
and process_results unchanged.
"""

from e4_common import (DIRECTIONS, E4SchemaError, E4ValidationError)
from evidence import all_unit_ids, render_units

# E1's DeepSeek user prompt ends with exactly this line (frozen anchor).
_E1_CLOSING = ('Identify the human values for each actor. '
               'Return ONLY a JSON object with an "items" array.')

_EVIDENCE_PREFIX = (
    "Actor evidence units (organized from the article's original sentences; "
    "S# IDs refer to sentences in reading order, u# IDs name the units):\n")

_EVIDENCE_SUFFIX = (
    "\n\nWork through each actor's evidence units one at a time so no "
    "actor-specific value is missed, then identify the human values for "
    'each actor. Return ONLY a JSON object with an "items" array.')


def build_e1_system_prompt(e1, variant):
    """Byte-identical to a frozen E1 run's system prompt."""
    few_shot = e1.load_few_shot_examples(n=2)
    if [ex["guid"] for ex in few_shot] != ["0-4349-1-t", "0-4352-3-1"]:
        raise E4ValidationError(
            "frozen E1 few-shot demo guids changed: "
            f"{[ex['guid'] for ex in few_shot]}")
    prompt = e1.build_deepseek_system_prompt(few_shot)
    return e1.apply_prompt_variant(prompt, variant)


def build_user_prompt(e1, article, units_by_actor, sentences):
    """E1's user prompt + evidence block, via assert-once anchor surgery."""
    base = e1.build_deepseek_user_prompt(article)
    count = base.count(_E1_CLOSING)
    if count != 1:
        raise E4ValidationError(
            f"E1 user-prompt anchor found {count} times (expected 1); the "
            "frozen E1 prompt shape has changed — refusing to guess")
    evidence_block = render_units(units_by_actor, article, sentences)
    return base.replace(
        _E1_CLOSING,
        _EVIDENCE_PREFIX + evidence_block + _EVIDENCE_SUFFIX)


def validate_items(obj, final):
    """Structural validation of the E1-format response ({"items": [...]}).

    Kept to E1's own tolerance (E1's parser accepts the items and its
    process_results drops invalid entries): here we only require the object
    shape, so the frozen E1 downstream behavior is preserved for E4a.
    """
    if "items" not in obj or not isinstance(obj["items"], list):
        raise E4SchemaError('missing/invalid "items" array')
    for item in obj["items"]:
        if not isinstance(item, dict):
            raise E4SchemaError(f"item not an object: {item!r}")
    return obj["items"]


def candidates_from_items(items, article, units_by_actor, taxonomy,
                          violations, guid):
    """Convert raw E1-format items into strict E4b global-view candidates.

    The frozen E1 logic emits (actor_id, l1_value_id, direction) with no
    per-label evidence, so global candidates carry the actor's full evidence
    unit list as their evidence reference. Items E1's own process_results
    would drop (invalid actor/l1) are rejected here too, but recorded as
    violations instead of vanishing; non-canonical directions are rejected
    (E1's parser would coerce them to "aligned" — for candidate provenance we
    refuse to guess).
    """
    valid_actors = {aid for d in article["actors"] for aid in d.values()}
    candidates = []
    seen = set()
    for item in items:
        aid = str(item.get("actor_id", ""))
        l1 = str(item.get("l1_value_id", ""))
        direction = item.get("direction", "")
        if aid not in valid_actors:
            violations.record(guid, "global", "invalid_actor",
                              {"item": item})
            continue
        if not taxonomy.valid_l1(l1):
            violations.record(guid, "global", "invalid_l1", {"item": item})
            continue
        if direction not in DIRECTIONS:
            violations.record(guid, "global", "invalid_direction",
                              {"item": item})
            continue
        key = (aid, l1, direction)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "actor_id": aid,
            "l1_value_id": l1,
            "direction": direction,
            "evidence": all_unit_ids(units_by_actor, aid),
            "reason": "global view (frozen E1 logic; no per-label rationale)",
            "source": "global",
        })
    return candidates
