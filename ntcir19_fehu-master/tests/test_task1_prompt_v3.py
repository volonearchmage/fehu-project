#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for FEHU Task-1 Pipeline V3 — prompts, call loop, cache, failures.
No API calls, no paid services.

Run from project root:
    python -m unittest tests.test_task1_prompt_v3 -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from task1_v2_taxonomy import load_taxonomy, build_rarity_metadata  # noqa: E402
from task1_v2_schema import (  # noqa: E402
    ERR_API, ERR_JSON, ERR_SEMANTIC, validate_response_object,
)
from run_pipeline_prompt_v2 import ProviderTransientError, CacheStore, cache_key  # noqa: E402
from prompts_task1_v2 import (  # noqa: E402
    build_system_prompt as build_system_prompt_v2,
    build_user_prompt,
)
from prompts_task1_v3 import (  # noqa: E402
    PROMPT_VERSION_V3, VARIANT_A, VARIANT_B, VARIANT_VERIFIER,
    build_system_prompt_a, build_system_prompt_b, build_verifier_system_prompt,
    build_verifier_user_prompt, select_demonstrations,
    compute_prompt_hash_a, compute_prompt_hash_b, compute_prompt_hash_verifier,
    TRAIN_ARTICLES_PATH,
)
from run_pipeline_prompt_v3 import (  # noqa: E402
    ProviderConfigError, ERR_API_CONFIG, run_validated_call, cache_identity_v3,
    RunContext, process_article_v3, compute_run_status, calibration_split,
    GENERATOR_CONTRACT_HINT, COUNTER_KEYS, RUN_COMPLETE, RUN_INCOMPLETE,
    RUN_FAILED,
)

TAX = load_taxonomy()
RARITY = build_rarity_metadata(TAX)
DEMOS, DEMO_PROV = select_demonstrations(TAX, RARITY, n=2)
PROMPT_A = build_system_prompt_a(TAX)
PROMPT_B = build_system_prompt_b(TAX, RARITY, DEMOS)
PROMPT_V = build_verifier_system_prompt(TAX)
PROMPT_V2 = build_system_prompt_v2(TAX, RARITY)

ARTICLE = {
    "guid": "test-guid-1",
    "title": "Test title",
    "content": "Alice helped Bob rebuild the flooded school.",
    "actors": [{"Alice": "a-1"}, {"Bob": "a-2"}],
}

VALID_A = json.dumps({"guid": "test-guid-1", "predictions": [
    {"actor_id": "a-1", "l1_value_id": "37", "direction": "1"},
    {"actor_id": "a-2", "l1_value_id": "22", "direction": "0"},
]})
VALID_B_SAME = VALID_A
VALID_B_EXTRA = json.dumps({"guid": "test-guid-1", "predictions": [
    {"actor_id": "a-1", "l1_value_id": "37", "direction": "1"},
    {"actor_id": "a-2", "l1_value_id": "22", "direction": "0"},
    {"actor_id": "a-1", "l1_value_id": "9", "direction": "1"},
]})
VERDICT_ACCEPT_9 = json.dumps({"guid": "test-guid-1", "verdicts": [
    {"actor_id": "a-1", "l1_value_id": "9", "accept": "1", "direction": "1"},
]})


def new_counters():
    return {k: 0 for k in COUNTER_KEYS}


def scripted_call_fn(responses):
    """Each element: raw text (str) or an Exception. Returns (text, usage)."""
    seq = list(responses)

    def call(messages, json_schema):
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, {"prompt_tokens": 10, "completion_tokens": 5}

    return call


def run_generator(responses, max_retries=3):
    counters = new_counters()
    outcome = run_validated_call(
        stage=VARIANT_A, guid="test-guid-1", system_prompt=PROMPT_A,
        user_prompt=build_user_prompt(ARTICLE),
        validate_fn=lambda obj, att: validate_response_object(
            obj, ARTICLE, TAX, att),
        json_schema=None, call_fn=scripted_call_fn(responses),
        max_retries=max_retries, counters=counters,
        contract_hint=GENERATOR_CONTRACT_HINT, sleep_fn=lambda s: None)
    return outcome, counters


class FakeArgs:
    provider = "deepseek"
    model = "deepseek-v4-flash"


