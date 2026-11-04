#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for FEHU Task-1 Pipeline V2. No API calls, no paid services.

Run from project root:
    python -m unittest tests.test_task1_prompt_v2 -v
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from task1_v2_taxonomy import (  # noqa: E402
    load_taxonomy, build_rarity_metadata, compute_article_hash, N_L1, N_L2,
)
from prompts_task1_v2 import (  # noqa: E402
    PROMPT_VERSION, build_system_prompt, build_user_prompt, compute_prompt_hash,
)
from task1_v2_schema import (  # noqa: E402
    ERR_API, ERR_EMPTY, ERR_JSON, ERR_SCHEMA, ERR_SEMANTIC,
    parse_response_json, validate_response_object,
    sorted_task1b_values, derive_task1a_values, build_response_json_schema,
)
from run_pipeline_prompt_v2 import (  # noqa: E402
    ProviderTransientError, process_article, cache_identity, cache_key,
    CacheStore, filter_by_guids,
)

TAX = load_taxonomy()
RARITY = build_rarity_metadata(TAX)
SYSTEM_PROMPT = build_system_prompt(TAX, RARITY)
PROMPT_HASH = compute_prompt_hash(TAX, RARITY)

ARTICLE = {
    "guid": "test-guid-1",
    "title": "Test title",
    "content": "Alice helped Bob rebuild the flooded school.",
    "actors": [{"Alice": "a-1"}, {"Bob": "a-2"}],
}

VALID_RESPONSE = {
    "guid": "test-guid-1",
    "predictions": [
        {"actor_id": "a-1", "l1_value_id": "37", "direction": "1"},
        {"actor_id": "a-2", "l1_value_id": "22", "direction": "0"},
    ],
}


def new_counters():
    return {k: 0 for k in (
        "api_calls", "cache_hits", "retries_api", "retries_empty",
        "retries_json", "retries_schema", "retries_semantic")}


def run_with_responses(responses, max_retries=3):
    """process_article with a scripted fake provider. Each element of
    `responses` is either a string (raw model text) or an Exception."""
    seq = list(responses)

    def call_fn(messages, json_schema):
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    counters = new_counters()
    outcome = process_article(
        ARTICLE, SYSTEM_PROMPT, TAX, call_fn, max_retries, counters,
        sleep_fn=lambda s: None,
    )
    return outcome, counters


# ============================================================
# Taxonomy
# ============================================================

class TestTaxonomy(unittest.TestCase):
    def test_taxonomy_completeness(self):
        self.assertEqual(len(TAX.l1_by_id), N_L1)
        self.assertEqual(len(TAX.l2_id_to_name), N_L2)
        for e in TAX.l1_by_id.values():
            self.assertTrue(e.l1_name)
            self.assertTrue(e.alternative_name)
            self.assertTrue(e.descriptions)
            self.assertTrue(e.l2_name)

    def test_l1_id_range(self):
        self.assertEqual(TAX.l1_ids, [str(i) for i in range(54)])

    def test_l2_id_range(self):
        self.assertEqual(TAX.l2_ids, [str(i) for i in range(20)])

    def test_complete_l1_to_l2_mapping(self):
        self.assertEqual(set(TAX.l1_id_to_l2_id.keys()), set(TAX.l1_by_id.keys()))
        self.assertTrue(set(TAX.l1_id_to_l2_id.values()) <= set(TAX.l2_id_to_name.keys()))

    def test_exact_direction_mapping(self):
        self.assertEqual(TAX.direction_mapping,
                         {"aligned": "1", "contradictory": "0"})

    def test_rarity_metadata_covers_all_labels(self):
        self.assertEqual(set(RARITY["labels"].keys()), set(TAX.l1_by_id.keys()))
        for meta in RARITY["labels"].values():
            self.assertIn(meta["frequency_group"],
                          ("frequent", "medium", "rare", "very_rare"))
            self.assertIsInstance(meta["train_gold_count"], int)


# ============================================================
# Prompt content
# ============================================================

