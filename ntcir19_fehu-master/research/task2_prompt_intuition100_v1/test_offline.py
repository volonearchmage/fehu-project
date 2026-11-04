"""Offline safeguards: does not prepare the real run, read .env, or use network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("intuition_runner", Path(__file__).with_name("run_experiment.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class OfflineTests(unittest.TestCase):
    def test_selection_order_independent_and_exact(self):
        keys = [(f"article{i // 7}", str(i)) for i in range(508)]
        selected = m.select_keys(keys)
        self.assertEqual(selected, m.select_keys(list(reversed(keys))))
        self.assertEqual(len(selected), 100)
        self.assertEqual(selected, sorted(keys, key=lambda k: (m.selection_key(k), k))[:100])
        with self.assertRaises(ValueError):
            m.select_keys(keys + [keys[0]])

    def test_budget_persisted_before_attempt_and_limits(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(m, "HERE", Path(temporary)):
                budget = m.Budget(Path(temporary) / "ledger.jsonl")
                for i in range(336):
                    n = budget.reserve({"sample_index": i}, b"{}")
                    budget.finish(n, "valid", usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110})
                for i in range(24):
                    n = budget.reserve({"sample_index": i}, b"{}", retry=True)
                    budget.finish(n, "valid", usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110})
                with self.assertRaises(RuntimeError):
                    budget.reserve({"sample_index": 0}, b"{}", retry=True)
                self.assertEqual(len(budget.path.read_text().splitlines()), 1080)
                self.assertLessEqual(budget.total, m.Decimal("1.50"))
                reloaded = m.Budget(budget.path)
                self.assertEqual(reloaded.total, budget.total)
                self.assertEqual(reloaded.attempts, 360)
                fresh = m.Budget(Path(temporary) / "new.jsonl")
                with self.assertRaises(RuntimeError):
                    fresh.reserve({"sample_index": 0}, b"a" * 6000000)
                self.assertEqual(fresh.attempts, 0)

    def test_scoped_stop_and_authorization(self):
        authorization = {"scope": m.CONFIG["experiment"], "authorized": True, "manifest_sha256": "abc",
                         "max_events": 112, "max_http_attempts": 360, "max_reserved_usd": "1.50",
                         "does_not_authorize_historical_resume": True}
        m.check_scope(authorization, "abc")
        with self.assertRaises(RuntimeError):
            m.check_scope(authorization, "changed")
        with self.assertRaises(RuntimeError):
            m.check_scope(authorization, "abc", stopped=True)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(m, "HERE", Path(temporary)):
                (Path(temporary) / "RUN_STOP.json").write_text("{}")
                with self.assertRaises(RuntimeError):
                    m.Budget(Path(temporary) / "ledger.jsonl").reserve({"sample_index": 0}, b"{}")

    def test_parser_all_actors_multiple_both_and_empty(self):
        case = {"candidate_actors": [{"actor": "a", "name": "A"}, {"actor": "b", "name": "B"}]}
        valid = {"actors": [{"actor": "a", "values": [{"l1_value": "5", "direction": "0"}, {"l1_value": "5", "direction": "1"}]}, {"actor": "b", "values": []}]}
        actors, labels = m.old.validate(json.dumps(valid), case)
        self.assertEqual(len(actors), 2)
        self.assertEqual(len(labels), 2)
        with self.assertRaises(ValueError):
            m.old.validate(json.dumps({"actors": valid["actors"][:1]}), case)
        valid["actors"][0]["values"].append({"l1_value": "5", "direction": "0"})
        with self.assertRaises(ValueError):
            m.old.validate(json.dumps(valid), case)

    def test_request_disables_thinking_and_keeps_all_candidates(self):
        case = {"subevent_id": "1", "subevent": "event", "candidate_actors": [{"actor": "a", "name": "A"}], "article_background": {"title": "title", "content": "content"}}
        request = m.payload(case, "system")
        self.assertEqual(request["thinking"], {"type": "disabled"})
        self.assertEqual(request["temperature"], 0)
        self.assertNotIn("reasoning_effort", request)
        self.assertNotIn("top_p", request)
        self.assertEqual(json.loads(request["messages"][1]["content"])["candidate_actors"], case["candidate_actors"])
        body = m.canonical(request).encode("utf-8")
        self.assertEqual(m.reserved_cost(body)[0], len(body) + 1024)

    def test_settlement_idempotent_and_unknown_usage_keeps_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(m, "HERE", Path(temporary)):
                budget = m.Budget(Path(temporary) / "ledger.jsonl")
                n = budget.reserve({"sample_index": 0}, b"{}")
                initial = budget.total
                budget.finish(n, "timeout", usage={})
                self.assertEqual(budget.total, initial)
                budget.finish(n, "valid", usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110})
                settled = budget.total
                self.assertLess(settled, initial)
                budget.finish(n, "valid", usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110})
                self.assertEqual(budget.total, settled)
                self.assertEqual(m.Budget(budget.path).total, settled)
                self.assertIsNone(m.usage_cost({"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 999}))

    def test_fusion_keeps_direction_and_tie_order(self):
        a = {("actor", "5", "1"), ("actor", "5", "0")}
        b = {("actor", "5", "1"), ("other", "3", "0")}
        c = {("other", "3", "0")}
        self.assertEqual(m.fused_labels(a, b, c, "VETO"), {("actor", "5", "1")})
        self.assertEqual(m.fused_labels(a, b, c, "CONSENSUS"), {("actor", "5", "1"), ("other", "3", "0")})
        scores = {name: {"task2b": {"micro_f1": .25}} for name in m.METHODS}
        self.assertEqual(m.choose_primary(scores), "A")
        scores["C"]["task2b"]["micro_f1"] = .3
        self.assertEqual(m.choose_primary(scores), "C")

    def test_official_export_and_independent_counts(self):
        case = {"guid": "toy", "subevent_id": "1", "subevent": "toy event", "candidate_actors": [{"actor": "actor", "name": "Actor"}]}
        result = {"actors": [{"actor": "actor", "values": [{"l1_value": "5", "direction": "1"}]}],
                  "labels": [{"actor": "actor", "l1_value": "5", "direction": "1"}]}
        ids = m.read(m.ROOT / "dataset/hv_categories/human_value_level1_values.json")
        l2 = m.read(m.ROOT / "dataset/hv_categories/human_value_level2_values.json")
        parents = m.read(m.ROOT / "dataset/hv_categories/level_1_to_level_2.json")["level_1_to_level_2"]
        mapping = {str(ids[name]): str(l2[parent]) for name, parent in parents.items()}
        gold = [{"guid": "toy", "subevents_human_values": [{"subevent_id": "1", "subevent_human_values": [
            {"actor": "actor", "l1_value": "5", "l2_value": mapping["5"], "direction": "1"}]}]}]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            m.write(directory / "gold.json", gold)
            metrics = m.export_and_score([case], [result], directory / "score", directory / "gold.json")
            self.assertEqual(metrics["task2b"]["micro_f1"], 1.0)
            check = m.read(directory / "score/verification.json")
            self.assertTrue(check["passed"])
            self.assertEqual(check["independent_scores"]["task2b"]["tp"], 1)

    def test_interrupt_marks_stop_before_cancelling_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(m, "HERE", Path(temporary)):
                calls = []
                class Pending:
                    def cancel(self):
                        self.assert_marker = (Path(temporary) / "RUN_STOP.json").exists()
                        calls.append(self.assert_marker)
                m.stop_pending([Pending(), Pending()], "test interrupt")
                self.assertEqual(calls, [True, True])
                before = (Path(temporary) / "RUN_STOP.json").read_bytes()
                m.stop_pending([], "must not replace original stop")
                self.assertEqual((Path(temporary) / "RUN_STOP.json").read_bytes(), before)
                with self.assertRaises(RuntimeError):
                    m.Budget(Path(temporary) / "ledger.jsonl").reserve({"sample_index": 0}, b"{}")


if __name__ == "__main__":
    unittest.main()
