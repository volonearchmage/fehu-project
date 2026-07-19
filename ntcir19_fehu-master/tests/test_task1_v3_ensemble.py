#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Pipeline V3 ensemble logic, verifier validation, and frozen
label-aware policies. No API calls.

Run from project root:
    python -m unittest tests.test_task1_v3_ensemble -v
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from task1_v2_taxonomy import load_taxonomy, build_rarity_metadata  # noqa: E402
from task1_v2_schema import ERR_SCHEMA, ERR_SEMANTIC  # noqa: E402
from task1_v3_ensemble import (  # noqa: E402
    POLICY_VERSION, STAGE_NAMES, preds_to_tuples, analyze_pairs,
    verifier_candidates, classify_pair, candidates_hash,
    validate_verifier_response, verdicts_from_response,
    build_verifier_json_schema, build_stage_sets, apply_policy,
    tuples_to_prediction_items, load_policy, policy_label_strategies,
    check_policy_compatibility, PolicyValidationError,
    REQUIRED_POLICY_PROVENANCE,
    compute_pair_diagnostics, final_contribution_by_stage,
)

TAX = load_taxonomy()
RARITY = build_rarity_metadata(TAX)

ARTICLE = {
    "guid": "g-1",
    "title": "t",
    "content": "c",
    "actors": [{"Alice": "a-1"}, {"Bob": "a-2"}],
}

A = {("a-1", "37", "1"), ("a-2", "22", "0"), ("a-1", "45", "1")}
B = {("a-1", "37", "1"), ("a-2", "22", "0"), ("a-1", "45", "0"),
     ("a-2", "9", "1")}
# pairs: (a-1,37) agreed; (a-2,22) agreed; (a-1,45) direction conflict;
# (a-2,9) single support from B.


def make_verdict(actor, l1, accept, direction):
    return {"actor_id": actor, "l1_value_id": l1,
            "accept": accept, "direction": direction}


def valid_verifier_obj(candidates, accept="1", direction="1"):
    return {"guid": "g-1",
            "verdicts": [make_verdict(a, l, accept, direction)
                         for a, l in candidates]}


def make_policy(labels=None, default_strategy="verified", **calib_overrides):
    calib = {f: f"{f}-value" for f in REQUIRED_POLICY_PROVENANCE}
    calib["temperature"] = 0.0
    calib["prompt_hashes"] = {"variant_a_concise": "ha", "variant_b_recall": "hb",
                              "verifier": "hv"}
    calib["verifier_enabled"] = True
    calib.update(calib_overrides)
    return {
        "policy_version": POLICY_VERSION,
        "default_strategy": default_strategy,
        "labels": labels or {},
        "calibration": calib,
    }


# ============================================================
# Pair analysis
# ============================================================

class TestPairAnalysis(unittest.TestCase):
    def test_analyze_and_classify(self):
        pairs = analyze_pairs(A, B)
        self.assertEqual(classify_pair(*pairs[("a-1", "37")]), "agreed")
        self.assertEqual(classify_pair(*pairs[("a-1", "45")]),
                         "direction_conflict")
        self.assertEqual(classify_pair(*pairs[("a-2", "9")]), "single_b")
        self.assertEqual(classify_pair(frozenset({"1"}), frozenset()),
                         "single_a")
        self.assertEqual(classify_pair(frozenset({"0", "1"}),
                                       frozenset({"1"})), "partial")

    def test_verifier_candidates_ordered_and_uncertain_only(self):
        pairs = analyze_pairs(A, B)
        cands = verifier_candidates(pairs, ARTICLE)
        self.assertEqual(cands, [("a-1", "45"), ("a-2", "9")])
        self.assertEqual(candidates_hash(cands), candidates_hash(list(cands)))

    def test_preds_roundtrip(self):
        items = tuples_to_prediction_items(A)
        self.assertEqual(preds_to_tuples(items), A)


# ============================================================
# Stage assembly / ensemble rules
# ============================================================

