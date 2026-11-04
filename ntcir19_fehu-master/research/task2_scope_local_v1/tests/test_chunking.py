import copy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import torch
from torch import nn

from research.task2_scope_local_v1.chunking import from_cache, make_windows, token_breakdown, validate_windows
from research.task2_scope_local_v1.chunk_model import ChunkedScopeModel, bag_targets, final_probabilities
from research.task2_scope_local_v1.data import Bag, Event, Article, bags, load_articles, load_json, taxonomy
from research.task2_scope_local_v1.losses import scope_loss
from research.task2_scope_local_v1.model import ScopeModel
from research.task2_scope_local_v1.predictions import export_predictions
from research.task2_scope_local_v1.tokenization import BagTokenizer, EncodedBag, collate

PROJECT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]


def example(body=9, events=2):
    # Two-token prefix, body, then one token per event and SEP.
    ids = tuple(range(body + events + 3))
    return EncodedBag((f"g{body}", "a"), tuple(str(i) for i in range(events)), ids,
                      (tuple(range(2, body + 2)),) + tuple((body + 2 + i,) for i in range(events)))


class IdentityEncoder(nn.Module):
    def forward(self, input_ids, attention_mask):
        x = input_ids.float()
        return SimpleNamespace(last_hidden_state=torch.stack([x, x.square()], -1))


class TrainableEncoder(nn.Module):
    def __init__(self):
        super().__init__(); self.embedding = nn.Embedding(128, 6)
    def forward(self, input_ids, attention_mask):
        return SimpleNamespace(last_hidden_state=self.embedding(input_ids % 128))


class WindowTests(unittest.TestCase):
    def test_capacity_and_boundaries_cover_once(self):
        for n in (1, 5, 6, 7, 9, 17, 21):
            for overlap in (0, 1, 3):
                enc = example(n)
                p = make_windows(enc, max_length=11, overlap=overlap)  # body capacity 6
                result = validate_windows(p, max_length=11)
                self.assertEqual(sum(result["owned_body_counts"]), n)
                self.assertTrue(all(len(w.input_ids) <= 11 for w in p.windows))
                self.assertEqual(p.windows[-1].body_end, n)
                for w in p.windows:
                    self.assertEqual(tuple(w.source_indices[i] for i in w.scope_indices[-1]), enc.scope_indices[-1])

    def test_one_window_identical_to_original(self):
        enc = example(5)
        p = make_windows(enc, max_length=11, overlap=3)
        self.assertEqual(p.windows[0].input_ids, enc.input_ids)
        self.assertEqual(p.windows[0].scope_indices, enc.scope_indices)

    def test_context_overflow_and_bad_overlap_fail_loudly(self):
        for cap, overlap in [(5, 0), (11, 6), (11, -1)]:
            with self.assertRaises(ValueError): make_windows(example(20), max_length=cap, overlap=overlap)

    def test_duplicate_ownership_missing_event_and_wrong_tokens_rejected(self):
        p = make_windows(example(), max_length=11, overlap=2)
        w = p.windows[-1]
        changes = [replace(w, scope_indices=(w.scope_indices[0][1:],) + w.scope_indices[1:]),
                   replace(w, scope_indices=w.scope_indices[:-1]),
                   replace(w, input_ids=(999,) + w.input_ids[1:])]
        for changed in changes:
            with self.assertRaises(ValueError): validate_windows(replace(p, windows=p.windows[:-1] + (changed,)), max_length=11)

    def test_cache_roundtrip_exact_and_deterministic(self):
        p = make_windows(example(20), max_length=11, overlap=2)
        q = from_cache(json.loads(json.dumps(p.as_cache())))
        self.assertEqual(p, q)
        self.assertEqual(p, make_windows(example(20), max_length=11, overlap=2))