def make_ctx(call_fn, tmpdir, use_verifier=True, max_retries=3,
             cache_path=None):
    return RunContext(
        args=FakeArgs(), tax=TAX, rarity=RARITY,
        system_prompts={VARIANT_A: PROMPT_A, VARIANT_B: PROMPT_B,
                        VARIANT_VERIFIER: PROMPT_V},
        prompt_hashes={VARIANT_A: compute_prompt_hash_a(TAX),
                       VARIANT_B: compute_prompt_hash_b(TAX, RARITY, DEMOS),
                       VARIANT_VERIFIER: compute_prompt_hash_verifier(TAX)},
        demo_set_hash=DEMO_PROV["demo_set_hash"],
        call_fn=call_fn, cache=CacheStore(cache_path),
        counters=new_counters(), lock=threading.Lock(),
        out_dir=Path(tmpdir), max_retries=max_retries,
        use_verifier=use_verifier)


# Patch sleeps once for all orchestration tests (no real waiting).
import run_pipeline_prompt_v3 as pipeline_mod  # noqa: E402
pipeline_mod.TRANSIENT_SLEEP_S = 0
pipeline_mod.CORRECTION_SLEEP_S = 0


# ============================================================
# Prompt content
# ============================================================

class TestPromptVariants(unittest.TestCase):
    def test_prompt_version_bumped_for_v3_1(self):
        self.assertEqual(PROMPT_VERSION_V3, "fehu_task1_prompt_v3.1.0")

    def test_variant_a_substantially_shorter_than_v2(self):
        self.assertLess(len(PROMPT_A), 0.65 * len(PROMPT_V2))

    def test_variant_a_preserves_full_taxonomy(self):
        for e in TAX.l1_by_id.values():
            self.assertIn(f"[{e.l1_id}] {e.l1_name}", PROMPT_A)
            for desc in e.descriptions:
                self.assertIn(desc, PROMPT_A)
        for l2_id, name in TAX.l2_id_to_name.items():
            self.assertIn(f"[{l2_id}] {name}", PROMPT_A)

    def test_variant_a_no_fixed_count_or_role_shortcuts(self):
        for banned in ("3-7", "3 to 7", "Common patterns",
                       "often aligned with", "Law enforcement"):
            self.assertNotIn(banned, PROMPT_A)
        self.assertIn("no required number of predictions", PROMPT_A)

    def test_variant_a_official_direction_ids(self):
        self.assertIn('"1" = aligned', PROMPT_A)
        self.assertIn('"0" = contradictory', PROMPT_A)

    def test_variant_b_contains_checklist_and_demos(self):
        self.assertIn("LOW-FREQUENCY CHECKLIST", PROMPT_B)
        # Checklist cues come from official taxonomy text.
        self.assertIn("Be daring", PROMPT_B)
        self.assertIn("fostering risk-taking", PROMPT_B)
        self.assertIn("never add a label because it is rare", PROMPT_B)
        for d in DEMOS:
            self.assertIn(f"train article {d['guid']}", PROMPT_B)

    def test_variant_b_contains_ported_liu_mechanisms(self):
        # Portable mechanisms adopted from the Liu audit (v3.1.0): a generic
        # two-directional cue block and a same-L2-group specificity rule.
        self.assertIn("DIRECTION CUES", PROMPT_B)
        self.assertIn("protects, provides, restores", PROMPT_B)
        self.assertIn("causes, threatens, blocks", PROMPT_B)
        self.assertIn("same Level-2 group", PROMPT_B)

    def test_checklist_labels_are_train_rare_only(self):
        # Liu's targeted-recovery list (22/26/27/19/20/13) was dev-derived;
        # the V3 checklist must contain ONLY train-rare labels.
        from prompts_task1_v3 import format_low_frequency_checklist
        import re as _re
        checklist = format_low_frequency_checklist(TAX, RARITY)
        ids = _re.findall(r"^\s*\[(\d+)\]", checklist, _re.M)
        self.assertTrue(ids)
        for l1_id in ids:
            self.assertIn(RARITY["labels"][l1_id]["frequency_group"],
                          ("rare", "very_rare"))
        for dev_derived in ("22", "26", "27", "19", "20", "13"):
            self.assertNotIn(dev_derived, ids)

    def test_no_liu_runtime_dependency_or_hardcoded_label_sets(self):
        # Liu's files are an audited data reference only: no src module may
        # import them, and no dev-selected add-label set may exist in code.
        import run_pipeline_prompt_v3 as pm
        import task1_v3_ensemble as em
        import prompts_task1_v3 as prm
        import calibrate_task1_v3 as cm
        for mod in (pm, em, prm, cm):
            src_text = Path(mod.__file__).read_text(encoding="utf-8")
            self.assertNotIn("import liu_method", src_text)
            self.assertNotIn("from liu_method", src_text)
            self.assertNotIn("DEFAULT_ADD_LABELS", src_text)
            self.assertFalse(hasattr(mod, "DEFAULT_ADD_LABELS"))

    def test_demonstrations_from_train_only_and_deterministic(self):
        train_guids = {str(a["guid"]) for a in json.loads(
            TRAIN_ARTICLES_PATH.read_text(encoding="utf-8"))}
        self.assertEqual(DEMO_PROV["source_split"], "train")
        for d in DEMOS:
            self.assertIn(d["guid"], train_guids)
        demos2, prov2 = select_demonstrations(TAX, RARITY, n=2)
        self.assertEqual([d["guid"] for d in DEMOS],
                         [d["guid"] for d in demos2])
        self.assertEqual(DEMO_PROV["demo_set_hash"], prov2["demo_set_hash"])

    def test_demo_outputs_follow_contract(self):
        # Every demo's correct output embedded in the prompt is contract-valid
        # JSON against its own article.
        from prompts_task1_v3 import _demo_output_json
        for d in DEMOS:
            obj = json.loads(_demo_output_json(d["guid"], d["article"],
                                               d["gold_tuples"]))
            issues = validate_response_object(obj, d["article"], TAX, retry=1)
            self.assertEqual(issues, [])

    def test_verifier_prompt_lists_candidates_without_directions(self):
        up = build_verifier_user_prompt(ARTICLE, [("a-1", "9")], TAX)
        self.assertIn("actor_id: a-1", up)
        self.assertIn("(Alice)", up)                    # actor name
        self.assertIn("l1_value_id: 9", up)
        self.assertIn("Be daring", up)                  # official L1 name
        for desc in TAX.l1_by_id["9"].descriptions:     # official definition
            self.assertIn(desc, up)
        self.assertIn(ARTICLE["content"], up)           # article context
        self.assertNotIn("proposed", up.lower())        # no anchor on A/B
        self.assertNotIn("variant", up.lower())         # no proposer identity
        self.assertIn("one verdict per candidate", up)

    def test_prompt_hashes_stable_and_distinct(self):
        self.assertEqual(compute_prompt_hash_a(TAX), compute_prompt_hash_a(TAX))
        hashes = {compute_prompt_hash_a(TAX),
                  compute_prompt_hash_b(TAX, RARITY, DEMOS),
                  compute_prompt_hash_verifier(TAX)}
        self.assertEqual(len(hashes), 3)


