import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn

from research.task2_scope_local_v1.data import (
    Article, Bag, Event, bags, label_index, load_articles, load_json,
    load_supervision, source_groups, taxonomy, validate_split,
)
from research.task2_scope_local_v1.losses import scope_loss
from research.task2_scope_local_v1.model import ScopeModel, masked_mean
from research.task2_scope_local_v1.predictions import export_predictions
from research.task2_scope_local_v1.tokenization import BagTokenizer, collate, render

PROJECT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]


class LossTests(unittest.TestCase):
    def run_case(self, a, c, ya, yc, mode="S", mask=None):
        a = torch.tensor([[a]], dtype=torch.float64, requires_grad=True)
        c = torch.tensor(c, dtype=torch.float64).reshape(1, -1, 1).requires_grad_()
        ya = torch.tensor([[ya]], dtype=torch.float64)
        yc = torch.tensor(yc, dtype=torch.float64).reshape_as(c)
        mask = torch.ones(c.shape[:2], dtype=torch.bool) if mask is None else torch.tensor([mask])
        return a, c, scope_loss(a, c, ya, yc, mask, mode)

    def test_article_only_positive_does_not_push_children_up(self):
        a, c, result = self.run_case(-1., [4., 2.], 1., [0., 0.])
        result["article_loss"].backward(retain_graph=True)
        self.assertLess(a.grad.item(), 0)
        torch.testing.assert_close(c.grad, torch.zeros_like(c))
        c.grad.zero_()
        result["loss"].backward()
        self.assertTrue((c.grad > 0).all())  # Child BCE corrects false positives.

    def test_negative_article_corrects_highest_erroneous_child(self):
        a, c, result = self.run_case(-1., [4., 2.], 0., [0., 0.])
        result["article_loss"].backward()
        self.assertEqual(a.grad.item(), 0)
        self.assertGreater(c.grad[0, 0, 0].item(), 0)
        self.assertEqual(c.grad[0, 1, 0].item(), 0)

    def test_positive_child_supports_article_but_negative_child_cannot(self):
        a, c, result = self.run_case(-2., [1., 8.], 1., [1., 0.])
        self.assertAlmostEqual(result["article_loss"].item(), math.log1p(math.exp(-1)))
        result["article_loss"].backward()
        self.assertEqual(a.grad.item(), 0)
        self.assertLess(c.grad[0, 0, 0].item(), 0)
        self.assertEqual(c.grad[0, 1, 0].item(), 0)

    def test_j_article_loss_has_no_child_path(self):
        a, c, result = self.run_case(-2., [5.], 1., [1.], mode="J")
        result["article_loss"].backward()
        self.assertIsNone(c.grad)

    def test_probability_reference(self):
        torch.manual_seed(11)
        a = torch.randn(3, 108, dtype=torch.float64)
        c = torch.randn(3, 4, 108, dtype=torch.float64)
        ya = torch.randint(0, 2, a.shape).double()
        yc = torch.randint(0, 2, c.shape).double()
        mask = torch.tensor([[1, 1, 1, 1], [1, 0, 0, 0], [1, 1, 0, 0]], dtype=torch.bool)
        expected = []
        for i in range(3):
            pa, pc, y = a[i].sigmoid(), c[i, mask[i]].sigmoid(), yc[i, mask[i]]
            up = torch.cat([pa[None], pc]).max(0).values
            pos = torch.cat([pa[None], pc * y]).max(0).values
            expected.append((-ya[i] * pos.log() - (1 - ya[i]) * torch.log1p(-up)).mean())
        got = scope_loss(a, c, ya, yc, mask, "S")
        torch.testing.assert_close(got["article_loss"], torch.stack(expected).mean())

    def test_padding_nan_has_no_effect_or_gradient(self):
        for mode in ("J", "S"):
            _, _, clean = self.run_case(1., [2.], 1., [1.], mode)
            a, c, padded = self.run_case(1., [2., float("nan")], 1., [1., float("nan")], mode, [True, False])
            torch.testing.assert_close(clean["loss"], padded["loss"])
            padded["loss"].backward()
            self.assertTrue(torch.isfinite(c.grad).all())
            self.assertEqual(c.grad[0, 1, 0].item(), 0)

    def test_extreme_logits_finite_forward_backward(self):
        for mode in ("J", "S"):
            a, c, result = self.run_case(-10000., [10000., -10000.], 1., [0., 1.], mode)
            result["loss"].backward()
            self.assertTrue(torch.isfinite(result["loss"]))
            self.assertTrue(torch.isfinite(c.grad).all())
            self.assertTrue(torch.isfinite(a.grad).all())

    def test_half_precision_reduction_does_not_overflow(self):
        a = torch.full((1, 108), 10000., dtype=torch.float16, requires_grad=True)
        c = torch.full((1, 9, 108), 10000., dtype=torch.float16, requires_grad=True)
        result = scope_loss(a, c, torch.zeros_like(a), torch.zeros_like(c), torch.ones(1, 9, dtype=torch.bool), "S")
        self.assertEqual(result["loss"].item(), 20000.)
        result["loss"].backward()
        self.assertTrue(torch.isfinite(c.grad).all())

    def test_zero_children_reduces_to_article_bce(self):
        for mode in ("J", "S"):
            _, _, result = self.run_case(0., [], 1., [], mode)
            self.assertEqual(result["event_loss"].item(), 0)
            self.assertAlmostEqual(result["loss"].item(), math.log(2))

    def test_event_loss_normalized_with_equal_bag_weight(self):
        a = torch.zeros(2, 108)
        c = torch.tensor([0., 9., 2., 2.]).reshape(2, 2, 1).expand(-1, -1, 108)
        mask = torch.tensor([[True, False], [True, True]])
        result = scope_loss(a, c, a, torch.zeros_like(c), mask)
        self.assertAlmostEqual(result["event_loss"].item(), (math.log(2) + math.log1p(math.exp(2))) / 2, places=6)

    def test_js_identical_child_loss_and_article_weight(self):
        _, _, j = self.run_case(0., [3.], 0., [0.], "J")
        _, _, s = self.run_case(0., [3.], 0., [0.], "S")
        torch.testing.assert_close(j["event_loss"], s["event_loss"])
        self.assertGreater(s["article_loss"].item(), j["article_loss"].item())

    def test_label_directions_independent_and_empty_allowed(self):
        a = torch.zeros(1, 108, requires_grad=True)
        c = torch.zeros(1, 2, 108, requires_grad=True)
        ya, yc = torch.zeros_like(a), torch.zeros_like(c)
        ya[0, :2] = yc[0, 0, :2] = 1
        result = scope_loss(a, c, ya, yc, torch.ones(1, 2, dtype=torch.bool), "J")
        result["loss"].backward()
        self.assertTrue((c.grad[0, 0, :2] < 0).all())
        self.assertTrue((c.grad[0, 1] > 0).all())

    def test_invalid_active_targets_and_logits_rejected(self):
        for args in [(0., [float("nan")], 0., [0.]), (0., [0.], 1., [2.])]:
            with self.assertRaises(ValueError):
                self.run_case(*args)

    def test_gradient_check_stable_max_away_from_ties(self):
        a = torch.tensor([[.7, -.3]], dtype=torch.double, requires_grad=True)
        c = torch.tensor([[[1.3, 2.4], [-2., -.9]]], dtype=torch.double, requires_grad=True)
        ya = torch.tensor([[1., 0.]], dtype=torch.double)
        yc = torch.tensor([[[1., 0.], [0., 0.]]], dtype=torch.double)
        mask = torch.ones(1, 2, dtype=torch.bool)
        self.assertTrue(torch.autograd.gradcheck(lambda a, c: scope_loss(a, c, ya, yc, mask, "S")["loss"], (a, c)))


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load_articles(PROJECT / "dataset/train/train_event_base.json")
        cls.manifest = load_json(PROJECT / "docs/2026-11-03_Task2_组会准备/evidence/grouped_train_split.json")
        cls.mapping = taxonomy(PROJECT / "dataset/hv_categories")

    def test_frozen_split_and_cartesian_coverage(self):
        parts = validate_split(self.train, self.manifest)
        self.assertEqual({p: len(v) for p, v in parts.items()}, dict(fit=973, tune=138, holdout=117))
        self.assertEqual(len(bags(self.train)), 3381)
        self.assertEqual(sum(len(b.events) for b in bags(self.train)), 30543)

    def test_changed_split_duplicate_or_seed_rejected(self):
        for kind in ("duplicate", "seed", "group"):
            manifest = copy.deepcopy(self.manifest)
            if kind == "duplicate": manifest["guids"]["fit"].append(manifest["guids"]["tune"][0])
            if kind == "seed": manifest["seed"] = "other"
            if kind == "group": manifest["groups"].pop(next(iter(manifest["groups"])))
            with self.assertRaises(ValueError): validate_split(self.train, manifest)

    def test_transitive_source_groups(self):
        def a(g, body, title): return Article(g, title, body, (("a", "A"),), (Event("e", "E"),))
        groups = source_groups((a("1", "Same  body", "one"), a("2", "same body", "two"), a("3", "different", " TWO ")))
        self.assertEqual(list(groups.values()), [["1", "2", "3"]])

    def test_gold_not_retained_in_inputs(self):
        raw = dict(guid="g", title="T", content="Body", actors=[{"Name": "a"}],
                   subevents=[dict(id="event-X", subevent="Event", explanation="SECRET")],
                   article_human_values=["SECRET"], explanation="SECRET")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text(json.dumps([raw]))
            b = bags(load_articles(p))[0]
            self.assertNotIn("SECRET", json.dumps(b.as_input()))
            self.assertNotIn("SECRET", render(b)[0])

    def test_gold_missing_rows_and_unidentified_empty_explicit(self):
        a = Article("g", "T", "Body", (("a", "A"),), (Event("x", "E"),))
        raw = [dict(guid="g", article_human_values=[], subevents_human_values=[dict(subevent_id="", subevent_human_values=[])])]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "gold.json"; p.write_text(json.dumps(raw))
            gold, stats = load_supervision(p, (a,), self.mapping)
            self.assertEqual(gold[("g", "a")]["children"], [[]])
            self.assertEqual(stats["unidentified_empty_rows"], 1)
            self.assertEqual(stats["missing_addressed_event_rows"], 1)
            raw[0]["subevents_human_values"][0]["subevent_id"] = "wrong"
            p.write_text(json.dumps(raw))
            with self.assertRaises(ValueError): load_supervision(p, (a,), self.mapping)

    def test_export_both_directions_coarse_dedup_empty_and_coverage(self):
        a = Article("g", "T", "Body", (("a", "A"),), (Event("x", "X"), Event("y", "Y")))
        scores = {("g", "a", s): [0.] * 108 for s in ("x", "y")}
        scores[("g", "a", "x")][:2] = [.8, .9]
        result = export_predictions((a,), scores, self.mapping, .5)
        self.assertEqual(len(result["task2b"][0]["subevents_human_values"][0]["subevent_human_values"]), 2)
        self.assertEqual(result["task2b"][0]["subevents_human_values"][1]["subevent_human_values"], [])
        self.assertEqual(result["task2a"][0]["subevents_human_values"][0]["subevent_human_values"], [dict(actor="a", l2_value=self.mapping["0"])])
        del scores[("g", "a", "y")]
        with self.assertRaises(ValueError): export_predictions((a,), scores, self.mapping, .5)

    def test_label_index_range(self):
        self.assertEqual((label_index("0", "0"), label_index("53", "1")), (0, 107))
        with self.assertRaises(ValueError): label_index("54", "1")

    def test_export_extra_candidate_or_nonfinite_score_rejected(self):
        a = Article("g", "T", "Body", (("a", "A"),), (Event("x", "X"),))
        scores = {("g", "a", "x"): [0.] * 108, ("extra", "a", "x"): [0.] * 108}
        with self.assertRaises(ValueError): export_predictions((a,), scores, self.mapping, .5)
        del scores[("extra", "a", "x")]
        scores[("g", "a", "x")][0] = float("nan")
        with self.assertRaises(ValueError): export_predictions((a,), scores, self.mapping, .5)


class TokenAndModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lock = load_json(PACKAGE / "tokenizer_lock.json")
        cls.directory = PROJECT / ".cache/task2_scope_local_v1/tokenizer" / lock["revision"]
        cls.tokenizer = BagTokenizer(cls.directory, lock)
        cls.bags = (Bag("g", "a", "Alice", "Alice helps.\n她帮助了别人。", (Event("x", "Help!"), Event("y", "Refused."))),
                    Bag("h", "b", "Bob", "A short body.", (Event("z", "Event."),)))

    def test_spans_masks_padding_and_gold_separation(self):
        encoded = [self.tokenizer.encode(b) for b in self.bags]
        batch, targets = collate(encoded, self.tokenizer.pad_id)
        self.assertEqual(set(batch), {"input_ids", "attention_mask", "scope_masks"})
        self.assertEqual(targets["child_mask"].tolist(), [[True, True], [True, False]])
        self.assertFalse((batch["scope_masks"] & ~batch["attention_mask"].unsqueeze(1)).any())
        self.assertTrue((batch["scope_masks"].sum(1) <= 1).all())
        self.assertFalse(batch["scope_masks"][:, :, 0].any())  # CLS excluded

    def test_overlength_explicit_never_truncated(self):
        b = Bag("long", "a", "Alice", "word " * 9000, (Event("x", "Last event is retained"),))
        with self.assertRaisesRegex(ValueError, "no truncation"):
            self.tokenizer.encode(b)
        encoded = self.tokenizer.encode(b, audit_overlength=True)
        self.assertGreater(len(encoded.input_ids), 8192)
        self.assertTrue(encoded.scope_indices[-1])

    def test_pooling_excludes_padding_and_zero_padded_scope(self):
        hidden = torch.tensor([[[1., 3.], [3., 5.], [float("nan"), float("nan")]]], requires_grad=True)
        masks = torch.tensor([[[True, True, False], [False, False, False]]])
        result = masked_mean(hidden, masks)
        torch.testing.assert_close(result, torch.tensor([[[2., 4.], [0., 0.]]]))
        result.sum().backward()
        torch.testing.assert_close(hidden.grad[0, 2], torch.zeros(2))

    def test_cpu_shared_head_js_forward_backward(self):
        class TinyEncoder(nn.Module):
            def __init__(self):
                super().__init__(); self.embedding = nn.Embedding(512, 8)
            def forward(self, input_ids, attention_mask):
                return SimpleNamespace(last_hidden_state=self.embedding(input_ids % 512))
        torch.manual_seed(11)
        base = ScopeModel(TinyEncoder(), 8)
        encoded = [self.tokenizer.encode(b) for b in self.bags]
        gold = {b.key: dict(article=[0, 1], children=[[0, 1]] + [[] for _ in b.events[1:]], event_ids=[e.id for e in b.events]) for b in self.bags}
        batch, targets = collate(encoded, self.tokenizer.pad_id, gold)
        outputs = []
        for mode in ("J", "S"):
            model = copy.deepcopy(base)
            a, c = model(**batch)
            outputs.append((a.detach(), c.detach()))
            self.assertEqual(a.shape, (2, 108)); self.assertEqual(c.shape, (2, 2, 108))
            result = scope_loss(a, c, mode=mode, **targets)
            result["loss"].backward()
            self.assertTrue(torch.isfinite(result["loss"]))
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
            self.assertGreater(model.head.weight.grad.abs().sum().item(), 0)
        for j, s in zip(*outputs): torch.testing.assert_close(j, s)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