class TestPrompt(unittest.TestCase):
    def test_prompt_contains_taxonomy_descriptions(self):
        # Official description strings from human_value_taxonomy.json.
        self.assertIn("allowing for more creativity or imagination", SYSTEM_PROMPT)
        self.assertIn("alternative name:", SYSTEM_PROMPT)
        # All 54 L1 names present.
        for e in TAX.l1_by_id.values():
            self.assertIn(e.l1_name, SYSTEM_PROMPT)

    def test_prompt_contains_rare_label_metadata(self):
        self.assertIn("frequency group", SYSTEM_PROMPT)
        self.assertIn("very_rare", SYSTEM_PROMPT)
        self.assertIn(
            "Rarity changes search attention, not the evidence standard.",
            SYSTEM_PROMPT)

    def test_prompt_has_no_fixed_label_count(self):
        for banned in ("3-7", "3 to 7", "three to seven"):
            self.assertNotIn(banned, SYSTEM_PROMPT)
        self.assertIn("no minimum and no maximum number of predictions",
                      SYSTEM_PROMPT)

    def test_prompt_has_no_actor_role_shortcuts(self):
        for banned in ("often aligned with", "often contradicted",
                       "often contradictory", "Common patterns",
                       "Law enforcement/authorities",
                       "Victims/affected people"):
            self.assertNotIn(banned, SYSTEM_PROMPT)

    def test_prompt_uses_official_direction_ids(self):
        self.assertIn('"1" = aligned', SYSTEM_PROMPT)
        self.assertIn('"0" = contradictory', SYSTEM_PROMPT)

    def test_few_shot_guard(self):
        with self.assertRaises(ValueError):
            build_system_prompt(TAX, RARITY, few_shot_block="example text")

    def test_user_prompt_contains_full_article_and_actors(self):
        up = build_user_prompt(ARTICLE)
        self.assertIn(ARTICLE["guid"], up)
        self.assertIn(ARTICLE["content"], up)
        self.assertIn("a-1", up)
        self.assertIn("a-2", up)

    def test_prompt_hash_stable(self):
        self.assertEqual(PROMPT_HASH, compute_prompt_hash(TAX, RARITY))


# ============================================================
# Schema / semantic validation
# ============================================================