# ============================================================
# Call loop: validation, retries, config errors
# ============================================================

class TestCallLoop(unittest.TestCase):
    def test_valid_output(self):
        outcome, counters = run_generator([VALID_A])
        self.assertTrue(outcome.success)
        self.assertEqual(len(outcome.obj["predictions"]), 2)
        self.assertEqual(counters["api_calls"], 1)
        self.assertEqual(counters["prompt_tokens"], 10)

    def test_malformed_json_retries_then_fails(self):
        outcome, counters = run_generator(["not json"] * 3)
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.obj)
        self.assertEqual(counters["retries_json"], 3)

    def test_invalid_actor_id_rejected(self):
        bad = json.dumps({"guid": "test-guid-1", "predictions": [
            {"actor_id": "ghost", "l1_value_id": "37", "direction": "1"}]})
        outcome, counters = run_generator([bad] * 3)
        self.assertFalse(outcome.success)
        self.assertEqual(counters["retries_semantic"], 3)

    def test_invalid_l1_id_rejected(self):
        bad = json.dumps({"guid": "test-guid-1", "predictions": [
            {"actor_id": "a-1", "l1_value_id": "99", "direction": "1"}]})
        outcome, _ = run_generator([bad, VALID_A])
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.attempts, 2)

    def test_invalid_direction_rejected_not_normalized(self):
        bad = json.dumps({"guid": "test-guid-1", "predictions": [
            {"actor_id": "a-1", "l1_value_id": "37", "direction": "aligned"}]})
        outcome, _ = run_generator([bad] * 3)
        self.assertFalse(outcome.success)
        self.assertTrue(any(i["error_type"] == ERR_SEMANTIC
                            for i in outcome.issues))

    def test_duplicate_prediction_rejected(self):
        bad = json.dumps({"guid": "test-guid-1", "predictions": [
            {"actor_id": "a-1", "l1_value_id": "37", "direction": "1"},
            {"actor_id": "a-1", "l1_value_id": "37", "direction": "1"}]})
        outcome, _ = run_generator([bad] * 3)
        self.assertFalse(outcome.success)

    def test_api_400_config_failure_no_retry(self):
        outcome, counters = run_generator(
            [ProviderConfigError("bad model", status_code=400), VALID_A])
        self.assertFalse(outcome.success)
        self.assertTrue(outcome.config_error)
        self.assertEqual(outcome.attempts, 1)          # never retried
        self.assertEqual(counters["config_errors"], 1)
        self.assertEqual(counters["api_calls"], 1)
        self.assertEqual(outcome.issues[0]["error_type"], ERR_API_CONFIG)

    def test_transient_retry_then_success(self):
        outcome, counters = run_generator(
            [ProviderTransientError("net"), VALID_A])
        self.assertTrue(outcome.success)
        self.assertEqual(counters["retries_api"], 1)
        self.assertEqual(counters["api_calls"], 2)

    def test_failure_never_returns_empty_predictions(self):
        outcome, _ = run_generator([ProviderTransientError("net")] * 3)
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.obj)


