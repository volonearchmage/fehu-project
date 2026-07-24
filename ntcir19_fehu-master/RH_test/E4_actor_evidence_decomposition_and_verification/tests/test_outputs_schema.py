import os
import tempfile
import unittest

import context
from e4_common import E4ValidationError, Taxonomy, load_frozen_e1
from outputs import validate_pred_files, write_pred_files


class TestOutputsSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e1 = load_frozen_e1()
        cls.taxonomy = Taxonomy(cls.e1)
        cls.article = context.synthetic_article()

    def test_write_and_validate_official_files(self):
        items = [
            {"actor_id": "A-police", "l1_value_id": "42",
             "direction": "aligned"},
            {"actor_id": "A-smuggler", "l1_value_id": "22",
             "direction": "contradictory"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p1a, p1b = write_pred_files(
                self.e1, [self.article],
                {self.article["guid"]: items}, tmp)
            self.assertTrue(os.path.exists(p1a))
            self.assertTrue(os.path.exists(p1b))
            import json
            data_1b = json.load(open(p1b, encoding="utf-8"))
            hv = data_1b[0]["article_human_values"]
            self.assertEqual(
                {(v["actor"], v["l1_value"], v["direction"]) for v in hv},
                {("A-police", "42", "1"), ("A-smuggler", "22", "0")})
            data_1a = json.load(open(p1a, encoding="utf-8"))
            hv_a = data_1a[0]["article_human_values"]
            # 42 -> Benevolence: dependability (15), 22 -> Security: personal (8)
            self.assertEqual(
                {(v["actor"], v["l2_value"]) for v in hv_a},
                {("A-police", self.taxonomy.l1_id_to_l2_id["42"]),
                 ("A-smuggler", self.taxonomy.l1_id_to_l2_id["22"])})

    def test_frozen_process_results_drops_invalid_items(self):
        """E4a keeps E1's tolerance: invalid actor/l1 silently dropped by
        the FROZEN code path (E1 behavior, unchanged by design)."""
        items = [
            {"actor_id": "GHOST", "l1_value_id": "42", "direction": "aligned"},
            {"actor_id": "A-police", "l1_value_id": "99",
             "direction": "aligned"},
            {"actor_id": "A-police", "l1_value_id": "42",
             "direction": "aligned"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            _p1a, p1b = write_pred_files(
                self.e1, [self.article],
                {self.article["guid"]: items}, tmp)
            import json
            hv = json.load(open(p1b, encoding="utf-8"))[0][
                "article_human_values"]
            self.assertEqual(len(hv), 1)

    def test_missing_article_items_is_hard_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(E4ValidationError, "no assembled"):
                write_pred_files(self.e1, [self.article], {}, tmp)

    def test_validate_rejects_corrupt_direction(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            p1a, p1b = write_pred_files(
                self.e1, [self.article],
                {self.article["guid"]: [
                    {"actor_id": "A-police", "l1_value_id": "42",
                     "direction": "aligned"}]}, tmp)
            data = json.load(open(p1b, encoding="utf-8"))
            data[0]["article_human_values"][0]["direction"] = "yes"
            json.dump(data, open(p1b, "w", encoding="utf-8"))
            with self.assertRaisesRegex(E4ValidationError,
                                        "invalid direction"):
                validate_pred_files([self.article], p1a, p1b)


if __name__ == "__main__":
    unittest.main()