class TestValidation(unittest.TestCase):
    def check(self, obj):
        return validate_response_object(obj, ARTICLE, TAX, retry=1)

    def test_valid_response_passes(self):
        self.assertEqual(self.check(VALID_RESPONSE), [])

    def test_valid_empty_predictions_passes(self):
        self.assertEqual(self.check({"guid": "test-guid-1", "predictions": []}), [])

    def test_incorrect_guid_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["guid"] = "other-guid"
        issues = self.check(bad)
        self.assertTrue(any(i.field == "guid" and i.error_type == ERR_SEMANTIC
                            for i in issues))

    def test_unknown_actor_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["predictions"][0]["actor_id"] = "not-an-actor"
        issues = self.check(bad)
        self.assertTrue(any("actor_id" in i.field and i.error_type == ERR_SEMANTIC
                            for i in issues))

    def test_invalid_l1_id_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["predictions"][0]["l1_value_id"] = "54"
        issues = self.check(bad)
        self.assertTrue(any("l1_value_id" in i.field for i in issues))

    def test_integer_id_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["predictions"][0]["l1_value_id"] = 37
        issues = self.check(bad)
        self.assertTrue(any(i.error_type == ERR_SCHEMA and "l1_value_id" in i.field
                            for i in issues))

    def test_invalid_direction_rejected_not_normalized(self):
        for bad_dir in ("aligned", "contradictory", "2", "yes", ""):
            bad = copy.deepcopy(VALID_RESPONSE)
            bad["predictions"][0]["direction"] = bad_dir
            issues = self.check(bad)
            self.assertTrue(
                any("direction" in i.field and i.error_type == ERR_SEMANTIC
                    for i in issues),
                f"direction {bad_dir!r} must be rejected, never normalized")

    def test_unexpected_top_level_field_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["reasoning"] = "should not be here"
        issues = self.check(bad)
        self.assertTrue(any(i.error_type == ERR_SCHEMA for i in issues))

    def test_unexpected_item_field_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["predictions"][0]["confidence"] = 0.9
        issues = self.check(bad)
        self.assertTrue(any(i.error_type == ERR_SCHEMA for i in issues))

    def test_duplicate_prediction_rejected(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["predictions"].append(dict(bad["predictions"][0]))
        issues = self.check(bad)
        self.assertTrue(any("Duplicate" in i.reason for i in issues))

    def test_top_level_list_not_wrapped(self):
        issues = self.check([VALID_RESPONSE])
        self.assertTrue(any(i.error_type == ERR_SCHEMA for i in issues))

    def test_no_markdown_stripping(self):
        raw = "```json\n" + json.dumps(VALID_RESPONSE) + "\n```"
        obj, issues = parse_response_json(raw, "test-guid-1", 1)
        self.assertIsNone(obj)
        self.assertEqual(issues[0].error_type, ERR_JSON)

    def test_empty_response_is_failure(self):
        obj, issues = parse_response_json("   ", "test-guid-1", 1)
        self.assertIsNone(obj)
        self.assertEqual(issues[0].error_type, ERR_EMPTY)

    def test_structured_error_fields(self):
        bad = copy.deepcopy(VALID_RESPONSE)
        bad["predictions"][0]["direction"] = "maybe"
        d = self.check(bad)[0].to_dict()
        for key in ("guid", "error_type", "field", "invalid_value",
                    "reason", "retry"):
            self.assertIn(key, d)
        self.assertEqual(d["guid"], "test-guid-1")
        self.assertEqual(d["retry"], 1)


# ============================================================
# Deterministic post-processing
# ============================================================

class TestPostProcessing(unittest.TestCase):
    def test_deterministic_sorting(self):
        preds = [
            {"actor_id": "a-2", "l1_value_id": "5", "direction": "1"},
            {"actor_id": "a-1", "l1_value_id": "42", "direction": "1"},
            {"actor_id": "a-1", "l1_value_id": "42", "direction": "0"},
            {"actor_id": "a-1", "l1_value_id": "3", "direction": "1"},
        ]
        rows = sorted_task1b_values(ARTICLE, preds)
        self.assertEqual(rows, [
            {"actor": "a-1", "l1_value": "3", "direction": "1"},
            {"actor": "a-1", "l1_value": "42", "direction": "0"},
            {"actor": "a-1", "l1_value": "42", "direction": "1"},
            {"actor": "a-2", "l1_value": "5", "direction": "1"},
        ])
        # Deterministic: same input, same output.
        self.assertEqual(rows, sorted_task1b_values(ARTICLE, preds))

    def test_deterministic_task1a_generation(self):
        # L1 "37" (Be helpful) and "41" (Be loving) share L2 "14"
        # (Benevolence: caring) → one Task-1a row after dedup.
        self.assertEqual(TAX.l1_id_to_l2_id["37"], "14")
        self.assertEqual(TAX.l1_id_to_l2_id["41"], "14")
        t1b = sorted_task1b_values(ARTICLE, [
            {"actor_id": "a-1", "l1_value_id": "37", "direction": "1"},
            {"actor_id": "a-1", "l1_value_id": "41", "direction": "1"},
            {"actor_id": "a-2", "l1_value_id": "45", "direction": "0"},
        ])
        t1a = derive_task1a_values(ARTICLE, t1b, TAX)
        self.assertEqual(t1a, [
            {"actor": "a-1", "l2_value": "14"},
            {"actor": "a-2", "l2_value": "16"},
        ])
        self.assertEqual(t1a, derive_task1a_values(ARTICLE, t1b, TAX))

    def test_response_json_schema_is_article_specific(self):
        schema = build_response_json_schema(ARTICLE, TAX)
        props = schema["schema"]["properties"]
        self.assertEqual(props["guid"]["enum"], ["test-guid-1"])
        item_props = props["predictions"]["items"]["properties"]
        self.assertEqual(item_props["actor_id"]["enum"], ["a-1", "a-2"])
        self.assertEqual(item_props["direction"]["enum"], ["0", "1"])
        self.assertEqual(len(item_props["l1_value_id"]["enum"]), 54)


# ============================================================
# Failure policy — failures are never empty predictions
# ============================================================

class TestFailurePolicy(unittest.TestCase):
    def test_api_failure_not_converted_to_empty_prediction(self):
        outcome, counters = run_with_responses(
            [ProviderTransientError("boom")] * 3)
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.predictions)  # never [] on failure
        self.assertEqual(counters["retries_api"], 3)
        self.assertTrue(all(i["error_type"] == ERR_API for i in outcome.issues))

    def test_schema_failure_not_converted_to_empty_prediction(self):
        outcome, _ = run_with_responses(["not json at all"] * 3)
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.predictions)
        self.assertTrue(any(i["error_type"] == ERR_JSON for i in outcome.issues))

    def test_semantic_failure_not_converted_to_empty_prediction(self):
        bad = json.dumps({"guid": "wrong-guid", "predictions": []})
        outcome, counters = run_with_responses([bad] * 3)
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.predictions)
        self.assertEqual(counters["retries_semantic"], 3)

    def test_valid_empty_predictions_is_success(self):
        raw = json.dumps({"guid": "test-guid-1", "predictions": []})
        outcome, _ = run_with_responses([raw])
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.predictions, [])

    def test_correction_retry_recovers(self):
        outcome, counters = run_with_responses(
            ["garbage", json.dumps(VALID_RESPONSE)])
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.attempts, 2)
        self.assertEqual(counters["retries_json"], 1)
        # First failed attempt is still recorded.
        self.assertEqual(len(outcome.issues), 1)
        self.assertEqual(len(outcome.raw_attempts), 2)

    def test_transient_then_success(self):
        outcome, counters = run_with_responses(
            [ProviderTransientError("net"), json.dumps(VALID_RESPONSE)])
        self.assertTrue(outcome.success)
        self.assertEqual(counters["retries_api"], 1)
        self.assertEqual(counters["api_calls"], 2)


