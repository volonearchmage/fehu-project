import unittest

import context  # noqa: F401
from aggregate import e4b_union, e4c_aggregate, merge_candidates
from e4_common import E4SchemaError, load_aggregation_rules
from verify import validate_verdicts

RULES = load_aggregation_rules()


def gcand(aid, l1, direction):
    return {"actor_id": aid, "l1_value_id": l1, "direction": direction,
            "evidence": ["u1"], "reason": "global", "source": "global"}


def fcand(aid, l1, direction, fam="conservation"):
    return {"actor_id": aid, "l1_value_id": l1, "direction": direction,
            "evidence": ["S1"], "reason": "family reason", "source": "family",
            "family_id": fam}


def verdict(rel="KEEP", att="actor", direction="aligned"):
    return {"relevance": rel, "attribution": att, "direction": direction,
            "sibling_note": ""}


class TestMerge(unittest.TestCase):
    def test_merge_unions_views_and_orders_deterministically(self):
        merged = merge_candidates(
            [gcand("A", "42", "aligned"), gcand("A", "22", "contradictory")],
            [fcand("A", "42", "aligned"), fcand("B", "26", "aligned")])
        keys = [(c["actor_id"], c["l1_value_id"], c["direction"])
                for c in merged]
        self.assertEqual(keys, [("A", "22", "contradictory"),
                                ("A", "42", "aligned"),
                                ("B", "26", "aligned")])
        self.assertEqual([c["cid"] for c in merged], ["c1", "c2", "c3"])
        both = merged[1]
        self.assertEqual(both["sources"], {"global", "family"})
        self.assertEqual(both["evidence"], ["u1", "S1"])

    def test_merge_is_stable_under_input_order(self):
        a = merge_candidates([gcand("A", "42", "aligned")],
                             [fcand("B", "26", "aligned")])
        b = merge_candidates([gcand("A", "42", "aligned")],
                             [fcand("B", "26", "aligned")])
        self.assertEqual([(c["cid"], c["actor_id"]) for c in a],
                         [(c["cid"], c["actor_id"]) for c in b])


class TestE4bUnion(unittest.TestCase):
    def test_plain_union(self):
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("B", "26", "aligned")])
        items, _ = e4b_union(merged, RULES)
        self.assertEqual(len(items), 2)

    def test_direction_conflict_prefers_global(self):
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("A", "42", "contradictory")])
        items, decisions = e4b_union(merged, RULES)
        self.assertEqual(items, [{"actor_id": "A", "l1_value_id": "42",
                                  "direction": "aligned"}])
        self.assertTrue(any(d.get("conflict") for d in decisions))

    def test_double_global_conflict_dropped(self):
        merged = merge_candidates(
            [gcand("A", "42", "aligned"), gcand("A", "42", "contradictory")],
            [])
        items, decisions = e4b_union(merged, RULES)
        self.assertEqual(items, [])
        self.assertEqual(decisions[0]["rule"],
                         "e4b_direction_conflict_unresolvable")

    def test_double_global_resolved_by_family_backing(self):
        merged = merge_candidates(
            [gcand("A", "42", "aligned"), gcand("A", "42", "contradictory")],
            [fcand("A", "42", "contradictory")])
        items, _ = e4b_union(merged, RULES)
        self.assertEqual(items[0]["direction"], "contradictory")

    def test_never_both_directions(self):
        merged = merge_candidates(
            [gcand("A", "42", "aligned")],
            [fcand("A", "42", "aligned"), fcand("A", "42", "contradictory")])
        items, _ = e4b_union(merged, RULES)
        pairs = [(i["actor_id"], i["l1_value_id"]) for i in items]
        self.assertEqual(len(pairs), len(set(pairs)))