class TestStageSets(unittest.TestCase):
    def stages(self, verdicts):
        return build_stage_sets(A, B, analyze_pairs(A, B), verdicts)

    def test_ab_agreement_always_accepted(self):
        st = self.stages(verdicts=None)
        for t in (("a-1", "37", "1"), ("a-2", "22", "0")):
            for stage in ("intersection", "union", "verified"):
                self.assertIn(t, st[stage])

    def test_no_verifier_verified_equals_intersection(self):
        st = self.stages(verdicts=None)
        self.assertEqual(st["verified"], st["intersection"])
        self.assertNotIn(("a-1", "45", "1"), st["verified"])
        self.assertNotIn(("a-1", "45", "0"), st["verified"])

    def test_direction_conflict_resolved_by_verifier(self):
        verdicts = {("a-1", "45"): {"accept": "1", "direction": "0"},
                    ("a-2", "9"): {"accept": "0", "direction": "1"}}
        st = self.stages(verdicts)
        self.assertIn(("a-1", "45", "0"), st["verified"])
        self.assertNotIn(("a-1", "45", "1"), st["verified"])
        # rejected single-support candidate stays out
        self.assertNotIn(("a-2", "9", "1"), st["verified"])

    def test_single_support_needs_verifier_accept(self):
        verdicts = {("a-1", "45"): {"accept": "0", "direction": "1"},
                    ("a-2", "9"): {"accept": "1", "direction": "1"}}
        st = self.stages(verdicts)
        self.assertIn(("a-2", "9", "1"), st["verified"])
        self.assertNotIn(("a-1", "45", "1"), st["verified"])

    def test_verifier_direction_flip_creates_tuple_outside_union(self):
        verdicts = {("a-1", "45"): {"accept": "1", "direction": "0"},
                    ("a-2", "9"): {"accept": "1", "direction": "0"}}
        st = self.stages(verdicts)
        self.assertIn(("a-2", "9", "0"), st["verified"])
        self.assertNotIn(("a-2", "9", "0"), st["union"])

    def test_both_direction_full_agreement_kept(self):
        a = {("a-1", "37", "0"), ("a-1", "37", "1")}
        st = build_stage_sets(a, set(a), analyze_pairs(a, set(a)), None)
        self.assertEqual(st["verified"], a)

    def test_partial_overlap_keeps_common_direction(self):
        a = {("a-1", "37", "0"), ("a-1", "37", "1")}
        b = {("a-1", "37", "1")}
        pairs = analyze_pairs(a, b)
        # verifier rejects → common direction survives, disputed one doesn't
        st = build_stage_sets(a, b, pairs,
                              {("a-1", "37"): {"accept": "0", "direction": "0"}})
        self.assertEqual(st["verified"], {("a-1", "37", "1")})


# ============================================================
# Verifier response validation (strict)
# ============================================================