# ============================================================
# Cache identity
# ============================================================

class TestCache(unittest.TestCase):
    def identity(self, **overrides):
        ident = cache_identity("deepseek", "deepseek-v4-flash", PROMPT_HASH,
                               TAX.taxonomy_hash, RARITY["rarity_hash"], ARTICLE)
        ident.update(overrides)
        return ident

    def test_prompt_change_causes_cache_miss(self):
        a = self.identity()
        b = self.identity(prompt_hash="deadbeef" * 8)
        self.assertNotEqual(cache_key(a), cache_key(b))

    def test_taxonomy_change_causes_cache_miss(self):
        a = self.identity()
        b = self.identity(taxonomy_hash="deadbeef" * 8)
        self.assertNotEqual(cache_key(a), cache_key(b))

    def test_rarity_change_causes_cache_miss(self):
        a = self.identity()
        b = self.identity(rarity_hash="deadbeef" * 8)
        self.assertNotEqual(cache_key(a), cache_key(b))

    def test_article_change_causes_cache_miss(self):
        modified = copy.deepcopy(ARTICLE)
        modified["content"] += " Extra sentence."
        a = self.identity()
        b = cache_identity("deepseek", "deepseek-v4-flash", PROMPT_HASH,
                           TAX.taxonomy_hash, RARITY["rarity_hash"], modified)
        self.assertNotEqual(compute_article_hash(ARTICLE),
                            compute_article_hash(modified))
        self.assertNotEqual(cache_key(a), cache_key(b))

    def test_model_and_provider_change_cause_cache_miss(self):
        a = self.identity()
        self.assertNotEqual(cache_key(a), cache_key(self.identity(model="other")))
        self.assertNotEqual(cache_key(a), cache_key(self.identity(provider="openai")))

    def test_failed_entry_never_reused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            store = CacheStore(Path(tmp) / "cache.json")
            ident = self.identity()
            store.store(ident, success=False, predictions=None,
                        error_types=[ERR_API])
            self.assertIsNone(store.lookup(ident))
            # Same identity, successful entry → reused.
            store.store(ident, success=True,
                        predictions=VALID_RESPONSE["predictions"])
            hit = store.lookup(ident)
            self.assertIsNotNone(hit)
            self.assertEqual(hit["predictions"], VALID_RESPONSE["predictions"])

    def test_identity_mismatch_never_reused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            store = CacheStore(Path(tmp) / "cache.json")
            ident = self.identity()
            store.store(ident, success=True,
                        predictions=VALID_RESPONSE["predictions"])
            other = self.identity(prompt_hash="deadbeef" * 8)
            self.assertIsNone(store.lookup(other))


# ============================================================
# Dev evaluation filtering
# ============================================================

class TestEvaluationFiltering(unittest.TestCase):
    def test_limited_dev_eval_filters_gold_to_same_guids(self):
        from evaluation import parse_task1a
        gold = parse_task1a(str(BASE_DIR / "dataset" / "gold_labels" / "dev"
                                / "dev_human_values.json"))
        all_guids = {k[0] for k in gold}
        subset = set(list(sorted(all_guids))[:5])
        filtered = filter_by_guids(gold, subset)
        self.assertTrue(filtered)
        self.assertEqual({k[0] for k in filtered}, subset)
        # No filter → unchanged.
        self.assertEqual(filter_by_guids(gold, None), gold)


if __name__ == "__main__":
    unittest.main()
