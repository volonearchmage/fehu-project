"""J/S differ only in the article term; gold is never an encoder input."""
import math
import torch
import torch.nn.functional as F


def scope_loss(article_logits, child_logits, article_targets, child_targets,
               child_mask, mode="J", article_weight=1.0):
    """Each bag contributes once; event BCE normalized by valid events * labels.

    S positive uses max(article, gold-positive valid children), S negative uses
    max(article, all valid children). Monotonic sigmoid gives the stable logit
    equivalent of the probability-space rule. Empty bags have zero event loss.
    """
    if mode not in {"J", "S"} or not math.isfinite(article_weight) or article_weight < 0:
        raise ValueError("Invalid loss configuration")
    if article_logits.ndim != 2 or child_logits.ndim != 3 or 0 in article_logits.shape:
        raise ValueError("Expected nonempty [B,C] and [B,M,C]")
    if (article_targets.shape != article_logits.shape or child_targets.shape != child_logits.shape
            or child_mask.shape != child_logits.shape[:2] or child_mask.dtype != torch.bool
            or (child_logits.shape[0], child_logits.shape[2]) != article_logits.shape):
        raise ValueError("Loss shape/mask mismatch")
    valid = child_mask.unsqueeze(-1)
    # Keep BCE reductions finite under future autocast as well as CPU fp32.
    if article_logits.dtype in {torch.float16, torch.bfloat16}:
        article_logits = article_logits.float()
        child_logits = child_logits.float()
        article_targets = article_targets.float()
        child_targets = child_targets.float()
    # Mask before BCE/max: padding may contain NaN and must have zero gradient.
    c = torch.where(valid, child_logits, 0.)
    y = torch.where(valid, child_targets, 0.)
    a, ya = article_logits, article_targets
    if not all(torch.isfinite(x).all() for x in (a, c, ya, y)):
        raise ValueError("Nonfinite active logit/target")
    if not all(((x == 0) | (x == 1)).all() for x in (ya, y)):
        raise ValueError("Targets must be binary")
    event_cell_loss = F.binary_cross_entropy_with_logits(c, y, reduction="none")
    event_per_bag = torch.where(valid, event_cell_loss, 0.).sum((1, 2)) / (child_mask.sum(1).clamp_min(1) * a.shape[1])
    if mode == "J":
        article_per_bag = F.binary_cross_entropy_with_logits(a, ya, reduction="none").mean(1)
    else:
        all_children = c.masked_fill(~valid, -torch.inf)
        positive_children = c.masked_fill(~(valid & (y == 1)), -torch.inf)
        up = torch.cat([a.unsqueeze(1), all_children], dim=1).amax(1)
        pos = torch.cat([a.unsqueeze(1), positive_children], dim=1).amax(1)
        article_per_bag = torch.where(ya == 1, F.softplus(-pos), F.softplus(up)).mean(1)
    event_loss, article_loss = event_per_bag.mean(), article_per_bag.mean()
    return {"loss": event_loss + article_weight * article_loss,
            "event_loss": event_loss, "article_loss": article_loss}
