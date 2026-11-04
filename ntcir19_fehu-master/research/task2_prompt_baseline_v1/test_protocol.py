"""Behavior checks for the frozen baseline; never calls an API."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("baseline", Path(__file__).with_name("run_experiment.py"))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.case = {"case_index": 0, "guid": "g", "subevent_id": "e", "subevent": "Event",
                     "candidate_actors": [{"actor": "a", "name": "Actor A"}, {"actor": "b", "name": "Actor B"}],
                     "article_background": {"title": "Title", "content": "Body"}}

    def test_requested_model_is_max_thinking(self):
        request = baseline.payload_for(self.case, "Frozen prompt")
        self.assertEqual(request["model"], "deepseek-flash")
        self.assertEqual(request["thinking"], {"type": "enabled"})
        self.assertEqual(request["reasoning_effort"], "max")
        self.assertNotIn("temperature", request)
        self.assertNotIn("api_key", baseline.canonical(request))
        user = json.loads(request["messages"][1]["content"])
        self.assertEqual(user["TARGET_SUBEVENT"]["id"], "e")
        self.assertEqual(user["article_background"]["content"], "Body")

    def test_empty_actors_must_be_explicit(self):
        actors, labels = baseline.validate('{"actors":[{"actor":"a","values":[]},{"actor":"b","values":[]}]}', self.case)
        self.assertEqual(len(actors), 2)
        self.assertEqual(labels, [])
        with self.assertRaises(ValueError):
            baseline.validate('{"actors":[]}', self.case)

    def test_multiple_labels_and_both_directions_are_allowed(self):
        values = [{"l1_value": "42", "direction": "0"}, {"l1_value": "42", "direction": "1"},
                  {"l1_value": "37", "direction": "1"}]
        response = {"actors": [{"actor": "a", "values": values}, {"actor": "b", "values": []}]}
        self.assertEqual(len(baseline.validate(json.dumps(response), self.case)[1]), 3)

    def test_bad_direction_or_unknown_actor_is_not_coerced(self):
        for actor, direction in (("a", "aligned"), ("x", "1"), ("a", 1)):
            response = {"actors": [{"actor": actor, "values": [{"l1_value": "42", "direction": direction}]},
                                   {"actor": "b", "values": []}]}
            with self.assertRaises(ValueError):
                baseline.validate(json.dumps(response), self.case)

    def test_duplicate_label_is_rejected(self):
        value = {"l1_value": "42", "direction": "1"}
        response = {"actors": [{"actor": "a", "values": [value, value]}, {"actor": "b", "values": []}]}
        with self.assertRaises(ValueError):
            baseline.validate(json.dumps(response), self.case)

    def test_metric_keeps_event_boundaries_and_gold_supported_macro(self):
        gold = {("g", "e", "a"): {"1:42"}}
        pred = {("g", "different", "a"): {"1:42"}, ("g", "e", "a"): {"0:37"}}
        metric, _ = baseline.independent_metrics(gold, pred)
        self.assertEqual((metric["tp"], metric["fp"], metric["fn"]), (0, 2, 1))
        self.assertEqual(metric["macro_f1"], 0.0)
        pred = {("g", "e", "a"): {"1:42", "0:37"}}
        metric, _ = baseline.independent_metrics(gold, pred)
        self.assertEqual(metric["macro_f1"], 1.0)
        self.assertAlmostEqual(metric["micro_f1"], 2/3)


if __name__ == "__main__":
    unittest.main()
