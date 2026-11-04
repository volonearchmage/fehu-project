"""Protocol checks for the small Task-2 experiment (no API access)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "task2_prompt_smoke", ROOT / "research/task2_prompt_smoke/run_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class Task2SmokeTests(unittest.TestCase):
    def setUp(self):
        self.case = {"guid": "news", "subevent_id": "se0", "subevent": "Target event",
                     "actors": [{"actor": "a", "name": "Factory"},
                                {"actor": "b", "name": "Volunteers"}],
                     "title": "BACKGROUND_TITLE", "content": "BACKGROUND_BODY"}

    def test_context_is_the_only_prompt_difference(self):
        local = smoke.make_payload(self.case, "local", "same scope rules", "model")
        full = smoke.make_payload(self.case, "full", "same scope rules", "model")
        local_input = json.loads(local["messages"][1]["content"])
        full_input = json.loads(full["messages"][1]["content"])
        self.assertNotIn("article_background", local_input)
        self.assertEqual(full_input.pop("article_background")["content"], "BACKGROUND_BODY")
        self.assertEqual(full_input, local_input)
        local["messages"].pop()
        full["messages"].pop()
        self.assertEqual(local, full)

    def test_empty_actors_and_both_directions_are_valid(self):
        response = {"actors": [{"actor": "a", "values": []}, {"actor": "b", "values": [
            {"l1_value": "42", "direction": "0"}, {"l1_value": "42", "direction": "1"}]}]}
        values = smoke.validate_prediction(json.dumps(response), self.case)
        self.assertEqual({v["direction"] for v in values}, {"0", "1"})
        self.assertEqual(len(values), 2)

    def test_missing_actor_is_failure_not_empty_output(self):
        with self.assertRaises(ValueError):
            smoke.validate_prediction('{"actors":[{"actor":"a","values":[]}]}', self.case)

    def test_invalid_id_or_direction_is_rejected(self):
        for field, value in (("actor", "unknown"), ("l1_value", "54"), ("direction", "aligned")):
            response = {"actors": [{"actor": "a", "values": [
                {"l1_value": "42", "direction": "1"}]}, {"actor": "b", "values": []}]}
            target = response["actors"][0] if field == "actor" else response["actors"][0]["values"][0]
            target[field] = value
            with self.assertRaises(ValueError):
                smoke.validate_prediction(json.dumps(response), self.case)

    def test_gold_is_restricted_before_official_scoring(self):
        values = [{"actor": "b", "l1_value": "42", "l2_value": "16", "direction": "1"}]
        gold = [{"guid": "news", "subevents_human_values": [
            {"subevent_id": "se0", "subevent_human_values": values},
            {"subevent_id": "unselected", "subevent_human_values": values}]}]
        selected, missing = smoke.subset_gold(gold, [self.case])
        self.assertEqual(missing, [])
        self.assertEqual(len(selected[0]["subevents_human_values"]), 1)
        prediction = [{"actor": "b", "l1_value": "42", "direction": "1"}]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            smoke.write_json(directory / "gold.json", selected)
            for coarse, task in ((False, "task2b"), (True, "task2a")):
                smoke.write_json(directory / f"pred_{task}.json", smoke.make_predictions(
                    [self.case], [prediction], {"42": "16"}, coarse=coarse))
            metrics = smoke.score_run(directory / "gold.json", directory)
            self.assertEqual(metrics["task2b"]["micro_f1"], 1.0)
            self.assertEqual(metrics["task2b"]["fn"], 0)
            self.assertEqual(metrics["task2a"]["micro_f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
