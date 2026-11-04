"""E4b family view: independent candidate scan of one taxonomy family.

Each of the four fixed families (config/taxonomy_families.json, built only
from the official L1->L2 taxonomy) is scanned in its own API call. The
prompt lists the family's Level-1 values (grouped under their official
Level-2 names) as the only assignable values, plus structurally adjacent
values from other families as explicit non-assignable contrast.

Validation policy: structural problems raise E4SchemaError (retried, then
hard fail). Item-level violations on the FINAL attempt (out-of-family value,
invalid actor/direction/evidence reference, empty evidence) reject only that
candidate and are recorded in violations.jsonl — never silently dropped.
On non-final attempts item violations also raise E4SchemaError so the model
gets a chance to correct itself.
"""

from e4_common import (DIRECTIONS, E4SchemaError, load_template,
                       render_template, render_actor_block)
from evidence import all_unit_ids, render_units
from sentence_split import render_numbered, visible_sids


def family_value_block(family, taxonomy):
    """The family's assignable values, grouped by official L2 category."""
    lines = []
    for l2_id in family["l2_ids"]:
        lines.append(f"{taxonomy.l2_id_to_name[l2_id]}:")
        for l1_id in taxonomy.l1_ids_by_l2[l2_id]:
            lines.append(f"  {l1_id}: {taxonomy.l1_id_to_name[l1_id]}")
    return "\n".join(lines)


def contrast_value_block(family, taxonomy):
    lines = []
    for l2_id in family["contrast_l2_ids"]:
        names = ", ".join(
            f"{l1_id}: {taxonomy.l1_id_to_name[l1_id]}"
            for l1_id in taxonomy.l1_ids_by_l2[l2_id])
        lines.append(f"{taxonomy.l2_id_to_name[l2_id]} — {names}")
    return "\n".join(lines)


def build_prompts(family, taxonomy, article, sentences, units_by_actor):
    system = render_template(load_template("family_system.txt"), {
        "FAMILY_NAME": family["family_name"],
        "FAMILY_VALUES": family_value_block(family, taxonomy),
        "CONTRAST_VALUES": contrast_value_block(family, taxonomy),
    })
    user = render_template(load_template("family_user.txt"), {
        "TITLE": article["title"],
        "NUMBERED_SENTENCES": render_numbered(
            sentences, visible_sids(article["content"], sentences)),
        "ACTORS": render_actor_block(article),
        "EVIDENCE_UNITS": render_units(units_by_actor, article, sentences),
    })
    return system, user


def validate_candidates(obj, final, family, article, sentences,
                        units_by_actor, taxonomy, violations, guid):
    """Validate one family response; return accepted candidate list."""
    if "candidates" not in obj or not isinstance(obj["candidates"], list):
        raise E4SchemaError('missing/invalid "candidates" array')

    valid_actors = {aid for d in article["actors"] for aid in d.values()}
    valid_refs = ({s["sid"] for s in sentences}
                  | set(all_unit_ids(units_by_actor)))
    family_l1 = set(family["l1_ids"])

    def item_problem(msg, cand):
        if not final:
            raise E4SchemaError(msg)
        violations.record(guid, f"family:{family['family_id']}", "rejected",
                          {"reason": msg, "candidate": cand})

    accepted = []
    seen = set()
    for cand in obj["candidates"]:
        if not isinstance(cand, dict):
            raise E4SchemaError(f"candidate not an object: {cand!r}")
        aid = str(cand.get("actor_id", ""))
        l1 = str(cand.get("l1_value_id", ""))
        direction = cand.get("direction", "")
        evid = cand.get("evidence", [])
        reason = cand.get("reason", "")
        if aid not in valid_actors:
            item_problem(f"unknown actor_id {aid!r}", cand)
            continue
        if not taxonomy.valid_l1(l1):
            item_problem(f"invalid l1_value_id {l1!r}", cand)
            continue
        if l1 not in family_l1:
            item_problem(
                f"out-of-family value {l1} "
                f"({taxonomy.l1_id_to_name[l1]}) proposed by "
                f"{family['family_id']}", cand)
            continue
        if direction not in DIRECTIONS:
            item_problem(f"invalid direction {direction!r}", cand)
            continue
        if not isinstance(evid, list) or not evid:
            item_problem("empty or non-list evidence", cand)
            continue
        bad_refs = [e for e in evid if str(e) not in valid_refs]
        if bad_refs:
            item_problem(f"nonexistent evidence refs {bad_refs}", cand)
            continue
        if not isinstance(reason, str) or not reason.strip():
            item_problem("missing/empty reason", cand)
            continue
        key = (aid, l1, direction)
        if key in seen:
            continue  # exact duplicate within one response: dedup only
        seen.add(key)
        accepted.append({
            "actor_id": aid,
            "l1_value_id": l1,
            "direction": direction,
            "evidence": [str(e) for e in evid],
            "reason": reason.strip(),
            "source": "family",
            "family_id": family["family_id"],
        })
    return accepted