class AggregateTests(unittest.TestCase):
    def test_identity_encoder_matches_full_input_for_any_overlap(self):
        torch.manual_seed(11)
        full = ScopeModel(IdentityEncoder(), 2)
        chunked = ChunkedScopeModel(IdentityEncoder(), 2)
        chunked.load_state_dict(full.state_dict())
        enc = example(20)
        batch, _ = collate([enc], 127)
        expected = full(**batch)
        for overlap in (0, 2, 4):
            actual = chunked([make_windows(enc, max_length=11, overlap=overlap)])
            for a, e in zip(actual, expected): torch.testing.assert_close(a, e, rtol=1e-5, atol=2e-5)

    def test_context_dependent_event_weight_uses_owned_body_not_window_count(self):
        class ContextEncoder(nn.Module):
            def forward(self, input_ids, attention_mask):
                value = input_ids.float().sum(1, keepdim=True)
                return SimpleNamespace(last_hidden_state=value.unsqueeze(-1).expand(-1, input_ids.shape[1], 1))
        model = ChunkedScopeModel(ContextEncoder(), 1, num_labels=1)
        with torch.no_grad(): model.head.weight.fill_(1); model.head.bias.fill_(3)
        plan = make_windows(example(9), max_length=11, overlap=2)
        a, c = model([plan])
        expected = sum(sum(w.input_ids) * w.owned_count / 9 for w in plan.windows) + 3
        self.assertAlmostEqual(a.item(), expected, places=5)
        torch.testing.assert_close(c, torch.full_like(c, expected))

    def test_loss_and_gradients_invariant_to_windows_for_context_free_encoder(self):
        torch.manual_seed(11)
        base = ChunkedScopeModel(TrainableEncoder(), 6)
        enc = example(20)
        gold = {enc.key: dict(article=[0, 1, 5], children=[[0, 1], []], event_ids=list(enc.event_ids))}
        for mode in ("J", "S"):
            values, grads = [], []
            for cap in (100, 11):
                model = copy.deepcopy(base)
                plan = make_windows(enc, max_length=cap, overlap=2)
                a, c = model([plan]); targets = bag_targets([plan], gold)
                result = scope_loss(a, c, mode=mode, **targets)
                result["loss"].backward()
                values.append(result["loss"]); grads.append([p.grad for p in model.parameters()])
            torch.testing.assert_close(*values)
            for a, b in zip(*grads): torch.testing.assert_close(a, b, atol=2e-7, rtol=1e-4)

    def test_bag_target_count_and_mixed_event_padding(self):
        plans = [make_windows(example(20, 3), max_length=12, overlap=2), make_windows(example(3, 1), max_length=12, overlap=2)]
        gold = {p.key: dict(article=[2], children=[[] for _ in p.event_ids], event_ids=list(p.event_ids)) for p in plans}
        targets = bag_targets(plans, gold)
        self.assertEqual(targets["article_targets"].sum().item(), 2)
        self.assertEqual(targets["child_mask"].sum().item(), 4)
        self.assertEqual(targets["child_mask"].tolist(), [[True, True, True], [True, False, False]])
        model = ChunkedScopeModel(TrainableEncoder(), 6)
        a, c = model(plans)
        for mode in ("J", "S"):
            full = scope_loss(a, c, mode=mode, **targets)["loss"]
            individual = []
            for i, p in enumerate(plans):
                individual.append(scope_loss(a[i:i+1], c[i:i+1, :len(p.event_ids)], mode=mode, **bag_targets([p], gold))["loss"])
            torch.testing.assert_close(full, torch.stack(individual).mean())

    def test_checkpoint_recomputation_preserves_gradients(self):
        torch.manual_seed(11)
        base = ChunkedScopeModel(TrainableEncoder(), 6)
        plan = make_windows(example(20), max_length=11, overlap=2)
        results = []
        for use_checkpoint in (False, True):
            model = copy.deepcopy(base); model.checkpoint_windows = use_checkpoint
            a, c = model([plan]); (a.square().mean() + c.square().mean()).backward()
            results.append([p.grad for p in model.parameters()])
        for a, b in zip(*results): torch.testing.assert_close(a, b)

    def test_p_multiplies_only_final_original_bag_probabilities(self):
        a = torch.tensor([[2., -3.]])
        c = torch.tensor([[[1., 4.], [-1., -4.]]])
        torch.testing.assert_close(final_probabilities(a, c, "P"), a.sigmoid()[:, None, :] * c.sigmoid())
        torch.testing.assert_close(final_probabilities(a, c, "J"), final_probabilities(a, c, "S"))

    def test_article_only_gradient_after_aggregation(self):
        plan = make_windows(example(20), max_length=11, overlap=2)
        a = torch.full((1, 108), -1., requires_grad=True)
        c = torch.full((1, 2, 108), 5., requires_grad=True)
        gold = {plan.key: dict(article=[0], children=[[], []], event_ids=list(plan.event_ids))}
        # Isolate the article-only label: it must not promote either child logit.
        target = bag_targets([plan], gold)
        r = scope_loss(a, c, mode="S", **target)
        r["article_loss"].backward()
        self.assertLess(a.grad[0, 0].item(), 0)
        self.assertEqual(c.grad[0, :, 0].abs().sum().item(), 0)