class TestE4cAggregate(unittest.TestCase):
    def test_both_views_survive_uncertain(self):
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("A", "42", "aligned")])
        verdicts = {"c1": verdict(rel="UNCERTAIN")}
        items, _ = e4c_aggregate(merged, verdicts, RULES)
        self.assertEqual(len(items), 1)

    def test_single_view_needs_keep(self):
        merged = merge_candidates([], [fcand("A", "42", "aligned")])
        items, decisions = e4c_aggregate(
            merged, {"c1": verdict(rel="UNCERTAIN")}, RULES)
        self.assertEqual(items, [])
        self.assertEqual(decisions[0]["outcome"], "rejected")
        items, _ = e4c_aggregate(merged, {"c1": verdict(rel="KEEP")}, RULES)
        self.assertEqual(len(items), 1)

    def test_drop_removed_even_for_both_views(self):
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("A", "42", "aligned")])
        items, _ = e4c_aggregate(merged, {"c1": verdict(rel="DROP")}, RULES)
        self.assertEqual(items, [])

    def test_attribution_rejection_overrides_keep(self):
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("A", "42", "aligned")])
        items, decisions = e4c_aggregate(
            merged, {"c1": verdict(att="quoted_speaker")}, RULES)
        self.assertEqual(items, [])
        self.assertEqual(decisions[0]["rule"], "attribution")

    def test_direction_repair_by_verifier_majority(self):
        # views say aligned; verifier says contradictory -> 1 vs 2? no:
        # global=aligned, family=aligned, verifier=contradictory -> aligned.
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("A", "42", "aligned")])
        items, _ = e4c_aggregate(
            merged, {"c1": verdict(direction="contradictory")}, RULES)
        self.assertEqual(items[0]["direction"], "aligned")
        # single view + verifier agree on flip? single view aligned,
        # verifier contradictory -> 1-1 tie -> pair dropped.
        merged = merge_candidates([gcand("A", "42", "aligned")], [])
        items, decisions = e4c_aggregate(
            merged, {"c1": verdict(direction="contradictory")}, RULES)
        self.assertEqual(items, [])
        self.assertEqual(decisions[-1]["rule"], "direction_tie")

    def test_opposite_direction_candidates_resolved_to_one(self):
        # global says aligned, family says contradictory, both KEEP;
        # verifier direction contradictory on both candidates ->
        # votes: global aligned, family contradictory, verifier contradictory
        merged = merge_candidates([gcand("A", "42", "aligned")],
                                  [fcand("A", "42", "contradictory")])
        verdicts = {"c1": verdict(direction="contradictory"),
                    "c2": verdict(direction="contradictory")}
        items, _ = e4c_aggregate(merged, verdicts, RULES)
        self.assertEqual(items, [{"actor_id": "A", "l1_value_id": "42",
                                  "direction": "contradictory"}])

    def test_uncertain_verifier_direction_ignored(self):
        merged = merge_candidates([gcand("A", "42", "aligned")], [])
        items, _ = e4c_aggregate(
            merged, {"c1": verdict(direction="uncertain")}, RULES)
        self.assertEqual(items[0]["direction"], "aligned")

    def test_verifier_cannot_add(self):
        with self.assertRaisesRegex(E4SchemaError, "must not add"):
            validate_verdicts(
                {"verdicts": [
                    {"cid": "c1", "relevance": "KEEP", "attribution": "actor",
                     "direction": "aligned"},
                    {"cid": "c99", "relevance": "KEEP",
                     "attribution": "actor", "direction": "aligned"}]},
                {"c1"})

    def test_verdicts_must_cover_all_candidates(self):
        with self.assertRaisesRegex(E4SchemaError, "missing"):
            validate_verdicts({"verdicts": []}, {"c1"})

    def test_verdict_enums_validated(self):
        with self.assertRaisesRegex(E4SchemaError, "bad relevance"):
            validate_verdicts(
                {"verdicts": [{"cid": "c1", "relevance": "MAYBE",
                               "attribution": "actor",
                               "direction": "aligned"}]}, {"c1"})


if __name__ == "__main__":
    unittest.main()
