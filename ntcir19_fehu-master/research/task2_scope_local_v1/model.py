"""Shared span head, accepting any encoder with last_hidden_state."""
import torch
from torch import nn


def masked_mean(hidden, masks):
    # [B,L,H], [B,S,L]. Empty padded scopes return zero, never NaN.
    if hidden.ndim != 3 or masks.ndim != 3 or masks.dtype != torch.bool or hidden.shape[:2] != (masks.shape[0], masks.shape[2]):
        raise ValueError("Pooling shape/mask mismatch")
    # Avoid the [B,S,L,H] expansion (large for 8192-token bags).
    active = masks.any(1).unsqueeze(-1)
    safe_hidden = torch.where(active, hidden, 0.)
    weights = masks.to(hidden.dtype)
    return torch.bmm(weights, safe_hidden) / weights.sum(-1, keepdim=True).clamp_min(1)


class ScopeModel(nn.Module):
    def __init__(self, encoder, hidden_size, num_labels=108):
        super().__init__()
        self.encoder = encoder
        self.head = nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask, scope_masks):
        if scope_masks.shape[1] < 1 or (scope_masks & ~attention_mask.bool().unsqueeze(1)).any():
            raise ValueError("Invalid/padded scope token")
        hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        logits = self.head(masked_mean(hidden, scope_masks))
        return logits[:, 0], logits[:, 1:]