class MappingAndGradientTests(unittest.TestCase):
    def test_all_official_mapping_values_and_both_directions_roundtrip(self):
        tax = PROJECT / "dataset/hv_categories"
        fine, coarse = load_json(tax / "human_value_level1_values.json"), load_json(tax / "human_value_level2_values.json")
        inverse = load_json(tax / "level_2_to_level_1.json")["level_2_to_level_1"]
        expected = {fine[name]: coarse[parent] for parent, names in inverse.items() for name in names}
        self.assertEqual(taxonomy(tax), expected)
        self.assertEqual(load_json(tax / "direction_mapping.json"), {"aligned": "1", "contradictory": "0"})
        spec = importlib.util.spec_from_file_location("frozen_official", PROJECT / "research/task2_prompt_baseline_v1/evaluator/official_cli.py")
        official = importlib.util.module_from_spec(spec); spec.loader.exec_module(official)
        article = Article("g", "T", "Body", (("a", "A"),), tuple(Event(str(i), "E") for i in range(54)))
        scores = {}
        for i in range(54):
            scores[("g", "a", str(i))] = [float(k in {2*i, 2*i+1}) for k in range(108)]
        result = export_predictions((article,), scores, taxonomy(tax), .5)
        with tempfile.TemporaryDirectory() as tmp:
            pa, pb = Path(tmp)/"a.json", Path(tmp)/"b.json"
            pa.write_text(json.dumps(result["task2a"])); pb.write_text(json.dumps(result["task2b"]))
            a, b = official.parse_task2a(str(pa)), official.parse_task2b(str(pb))
        self.assertEqual(a, {("g",str(i),"a"): {expected[str(i)]} for i in range(54)})
        self.assertEqual(b, {("g",str(i),"a"): {f"0:{i}", f"1:{i}"} for i in range(54)})

    def test_empty_labels_all_cells_and_padding_gradient(self):
        a = torch.zeros(2, 108, requires_grad=True)
        c = torch.tensor([1., 2., 100., 3., 200., 300.]).reshape(2, 3, 1).expand(-1, -1, 108).clone().requires_grad_()
        mask = torch.tensor([[True, True, False], [True, False, False]])
        for mode in ("J", "S"):
            result = scope_loss(a, c, torch.zeros_like(a), torch.zeros_like(c), mask, mode)
            grad = torch.autograd.grad(result["event_loss"], c, retain_graph=True)[0]
            expected = c.sigmoid() / (mask.sum(1)[:, None, None] * 108 * 2)
            expected = expected * mask[:, :, None]
            torch.testing.assert_close(grad, expected)
            total = torch.autograd.grad(result["loss"], c, retain_graph=True)[0]
            self.assertTrue((total[mask] > 0).all())
            self.assertEqual(total[~mask].abs().sum().item(), 0)


class RealTokenizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lock = load_json(PACKAGE / "tokenizer_lock.json")
        cls.tokenizer = BagTokenizer(PROJECT / ".cache/task2_scope_local_v1/tokenizer" / lock["revision"], lock)

    def test_real_long_fit_bag_accounting_and_final_event_retained(self):
        bag = next(b for b in bags(load_articles(PROJECT / "dataset/train/train_event_base.json")) if b.guid == "33-2677-7-t")
        enc = self.tokenizer.encode(bag, audit_overlength=True)
        counts = token_breakdown(bag, self.tokenizer, enc)
        self.assertEqual(counts["categories"], dict(body=9249,event_text=288,event_list_markers=77,actor_article_header=25,model_special=2))
        plan = make_windows(enc)
        self.assertEqual([len(w.input_ids) for w in plan.windows], [8192, 2097])
        self.assertEqual([w.owned_count for w in plan.windows], [7800, 1449])
        self.assertEqual(plan.event_ids, tuple(str(i) for i in range(9)))
        for w in plan.windows:
            self.assertEqual([w.input_ids[i] for i in w.scope_indices[-1]], [enc.input_ids[i] for i in enc.scope_indices[-1]])

    def test_unicode_offsets_survive_small_windows(self):
        b = Bag("g", "a", "名", "你好。Café helps 👩🏽‍🔬. " * 30, (Event("not-numeric", "最后事件！"),))
        enc = self.tokenizer.encode(b)
        plan = make_windows(enc, max_length=100, overlap=8)
        validate_windows(plan, max_length=100)
        for w in plan.windows:
            self.assertEqual(tuple(w.source_indices[i] for i in w.scope_indices[-1]), enc.scope_indices[-1])

    def test_tiny_modernbert_cpu_interface_forward_backward(self):
        from transformers import ModernBertConfig, ModernBertModel
        config = ModernBertConfig(vocab_size=128, hidden_size=16, intermediate_size=32,
            num_hidden_layers=2, num_attention_heads=2, max_position_embeddings=32,
            local_attention=8, pad_token_id=127, cls_token_id=0, sep_token_id=1,
            attention_dropout=0., embedding_dropout=0., mlp_dropout=0.)
        config._attn_implementation = "eager"
        model = ChunkedScopeModel(ModernBertModel(config), 16, checkpoint_windows=True)
        plan = make_windows(example(20), max_length=11, overlap=2)
        gold = {plan.key: dict(article=[0],children=[[0],[]],event_ids=list(plan.event_ids))}
        a,c = model([plan]); r = scope_loss(a,c,mode="S",**bag_targets([plan],gold))
        r["loss"].backward()
        self.assertTrue(torch.isfinite(r["loss"]))
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
