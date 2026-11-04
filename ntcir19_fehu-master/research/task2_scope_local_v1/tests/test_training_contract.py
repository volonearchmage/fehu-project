from pathlib import Path
import unittest
from unittest.mock import patch

import torch

from research.task2_scope_local_v1.train import accumulation_groups, better_checkpoint, choose_threshold, cuda_gate, epoch_order


class TrainingContractTests(unittest.TestCase):
    def test_tail_accumulation_has_equal_original_bag_weight(self):
        order = list(range(19))
        groups = accumulation_groups(order, 16)
        self.assertEqual(list(map(len, groups)), [16, 3])
        for group in groups:
            x = torch.tensor(1., requires_grad=True)
            values = [x * (i + 1) for i in group]
            gradient = sum(torch.autograd.grad(v / len(group), x, retain_graph=True)[0] for v in values)
            self.assertAlmostEqual(gradient.item(), sum(i+1 for i in group) / len(group), places=5)

    def test_js_order_identical_but_each_epoch_deterministic(self):
        self.assertEqual(epoch_order(100, 1), epoch_order(100, 1))
        self.assertEqual(sorted(epoch_order(100, 1)), list(range(100)))
        self.assertNotEqual(epoch_order(100, 1), epoch_order(100, 2))

    def test_threshold_tie_higher_and_checkpoint_tie_earlier(self):
        result = choose_threshold(torch.tensor([[.9, .1]]), torch.tensor([[1., 0.]]))
        self.assertEqual(result["threshold"], .9)
        self.assertEqual(result["micro_f1"], 1.)
        self.assertFalse(better_checkpoint(dict(result,epoch=2), dict(result,epoch=1)))
        self.assertTrue(better_checkpoint(dict(result,epoch=1), dict(result,epoch=2)))

    def test_missing_weights_or_receipt_blocks_before_gpu_probe(self):
        with patch("torch.cuda.is_available", side_effect=AssertionError("No GPU access permitted in CPU tests")):
            with self.assertRaisesRegex(RuntimeError, "weights"):
                cuda_gate(None, dict(missing_model_files=["absent.safetensors"]))
            with self.assertRaisesRegex(RuntimeError, "receipt"):
                cuda_gate(Path("/nonexistent-fehu-receipt"), dict(missing_model_files=[]))


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