# ============================================================
# Cache identity + resume
# ============================================================

class TestCacheV3(unittest.TestCase):
    def identity(self, **overrides):
        ident = cache_identity_v3(
            "deepseek", "deepseek-v4-flash", VARIANT_A,
            compute_prompt_hash_a(TAX), TAX.taxonomy_hash,
            RARITY["rarity_hash"], "", ARTICLE)
        ident.update(overrides)
        return ident

    def test_prompt_change_invalidates_cache(self):
        self.assertNotEqual(cache_key(self.identity()),
                            cache_key(self.identity(prompt_hash="x" * 64)))

    def test_prompt_version_bump_invalidates_cache(self):
        # An entry written under v3.0.0 must be a cache miss under v3.1.0.
        old = self.identity(prompt_version="fehu_task1_prompt_v3.0.0")
        self.assertEqual(self.identity()["prompt_version"],
                         "fehu_task1_prompt_v3.1.0")
        self.assertNotEqual(cache_key(self.identity()), cache_key(old))

    def test_variant_model_and_verifier_config_distinguish_entries(self):
        base = cache_key(self.identity())
        self.assertNotEqual(base, cache_key(self.identity(variant=VARIANT_B)))
        self.assertNotEqual(base, cache_key(self.identity(model="deepseek-v4-pro")))
        self.assertNotEqual(base, cache_key(self.identity(
            verifier_config={"enabled": True, "candidates_hash": "abc"})))
        self.assertNotEqual(base, cache_key(self.identity(demo_set_hash="d" * 64)))

    def test_failed_response_not_cached_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CacheStore(Path(tmp) / "c.json")
            ident = self.identity()
            store.store(ident, success=False, predictions=None,
                        error_types=[ERR_API])
            self.assertIsNone(store.lookup(ident))

    def test_resume_uses_cache_no_new_api_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            calls = {"n": 0}

            def counting_call(messages, json_schema):
                calls["n"] += 1
                sys_text = messages[0]["content"]
                if VARIANT_VERIFIER in sys_text:
                    return VERDICT_ACCEPT_9, None
                if VARIANT_B in sys_text:
                    return VALID_B_EXTRA, None
                return VALID_A, None

            ctx = make_ctx(counting_call, tmp, cache_path=cache_path)
            res1 = process_article_v3(ARTICLE, ctx)
            self.assertTrue(res1.success)
            first_calls = calls["n"]
            self.assertEqual(first_calls, 3)  # A + B + verifier

            # Second run (fresh context, same cache file): zero API calls.
            ctx2 = make_ctx(counting_call, tmp, cache_path=cache_path)
            res2 = process_article_v3(ARTICLE, ctx2)
            self.assertTrue(res2.success)
            self.assertEqual(calls["n"], first_calls)
            self.assertEqual(ctx2.counters["cache_hits"], 3)
            self.assertEqual(res1.stages["verified"], res2.stages["verified"])


