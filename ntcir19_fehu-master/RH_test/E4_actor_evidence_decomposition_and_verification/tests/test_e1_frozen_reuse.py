"""Checks that E4's global stage really is the FROZEN E1 logic.

The system prompt must be byte-identical to what a real E1 run builds, and
the E4a user prompt must be E1's own user prompt with exactly one insertion
(the evidence block) in front of E1's closing instruction.
"""

import unittest

import context
from e4_common import Taxonomy, load_frozen_e1, load_model_config
from evidence import validate_evidence
from predict_global import (_E1_CLOSING, build_e1_system_prompt,
                            build_user_prompt, candidates_from_items)
from sentence_split import split_sentences


class _NullViolations:
    def __init__(self):
        self.records = []

    def record(self, guid, stage, kind, detail):
        self.records.append((guid, stage, kind, detail))


class TestE1FrozenReuse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e1 = load_frozen_e1()
        cls.taxonomy = Taxonomy(cls.e1)
        cls.config = load_model_config()
        cls.article = context.synthetic_article()
        cls.sentences = split_sentences(cls.article["content"])
        cls.units = validate_evidence(
            {"actors": [
                {"actor_id": "A-police", "units": [
                    {"kind": "action", "sentence_ids": ["S1"],
                     "note": "arrest"}]},
                {"actor_id": "A-smuggler", "units": []},
            ]}, cls.article, cls.sentences)

    def test_system_prompt_byte_identical_to_e1(self):
        ours = build_e1_system_prompt(self.e1,
                                      self.config["e1_prompt_variant"])
        e1_own = self.e1.apply_prompt_variant(
            self.e1.build_deepseek_system_prompt(
                self.e1.load_few_shot_examples(n=2)),
            self.config["e1_prompt_variant"])
        self.assertEqual(ours, e1_own)
        # E1's repaired demos really are inside
        self.assertIn("EXAMPLES:", ours)
        self.assertIn("BALANCED TARGETED CALIBRATION", ours)

    def test_user_prompt_is_e1_plus_single_insertion(self):
        base = self.e1.build_deepseek_user_prompt(self.article)
        out = build_user_prompt(self.e1, self.article, self.units,
                                self.sentences)
        prefix = base[:base.index(_E1_CLOSING)]
        self.assertTrue(out.startswith(prefix))
        self.assertIn("Actor evidence units", out)
        self.assertIn('[u1 | action]', out)
        self.assertIn('Return ONLY a JSON object with an "items" array.', out)
        # nothing of E1's prompt before the anchor was altered
        self.assertEqual(out[:len(prefix)], prefix)

    def test_global_candidates_strict_and_recorded(self):
        violations = _NullViolations()
        items = [
            {"actor_id": "A-police", "l1_value_id": "42",
             "direction": "aligned"},
            {"actor_id": "GHOST", "l1_value_id": "42",
             "direction": "aligned"},
            {"actor_id": "A-police", "l1_value_id": "42",
             "direction": "supported"},  # non-canonical direction
        ]
        cands = candidates_from_items(items, self.article, self.units,
                                      self.taxonomy, violations, "g")
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["evidence"], ["u1"])
        kinds = [k for _, _, k, _ in violations.records]
        self.assertEqual(sorted(kinds), ["invalid_actor",
                                         "invalid_direction"])


if __name__ == "__main__":
    unittest.main()
