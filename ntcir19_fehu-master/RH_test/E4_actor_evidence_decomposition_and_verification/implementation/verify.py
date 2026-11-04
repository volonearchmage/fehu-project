"""E4c verifier: independent judgment of E4b candidates.

One API call per article, covering every merged candidate. The verifier can
only judge — the verdict set must cover the candidate ID set EXACTLY (a
missing or extra verdict is a structural error: retried, then a hard fail),
which enforces "the verifier must not add labels" mechanically.
"""

import json

from e4_common import (ATTRIBUTIONS, DIRECTION_VERDICTS, RELEVANCE_VERDICTS,
                       E4SchemaError, load_template, render_template,
                       render_actor_block)
from evidence import render_units
from sentence_split import render_numbered, visible_sids


def render_candidates(merged, taxonomy, sibling_map, actor_names):
    """Render merged candidates (with cids) for the verifier prompt."""
    lines = []
    for cand in merged:
        siblings = ", ".join(
            f"{sib}: {taxonomy.l1_id_to_name[sib]}"
            for sib in sibling_map[cand["l1_value_id"]])
        sources = "+".join(sorted(cand["sources"]))
        lines.append(json.dumps({
            "cid": cand["cid"],
            "actor": f"{actor_names[cand['actor_id']]} "
                     f"(ID: {cand['actor_id']})",
            "value": f"{cand['l1_value_id']}: "
                     f"{taxonomy.l1_id_to_name[cand['l1_value_id']]}",
            "claimed_direction": cand["direction"],
            "evidence": cand["evidence"],
            "reason": cand["reason"],
            "found_by": sources,
            "closest_confusable_values": siblings,
        }, ensure_ascii=False))
    return "\n".join(lines)


def build_prompts(article, sentences, units_by_actor, merged, taxonomy,
                  sibling_map):
    actor_names = {aid: name for d in article["actors"]
                   for name, aid in d.items()}
    system = load_template("verifier_system.txt")
    user = render_template(load_template("verifier_user.txt"), {
        "TITLE": article["title"],
        "NUMBERED_SENTENCES": render_numbered(
            sentences, visible_sids(article["content"], sentences)),
        "ACTORS": render_actor_block(article),
        "EVIDENCE_UNITS": render_units(units_by_actor, article, sentences),
        "CANDIDATES": render_candidates(merged, taxonomy, sibling_map,
                                        actor_names),
    })
    return system, user


def validate_verdicts(obj, expected_cids):
    """Return {cid: verdict}; exact cid coverage and valid enums required."""
    if "verdicts" not in obj or not isinstance(obj["verdicts"], list):
        raise E4SchemaError('missing/invalid "verdicts" array')
    out = {}
    for v in obj["verdicts"]:
        if not isinstance(v, dict) or "cid" not in v:
            raise E4SchemaError(f"bad verdict entry: {v!r}")
        cid = str(v["cid"])
        if cid not in expected_cids:
            raise E4SchemaError(
                f"verdict for unknown candidate {cid!r} (the verifier must "
                "not add candidates)")
        if cid in out:
            raise E4SchemaError(f"duplicate verdict for {cid!r}")
        rel = v.get("relevance")
        att = v.get("attribution")
        direction = v.get("direction")
        if rel not in RELEVANCE_VERDICTS:
            raise E4SchemaError(f"{cid}: bad relevance {rel!r}")
        if att not in ATTRIBUTIONS:
            raise E4SchemaError(f"{cid}: bad attribution {att!r}")
        if direction not in DIRECTION_VERDICTS:
            raise E4SchemaError(f"{cid}: bad direction {direction!r}")
        note = v.get("sibling_note", "")
        if note is not None and not isinstance(note, str):
            raise E4SchemaError(f"{cid}: sibling_note must be a string")
        out[cid] = {"relevance": rel, "attribution": att,
                    "direction": direction,
                    "sibling_note": (note or "").strip()}
    missing = expected_cids - set(out)
    if missing:
        raise E4SchemaError(
            f"verdicts missing for candidates {sorted(missing)}")
    return out
