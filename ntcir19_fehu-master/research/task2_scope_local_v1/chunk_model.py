"""Aggregate windows before applying the shared head or any supervision."""
import torch
from torch.nn.utils.rnn import pad_sequence
from torch.utils.checkpoint import checkpoint

from .model import ScopeModel, masked_mean


class ChunkedScopeModel(ScopeModel):
    def __init__(self, encoder, hidden_size, num_labels=108, checkpoint_windows=False):
        super().__init__(encoder, hidden_size, num_labels)
        self.checkpoint_windows = checkpoint_windows

    def _pool(self, ids, attention, scopes):
        hidden = self.encoder(input_ids=ids, attention_mask=attention).last_hidden_state
        return masked_mean(hidden.float(), scopes)[0]

    def forward_bag(self, plan):
        device = self.head.weight.device
        body_count = len(plan.original.scope_indices[0])
        aggregate = None
        for window in plan.windows:
            ids = torch.tensor([window.input_ids], dtype=torch.long, device=device)
            attention = torch.ones_like(ids, dtype=torch.bool)
            scopes = torch.zeros((1, len(window.scope_indices), ids.shape[1]), dtype=torch.bool, device=device)
            for i, indices in enumerate(window.scope_indices):
                scopes[0, i, list(indices)] = True
            if self.checkpoint_windows and self.training and torch.is_grad_enabled():
                pooled = checkpoint(self._pool, ids, attention, scopes, use_reentrant=False, preserve_rng_state=True)
            else:
                pooled = self._pool(ids, attention, scopes)
            weighted = pooled * (window.owned_count / body_count)
            aggregate = weighted if aggregate is None else aggregate + weighted
        # Linear bias is applied once after aggregation. No per-window loss.
        logits = self.head(aggregate)
        return logits[0], logits[1:]

    def forward(self, plans):
        if not plans:
            raise ValueError("Empty bag batch")
        outputs = [self.forward_bag(plan) for plan in plans]
        return torch.stack([a for a, _ in outputs]), pad_sequence([c for _, c in outputs], batch_first=True)


def bag_targets(plans, supervision=None, *, device="cpu"):
    """Original bags are the batch dimension; windows never duplicate labels."""
    if not plans:
        raise ValueError("Empty bag batch")
    count = max(len(p.event_ids) for p in plans)
    mask = torch.zeros((len(plans), count), dtype=torch.bool, device=device)
    article = torch.zeros((len(plans), 108), device=device)
    children = torch.zeros((len(plans), count, 108), device=device)
    for i, p in enumerate(plans):
        mask[i, :len(p.event_ids)] = True
        if supervision is None:
            continue
        gold = supervision[p.key]
        if tuple(gold["event_ids"]) != p.event_ids or len(gold["children"]) != len(p.event_ids):
            raise ValueError("Bag supervision order/count mismatch")
        for indices in [gold["article"], *gold["children"]]:
            if len(indices) != len(set(indices)) or any(type(k) is not int or not 0 <= k < 108 for k in indices):
                raise ValueError("Invalid/duplicate directed target")
        article[i, gold["article"]] = 1
        for j, indices in enumerate(gold["children"]):
            children[i, j, indices] = 1
    result = {"child_mask": mask}
    if supervision is not None:
        result.update(article_targets=article, child_targets=children)
    return result


def final_probabilities(article_logits, child_logits, method="J"):
    if method not in {"J", "S", "P"}:
        raise ValueError("Unknown scoring method")
    p = child_logits.float().sigmoid()
    return p * article_logits.float().sigmoid().unsqueeze(-2) if method == "P" else p
