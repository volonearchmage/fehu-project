"""Candidate merging and fixed aggregation rules (config/aggregation_rules.json).

All decisions here are deterministic functions of (candidates, verdicts,
rules). Every kept/dropped pair is returned as an explicit decision record
so runs can write a full audit trail (decisions.jsonl).

Invariant enforced for both E4b and E4c outputs: one (actor, l1_value) pair
yields at most ONE direction; aligned and contradictory are never both
emitted (asserted before returning).
"""

from e4_common import E4ValidationError


def merge_candidates(global_cands, family_cands):
    """Union of the two views, keyed by (actor, l1, direction).

    Returns a deterministically ordered list; each entry carries cid,
    sources {"global","family"}, contributing family_ids, unioned evidence,
    and the per-view directions needed later for direction resolution.
    """
    merged = {}
    for cand in list(global_cands) + list(family_cands):
        key = (cand["actor_id"], cand["l1_value_id"], cand["direction"])
        entry = merged.setdefault(key, {
            "actor_id": cand["actor_id"],
            "l1_value_id": cand["l1_value_id"],
            "direction": cand["direction"],
            "sources": set(),
            "family_ids": [],
            "evidence": [],
            "reason": "",
        })
        entry["sources"].add(cand["source"])
        if cand["source"] == "family":
            entry["family_ids"].append(cand["family_id"])
        for ref in cand["evidence"]:
            if ref not in entry["evidence"]:
                entry["evidence"].append(ref)
        if cand["reason"] and cand["source"] == "family":
            # family reasons are per-label and evidence-grounded; prefer them
            entry["reason"] = (entry["reason"] + " | " + cand["reason"]
                               if entry["reason"] else cand["reason"])
        elif not entry["reason"]:
            entry["reason"] = cand["reason"]
    ordered = sorted(
        merged.values(),
        key=lambda c: (c["actor_id"], int(c["l1_value_id"]),
                       c["direction"] != "aligned"))
    for i, cand in enumerate(ordered, 1):
        cand["cid"] = f"c{i}"
        cand["sources"] = set(cand["sources"])
    return ordered


def _assert_single_direction(items):
    pairs = {}
    for item in items:
        key = (item["actor_id"], item["l1_value_id"])
        if key in pairs and pairs[key] != item["direction"]:
            raise E4ValidationError(
                f"aggregation bug: both directions emitted for {key}")
        pairs[key] = item["direction"]


def e4b_union(merged, rules):
    """E4b output: union of views with deterministic direction conflicts.

    Returns (items, decisions). Direction conflicts follow
    rules["e4b_direction_conflict"] == "prefer_global": keep the direction
    backed by the global view; if both or neither direction has global
    backing, prefer the one also backed by a family; still tied -> drop the
    pair (recorded).
    """
    by_pair = {}
    for cand in merged:
        by_pair.setdefault(
            (cand["actor_id"], cand["l1_value_id"]), []).append(cand)

    items, decisions = [], []
    for (aid, l1), cands in sorted(by_pair.items(),
                                   key=lambda kv: (kv[0][0], int(kv[0][1]))):
        if len(cands) == 1:
            chosen = cands[0]
        else:  # both directions proposed
            with_global = [c for c in cands if "global" in c["sources"]]
            if len(with_global) == 1:
                chosen = with_global[0]
            else:
                pool = with_global if with_global else cands
                with_family = [c for c in pool if "family" in c["sources"]]
                if len(with_family) == 1:
                    chosen = with_family[0]
                else:
                    decisions.append({
                        "pair": [aid, l1], "outcome": "dropped",
                        "rule": "e4b_direction_conflict_unresolvable",
                        "directions": sorted(c["direction"] for c in cands)})
                    continue
        items.append({"actor_id": aid, "l1_value_id": l1,
                      "direction": chosen["direction"]})
        decisions.append({
            "pair": [aid, l1], "outcome": "kept",
            "direction": chosen["direction"],
            "sources": sorted(chosen["sources"]),
            "conflict": len(cands) > 1})
    _assert_single_direction(items)
    return items, decisions


def _pair_view_opinion(cands, view):
    """The view's direction opinion for a pair: a direction or None."""
    dirs = {c["direction"] for c in cands if view in c["sources"]}
    return dirs.pop() if len(dirs) == 1 else None


def _pair_verifier_opinion(cands, verdicts):
    dirs = {verdicts[c["cid"]]["direction"] for c in cands}
    dirs.discard("uncertain")
    return dirs.pop() if len(dirs) == 1 else None


def e4c_aggregate(merged, verdicts, rules):
    """E4c output: verifier-filtered candidates + direction resolution.

    Returns (items, decisions). Per candidate: attribution rejection, then
    relevance survival by provenance (both views: KEEP/UNCERTAIN; single
    view: KEEP only). Per surviving (actor, l1) pair: strict majority over
    the non-uncertain direction opinions of {global view, family view,
    verifier}; tie or no opinion drops the pair. The verifier never adds:
    only merged candidates are considered at all.
    """
    surviving = []
    decisions = []
    reject_atts = set(rules["attribution_reject"])
    keep_uncertain_att = rules["attribution_uncertain_policy"] == "keep"

    for cand in merged:
        verdict = verdicts[cand["cid"]]
        record = {"cid": cand["cid"],
                  "pair": [cand["actor_id"], cand["l1_value_id"]],
                  "direction": cand["direction"],
                  "sources": sorted(cand["sources"]),
                  "verdict": verdict}
        if verdict["attribution"] in reject_atts:
            record.update(outcome="rejected", rule="attribution")
        elif verdict["attribution"] == "uncertain" and not keep_uncertain_att:
            record.update(outcome="rejected", rule="attribution_uncertain")
        else:
            both = {"global", "family"} <= cand["sources"]
            allowed = (rules["survival"]["both_views"] if both
                       else rules["survival"]["single_view"])
            if verdict["relevance"] in allowed:
                record.update(outcome="survived",
                              rule="both_views" if both else "single_view")
                surviving.append(cand)
            else:
                record.update(outcome="rejected",
                              rule="both_views" if both else "single_view")
        decisions.append(record)

    by_pair = {}
    for cand in surviving:
        by_pair.setdefault(
            (cand["actor_id"], cand["l1_value_id"]), []).append(cand)

    items = []
    for (aid, l1), cands in sorted(by_pair.items(),
                                   key=lambda kv: (kv[0][0], int(kv[0][1]))):
        opinions = {
            "global": _pair_view_opinion(cands, "global"),
            "family": _pair_view_opinion(cands, "family"),
            "verifier": _pair_verifier_opinion(cands, verdicts),
        }
        votes = [d for d in opinions.values() if d is not None]
        n_aligned = votes.count("aligned")
        n_contra = votes.count("contradictory")
        if n_aligned > n_contra:
            final_dir = "aligned"
        elif n_contra > n_aligned:
            final_dir = "contradictory"
        else:
            decisions.append({"pair": [aid, l1], "outcome": "dropped",
                              "rule": "direction_tie", "opinions": opinions})
            continue
        items.append({"actor_id": aid, "l1_value_id": l1,
                      "direction": final_dir})
        decisions.append({"pair": [aid, l1], "outcome": "kept",
                          "direction": final_dir, "opinions": opinions})
    _assert_single_direction(items)
    return items, decisions
