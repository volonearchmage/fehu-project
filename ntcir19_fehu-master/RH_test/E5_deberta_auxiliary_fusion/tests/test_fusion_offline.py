#!/usr/bin/env python3
"""Offline validation for the E5 fusion pipeline. No API calls, no GPU.

Run from project root:
    python -m unittest RH_test.E5_deberta_auxiliary_fusion.tests.test_fusion_offline -v
or directly:
    python RH_test/E5_deberta_auxiliary_fusion/tests/test_fusion_offline.py
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[1]
sys.path.insert(0, str(EXP / "scripts"))
sys.path.insert(0, str(ROOT))

from fusion_lib import (  # noqa: E402
    FusionError, NUM_LABELS, label_of, index_of, all_labels,
    load_articles, load_task1b, load_probs, load_l1_to_l2, frequent_classes,
    make_scorer, pav_fit, pav_apply, crossfit_fold_of, micro_f1,
    fit_calibration, fuse, project_1a, write_pred_files,
)

DEV_ARTICLES = ROOT / "dataset/dev/dev_event_base.json"
E1_RUN = ROOT / "RH_test/E1_fewshot_repair/runs/20260722_152456"
V2_PROBS = (ROOT / "output/research_hybrid_deberta_v2_liu_flash/20260714_184515/"
            "02_deberta_actor_probabilities.jsonl")
TRAIN_GOLD = ROOT / "dataset/gold_labels/train/train_human_values.json"


# ------------------------------------------------------------------ fixtures
def probvec(**at):
    """108-dim zero vector with prob[index_of(label)] = value overrides."""
    p = [0.0] * NUM_LABELS
    for lab, v in at.items():
        p[index_of(lab.replace("_", ":"))] = v
    return p


def fixture():
    """Tiny synthetic world.

    Labels used: "1:10" / "0:10" (value 10), "1:20", "0:30", "1:40".
    freq tier = {"1:10", "0:10", "1:20", "1:40"} ("0:30" is rare-tier).
    """
    e1 = {
        ("g1", "a1"): {"1:10", "1:20"},
        ("g1", "a2"): {"0:30"},
        ("g2", "a3"): {"1:20"},
    }
    gold = {
        ("g1", "a1"): {"1:10"},
        ("g1", "a2"): {"0:30"},
        ("g2", "a3"): {"1:20", "1:40"},
        ("g2", "a4"): {"1:40"},
    }
    probs = {
        ("g1", "a1"): probvec(**{"1_10": 0.9, "1_20": 0.01}),
        ("g1", "a2"): probvec(**{"0_30": 0.01}),
        ("g2", "a3"): probvec(**{"1_20": 0.8, "1_40": 0.95}),
        ("g2", "a4"): probvec(**{"1_40": 0.9}),
    }
    actor_keys = sorted(probs)
    freq = {"1:10", "0:10", "1:20", "1:40"}
    return e1, gold, probs, actor_keys, freq


def const_calib(theta, removal=None, addition=None):
    cal = {"removal": removal or [(1.0, 0.5)],
           "addition": addition or [(1.0, 0.5)], "theta": theta}
    return lambda key: cal


class TestLabelSpace(unittest.TestCase):
    def test_roundtrip(self):
        for i in range(NUM_LABELS):
            self.assertEqual(index_of(label_of(i)), i)
        self.assertEqual(len(all_labels()), 108)
        self.assertEqual(label_of(45), "1:22")  # l1=22 aligned -> 22*2+1


class TestPAV(unittest.TestCase):
    def test_monotone_and_pooling(self):
        model = pav_fit([(0.1, 0), (0.2, 1), (0.3, 0), (0.4, 1), (0.5, 1)])
        vals = [m for _, m in model]
        self.assertEqual(vals, sorted(vals))
        # isotonic fit: (0.1)->0.0, (0.2,0.3) pooled to 0.5, (0.4,0.5)->1.0
        self.assertAlmostEqual(pav_apply(model, 0.05), 0.0)
        self.assertAlmostEqual(pav_apply(model, 0.25), 0.5)
        self.assertAlmostEqual(pav_apply(model, 0.45), 1.0)
        self.assertAlmostEqual(pav_apply(model, 9.9), 1.0)  # above max score

    def test_tie_pooling(self):
        model = pav_fit([(0.5, 0), (0.5, 1)])
        self.assertAlmostEqual(pav_apply(model, 0.5), 0.5)

    def test_empty_fails(self):
        with self.assertRaises(FusionError):
            pav_fit([])


class TestCrossfit(unittest.TestCase):
    def test_deterministic_and_balanced_on_dev(self):
        guids, _ = load_articles(DEV_ARTICLES)
        folds = [crossfit_fold_of(g) for g in guids]
        self.assertEqual(folds, [crossfit_fold_of(g) for g in guids])
        self.assertGreater(sum(folds), 30)
        self.assertGreater(len(folds) - sum(folds), 30)


class TestLoaders(unittest.TestCase):
    def test_load_probs_rejects_bad_rows(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.jsonl"
            p.write_text(json.dumps({"guid": "g", "actor_id": "a",
                                     "probabilities_108": [0.5] * 107}) + "\n")
            with self.assertRaises(FusionError):
                load_probs(p)
            p.write_text(json.dumps({"guid": "g", "actor_id": "a",
                                     "probabilities_108": [1.5] * 108}) + "\n")
            with self.assertRaises(FusionError):
                load_probs(p)
            row = json.dumps({"guid": "g", "actor_id": "a",
                              "probabilities_108": [0.5] * 108})
            p.write_text(row + "\n" + row + "\n")  # duplicate key
            with self.assertRaises(FusionError):
                load_probs(p)

    def test_load_task1b_rejects_out_of_range(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text(json.dumps([{"guid": "g", "article_human_values": [
                {"actor": "a", "l1_value": "54", "direction": "1"}]}]))
            with self.assertRaises(FusionError):
                load_task1b(p)

    def test_frequent_classes_real(self):
        freq = frequent_classes(TRAIN_GOLD)
        self.assertEqual(len(freq), 38)
        targets = json.loads(
            (ROOT / "output/research_label_aware_low_frequency_augmentation_v2/"
                    "20260713_163751/02_selected_targets_and_allocation.json"
             ).read_text())
        t18 = {f"{t['direction']}:{t['l1_value_id']}"
               for t in targets["targets"]}
        self.assertFalse(freq & t18,
                         "target-18 classes must never be in the veto tier")


class TestScorer(unittest.TestCase):
    def test_value_vs_exact(self):
        _, _, probs, *_ = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        self.assertAlmostEqual(se(("g1", "a1"), "0:10"), 0.0)
        self.assertAlmostEqual(sv(("g1", "a1"), "0:10"), 0.9)  # other dir

    def test_seed_average_and_missing_key(self):
        _, _, probs, *_ = fixture()
        seed = {("g1", "a1"): probvec(**{"1_10": 0.5})}
        s = make_scorer("exact", probs, [seed])
        self.assertAlmostEqual(s(("g1", "a1"), "1:10"), 0.7)
        with self.assertRaises(FusionError):
            s(("g2", "a3"), "1:10")  # seed lacks the key -> loud failure


class TestCalibration(unittest.TestCase):
    def test_theta_and_cell_partition(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        cal = fit_calibration(e1, gold, actor_keys, sv, se, freq)
        self.assertAlmostEqual(cal["theta"], micro_f1(gold, e1) / 2.0)
        # removal cells = frequent E1 cells = 3 ("0:30" is rare-tier)
        self.assertEqual(cal["n_removal_cells"], 3)
        # addition cells exclude E1-held values in either direction:
        # a1 holds values {10,20} -> 1 candidate ("1:40")
        # a2 holds {30} -> 4; a3 holds {20} -> 3; a4 holds none -> 4
        self.assertEqual(cal["n_addition_cells"], 1 + 4 + 3 + 4)

    def test_crossfit_excludes_own_fold(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        only_g1 = fit_calibration(e1, gold, actor_keys, sv, se, freq,
                                  guid_filter=lambda g: g == "g1")
        both = fit_calibration(e1, gold, actor_keys, sv, se, freq)
        self.assertEqual(only_g1["n_removal_cells"], 2)
        self.assertNotEqual(only_g1["n_removal_cells"],
                            both["n_removal_cells"])


class TestFuseArms(unittest.TestCase):
    def test_identity_passthrough(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        fused, actions, ann = fuse(e1, actor_keys, sv, se, freq, None,
                                   set(), probs=probs)
        self.assertEqual(fused, e1)
        self.assertEqual(actions, [])
        self.assertTrue(all(a["from_e1"] for a in ann))

    def test_removal_respects_theta_gate_and_last_label(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        # calibrator: p == raw score; theta 0.25
        ident = [(x / 100.0, x / 100.0) for x in range(0, 101)]
        cal = const_calib(0.25, removal=ident, addition=ident)
        fused, actions, _ = fuse(e1, actor_keys, sv, se, freq, cal,
                                 {"removal"}, probs=probs)
        # a1: "1:20" has value score 0.01 < 0.25 -> removed; "1:10" 0.9 kept
        self.assertEqual(fused[("g1", "a1")], {"1:10"})
        # a2: "0:30" score 0.01 but rare-tier -> never touched
        self.assertEqual(fused[("g1", "a2")], {"0:30"})
        # a3: "1:20" 0.8 kept
        self.assertEqual(fused[("g2", "a3")], {"1:20"})
        self.assertEqual([a["action"] for a in actions], ["remove"])

    def test_removal_never_empties_actor(self):
        e1 = {("g1", "a1"): {"1:10", "1:20"}}
        probs = {("g1", "a1"): probvec()}  # zero evidence for everything
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        ident = [(x / 100.0, x / 100.0) for x in range(0, 101)]
        cal = const_calib(0.25, removal=ident, addition=ident)
        fused, actions, _ = fuse(e1, [("g1", "a1")], sv, se,
                                 {"1:10", "1:20"}, cal, {"removal"},
                                 probs=probs)
        self.assertEqual(len(fused[("g1", "a1")]), 1)
        self.assertEqual(len(actions), 1)

    def test_addition_guards(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        ident = [(x / 100.0, x / 100.0) for x in range(0, 101)]
        cal = const_calib(0.25, removal=ident, addition=ident)
        fused, actions, _ = fuse(e1, actor_keys, sv, se, freq, cal,
                                 {"addition"}, probs=probs)
        # a3: "1:40" p 0.95 >= theta and value 40 not held -> added
        self.assertIn("1:40", fused[("g2", "a3")])
        # a1: candidate "1:40" has p 0.0 < theta -> not added; "0:10" blocked
        # by direction-conflict guard even though value score is 0.9
        self.assertEqual(fused[("g1", "a1")], {"1:10", "1:20"})
        # a4 had no E1 labels; addition arm still adds "1:40" (p 0.9)
        self.assertIn("1:40", fused[("g2", "a4")])

    def test_addition_cap(self):
        e1 = {("g1", "a1"): set()}
        p = probvec(**{"1_10": 0.9, "1_20": 0.8, "1_40": 0.7})
        probs = {("g1", "a1"): p}
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        ident = [(x / 100.0, x / 100.0) for x in range(0, 101)]
        cal = const_calib(0.25, removal=ident, addition=ident)
        freq = {"1:10", "1:20", "1:40"}
        fused, actions, _ = fuse(e1, [("g1", "a1")], sv, se, freq, cal,
                                 {"addition"}, max_add=2, probs=probs)
        self.assertEqual(fused[("g1", "a1")], {"1:10", "1:20"})  # top-2 only

    def test_backfill_only_empty_actors(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        fused, actions, _ = fuse(e1, actor_keys, sv, se, freq, None,
                                 {"backfill"}, probs=probs)
        self.assertEqual(fused[("g2", "a4")], {"1:40"})  # argmax backfill
        self.assertEqual(fused[("g1", "a1")], e1[("g1", "a1")])  # untouched
        self.assertEqual([a["action"] for a in actions], ["backfill"])

    def test_union_diag(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        fused, actions, _ = fuse(e1, actor_keys, sv, se, freq, None,
                                 {"union_diag"}, probs=probs)
        self.assertEqual(fused[("g2", "a3")], {"1:20", "1:40"})
        self.assertEqual(fused[("g2", "a4")], {"1:40"})

    def test_calibration_required_for_active_arms(self):
        e1, gold, probs, actor_keys, freq = fixture()
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        with self.assertRaises(FusionError):
            fuse(e1, actor_keys, sv, se, freq, None, {"removal"}, probs=probs)

    def test_stray_e1_key_fails(self):
        e1 = {("gX", "aX"): {"1:10"}}
        probs = {("g1", "a1"): probvec()}
        sv = make_scorer("value", probs, [])
        se = make_scorer("exact", probs, [])
        with self.assertRaises(FusionError):
            fuse(e1, [("g1", "a1")], sv, se, {"1:10"}, None, set(),
                 probs=probs)


class TestOutputs(unittest.TestCase):
    def test_projection_matches_real_e1(self):
        l1_to_l2 = load_l1_to_l2(ROOT / "dataset/hv_categories")
        e1b = load_task1b(E1_RUN / "pred_task1b.json")
        proj = project_1a(e1b, l1_to_l2)
        # official parser on E1's own 1a file
        from evaluation import parse_task1a
        e1a = parse_task1a(str(E1_RUN / "pred_task1a.json"))
        self.assertEqual(proj, e1a)

    def test_write_roundtrip(self):
        e1, gold, probs, actor_keys, freq = fixture()
        l2map = {"10": "3", "20": "5", "30": "7", "40": "9"}
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            write_pred_files(out, ["g1", "g2"], e1, project_1a(e1, l2map))
            back = load_task1b(out / "pred_task1b.json")
            self.assertEqual(back, e1)
            data = json.loads((out / "pred_task1b.json").read_text())
            self.assertEqual([d["guid"] for d in data], ["g1", "g2"])
            a = json.loads((out / "pred_task1a.json").read_text())
            self.assertEqual(
                {(h["actor"], h["l2_value"]) for h in a[0]
                 ["article_human_values"]},
                {("a1", "3"), ("a1", "5"), ("a2", "7")})


class TestEndToEndIdentity(unittest.TestCase):
    """F0_identity on the real dev inputs must reproduce E1 exactly.

    This exercises the full runner (loaders, validation, projection,
    serialization) without running any calibrated dev experiment.
    """

    def test_f0_identity_reproduces_e1(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "f0"
            r = subprocess.run(
                [sys.executable,
                 str(EXP / "scripts/run_fusion_e5.py"),
                 "--variant", "F0_identity", "--out_dir", str(out)],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            fused = load_task1b(out / "pred_task1b.json")
            e1 = load_task1b(E1_RUN / "pred_task1b.json")
            self.assertEqual(fused, e1)
            from evaluation import parse_task1a
            self.assertEqual(parse_task1a(str(out / "pred_task1a.json")),
                             parse_task1a(str(E1_RUN / "pred_task1a.json")))
            manifest = json.loads((out / "fusion_manifest.json").read_text())
            self.assertEqual(manifest["counts"]["actions"], {})
            self.assertEqual(manifest["counts"]["e1_pred_labels"],
                             manifest["counts"]["fused_pred_labels"])

    def test_runner_refuses_nonempty_out_dir(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "f0"
            out.mkdir()
            (out / "existing.txt").write_text("x")
            r = subprocess.run(
                [sys.executable,
                 str(EXP / "scripts/run_fusion_e5.py"),
                 "--variant", "F0_identity", "--out_dir", str(out)],
                capture_output=True, text=True, cwd=ROOT)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("refusing", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