class TestVerifierValidation(unittest.TestCase):
    CANDS = [("a-1", "45"), ("a-2", "9")]

    def check(self, obj):
        return validate_verifier_response(obj, ARTICLE, TAX, self.CANDS, 1)

    def test_valid_passes(self):
        self.assertEqual(self.check(valid_verifier_obj(self.CANDS)), [])
        v = verdicts_from_response(valid_verifier_obj(self.CANDS))
        self.assertEqual(v[("a-1", "45")], {"accept": "1", "direction": "1"})

    def test_missing_candidate_rejected(self):
        obj = valid_verifier_obj(self.CANDS[:1])
        issues = self.check(obj)
        self.assertTrue(any("Missing verdicts" in i.reason for i in issues))

    def test_added_candidate_rejected(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["verdicts"].append(make_verdict("a-1", "37", "1", "1"))
        issues = self.check(obj)
        self.assertTrue(any("must not add candidates" in i.reason
                            for i in issues))

    def test_duplicate_verdict_rejected(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["verdicts"].append(dict(obj["verdicts"][0]))
        issues = self.check(obj)
        self.assertTrue(any("Duplicate verdict" in i.reason for i in issues))

    def test_invalid_accept_token_rejected(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["verdicts"][0]["accept"] = "yes"
        issues = self.check(obj)
        self.assertTrue(any(i.error_type == ERR_SEMANTIC and "accept" in i.field
                            for i in issues))

    def test_invalid_direction_rejected_not_normalized(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["verdicts"][0]["direction"] = "aligned"
        issues = self.check(obj)
        self.assertTrue(any("direction" in i.field for i in issues))

    def test_extra_keys_rejected(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["confidence"] = 0.5
        self.assertTrue(any(i.error_type == ERR_SCHEMA
                            for i in self.check(obj)))
        obj2 = valid_verifier_obj(self.CANDS)
        obj2["verdicts"][0]["why"] = "because"
        self.assertTrue(any(i.error_type == ERR_SCHEMA
                            for i in self.check(obj2)))

    def test_wrong_guid_rejected(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["guid"] = "other"
        self.assertTrue(any(i.field == "guid" for i in self.check(obj)))

    def test_non_string_field_rejected(self):
        obj = valid_verifier_obj(self.CANDS)
        obj["verdicts"][0]["accept"] = 1
        self.assertTrue(any(i.error_type == ERR_SCHEMA
                            for i in self.check(obj)))

    def test_json_schema_shape(self):
        schema = build_verifier_json_schema(ARTICLE, self.CANDS)
        props = schema["schema"]["properties"]
        self.assertEqual(props["guid"]["enum"], ["g-1"])
        item = props["verdicts"]["items"]["properties"]
        self.assertEqual(sorted(item["actor_id"]["enum"]), ["a-1", "a-2"])
        self.assertEqual(item["accept"]["enum"], ["0", "1"])


# ============================================================
# Offline diagnostics
# ============================================================

class TestPairDiagnostics(unittest.TestCase):
    VERDICTS = {("a-1", "45"): {"accept": "1", "direction": "0"},
                ("a-2", "9"): {"accept": "1", "direction": "1"}}

    def diag(self, verdicts="default"):
        if verdicts == "default":
            verdicts = self.VERDICTS
        return compute_pair_diagnostics(A, B, analyze_pairs(A, B),
                                        verdicts, RARITY)

    def test_agreement_and_complementarity_counts(self):
        d = self.diag()
        self.assertFalse(d["ab_exact_agreement"])
        # |A∩B| = 2, |A∪B| = 5
        self.assertAlmostEqual(d["tuple_jaccard"], 2 / 5)
        # pairs proposed by both: (a-1,37), (a-2,22), (a-1,45); dir-agreed: 2
        self.assertEqual(d["pairs_proposed_by_both"], 3)
        self.assertEqual(d["pairs_direction_agreed"], 2)
        self.assertEqual(d["tuples_only_a"], 1)      # (a-1,45,1)
        self.assertEqual(d["tuples_only_b"], 2)      # (a-1,45,0),(a-2,9,1)
        self.assertEqual(d["labels_only_a"], ["1:45"])
        self.assertEqual(d["labels_only_b"], ["0:45", "1:9"])

    def test_rare_labels_added_by_b_uses_train_rarity(self):
        d = self.diag()
        # l1=9 (Be daring) is train-rare; l1=45 (Be just) is not.
        self.assertEqual(RARITY["labels"]["9"]["frequency_group"] in
                         ("rare", "very_rare"), True)
        self.assertEqual(d["rare_labels_added_by_b"], ["1:9"])

    def test_verifier_category_split(self):
        d = self.diag()
        vb = d["verifier_by_category"]
        self.assertEqual(vb["direction_conflict"],
                         {"candidates": 1, "accepted": 1})   # (a-1,45)
        self.assertEqual(vb["single_b"],
                         {"candidates": 1, "accepted": 1})   # (a-2,9)
        self.assertEqual(vb["single_a"], {"candidates": 0, "accepted": 0})
        self.assertEqual(d["conflict_direction_decisions"],
                         {"accepted_direction_0": 1, "accepted_direction_1": 0,
                          "rejected": 0})

    def test_no_verifier_yields_zero_verifier_stats(self):
        d = self.diag(verdicts=None)
        for cat in d["verifier_by_category"].values():
            self.assertEqual(cat, {"candidates": 0, "accepted": 0})

    def test_diagnostics_deterministic(self):
        self.assertEqual(self.diag(), self.diag())

    def test_final_contribution_by_stage(self):
        stages = build_stage_sets(A, B, analyze_pairs(A, B), self.VERDICTS)
        final = apply_policy(stages, {"1:45": "variant_a"}, "verified")
        contrib = final_contribution_by_stage(final, stages)
        # 2 agreed tuples; 2 verifier-accepted; 1 policy override (1:45 via A).
        self.assertEqual(contrib, {"from_generator_agreement": 2,
                                   "from_verifier_acceptance": 2,
                                   "from_label_policy_override": 1})
        self.assertEqual(sum(contrib.values()), len(final))


# ============================================================
# Frozen label-aware policy
# ============================================================

class TestPolicy(unittest.TestCase):
    def stages(self):
        verdicts = {("a-1", "45"): {"accept": "1", "direction": "1"},
                    ("a-2", "9"): {"accept": "0", "direction": "1"}}
        return build_stage_sets(A, B, analyze_pairs(A, B), verdicts)

    def test_default_policy_is_verified(self):
        st = self.stages()
        final = apply_policy(st, {}, "verified")
        self.assertEqual(final, st["verified"])

    def test_label_override_variant_b(self):
        st = self.stages()
        # ("a-2","9","1") was rejected by the verifier, but a frozen policy
        # trusting variant_b for label 1:9 admits it.
        final = apply_policy(st, {"1:9": "variant_b"}, "verified")
        self.assertIn(("a-2", "9", "1"), final)

    def test_drop_strategy_suppresses_label(self):
        st = self.stages()
        final = apply_policy(st, {"1:37": "drop"}, "verified")
        self.assertNotIn(("a-1", "37", "1"), final)
        self.assertIn(("a-2", "22", "0"), final)

    def test_direction_specific_keys(self):
        st = self.stages()
        final = apply_policy(st, {"0:22": "drop"}, "verified")
        self.assertNotIn(("a-2", "22", "0"), final)
        # 1:22 untouched (not predicted anyway)

    def test_invalid_default_strategy_raises(self):
        with self.assertRaises(ValueError):
            apply_policy(self.stages(), {}, "drop")

    def test_load_policy_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "policy.json"

            good = make_policy(labels={"1:9": {"strategy": "variant_b"}})
            p.write_text(json.dumps(good), encoding="utf-8")
            loaded = load_policy(p)
            self.assertEqual(policy_label_strategies(loaded),
                             {"1:9": "variant_b"})

            bad_version = copy.deepcopy(good)
            bad_version["policy_version"] = "v0"
            p.write_text(json.dumps(bad_version), encoding="utf-8")
            with self.assertRaises(PolicyValidationError):
                load_policy(p)

            bad_strategy = copy.deepcopy(good)
            bad_strategy["labels"]["1:9"]["strategy"] = "majority_vote"
            p.write_text(json.dumps(bad_strategy), encoding="utf-8")
            with self.assertRaises(PolicyValidationError):
                load_policy(p)

            bad_key = copy.deepcopy(good)
            bad_key["labels"]["2:9"] = {"strategy": "union"}
            p.write_text(json.dumps(bad_key), encoding="utf-8")
            with self.assertRaises(PolicyValidationError):
                load_policy(p)

            no_prov = copy.deepcopy(good)
            del no_prov["calibration"]["gold_sha256"]
            p.write_text(json.dumps(no_prov), encoding="utf-8")
            with self.assertRaises(PolicyValidationError):
                load_policy(p)

            with self.assertRaises(PolicyValidationError):
                load_policy(Path(tmp) / "missing.json")

    def test_policy_compatibility_check(self):
        policy = make_policy(model="deepseek-v4-flash")
        run_identity = {f: f"{f}-value" for f in REQUIRED_POLICY_PROVENANCE}
        run_identity.update({
            "model": "deepseek-v4-flash", "temperature": 0.0,
            "prompt_hashes": {"variant_a_concise": "ha",
                              "variant_b_recall": "hb", "verifier": "hv"},
            "verifier_enabled": True,
        })
        self.assertEqual(check_policy_compatibility(policy, run_identity), [])

        run_identity["model"] = "deepseek-v4-pro"
        mism = check_policy_compatibility(policy, run_identity)
        self.assertTrue(any("model" in m for m in mism))

        run_identity["model"] = "deepseek-v4-flash"
        run_identity["prompt_hashes"] = dict(run_identity["prompt_hashes"],
                                             variant_a_concise="OTHER")
        mism = check_policy_compatibility(policy, run_identity)
        self.assertTrue(any("prompt_hashes[variant_a_concise]" in m
                            for m in mism))


if __name__ == "__main__":
    unittest.main()
