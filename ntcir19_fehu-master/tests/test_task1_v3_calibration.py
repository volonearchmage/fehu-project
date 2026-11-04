#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Pipeline V3 label-aware calibration. No API calls.

Run from project root:
    python -m unittest tests.test_task1_v3_calibration -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from calibrate_task1_v3 import (  # noqa: E402
    per_label_prf, select_label_policies, DEFAULT_MIN_SUPPORT,
    STRATEGY_PREFERENCE,
)
from task1_v3_ensemble import STAGE_NAMES  # noqa: E402


def instances(mapping):
    """{'g1/a1': {'1:37', ...}} → {('g1','a1'): {...}}"""
    return {tuple(k.split("/")): set(v) for k, v in mapping.items()}


def uniform_stage_preds(pred):
    """All five stages predict the same thing (baseline for tests)."""
    return {s: {k: set(v) for k, v in pred.items()} for s in STAGE_NAMES}


class TestPerLabelPRF(unittest.TestCase):
    def test_counts(self):
        gold = instances({"g/a": {"1:37"}, "g/b": {"1:37"}, "g/c": {"0:22"}})
        pred = instances({"g/a": {"1:37"}, "g/c": {"1:37"}})
        m = per_label_prf(gold, pred, "1:37")
        self.assertEqual((m["tp"], m["fp"], m["fn"]), (1, 1, 1))
        self.assertEqual(m["precision"], 0.5)
        self.assertEqual(m["recall"], 0.5)
        self.assertEqual(m["f1"], 0.5)

    def test_absent_label(self):
        m = per_label_prf(instances({"g/a": {"1:0"}}), {}, "1:37")
        self.assertEqual((m["tp"], m["fp"], m["fn"]), (0, 0, 0))
        self.assertEqual(m["f1"], 0.0)


class TestPolicySelection(unittest.TestCase):
    def make_data(self, n_gold, n_hit_default, n_hit_alt, label="1:9",
                  alt="variant_b"):
        """n_gold instances carry `label`; default strategy recovers
        n_hit_default of them, `alt` recovers n_hit_alt (no false
        positives)."""
        gold, default_pred, alt_pred = {}, {}, {}
        for i in range(n_gold):
            iid = ("g", f"a{i}")
            gold[iid] = {label}
            default_pred[iid] = {label} if i < n_hit_default else set()
            alt_pred[iid] = {label} if i < n_hit_alt else set()
        stage_preds = {s: dict(default_pred) for s in STAGE_NAMES}
        stage_preds[alt] = alt_pred
        return gold, stage_preds

    def test_insufficient_support_keeps_default(self):
        gold, preds = self.make_data(n_gold=3, n_hit_default=0, n_hit_alt=3)
        labels = select_label_policies(gold, preds, "verified",
                                       min_support=5, min_gain=0.05)
        rec = labels["1:9"]
        self.assertEqual(rec["strategy"], "default")
        self.assertIn("insufficient calibration support", rec["reason"])
        self.assertEqual(rec["support"], 3)

    def test_gain_below_min_gain_keeps_default(self):
        # default F1 ≈ 0.9091 (10/12 hits... construct: 10 gold, default hits
        # 9, alt hits 10 → default f1 = 2*.9/1.9=0.947, alt = 1.0; gain 0.053
        # → with min_gain 0.10 the default is kept.
        gold, preds = self.make_data(n_gold=10, n_hit_default=9, n_hit_alt=10)
        labels = select_label_policies(gold, preds, "verified",
                                       min_support=5, min_gain=0.10)
        self.assertEqual(labels["1:9"]["strategy"], "default")
        self.assertIn("no strategy beats default", labels["1:9"]["reason"])

    def test_clear_winner_selected(self):
        gold, preds = self.make_data(n_gold=10, n_hit_default=2, n_hit_alt=9)
        labels = select_label_policies(gold, preds, "verified",
                                       min_support=5, min_gain=0.05)
        rec = labels["1:9"]
        self.assertEqual(rec["strategy"], "variant_b")
        self.assertIn("beats default", rec["reason"])
        # Report contains full per-strategy scores.
        for s in STAGE_NAMES:
            self.assertIn(s, rec["scores"])
            for key in ("precision", "recall", "f1"):
                self.assertIn(key, rec["scores"][s])

    def test_deterministic_tie_break_prefers_earlier_strategy(self):
        # variant_a and variant_b get identical perfect scores; default
        # (verified) recovers nothing. variant_a precedes variant_b in
        # STRATEGY_PREFERENCE → variant_a must win, deterministically.
        gold, preds = self.make_data(n_gold=8, n_hit_default=0, n_hit_alt=8,
                                     alt="variant_b")
        preds["variant_a"] = {k: set(v) for k, v in preds["variant_b"].items()}
        self.assertLess(STRATEGY_PREFERENCE.index("variant_a"),
                        STRATEGY_PREFERENCE.index("variant_b"))
        for _ in range(3):
            labels = select_label_policies(gold, preds, "verified",
                                           min_support=5, min_gain=0.05)
            self.assertEqual(labels["1:9"]["strategy"], "variant_a")

    def test_unaffected_labels_default_with_zero_support(self):
        gold, preds = self.make_data(n_gold=10, n_hit_default=2, n_hit_alt=9)
        labels = select_label_policies(gold, preds, "verified",
                                       min_support=5, min_gain=0.05)
        self.assertEqual(labels["0:53"]["strategy"], "default")
        self.assertEqual(labels["0:53"]["support"], 0)
        # Full official label universe covered: 54 L1 × 2 directions.
        self.assertEqual(len(labels), 108)

    def test_missing_default_strategy_raises(self):
        gold, preds = self.make_data(n_gold=10, n_hit_default=2, n_hit_alt=9)
        del preds["verified"]
        with self.assertRaises(ValueError):
            select_label_policies(gold, preds, "verified")

    def test_invalid_default_name_raises(self):
        gold, preds = self.make_data(n_gold=10, n_hit_default=2, n_hit_alt=9)
        with self.assertRaises(ValueError):
            select_label_policies(gold, preds, "drop")

    def test_selection_uses_only_supplied_calibration_data(self):
        # Pure-function check: identical inputs → identical outputs (no
        # hidden state, no file access beyond the evaluation universe).
        gold, preds = self.make_data(n_gold=10, n_hit_default=2, n_hit_alt=9)
        l1 = select_label_policies(gold, preds, "verified")
        l2 = select_label_policies(gold, preds, "verified")
        self.assertEqual(l1, l2)


class TestCalibrateCLIGuards(unittest.TestCase):
    def test_refuses_dev_run_without_exploratory_flag(self):
        import json
        import tempfile
        from calibrate_task1_v3 import main
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps({
                "mode": "dev", "dry_run": False,
                "n_articles_succeeded": 5, "succeeded_guids": ["g1"],
            }), encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                main(["--run_dir", str(run_dir)])
            self.assertIn("leakage", str(cm.exception))

    def test_refuses_dry_run_dir(self):
        import json
        import tempfile
        from calibrate_task1_v3 import main
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps({
                "mode": "calibrate", "dry_run": True,
                "n_articles_succeeded": 0, "succeeded_guids": [],
            }), encoding="utf-8")
            with self.assertRaises(SystemExit):
                main(["--run_dir", str(run_dir)])


if __name__ == "__main__":
    unittest.main()