# ============================================================
# Article orchestration + run status
# ============================================================

class TestOrchestration(unittest.TestCase):
    def test_full_agreement_no_verifier_call_needed(self):
        calls = {"verifier": 0}

        def call(messages, json_schema):
            if VARIANT_VERIFIER in messages[0]["content"]:
                calls["verifier"] += 1
                raise AssertionError("verifier must not be called")
            return VALID_A, None

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(call, tmp)
            res = process_article_v3(ARTICLE, ctx)
        self.assertTrue(res.success)
        self.assertEqual(calls["verifier"], 0)
        self.assertEqual(res.stages["verified"], res.stages["union"])

    def test_single_support_goes_through_verifier(self):
        def call(messages, json_schema):
            sys_text = messages[0]["content"]
            if VARIANT_VERIFIER in sys_text:
                return VERDICT_ACCEPT_9, None
            if VARIANT_B in sys_text:
                return VALID_B_EXTRA, None
            return VALID_A, None

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(call, tmp)
            res = process_article_v3(ARTICLE, ctx)
        self.assertTrue(res.success)
        self.assertIn(("a-1", "9", "1"), res.stages["verified"])
        self.assertNotIn(("a-1", "9", "1"), res.stages["intersection"])
        self.assertEqual(res.verifier_stats,
                         {"candidates": 1, "accepted": 1, "rejected": 0})

    def test_generator_failure_fails_article_not_empty(self):
        def call(messages, json_schema):
            if VARIANT_B in messages[0]["content"]:
                return "garbage", None
            return VALID_A, None

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(call, tmp)
            res = process_article_v3(ARTICLE, ctx)
        self.assertFalse(res.success)
        self.assertIsNone(res.stages)
        self.assertIn(ERR_JSON, res.error_types)

    def test_verifier_failure_fails_article(self):
        def call(messages, json_schema):
            sys_text = messages[0]["content"]
            if VARIANT_VERIFIER in sys_text:
                return "not json", None
            if VARIANT_B in sys_text:
                return VALID_B_EXTRA, None
            return VALID_A, None

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(call, tmp)
            res = process_article_v3(ARTICLE, ctx)
        self.assertFalse(res.success)
        self.assertIsNone(res.stages)

    def test_no_verifier_falls_back_to_intersection(self):
        def call(messages, json_schema):
            if VARIANT_B in messages[0]["content"]:
                return VALID_B_EXTRA, None
            return VALID_A, None

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(call, tmp, use_verifier=False)
            res = process_article_v3(ARTICLE, ctx)
        self.assertTrue(res.success)
        self.assertEqual(res.stages["verified"], res.stages["intersection"])
        self.assertNotIn(("a-1", "9", "1"), res.stages["verified"])

    def test_run_status_values(self):
        self.assertEqual(compute_run_status(5, 5, 0), RUN_COMPLETE)
        self.assertEqual(compute_run_status(5, 3, 2), RUN_INCOMPLETE)
        self.assertEqual(compute_run_status(5, 0, 5), RUN_FAILED)

    def test_calibration_split_deterministic_and_excludes_demos(self):
        train = json.loads(TRAIN_ARTICLES_PATH.read_text(encoding="utf-8"))
        demo_guids = {d["guid"] for d in DEMOS}
        s1 = calibration_split(train, demo_guids, 50)
        s2 = calibration_split(train, demo_guids, 50)
        self.assertEqual([a["guid"] for a in s1], [a["guid"] for a in s2])
        self.assertEqual(len(s1), 50)
        self.assertFalse({str(a["guid"]) for a in s1} & demo_guids)


if __name__ == "__main__":
    unittest.main()
