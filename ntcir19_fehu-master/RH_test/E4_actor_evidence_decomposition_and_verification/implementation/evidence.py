"""E4a stage 1: actor-specific evidence extraction (no value labels).

The model organizes exact sentence IDs into typed evidence units per actor.
Validation is all-or-nothing per response: any structural or referential
problem (missing/unknown actor, unknown kind, invalid sentence ID, wrong
keys, value-label leakage keys) raises E4SchemaError, which the call layer
retries and then hard-fails. Evidence is never partially accepted, so every
accepted evidence set is fully traceable to real sentence IDs and covers
every actor.
"""

from e4_common import (EVIDENCE_KINDS, E4SchemaError, load_template,
                       render_template, render_actor_block)
from sentence_split import render_numbered, visible_sids

# Keys that would smuggle value predictions into the evidence stage.
_FORBIDDEN_UNIT_KEYS = {"l1_value_id", "l1_value", "l2_value", "value",
                        "direction", "label"}
_REQUIRED_UNIT_KEYS = {"kind", "sentence_ids", "note"}


def build_prompts(article, sentences):
    system = load_template("evidence_system.txt")
    user = render_template(load_template("evidence_user.txt"), {
        "TITLE": article["title"],
        "NUMBERED_SENTENCES": render_numbered(
            sentences, visible_sids(article["content"], sentences)),
        "ACTORS": render_actor_block(article),
    })
    return system, user


def validate_evidence(obj, article, sentences):
    """Validate one evidence response; return normalized units_by_actor.

    Returns {actor_id: [{"uid","kind","sentence_ids","note"}, ...]} with
    globally numbered unit IDs (u1, u2, ... in response order).
    Raises E4SchemaError on ANY problem (retried by the call layer).
    """
    valid_sids = {s["sid"] for s in sentences}
    valid_actors = {aid for _, aid in
                    (pair for pair in _actor_pairs(article))}
    if "actors" not in obj or not isinstance(obj["actors"], list):
        raise E4SchemaError('missing/invalid "actors" array')

    units_by_actor = {}
    uid_counter = 0
    for block in obj["actors"]:
        if not isinstance(block, dict) or "actor_id" not in block \
                or "units" not in block:
            raise E4SchemaError(f"bad actor block: {block!r}")
        aid = str(block["actor_id"])
        if aid not in valid_actors:
            raise E4SchemaError(f"unknown actor_id {aid!r}")
        if aid in units_by_actor:
            raise E4SchemaError(f"duplicate actor block for {aid!r}")
        if not isinstance(block["units"], list):
            raise E4SchemaError(f'"units" not a list for actor {aid!r}')
        units = []
        for unit in block["units"]:
            if not isinstance(unit, dict):
                raise E4SchemaError(f"unit not an object: {unit!r}")
            keys = set(unit)
            leaked = keys & _FORBIDDEN_UNIT_KEYS
            if leaked:
                raise E4SchemaError(
                    f"evidence unit contains value-label keys {sorted(leaked)} "
                    "(evidence stage must not predict labels)")
            if keys != _REQUIRED_UNIT_KEYS:
                raise E4SchemaError(
                    f"unit keys {sorted(keys)} != required "
                    f"{sorted(_REQUIRED_UNIT_KEYS)}")
            if unit["kind"] not in EVIDENCE_KINDS:
                raise E4SchemaError(f"unknown evidence kind {unit['kind']!r}")
            sids = unit["sentence_ids"]
            if not isinstance(sids, list) or not sids:
                raise E4SchemaError(
                    f"unit sentence_ids must be a non-empty list: {sids!r}")
            bad = [s for s in sids if s not in valid_sids]
            if bad:
                raise E4SchemaError(
                    f"unit references nonexistent sentence IDs {bad}")
            if not isinstance(unit["note"], str):
                raise E4SchemaError("unit note must be a string")
            uid_counter += 1
            units.append({
                "uid": f"u{uid_counter}",
                "kind": unit["kind"],
                "sentence_ids": [str(s) for s in sids],
                "note": unit["note"].strip(),
            })
        units_by_actor[aid] = units

    missing = valid_actors - set(units_by_actor)
    if missing:
        raise E4SchemaError(
            f"actor completeness violated: missing actors {sorted(missing)}")
    return units_by_actor


def render_units(units_by_actor, article, sentences):
    """Render the evidence block for downstream prompts.

    Each unit line carries its uid, kind, note, and the quoted original
    sentences, so downstream stages can both cite unit IDs and read the
    exact evidence text.
    """
    text_by_sid = {s["sid"]: s["text"] for s in sentences}
    lines = []
    for name, aid in _actor_pairs(article):
        lines.append(f"Actor {name} (ID: {aid}):")
        units = units_by_actor.get(aid, [])
        if not units:
            lines.append("  (no evidence units)")
            continue
        for unit in units:
            note = f" — {unit['note']}" if unit["note"] else ""
            lines.append(f"  [{unit['uid']} | {unit['kind']}]{note}")
            for sid in unit["sentence_ids"]:
                lines.append(f"    {sid}: \"{text_by_sid[sid]}\"")
    return "\n".join(lines)


def all_unit_ids(units_by_actor, actor_id=None):
    if actor_id is not None:
        return [u["uid"] for u in units_by_actor.get(actor_id, [])]
    return [u["uid"] for units in units_by_actor.values() for u in units]


def _actor_pairs(article):
    for actor_dict in article["actors"]:
        for name, aid in actor_dict.items():
            yield name, aid
