"""End-to-end offline test of run_e4.py with a mocked model transport.

Covers: stage sequencing, cache identity + resume (a second run must need
ZERO model calls), all three variant outputs, decision logging, official
file schema, and the dry run (no API). No network, no API keys.
"""

import argparse
import contextlib
import io
import json
import os
import re
import tempfile
import unittest

import context
import run_e4
from e4_common import E4ModelError, ModelCaller

GUID = context.synthetic_article()["guid"]

EVIDENCE_RESPONSE = json.dumps({"actors": [
    {"actor_id": "A-police", "units": [
        {"kind": "action", "sentence_ids": ["S1"], "note": "made arrest"},
        {"kind": "statement", "sentence_ids": ["S3"],
         "note": "vowed protection"}]},
    {"actor_id": "A-smuggler", "units": [
        {"kind": "action", "sentence_ids": ["S2"],
         "note": "sold unsafe fuel"}]},
]})

GLOBAL_RESPONSE = json.dumps({"items": [
    {"actor_id": "A-police", "l1_value_id": "42", "direction": "aligned"},
    {"actor_id": "A-smuggler", "l1_value_id": "30",
     "direction": "contradictory"},
]})

FAMILY_RESPONSES = {
    "Conservation": json.dumps({"candidates": [
        {"actor_id": "A-smuggler", "l1_value_id": "30",
         "direction": "contradictory", "evidence": ["S2"],
         "reason": "broke fuel-safety rules"},
        {"actor_id": "A-police", "l1_value_id": "26",
         "direction": "aligned", "evidence": ["S3", "u2"],
         "reason": "protecting public safety"},
    ]}),
    "Self-transcendence": json.dumps({"candidates": [
        {"actor_id": "A-police", "l1_value_id": "42",
         "direction": "aligned", "evidence": ["u1"],
         "reason": "fulfilled duty by arresting"},
    ]}),
}


def make_transport(call_log):
    def transport(system, user, max_tokens=None):
        call_log.append(system[:40])
        if system.startswith("You are an evidence organizer"):
            return EVIDENCE_RESPONSE
        if "independent verifier" in system:
            cids = re.findall(r'"cid": "(c\d+)"', user)
            verdicts = []
            for cid in cids:
                rel = "KEEP"
                # the single-view family candidate (26) gets UNCERTAIN
                if '"26: Have a safe country"' in _candidate_line(user, cid):
                    rel = "UNCERTAIN"
                direction = ("contradictory"
                             if '"claimed_direction": "contradictory"'
                             in _candidate_line(user, cid) else "aligned")
                verdicts.append({"cid": cid, "relevance": rel,
                                 "attribution": "actor",
                                 "direction": direction})
            return json.dumps({"verdicts": verdicts})
        if "scanning ONE semantic family" in system:
            for marker, resp in FAMILY_RESPONSES.items():
                if marker in system:
                    return resp
            return json.dumps({"candidates": []})
        if "Actor evidence units" in user:  # global stage (frozen E1 prompt)
            return GLOBAL_RESPONSE
        raise AssertionError("unrecognized stage prompt")
    return transport


def _candidate_line(user, cid):
    for line in user.splitlines():
        if f'"cid": "{cid}"' in line:
            return line
    raise AssertionError(f"candidate {cid} not in prompt")


def refusing_transport(_system, _user, _max_tokens=None):
    raise AssertionError("API called although everything should be cached")


class _TestRunner(run_e4.E4Runner):
    def load_articles(self):
        return [context.synthetic_article()]


class _MultiRunner(run_e4.E4Runner):
    N = 8

    def load_articles(self):
        arts = []
        for i in range(self.N):
            a = context.synthetic_article()
            a["guid"] = f"e4-multi-{i:03d}"
            arts.append(a)
        return arts


def _args(variant, dry_run=False):
    return argparse.Namespace(variant=variant, mode="dev", limit=1,
                              dry_run=dry_run, evaluate=False, api_key=None,
                              max_article_failures=15, workers=1)


def _read_1b(run_dir, variant):
    path = os.path.join(run_dir, f"{variant}_pred", "pred_task1b.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(v["actor"], v["l1_value"], v["direction"])
            for v in data[0]["article_human_values"]}


