import unittest

import context
from e4_common import E4SchemaError
from evidence import all_unit_ids, render_units, validate_evidence
from sentence_split import split_sentences


def _valid_response():
    return {"actors": [
        {"actor_id": "A-police", "units": [
            {"kind": "action", "sentence_ids": ["S1"],
             "note": "arrested the smuggler"},
            {"kind": "statement", "sentence_ids": ["S3"],
             "note": "vowed to protect the public"},
        ]},
        {"actor_id": "A-smuggler", "units": [
            {"kind": "action", "sentence_ids": ["S2"],
             "note": "sold unsafe fuel"},
        ]},
    ]}


class TestEvidenceValidation(unittest.TestCase):
    def setUp(self):
        self.article = context.synthetic_article()
        self.sentences = split_sentences(self.article["content"])

    def _validate(self, obj):
        return validate_evidence(obj, self.article, self.sentences)

    def test_valid_response_normalized(self):
        units = self._validate(_valid_response())
        self.assertEqual(set(units), {"A-police", "A-smuggler"})
        self.assertEqual(all_unit_ids(units), ["u1", "u2", "u3"])
        self.assertEqual(units["A-police"][0]["kind"], "action")

    def test_missing_actor_is_schema_error(self):
        resp = _valid_response()
        resp["actors"].pop()
        with self.assertRaisesRegex(E4SchemaError, "actor completeness"):
            self._validate(resp)

    def test_empty_units_allowed_when_explicit(self):
        resp = _valid_response()
        resp["actors"][1]["units"] = []
        units = self._validate(resp)
        self.assertEqual(units["A-smuggler"], [])

    def test_unknown_actor_rejected(self):
        resp = _valid_response()
        resp["actors"].append({"actor_id": "GHOST", "units": []})
        with self.assertRaisesRegex(E4SchemaError, "unknown actor_id"):
            self._validate(resp)

    def test_nonexistent_sentence_id_rejected(self):
        resp = _valid_response()
        resp["actors"][0]["units"][0]["sentence_ids"] = ["S1", "S99"]
        with self.assertRaisesRegex(E4SchemaError, "nonexistent sentence"):
            self._validate(resp)

    def test_value_label_leakage_rejected(self):
        resp = _valid_response()
        resp["actors"][0]["units"][0]["l1_value_id"] = "42"
        with self.assertRaisesRegex(E4SchemaError, "must not predict labels"):
            self._validate(resp)

    def test_unknown_kind_rejected(self):
        resp = _valid_response()
        resp["actors"][0]["units"][0]["kind"] = "vibe"
        with self.assertRaisesRegex(E4SchemaError, "unknown evidence kind"):
            self._validate(resp)

    def test_empty_sentence_ids_rejected(self):
        resp = _valid_response()
        resp["actors"][0]["units"][0]["sentence_ids"] = []
        with self.assertRaises(E4SchemaError):
            self._validate(resp)

    def test_duplicate_actor_block_rejected(self):
        resp = _valid_response()
        resp["actors"].append(dict(resp["actors"][0]))
        with self.assertRaisesRegex(E4SchemaError, "duplicate actor"):
            self._validate(resp)

    def test_render_units_quotes_original_sentences(self):
        units = self._validate(_valid_response())
        block = render_units(units, self.article, self.sentences)
        self.assertIn("[u1 | action]", block)
        self.assertIn("Police arrested the smuggler on Monday.", block)
        self.assertIn("Actor The smuggler (ID: A-smuggler):", block)


if __name__ == "__main__":
    unittest.main()