class TestPipelineMocked(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_runs = run_e4.RUNS_DIR
        run_e4.RUNS_DIR = self._tmp.name
        os.environ["E4_RUN_TS"] = "mocked_run"
        self.run_dir = os.path.join(self._tmp.name, "mocked_run")

    def tearDown(self):
        run_e4.RUNS_DIR = self._orig_runs
        os.environ.pop("E4_RUN_TS", None)
        self._tmp.cleanup()

    def _run(self, variant, transport, max_article_failures=15):
        args = _args(variant)
        args.max_article_failures = max_article_failures
        runner = _TestRunner(args)
        runner.config["retry_backoff_seconds"] = 0  # keep tests fast
        runner._caller = ModelCaller(runner.config, transport, runner.log)
        runner.run()
        return runner

    def test_full_flow_all_variants_and_resume(self):
        calls = []
        # e4a: evidence + global = 2 calls
        runner = self._run("e4a", make_transport(calls))
        self.assertEqual(runner._caller.n_calls, 2)
        self.assertEqual(_read_1b(self.run_dir, "e4a"),
                         {("A-police", "42", "1"),
                          ("A-smuggler", "30", "0")})

        # e4b reuses evidence+global caches: only 4 family calls
        runner = self._run("e4b", make_transport(calls))
        self.assertEqual(runner._caller.n_calls, 4)
        self.assertEqual(_read_1b(self.run_dir, "e4b"),
                         {("A-police", "42", "1"),
                          ("A-police", "26", "1"),
                          ("A-smuggler", "30", "0")})

        # e4c reuses everything, adds 1 verifier call; the single-view
        # UNCERTAIN candidate (police 26) is rejected by the rules
        runner = self._run("e4c", make_transport(calls))
        self.assertEqual(runner._caller.n_calls, 1)
        self.assertEqual(_read_1b(self.run_dir, "e4c"),
                         {("A-police", "42", "1"),
                          ("A-smuggler", "30", "0")})
        self.assertEqual(runner.violations.count, 0)

        # decisions audit trail exists and explains the rejection
        with open(os.path.join(self.run_dir, "e4c_pred",
                               "decisions.jsonl"), encoding="utf-8") as f:
            decisions = [json.loads(line) for line in f]
        rejected = [d for d in decisions if d.get("outcome") == "rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["pair"], ["A-police", "26"])
        self.assertEqual(rejected[0]["rule"], "single_view")

        # full resume: rerunning e4c must hit only caches (zero API calls)
        runner = self._run("e4c", refusing_transport)
        self.assertEqual(runner._caller.n_calls, 0)
        self.assertEqual(_read_1b(self.run_dir, "e4c"),
                         {("A-police", "42", "1"),
                          ("A-smuggler", "30", "0")})

    def test_run_summary_written(self):
        self._run("e4a", make_transport([]))
        with open(os.path.join(self.run_dir, "e4a_pred",
                               "run_summary.json"), encoding="utf-8") as f:
            summary = json.load(f)
        self.assertEqual(summary["variant"], "e4a")
        self.assertEqual(summary["violations"]["total"], 0)

    def test_persistent_failure_recorded_not_fatal_by_default(self):
        """A per-article stage failure is surfaced (failures.jsonl + summary)
        and given empty predictions; it does not abort the whole run."""
        def broken(_s, _u, _mt=None):
            return "this is not json"
        runner = self._run("e4a", broken)
        self.assertEqual(len(runner.article_failures), 1)
        self.assertEqual(runner.article_failures[0]["guid"], GUID)
        with open(os.path.join(self.run_dir, "failures.jsonl"),
                  encoding="utf-8") as f:
            self.assertEqual(len(f.readlines()), 1)
        with open(os.path.join(self.run_dir, "e4a_pred",
                               "run_summary.json"), encoding="utf-8") as f:
            summary = json.load(f)
        self.assertEqual(summary["article_failures"], 1)
        self.assertEqual(summary["failed_guids"], [GUID])
        # empty predictions written for the failed article (schema still valid)
        self.assertEqual(_read_1b(self.run_dir, "e4a"), set())

    def test_failures_over_threshold_abort(self):
        def broken(_s, _u, _mt=None):
            return "this is not json"
        from e4_common import E4ValidationError
        with self.assertRaises(E4ValidationError):
            self._run("e4a", broken, max_article_failures=0)

    def test_concurrent_matches_sequential(self):
        """Threaded execution (workers>1) yields byte-identical predictions
        to sequential and does not corrupt the shared stage caches."""
        def make_runner(ts, workers):
            os.environ["E4_RUN_TS"] = ts
            args = _args("e4c")
            args.workers = workers
            runner = _MultiRunner(args)
            runner.config["retry_backoff_seconds"] = 0
            runner._caller = ModelCaller(runner.config, make_transport([]),
                                         runner.log)
            runner.run()
            return runner

        make_runner("seq_run", 1)
        make_runner("par_run", 6)
        seq_dir = os.path.join(self._tmp.name, "seq_run", "e4c_pred")
        par_dir = os.path.join(self._tmp.name, "par_run", "e4c_pred")
        for fname in ("pred_task1a.json", "pred_task1b.json"):
            with open(os.path.join(seq_dir, fname), encoding="utf-8") as f:
                seq = json.load(f)
            with open(os.path.join(par_dir, fname), encoding="utf-8") as f:
                par = json.load(f)
            self.assertEqual(seq, par, fname)
        # all 8 articles produced predictions; every cache holds 8 entries
        par_run_dir = os.path.join(self._tmp.name, "par_run")
        for cache in ("cache_evidence.json", "cache_global.json",
                      "cache_verify.json",
                      "cache_family_conservation.json"):
            with open(os.path.join(par_run_dir, cache), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data["entries"]), _MultiRunner.N, cache)

    def test_dry_run_calls_no_api(self):
        runner = _TestRunner(_args("e4c", dry_run=True))
        runner._caller = ModelCaller(runner.config, refusing_transport,
                                     runner.log)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            runner.run()
        out = buf.getvalue()
        self.assertIn("EVIDENCE STAGE", out)
        self.assertIn("GLOBAL STAGE", out)
        self.assertIn("FAMILY STAGE", out)
        self.assertIn("VERIFY STAGE", out)
        self.assertIn("no API was called", out)
        self.assertEqual(runner._caller.n_calls, 0)


if __name__ == "__main__":
    unittest.main()
